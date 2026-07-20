"""QA / groundedness gate. Different agents need different verification strategies:

- RAG answers are free text generated from retrieved passages, so groundedness has to be
  judged -- an LLM-judge checks every claim is actually supported by the cited passages.
- SQL answers are generated from the query's own execution result, so ground truth is
  directly available -- a deterministic check (did it execute, did it return the rows the
  summary claims) is cheaper and more reliable than asking another LLM to "judge" a fact
  it could just as easily verify by re-reading the result set.

Either agent failing its gate returns a safe fallback instead of a hallucinated answer.
"""

import json

from .store import CHAT_MODEL, get_client

JUDGE_SYSTEM_PROMPT = """You are a strict fact-checker. Given numbered source passages and an \
answer that cites them, verify every factual claim in the answer is actually supported by the \
cited passage(s). Respond with strict JSON: {"grounded": true|false, "score": 1-5, "reasoning": \
"<one short sentence>"}. Score 5 = fully supported, no unsupported claims. Score 1 = mostly \
unsupported or citations don't back the claims. grounded=true only if score >= 4."""

FALLBACK_MESSAGE = (
    "I couldn't verify a reliable answer to this from the available procurement knowledge "
    "base or data. Please escalate this question to the L2 procurement team."
)


def check_rag_groundedness(answer: str, chunks_used: list) -> dict:
    context = "\n\n".join(f"[{i + 1}] {c['text']}" for i, c in enumerate(chunks_used))
    resp = get_client().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Source passages:\n\n{context}\n\nAnswer to check:\n{answer}"},
        ],
    )
    result = json.loads(resp.choices[0].message.content)
    return {
        "passed": bool(result.get("grounded", False)),
        "score": result.get("score"),
        "reasoning": result.get("reasoning", ""),
        "method": "llm_judge",
    }


def check_sql_groundedness(data_result: dict) -> dict:
    if data_result.get("error"):
        return {"passed": False, "reasoning": data_result["error"], "method": "deterministic"}
    return {
        "passed": True,
        "reasoning": f"SQL executed successfully, {len(data_result.get('rows', []))} row(s) returned.",
        "method": "deterministic",
    }
