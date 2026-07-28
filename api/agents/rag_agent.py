"""RAG agent: retrieves top-k chunks from the KnowledgeBase vector store and
answers strictly from them, with inline numbered citations."""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .contracts import RAGResult
from .store import get_chat_model, top_k_chunks

SYSTEM_PROMPT = """You are a procurement policy assistant for a pharmaceutical company's L1 \
helpdesk. Answer the user's question using ONLY the numbered context passages below -- do not \
use outside knowledge. Cite every claim with the passage number(s) it came from, like [1] or \
[1][3]. If the passages don't contain enough information to answer, say so plainly and suggest \
escalating to the L2 procurement team -- do not guess or fill gaps from general knowledge."""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Context passages:\n\n{context}\n\nQuestion: {query}"),
    ]
)


def answer_from_docs(query: str, top_k: int = 6) -> dict:
    chunks = top_k_chunks(query, k=top_k)
    context = "\n\n".join(
        f"[{i + 1}] (source: {c['source']}, {c['location']})\n{c['text']}" for i, c in enumerate(chunks)
    )
    chain = _prompt | get_chat_model() | StrOutputParser()
    answer = chain.invoke({"context": context, "query": query})
    citations = [
        {"marker": i + 1, "source": c["source"], "location": c["location"], "score": round(c["score"], 3)}
        for i, c in enumerate(chunks)
    ]
    result = RAGResult(answer=answer, citations=citations, chunks_used=chunks)
    return result.model_dump()
