"""NLP adversarial conversation test — two LLMs in a turn-based dialogue.

One LLM runs the Agent prompt under test, the other simulates a user with
a given persona/scenario. An optional evaluator LLM scores the result.

All output is streamed as SSE events for real-time frontend display.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import openai

from backend.services.prompts.conversation_test import (
    AUTO_PERSONA_SYSTEM,
    EVALUATOR_SYSTEM,
    EVALUATOR_USER_TEMPLATE,
    SIMULATED_USER_SYSTEM,
)

logger = logging.getLogger("sumi.conversation_test")


def _sse(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned


async def _chat(
    client: openai.AsyncOpenAI,
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    """Single LLM call, return content string."""
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


async def _generate_persona(
    client: openai.AsyncOpenAI,
    model: str,
    scenario: str,
) -> str:
    """Auto-generate a user persona from the scenario description."""
    resp = await _chat(
        client, model,
        [{"role": "user", "content": AUTO_PERSONA_SYSTEM.format(scenario=scenario)}],
        temperature=0.8,
        max_tokens=200,
    )
    return resp


async def run_conversation_test(
    *,
    agent_system_prompt: str,
    agent_opening_line: str | None,
    scenario: str,
    persona: str,
    max_turns: int,
    api_key: str,
    base_url: str,
    model: str,
    evaluate: bool = True,
) -> AsyncIterator[str]:
    """SSE async generator: run a turn-based conversation test.

    Yields SSE events: config, turn, evaluation, done, error.
    """
    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    # Auto-generate persona if not provided
    if not persona.strip():
        try:
            persona = await _generate_persona(client, model, scenario)
        except Exception as e:
            logger.warning(f"Auto-persona generation failed: {e}")
            persona = "普通用户，对这个场景不太熟悉，会提一些基本问题。"

    yield _sse("config", {
        "scenario": scenario,
        "persona": persona,
        "max_turns": max_turns,
        "model": model,
        "evaluate": evaluate,
    })

    # Build simulated user system prompt
    sim_user_system = SIMULATED_USER_SYSTEM.format(
        scenario=scenario,
        persona=persona,
    )

    # Message histories (separate for each LLM)
    agent_messages: list[dict] = [
        {"role": "system", "content": agent_system_prompt},
    ]
    user_messages: list[dict] = [
        {"role": "system", "content": sim_user_system},
    ]

    # Track full conversation for evaluation
    conversation_log: list[dict] = []
    turn_count = 0

    # Turn 1: Agent opening line
    if agent_opening_line and agent_opening_line.strip():
        agent_reply = agent_opening_line.strip()
    else:
        # Generate opening from Agent LLM
        try:
            agent_messages.append({"role": "user", "content": "（用户接听了电话 / 进入了对话）"})
            agent_reply = await _chat(client, model, agent_messages)
            # Replace the placeholder with the actual exchange
            agent_messages[-1] = {"role": "user", "content": "（对话开始）"}
            agent_messages.append({"role": "assistant", "content": agent_reply})
        except Exception as e:
            logger.error(f"Agent opening failed: {e}")
            yield _sse("error", {"message": f"Agent 开场白生成失败: {e}"})
            return

    turn_count += 1
    conversation_log.append({"role": "agent", "content": agent_reply, "turn": turn_count})
    yield _sse("turn", {"role": "agent", "content": agent_reply, "turn": turn_count})

    # If we used the opening line directly, seed agent_messages properly
    if agent_opening_line and agent_opening_line.strip():
        agent_messages.append({"role": "assistant", "content": agent_reply})

    # Conversation loop
    while turn_count < max_turns:
        # --- Simulated user turn ---
        # Add agent's last message as "assistant" in user's perspective
        user_messages.append({"role": "user", "content": agent_reply})

        try:
            user_reply = await _chat(client, model, user_messages, temperature=0.8)
        except Exception as e:
            logger.error(f"Simulated user generation failed at turn {turn_count + 1}: {e}")
            yield _sse("error", {"message": f"模拟用户回复生成失败 (Round {turn_count + 1}): {e}"})
            return

        user_messages.append({"role": "assistant", "content": user_reply})

        # Check for [END] signal
        clean_user_reply = user_reply.replace("[END]", "").strip()
        has_end_signal = "[END]" in user_reply

        turn_count += 1
        conversation_log.append({"role": "user", "content": clean_user_reply, "turn": turn_count})
        yield _sse("turn", {"role": "user", "content": clean_user_reply, "turn": turn_count})

        if has_end_signal:
            break

        if turn_count >= max_turns:
            break

        # --- Agent turn ---
        agent_messages.append({"role": "user", "content": clean_user_reply})

        try:
            agent_reply = await _chat(client, model, agent_messages, temperature=0.5, max_tokens=800)
        except Exception as e:
            logger.error(f"Agent generation failed at turn {turn_count + 1}: {e}")
            yield _sse("error", {"message": f"Agent 回复生成失败 (Round {turn_count + 1}): {e}"})
            return

        agent_messages.append({"role": "assistant", "content": agent_reply})

        turn_count += 1
        conversation_log.append({"role": "agent", "content": agent_reply, "turn": turn_count})
        yield _sse("turn", {"role": "agent", "content": agent_reply, "turn": turn_count})

    # --- Evaluation ---
    if evaluate:
        yield _sse("progress", {"step": "evaluating", "message": "正在评估对话质量..."})

        # Format conversation for evaluator
        conv_text = "\n".join(
            f"[{'Agent' if t['role'] == 'agent' else '用户'}] (Round {t['turn']}): {t['content']}"
            for t in conversation_log
        )

        eval_user_msg = EVALUATOR_USER_TEMPLATE.format(
            system_prompt=agent_system_prompt[:3000],  # Truncate if very long
            conversation=conv_text,
        )

        try:
            eval_raw = await _chat(
                client, model,
                [
                    {"role": "system", "content": EVALUATOR_SYSTEM},
                    {"role": "user", "content": eval_user_msg},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            eval_json = json.loads(_strip_code_fences(eval_raw))
            yield _sse("evaluation", eval_json)
        except json.JSONDecodeError as e:
            logger.warning(f"Evaluation JSON parse failed: {e}")
            yield _sse("error", {"message": "评估结果格式错误，但对话已完成"})
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            yield _sse("error", {"message": f"评估失败: {e}，但对话已完成"})

    yield _sse("done", {"total_turns": turn_count})
