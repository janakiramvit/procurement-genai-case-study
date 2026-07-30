"""Bounded tools invoked by the planner's graph nodes -- Step 3A.

Named for what they actually do, not just their underlying data source:
policy_answer wraps retrieval *plus* LLM answer generation (not search
alone), and procurement_data_answer wraps SQL generation, execution, *and*
LLM summarization. Both are thin wrappers -- the underlying rag_agent.py /
data_agent.py logic is unchanged, same as every prior step's discipline of
wrapping existing agents rather than rewriting them.
"""

from . import data_agent, rag_agent


def policy_answer(query: str) -> dict:
    return rag_agent.answer_from_docs(query)


def procurement_data_answer(query: str) -> dict:
    return data_agent.answer_from_data(query)
