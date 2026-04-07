# Sumi.web Voice AI Platform Optimization Plan

## Executive Summary

Five workstreams addressing latency optimization, memory enhancement, annotation/testing, skill tracking, and the function-calling vs ReAct question. Organized into 3 phases: latency-critical first, then mid-conversation memory + annotation, then skill system refinement.

---

## Phase 1: Latency Optimization & Function Calling Strategy (Week 1-2)

### 1A. ReAct vs Function Calling Decision

**Recommendation: Keep function calling. Do NOT switch to ReAct for voice.**

Rationale:
- ReAct requires multiple LLM round-trips per action (Thought > Action > Observation > Thought...). Each round-trip adds ~300-800ms of LLM TTFB. For voice, this is catastrophic.
- LiveKit Agents v1.5 already has excellent function-calling support: streaming tool calls, parallel execution, max 3 tool steps.
- Qwen 2.5-72B via OpenAI-compatible API supports native function calling. No reason to hand-roll a ReAct loop.
- ReAct's "thinking out loud" pattern is anti-voice -- users hear nothing while the model reasons internally.

**What to do instead**: Optimize the existing function-calling path with filler words, speculative execution, and pipeline overlap.

### 1B. E2E Latency Reduction

**Current E2E: ~1500-2000ms (VAD end > first audio)**

Breakdown estimate:
- VAD silence detection: ~300ms (min_silence_duration=0.3)
- ASR final transcript: ~100-200ms (DashScope server VAD > final)
- LLM TTFB: ~400-800ms (Qwen 2.5-72B)
- TTS first audio: ~300-500ms (CosyVoice WebSocket setup + first chunk)

**Target: <800ms perceived latency**

#### 1B.1. Filler Word System

**New file: `backend/pipeline/filler.py`**

A FillerWordManager class that:
- Maintains pre-synthesized filler audio cache (嗯、好的、让我想想、稍等)
- Selects filler based on context: after user question -> "嗯，"; before tool call -> "让我查一下，"; long thinking -> "稍等一下，"
- Stores filler audio as pre-rendered PCM bytes at matching sample rate (22050Hz for CosyVoice)
- Exposes get_filler(context: str) -> bytes | None

**Modify: `backend/pipeline/worker.py`**

In entrypoint(), hook into the user_input_transcribed event to inject filler audio immediately after ASR final, before LLM starts processing. Use LiveKit's session.say() with allow_interruptions=True so the real response can override the filler.

The key hook point is between ASR final and LLM start. LiveKit v1.5 Agent class may support a before_llm_cb or similar; alternatively subclass Agent to intercept the turn pipeline.

#### 1B.2. VAD Tuning

**Modify: `backend/pipeline/worker.py` line 343**

Current min_silence_duration=0.3. Reduce to 0.25 and lower activation_threshold to 0.4 for faster detection.

**Modify: `backend/providers/asr/dashscope_realtime.py` line 39**

Current default silence_duration_ms=600. Reduce to 300 to match the local VAD timing and reduce the gap between speech end and ASR final.

#### 1B.3. TTS Connection Prewarming

**Modify: `backend/providers/tts/dashscope_cosyvoice.py`**

Current: CosyVoice opens a new WebSocket per synthesis stream. Handshake + run-task + task-started adds ~200-300ms.

Implement the prewarm() method (already part of LiveKit TTS interface, called at session start): pre-establish WebSocket, send run-task, cache the ready connection for the first stream() call. Subsequent calls reuse or create new connections.

#### 1B.4. Tool Call Acknowledgment

**Modify: `backend/pipeline/worker.py`**

For tool-calling turns, inject a verbal cue before tool execution: "让我帮你查一下". This fills the silence during tool execution. LiveKit v1.5's parallel execution already allows TTS to play while tools run -- ensure this is properly wired.

#### 1B.5. ASR Interim Speculative LLM (P2)

**New file: `backend/pipeline/speculative.py`**

SpeculativeLLMRunner class that starts LLM generation on interim ASR transcripts when they look complete (length > 8 chars and ends with punctuation). If final transcript matches interim, the speculative generation continues; otherwise cancel and restart.

Risk: higher compute cost, wasted LLM calls. Only enable for high-quality ASR where interim-to-final match rate is high.

| Technique | Estimated Savings | Risk | Priority |
|-----------|------------------|------|----------|
| Filler words | -300ms perceived | Low | P0 |
| VAD tuning | -50ms | Medium | P0 |
| TTS prewarm | -200ms | Low | P0 |
| Tool acknowledgment | -500ms for tool turns | Low | P1 |
| Speculative LLM | -300ms | High | P2 |

#### 1B.6. Latency Tracing Enhancement

**Modify: `backend/pipeline/events.py`** -- Add FILLER_PLAYED, SPECULATIVE_HIT, SPECULATIVE_MISS event types.

**Modify: `backend/tracing/schemas.py`** -- Add FillerData model with filler_text, filler_type, latency_ms fields.

---

## Phase 2: Mid-Conversation Memory (Week 2-3)

### 2A. Problem

Current memory_manager.build_context() is called once at session start (worker.py line 272). Memory is static for the entire conversation. Important facts from turn 3 are not available for turn 4.

### 2B. Architecture: Two-Layer Memory

1. **Session memory** (in-process, fast): Facts extracted from current conversation turns, held in worker process memory
2. **Persistent memory** (DB + vector, async): Updated incrementally, queried when relevant

#### 2B.1. Session Memory Store

**New file: `backend/memory/session_memory.py`**

SessionMemory class:
- Holds user_id, conversation_id, in-memory fact list, recent turn buffer (last 5 turns)
- Background asyncio task runs fact extraction via qwen-turbo on user turns
- Extraction is batched (waits 5s for more turns before calling LLM)
- build_dynamic_context() returns formatted string of session-extracted facts
- Also writes extracted facts to DB asynchronously for persistence

#### 2B.2. Dynamic System Prompt Update

**Modify: `backend/pipeline/worker.py`**

After session.start(), create SessionMemory and hook it into events:
- On user_input_transcribed (final): feed user turn to SessionMemory
- On conversation_item_added (assistant): feed agent turn to SessionMemory
- After each agent turn: update agent.instructions with base_system_prompt + session_memory.build_dynamic_context()

LiveKit Agents v1.5 Agent.instructions is mutable -- updating it changes the system prompt for the next LLM call.

#### 2B.3. Memory as a Function-Calling Tool

**New file: `backend/agents/tools/common/memory_recall.py`**

MemoryRecallTool (extends BaseTool):
- name: "recall_memory"
- description: "Search your memory for information about the user from past conversations"
- parameter: query (string)
- execute: calls memory_manager vector search + fact lookup, returns formatted results

This gives the LLM agency to pull past context when needed, paying the tool-call cost only when actually useful.

**Modify: `backend/main.py`** -- Register MemoryRecallTool in lifespan startup.

#### 2B.4. Vector Search Enhancement

**Modify: `backend/memory/manager.py`**

Add search_relevant_context(user_id, query) method for quick mid-conversation vector search (top_k=2, lightweight).

---

## Phase 3: Annotation & E2E Testing (Week 3-4)

### 3A. Annotation System

#### 3A.1. DB Schema

**Modify: `backend/db/models.py`** -- Add Annotation model:

Fields: id, conversation_id, message_id (nullable FK), turn_index, annotation_type (enum: asr_quality/response_quality/skill_accuracy/latency/general), rating (1-5), labels (JSON array of tag strings like "asr_wrong", "hallucination", "too_slow"), corrected_text, expected_response, expected_skill, notes, annotator_id, created_at.

#### 3A.2. Annotation API

**New file: `backend/api/annotations.py`**

CRUD endpoints:
- POST /{conversation_id}/annotations -- create
- GET /{conversation_id}/annotations -- list for conversation
- PATCH /annotations/{id} -- update
- GET /annotations/summary?agent_id=X -- aggregate stats (ASR accuracy, response quality distribution)

**Modify: `backend/main.py`** -- Register annotations router.

#### 3A.3. Frontend Annotation UI

**Modify: `frontend/src/app/(app)/history/[id]/page.tsx`** -- Add AnnotationBar component below each message in ConversationPanel.

**New file: `frontend/src/app/(app)/history/[id]/components/AnnotationBar.tsx`** -- Inline annotation widget with: 5-star rating, quick label buttons (thumbs up/down, issue tags), expandable correction field, save to API.

### 3B. Automated E2E Testing

#### 3B.1. Test Case Schema

**Modify: `backend/db/models.py`** -- Add TestCase and TestRun models.

TestCase: id, name, agent_id, steps (JSON array), tags, is_active, created_at.
Each step: { input_type, input_text, expected_keywords, expected_skill, max_latency_ms, wait_ms }.

TestRun: id, test_case_id, conversation_id, status (pending/running/passed/failed/error), results (JSON with per-step details), started_at, ended_at.

#### 3B.2. Test Runner

**New file: `backend/tests/e2e_runner.py`**

E2ETestRunner class that refactors the existing test_e2e.py pattern into a reusable runner:
1. Load TestCase from DB
2. Create room via backend API
3. Connect to LiveKit as test participant
4. For each step: generate/load audio, publish, wait for ASR+NLP+TTS, capture results, run assertions
5. Save TestRun to DB
6. Cleanup room

Key reuse: The audio generation, room creation, event handling patterns from test_e2e.py (lines 97-556) are extracted into the runner.

#### 3B.3. Test API

**New file: `backend/api/tests.py`**

Endpoints:
- POST /test-cases -- create test case
- GET /test-cases?agent_id=X -- list
- POST /test-cases/{id}/run -- trigger test run
- GET /test-runs?test_case_id=X -- list runs
- GET /test-runs/{id} -- get run details

#### 3B.4. Frontend Test Management

**New file: `frontend/src/app/(app)/testing/page.tsx`** -- Test management page showing test cases, run history, pass/fail status, latency comparisons.

---

## Phase 4: Skill System Enhancement (Week 4-5)

### 4A. Skill Tracking

**New file: `backend/pipeline/skill_tracker.py`**

SkillTracker class:
- Parses <skill>code</skill> tags from agent responses
- Tracks current active skill, skill history (enter/exit timestamps, turn counts)
- Emits SKILL_ENTER, SKILL_EXIT, SKILL_TRANSITION trace events

### 4B. Skill Trace Events

**Modify: `backend/pipeline/events.py`** -- Add SKILL_ENTER, SKILL_EXIT, SKILL_TRANSITION.

**Modify: `backend/tracing/schemas.py`** -- Add SkillTransitionData model.

### 4C. Integrate into Worker

**Modify: `backend/pipeline/worker.py`** -- Create SkillTracker after loading skills. Hook into conversation_item_added event to call skill_tracker.update() on each agent response. Emit transition events via tracer.

### 4D. Skill Analytics

**Modify: `backend/api/agent_skills.py`** -- Add GET /{agent_id}/skills/analytics endpoint that aggregates skill usage from trace events: entry counts, avg turns per skill, transition patterns, annotation quality ratings per skill.

### 4E. Optional: Skill State Machine

**Modify: `backend/db/models.py` (AgentSkill)** -- Add nullable columns: entry_conditions (JSON), exit_conditions (JSON), allowed_transitions (JSON list), success_criteria (JSON). These let skills define structured progression rules. SkillTracker validates transitions and emits warnings on unexpected jumps.

---

## Database Migration

**New file: `backend/db/migrations/versions/xxx_add_annotations_tests_skills.py`**

Single migration creating:
- annotations table
- test_cases table
- test_runs table
- Adding columns to agent_skills: entry_conditions, exit_conditions, allowed_transitions, success_criteria

---

## Implementation Priority

1. P0 Week 1: Filler words + VAD tuning + TTS prewarm (latency)
2. P0 Week 1: Annotation schema + API + basic UI (unblocks QA)
3. P1 Week 2: Session memory + dynamic prompt (memory)
4. P1 Week 2: E2E test runner + test case schema (testing)
5. P2 Week 3: Skill tracker + analytics
6. P2 Week 3: Memory recall tool
7. P3 Week 4: Speculative LLM
8. P3 Week 4: Skill state machine
