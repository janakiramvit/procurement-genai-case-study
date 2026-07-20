"""
Offline evaluation harness. Runs the fixed eval/eval_questions.json set
through the full orchestrator pipeline (same code path as the live app,
called directly rather than over HTTP) and reports:

- router accuracy       (predicted category == expected category)
- retrieval hit-rate     (expected source doc appears in top-k citations,
                          for policy questions with a known expected source)
- groundedness pass-rate (per QA gate, policy vs data)
- refusal correctness    (out-of-scope questions correctly refused)
- answer relevance       (separate LLM-judge axis from groundedness: does the
                          answer actually address the question, 1-5)
- latency                (p50 / p95 total pipeline latency)

Writes eval/eval_results.json (raw per-question results + aggregates).
"""

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from agents.orchestrator import handle_query  # noqa: E402
from agents.store import CHAT_MODEL, get_client  # noqa: E402

EVAL_DIR = ROOT / "eval"

RELEVANCE_JUDGE_PROMPT = """You are grading a procurement helpdesk chatbot's answer for RELEVANCE \
only (not correctness/groundedness -- a separate check already covers that). Given the question \
and the answer, score 1-5: 5 = directly and usefully addresses the question, 3 = partially \
addresses it or is an appropriately honest refusal given real information gaps, 1 = ignores the \
question or is unhelpful. Respond with strict JSON: {"score": 1-5, "reasoning": "<one sentence>"}"""


def judge_relevance(query: str, answer: str) -> dict:
    resp = get_client().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": RELEVANCE_JUDGE_PROMPT},
            {"role": "user", "content": f"Question: {query}\n\nAnswer: {answer}"},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def run():
    questions = json.loads((EVAL_DIR / "eval_questions.json").read_text())
    results = []

    for q in questions:
        print(f"[{q['id']}] {q['query'][:70]}...")
        response = handle_query(q["query"])

        category_match = response["category"] == q["expected_category"]

        retrieval_hit = None
        if q.get("expected_source"):
            # measured against what the retriever actually found, independent of whether
            # the downstream QA gate kept it in the user-facing citations
            sources = set(response.get("retrieved_sources", []))
            retrieval_hit = q["expected_source"] in sources

        relevance = judge_relevance(q["query"], response["answer"] or "")

        results.append({
            "id": q["id"],
            "query": q["query"],
            "expected_category": q["expected_category"],
            "actual_category": response["category"],
            "category_match": category_match,
            "expected_source": q.get("expected_source"),
            "retrieval_hit": retrieval_hit,
            "groundedness": response["groundedness"],
            "relevance_score": relevance["score"],
            "relevance_reasoning": relevance["reasoning"],
            "total_latency_ms": response["total_latency_ms"],
            "answer": response["answer"],
        })

    aggregates = summarize(results)
    output = {"results": results, "aggregates": aggregates}
    (EVAL_DIR / "eval_results.json").write_text(json.dumps(output, indent=2))
    print_summary(aggregates)


def summarize(results: list) -> dict:
    n = len(results)
    router_acc = sum(r["category_match"] for r in results) / n

    retrieval_cases = [r for r in results if r["retrieval_hit"] is not None]
    retrieval_hit_rate = (
        sum(1 for r in retrieval_cases if r["retrieval_hit"]) / len(retrieval_cases) if retrieval_cases else None
    )

    policy_qa = [g for r in results for g in r["groundedness"] if g["path"] == "policy"]
    data_qa = [g for r in results for g in r["groundedness"] if g["path"] == "data"]
    policy_pass_rate = sum(1 for g in policy_qa if g["passed"]) / len(policy_qa) if policy_qa else None
    data_pass_rate = sum(1 for g in data_qa if g["passed"]) / len(data_qa) if data_qa else None

    oos_cases = [r for r in results if r["expected_category"] == "OUT_OF_SCOPE"]
    refusal_correctness = (
        sum(1 for r in oos_cases if r["category_match"]) / len(oos_cases) if oos_cases else None
    )

    relevance_scores = [r["relevance_score"] for r in results]
    latencies = [r["total_latency_ms"] for r in results]

    return {
        "n_questions": n,
        "router_accuracy": round(router_acc, 3),
        "retrieval_hit_rate": round(retrieval_hit_rate, 3) if retrieval_hit_rate is not None else None,
        "retrieval_n": len(retrieval_cases),
        "policy_groundedness_pass_rate": round(policy_pass_rate, 3) if policy_pass_rate is not None else None,
        "policy_qa_n": len(policy_qa),
        "data_groundedness_pass_rate": round(data_pass_rate, 3) if data_pass_rate is not None else None,
        "data_qa_n": len(data_qa),
        "refusal_correctness": round(refusal_correctness, 3) if refusal_correctness is not None else None,
        "avg_relevance_score": round(statistics.mean(relevance_scores), 2),
        "p50_latency_ms": round(statistics.median(latencies)),
        "p95_latency_ms": round(sorted(latencies)[max(0, round(0.95 * len(latencies)) - 1)]),
    }


def print_summary(agg: dict):
    print("\n" + "=" * 60)
    print("EVAL SUMMARY")
    print("=" * 60)
    for k, v in agg.items():
        print(f"{k:32s} {v}")


if __name__ == "__main__":
    run()
