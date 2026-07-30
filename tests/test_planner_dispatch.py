"""Deterministic unit tests for Step 3A's planner-based tool dispatch.

No OpenAI API calls: canonicalize_tools()/derive_category() are pure
functions tested directly, and plan()'s LLM call is stood in for with a
langchain_core.runnables.RunnableLambda (a real Runnable, so it composes
correctly with ChatPromptTemplate's `|` operator, unlike a plain mock)
that either returns a canned PlannerDecision or raises -- covering the
success path and the exception-fallback path without any network access.

Run directly: python3 tests/test_planner_dispatch.py
"""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from langchain_core.runnables import RunnableLambda  # noqa: E402

from agents import planner  # noqa: E402
from agents.contracts import PlannerDecision  # noqa: E402

_FAILURES = []


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


# --- tool-list normalisation / duplicate removal / canonical ordering ---


def test_tool_list_normalisation():
    # order-independent input -> canonical output order (policy before data)
    check(
        "normalisation: reversed input order -> canonical order",
        planner.canonicalize_tools(["procurement_data_answer", "policy_answer"])
        == ["policy_answer", "procurement_data_answer"],
    )
    check(
        "normalisation: already-canonical input stays canonical",
        planner.canonicalize_tools(["policy_answer", "procurement_data_answer"])
        == ["policy_answer", "procurement_data_answer"],
    )
    check(
        "normalisation: unknown tool names are silently dropped (defense in depth)",
        planner.canonicalize_tools(["policy_answer", "not_a_real_tool"]) == ["policy_answer"],
    )
    check(
        "normalisation: empty input -> empty output",
        planner.canonicalize_tools([]) == [],
    )


def test_duplicate_removal():
    check(
        "dedup: repeated policy_answer collapses to one",
        planner.canonicalize_tools(["policy_answer", "policy_answer", "procurement_data_answer"])
        == ["policy_answer", "procurement_data_answer"],
    )
    check(
        "dedup: repeated single tool collapses to one",
        planner.canonicalize_tools(["procurement_data_answer", "procurement_data_answer"])
        == ["procurement_data_answer"],
    )


def test_canonical_ordering():
    # policy_answer must precede procurement_data_answer regardless of how many
    # permutations of duplicated/reordered input are thrown at it
    permutations = [
        ["policy_answer", "procurement_data_answer"],
        ["procurement_data_answer", "policy_answer"],
        ["procurement_data_answer", "policy_answer", "policy_answer"],
        ["policy_answer", "policy_answer", "procurement_data_answer", "procurement_data_answer"],
    ]
    for p in permutations:
        result = planner.canonicalize_tools(p)
        check(
            f"canonical order holds for input {p}",
            result == ["policy_answer", "procurement_data_answer"],
            detail=f"got {result}",
        )


# --- category derivation ---


def test_category_derivation():
    cases = [
        ([], "OUT_OF_SCOPE"),
        (["policy_answer"], "POLICY"),
        (["procurement_data_answer"], "DATA"),
        (["policy_answer", "procurement_data_answer"], "BOTH"),
    ]
    for tools, expected in cases:
        check(
            f"derive_category({tools}) == {expected}",
            planner.derive_category(tools) == expected,
        )


# --- planner exception fallback, and its distinction from genuine OUT_OF_SCOPE ---


def _fake_chat_model(structured_output_fn):
    class _FakeChatModel:
        def with_structured_output(self, model, method=None, strict=None):
            return RunnableLambda(lambda _rendered_prompt: structured_output_fn())

    return _FakeChatModel()


def test_planner_exception_fallback():
    def raise_error(*_a, **_kw):
        raise RuntimeError("simulated API/infrastructure failure")

    with patch.object(planner, "get_chat_model", return_value=_fake_chat_model(raise_error)):
        result = planner.plan("some query that would normally be classified")

    check("exception fallback: tools_to_call == []", result["tools_to_call"] == [])
    check("exception fallback: category == OUT_OF_SCOPE", result["category"] == "OUT_OF_SCOPE")
    check("exception fallback: planner_failed is True", result["planner_failed"] is True)
    check(
        "exception fallback: planner_error records the exception text",
        result["planner_error"] is not None and "simulated API/infrastructure failure" in result["planner_error"],
    )


def test_distinction_between_legitimate_out_of_scope_and_planner_failure():
    # legitimate: the LLM call succeeds and genuinely decides no capability is needed
    def genuine_out_of_scope(*_a, **_kw):
        return PlannerDecision(tools_to_call=[], reasoning="Unrelated to procurement.")

    with patch.object(planner, "get_chat_model", return_value=_fake_chat_model(genuine_out_of_scope)):
        legit_result = planner.plan("What's the capital of France?")

    # failure: the LLM call raises
    def raise_error(*_a, **_kw):
        raise RuntimeError("simulated failure")

    with patch.object(planner, "get_chat_model", return_value=_fake_chat_model(raise_error)):
        failure_result = planner.plan("What's the capital of France?")

    # both produce the same empty tool list and OUT_OF_SCOPE category (unchanged
    # graph routing/response contract, per correction 7) ...
    check(
        "both legit-OOS and failure produce tools_to_call == []",
        legit_result["tools_to_call"] == [] and failure_result["tools_to_call"] == [],
    )
    check(
        "both legit-OOS and failure produce category == OUT_OF_SCOPE",
        legit_result["category"] == "OUT_OF_SCOPE" and failure_result["category"] == "OUT_OF_SCOPE",
    )
    # ... but planner_failed distinguishes them, which is the whole point of correction 6
    check("legitimate OUT_OF_SCOPE has planner_failed == False", legit_result["planner_failed"] is False)
    check("planner failure has planner_failed == True", failure_result["planner_failed"] is True)
    check(
        "legitimate OUT_OF_SCOPE has no planner_error recorded",
        legit_result["planner_error"] is None,
    )
    check(
        "planner failure has a planner_error recorded",
        failure_result["planner_error"] is not None,
    )


def run():
    test_tool_list_normalisation()
    test_duplicate_removal()
    test_canonical_ordering()
    test_category_derivation()
    test_planner_exception_fallback()
    test_distinction_between_legitimate_out_of_scope_and_planner_failure()

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} FAILED: {_FAILURES}")
        sys.exit(1)
    print("All deterministic planner-dispatch tests passed.")


if __name__ == "__main__":
    run()
