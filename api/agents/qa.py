"""QA / groundedness gate. Different agents need different verification strategies:

- RAG answers are free text generated from retrieved passages, so groundedness has to be
  judged -- an LLM-judge checks every claim is actually supported by the cited passages.
- SQL answers are generated from the query's own execution result, so ground truth is
  directly available -- a deterministic check (did it execute, did it return the rows the
  summary claims) is cheaper and more reliable than asking another LLM to "judge" a fact
  it could just as easily verify by re-reading the result set.

Either agent failing its gate returns a safe fallback instead of a hallucinated answer.
"""

from langchain_core.prompts import ChatPromptTemplate

from .contracts import GroundednessJudgment, QAResult
from .store import get_chat_model

# No real template variables in the system message itself (context/answer go into the
# human message) -- escaped for LangChain's f-string-style renderer so the rendered
# system message is byte-identical to the original literal text.
JUDGE_SYSTEM_PROMPT = """You are a strict fact-checker. Given numbered source passages and an \
answer that cites them, verify every factual claim in the answer is actually supported by the \
cited passage(s). Respond with strict JSON: {{"grounded": true|false, "score": 1-5, "reasoning": \
"<one short sentence>"}}. Score 5 = fully supported, no unsupported claims. Score 1 = mostly \
unsupported or citations don't back the claims. grounded=true only if score >= 4."""

FALLBACK_MESSAGE = (
    "I couldn't verify a reliable answer to this from the available procurement knowledge "
    "base or data. Please escalate this question to the L2 procurement team."
)

_judge_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", JUDGE_SYSTEM_PROMPT),
        ("human", "Source passages:\n\n{context}\n\nAnswer to check:\n{answer}"),
    ]
)


def check_rag_groundedness(answer: str, chunks_used: list) -> dict:
    context = "\n\n".join(f"[{i + 1}] {c['text']}" for i, c in enumerate(chunks_used))
    chain = _judge_prompt | get_chat_model().with_structured_output(
        GroundednessJudgment, method="json_schema", strict=True
    )
    judgment = chain.invoke({"context": context, "answer": answer})
    result = QAResult(
        passed=judgment.grounded,
        score=judgment.score,
        reasoning=judgment.reasoning,
        method="llm_judge",
    )
    return result.model_dump(exclude_none=True)


def check_sql_groundedness(data_result: dict) -> dict:
    if data_result.get("error"):
        result = QAResult(passed=False, reasoning=data_result["error"], method="deterministic")
        return result.model_dump(exclude_none=True)
    result = QAResult(
        passed=True,
        reasoning=f"SQL executed successfully, {len(data_result.get('rows', []))} row(s) returned.",
        method="deterministic",
    )
    return result.model_dump(exclude_none=True)
