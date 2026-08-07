"""Deterministic unit tests for Step 3B's short-term memory (server-side
validation/truncation). No API calls -- pure logic over agents.memory.

Run directly: python3 tests/test_memory.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from agents import memory  # noqa: E402

_FAILURES = []


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


def _turns(n, offset=0):
    return [{"user": f"q{i + offset}", "assistant": f"a{i + offset}"} for i in range(n)]


def test_new_session_has_no_prior_context():
    result = memory.validate_and_truncate_history([])
    check("new session: empty history -> empty", result == [])
    check("new session: renders as 'no prior conversation'", memory.render_history_for_prompt(result) == "(no prior conversation this session)")


def test_malformed_history_degrades_gracefully():
    check("malformed: non-list input -> []", memory.validate_and_truncate_history("not a list") == [])
    check("malformed: None -> []", memory.validate_and_truncate_history(None) == [])
    mixed = [{"user": "a", "assistant": "b"}, {"garbage": True}, "not even a dict", {"user": "c", "assistant": "d"}]
    result = memory.validate_and_truncate_history(mixed)
    check("malformed: bad entries dropped, good ones kept", result == [{"user": "a", "assistant": "b"}, {"user": "c", "assistant": "d"}])


def test_exactly_10_turn_window():
    result = memory.validate_and_truncate_history(_turns(10))
    check("exactly 10 turns: all kept", len(result) == 10)
    check("exactly 10 turns: order preserved", result[0]["user"] == "q0" and result[-1]["user"] == "q9")


def test_oldest_complete_turn_dropped_when_window_exceeded():
    result = memory.validate_and_truncate_history(_turns(11))
    check("11 turns -> truncated to last 10", len(result) == 10)
    check("11 turns: oldest (q0) dropped entirely", all(t["user"] != "q0" for t in result))
    check("11 turns: newest (q10) kept", result[-1]["user"] == "q10")


def test_server_truncates_regardless_of_client_claim():
    # Server must independently re-truncate even if the client sends far more than
    # the window -- never trust client-supplied bounds.
    result = memory.validate_and_truncate_history(_turns(50))
    check("client sends 50 turns -> server still caps at 10", len(result) == memory.MAX_MEMORY_TURNS)
    check("server keeps the most recent, not the first, 10", result[0]["user"] == "q40")


def test_current_turn_observations_stay_separate_from_history():
    # Structural check: conversation_history and actions_taken/observations are
    # different fields entirely in AgentGraphState -- validate_and_truncate_history
    # only ever touches what's explicitly passed to it, never anything resembling
    # this-turn's tool observations.
    history_only = memory.validate_and_truncate_history(_turns(2))
    check("history function only processes what's passed in", len(history_only) == 2)
    check(
        "no observation-shaped keys leak into a turn",
        all(set(t.keys()) == {"user", "assistant"} for t in history_only),
    )


def run():
    test_new_session_has_no_prior_context()
    test_malformed_history_degrades_gracefully()
    test_exactly_10_turn_window()
    test_oldest_complete_turn_dropped_when_window_exceeded()
    test_server_truncates_regardless_of_client_claim()
    test_current_turn_observations_stay_separate_from_history()

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} FAILED: {_FAILURES}")
        sys.exit(1)
    print("All deterministic memory tests passed.")


if __name__ == "__main__":
    run()
