"""Agent initialization from audio — ASR transcription + LLM SOP extraction.

Orchestrates:
  1. DashScope File Transcription API (submit → poll → fetch)
  2. LLM analysis via AIHubMix (OpenAI-compatible)
  3. SSE event stream for real-time frontend feedback
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import AsyncIterator

import httpx
import openai

from backend.services.prompts.sop_extraction import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    REPAIR_PROMPT,
)

logger = logging.getLogger("kodama.audio_init")

# DashScope File Transcription API
DASHSCOPE_TRANSCRIPTION_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
DASHSCOPE_TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

# Limits
POLL_INTERVAL = 2  # seconds
POLL_TIMEOUT = 180  # seconds


def _sse(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ─── DashScope File Transcription ───────────────────────────


async def transcribe_audio(
    file_path: Path,
    api_key: str,
    file_url: str | None = None,
) -> dict:
    """Transcribe audio file via DashScope File Transcription API.

    Returns: {"text": "full transcript", "turns": [{"speaker": "A", "text": "..."}]}
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Build request — use file_url if provided, otherwise try direct upload
    request_body = {
        "model": "paraformer-v2",
        "input": {},
        "parameters": {
            "diarization_enabled": True,
            "speaker_count": 2,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        if file_url:
            request_body["input"]["file_urls"] = [file_url]
        else:
            # Upload file directly via multipart, then use the returned URL
            # DashScope supports file upload via their upload endpoint
            upload_url = "https://dashscope.aliyuncs.com/api/v1/uploads"
            with open(file_path, "rb") as f:
                upload_resp = await client.post(
                    upload_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (file_path.name, f, "audio/mpeg")},
                )
            if upload_resp.status_code != 200:
                raise RuntimeError(f"File upload failed: {upload_resp.status_code} {upload_resp.text}")
            uploaded_url = upload_resp.json().get("data", {}).get("uploaded_file_url")
            if not uploaded_url:
                raise RuntimeError(f"No file URL in upload response: {upload_resp.text}")
            request_body["input"]["file_urls"] = [uploaded_url]

        # Submit transcription job
        resp = await client.post(
            DASHSCOPE_TRANSCRIPTION_URL,
            headers=headers,
            json=request_body,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Transcription submit failed: {resp.status_code} {resp.text}")

        result = resp.json()
        task_id = result.get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"No task_id in response: {result}")

        # Poll for completion
        start = time.time()
        while time.time() - start < POLL_TIMEOUT:
            await asyncio.sleep(POLL_INTERVAL)

            poll_resp = await client.get(
                DASHSCOPE_TASK_URL.format(task_id=task_id),
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if poll_resp.status_code != 200:
                continue

            poll_data = poll_resp.json()
            status = poll_data.get("output", {}).get("task_status", "")

            if status == "SUCCEEDED":
                return _parse_transcription_result(poll_data)
            elif status == "FAILED":
                msg = poll_data.get("output", {}).get("message", "Unknown error")
                raise RuntimeError(f"Transcription failed: {msg}")
            # PENDING / RUNNING — keep polling

        raise RuntimeError(f"Transcription timed out after {POLL_TIMEOUT}s")


def _parse_transcription_result(data: dict) -> dict:
    """Parse DashScope transcription result into our format."""
    output = data.get("output", {})
    results = output.get("results", [])

    turns = []
    full_text_parts = []

    for result in results:
        # Each result may contain a transcription_url or inline content
        transcript_url = result.get("transcription_url")
        if transcript_url:
            # Would need to fetch — for now handle inline
            pass

        # Handle inline sentence-level results
        sentences = result.get("sentences", [])
        for s in sentences:
            text = s.get("text", "")
            speaker = s.get("speaker_id", "unknown")
            if text.strip():
                turns.append({"speaker": f"Speaker_{speaker}", "text": text.strip()})
                full_text_parts.append(text.strip())

    # If no sentence-level data, try the top-level text
    if not turns:
        text = output.get("text", "")
        if text:
            full_text_parts = [text]
            # Split by common dialogue markers
            for line in text.split("\n"):
                line = line.strip()
                if line:
                    turns.append({"speaker": "unknown", "text": line})

    return {
        "text": "\n".join(full_text_parts),
        "turns": turns,
    }


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned


# ─── LLM SOP Extraction ────────────────────────────────────


async def analyze_transcript(
    transcript: str,
    api_key: str,
    base_url: str,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """Analyze conversation transcript with LLM to extract SOP structure.

    Returns parsed JSON dict with role, goal, task_chain, skills, rules, opening_line.
    """
    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    user_msg = USER_PROMPT_TEMPLATE.format(transcript=transcript)

    # First attempt
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=16000,  # Production-grade SOP output is large (system_prompt alone 1500-4000 chars)
    )

    raw = response.choices[0].message.content or ""

    # Try to parse JSON (strip possible markdown fences)
    cleaned = _strip_code_fences(raw)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"First JSON parse failed: {e}, attempting repair")

    # Retry with repair prompt
    repair_msg = REPAIR_PROMPT.format(error=str(e))
    response2 = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": raw},
            {"role": "user", "content": repair_msg},
        ],
        temperature=0.1,
        max_tokens=16000,
    )

    raw2 = response2.choices[0].message.content or ""
    cleaned2 = _strip_code_fences(raw2)

    return json.loads(cleaned2)  # Let it raise if still invalid


# ─── SSE Stream Orchestrator ───────────────────────────────


async def init_from_audio_stream(
    file_path: Path,
    dashscope_api_key: str,
    aihubmix_api_key: str,
    aihubmix_base_url: str,
    file_url: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> AsyncIterator[str]:
    """SSE async generator: transcribe audio → analyze → yield structured events."""

    yield _sse("progress", {"step": "uploading", "message": "文件已接收，准备转写..."})

    # Step 1: Transcribe
    try:
        yield _sse("progress", {"step": "transcribing", "message": "正在转写音频..."})
        transcript_data = await transcribe_audio(file_path, dashscope_api_key, file_url)
        yield _sse("transcript", transcript_data)
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        yield _sse("error", {"message": f"转写失败：{e}"})
        return

    transcript_text = transcript_data.get("text", "")
    if not transcript_text.strip():
        yield _sse("error", {"message": "转写结果为空，请检查音频文件质量"})
        return

    # Format turns for LLM analysis
    turns = transcript_data.get("turns", [])
    if turns:
        formatted = "\n".join(f"[{t['speaker']}]: {t['text']}" for t in turns)
    else:
        formatted = transcript_text

    # Step 2: LLM Analysis
    try:
        yield _sse("progress", {"step": "analyzing", "message": "正在分析对话结构..."})
        sop_data = await analyze_transcript(
            formatted, aihubmix_api_key, aihubmix_base_url, model
        )
        yield _sse("result", sop_data)
    except json.JSONDecodeError as e:
        logger.error(f"LLM output not valid JSON: {e}")
        yield _sse("error", {"message": f"分析结果格式错误，请重试"})
        return
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        yield _sse("error", {"message": f"分析失败：{e}"})
        return

    yield _sse("done", {})
