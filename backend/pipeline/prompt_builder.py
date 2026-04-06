"""Dynamic prompt builder — assembles the 6-layer agent system prompt.

Layers:
1. Role — persona, tone, boundaries
2. Target — conversation objective
3. Task Chain + Skill — current task context (dynamic per turn)
4. Rules — behavioral constraints
5. Optimization — EQ/IQ tuning
6. Memory — conversation history context
"""


def build_dynamic_prompt(
    *,
    role: str = "",
    target: str = "",
    task_prompt: str = "",
    rules_text: str = "",
    memory_prompt: str = "",
    optimization: str = "",
    system_prompt: str = "",
) -> str:
    """Assemble the full system prompt from all 6 layers.

    Args:
        role: Layer 1 — role definition
        target: Layer 2 — conversation objective
        task_prompt: Layer 3+4 — current task + skill (from TaskChainController)
        rules_text: Layer 5 — behavioral rules
        memory_prompt: Layer 6 — memory context
        optimization: Optimization instructions
        system_prompt: Legacy system_prompt (used as fallback/supplement)
    """
    sections: list[str] = []

    # Layer 1: Role
    if role:
        sections.append(f"## 角色设定\n{role}")

    # Layer 2: Target
    if target:
        sections.append(f"## 对话目标\n{target}")

    # Layer 3+4: Current Task + Skill
    if task_prompt:
        sections.append(task_prompt)

    # Legacy system prompt (if no role/task defined, use as main instructions)
    if system_prompt:
        if not role and not task_prompt:
            sections.insert(0, system_prompt)
        else:
            sections.append(f"## 补充指令\n{system_prompt}")

    # Layer 5: Rules
    if rules_text:
        sections.append(f"## 规则约束\n{rules_text}")

    # Layer 6: Optimization
    if optimization:
        sections.append(f"## 优化指导\n{optimization}")

    # Memory
    if memory_prompt:
        sections.append(memory_prompt)

    return "\n\n".join(sections)


def format_rules(rules: list[dict]) -> str:
    """Format agent rules into prompt text.

    Args:
        rules: list of {rule_type, content, priority, is_active}
    """
    if not rules:
        return ""

    active_rules = [r for r in rules if r.get("is_active", True)]
    if not active_rules:
        return ""

    # Sort by priority (higher first)
    active_rules.sort(key=lambda r: r.get("priority", 0), reverse=True)

    parts: list[str] = []

    forbidden = [r for r in active_rules if r.get("rule_type") == "forbidden"]
    required = [r for r in active_rules if r.get("rule_type") == "required"]
    format_rules_list = [r for r in active_rules if r.get("rule_type") == "format"]

    if forbidden:
        parts.append("### 禁止事项")
        for r in forbidden:
            parts.append(f"- ❌ {r['content']}")

    if required:
        parts.append("### 必须事项")
        for r in required:
            parts.append(f"- ✅ {r['content']}")

    if format_rules_list:
        parts.append("### 格式要求")
        for r in format_rules_list:
            parts.append(f"- {r['content']}")

    return "\n".join(parts)


def format_optimization(optimization: dict | None) -> str:
    """Format optimization config into prompt text."""
    if not optimization:
        return ""

    parts: list[str] = []

    if optimization.get("eq_instructions"):
        parts.append(f"### 情商优化\n{optimization['eq_instructions']}")

    if optimization.get("iq_instructions"):
        parts.append(f"### 智商优化\n{optimization['iq_instructions']}")

    if optimization.get("response_style"):
        parts.append(f"### 回复风格\n{optimization['response_style']}")

    if optimization.get("filler_words"):
        fillers = "、".join(optimization["filler_words"])
        parts.append(f"### 承接词\n在回复开头适当使用承接词使对话更自然: {fillers}")

    return "\n".join(parts)
