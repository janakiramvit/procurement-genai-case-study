"""Short-term conversational memory -- Step 3B.

Storage itself is client-side (browser sessionStorage, tab-scoped) -- that's a
frontend concern, not this module's. This module only handles what the SERVER
does with whatever `conversation_history` arrives in a request: independently
validate and truncate it to the last MAX_MEMORY_TURNS complete turns,
regardless of what (or how much) the client sent. Never trust client-supplied
bounds -- a malformed or oversized payload degrades to "no memory" for that
request rather than failing the whole turn.

Memory is context, not evidence: this module renders history for the planner
prompt as background for reference resolution ("who/what is the user asking
about") only. The planner is separately instructed (see planner.py) that a
prior assistant answer is never itself grounded evidence for the current turn.
"""

from .contracts import ConversationTurn

MAX_MEMORY_TURNS = 10  # 1 turn = one user message + its assistant response


def validate_and_truncate_history(raw_history) -> list[dict]:
    """Never raises. Malformed entries are dropped, not fatal -- worst case
    this returns []. Keeps only the last MAX_MEMORY_TURNS complete turns."""
    if not isinstance(raw_history, list):
        return []

    turns: list[dict] = []
    for entry in raw_history:
        if not isinstance(entry, dict):
            continue
        try:
            turn = ConversationTurn.model_validate(entry)
        except Exception:
            continue
        turns.append(turn.model_dump())

    return turns[-MAX_MEMORY_TURNS:]


def render_history_for_prompt(history: list[dict]) -> str:
    if not history:
        return "(no prior conversation this session)"
    lines = []
    for i, turn in enumerate(history, start=1):
        lines.append(f"Turn {i}:\nUser: {turn['user']}\nAssistant: {turn['assistant']}")
    return "\n\n".join(lines)
