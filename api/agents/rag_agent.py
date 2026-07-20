"""RAG agent: retrieves top-k chunks from the KnowledgeBase vector store and
answers strictly from them, with inline numbered citations."""

from .store import CHAT_MODEL, get_client, top_k_chunks

SYSTEM_PROMPT = """You are a procurement policy assistant for a pharmaceutical company's L1 \
helpdesk. Answer the user's question using ONLY the numbered context passages below -- do not \
use outside knowledge. Cite every claim with the passage number(s) it came from, like [1] or \
[1][3]. If the passages don't contain enough information to answer, say so plainly and suggest \
escalating to the L2 procurement team -- do not guess or fill gaps from general knowledge."""


def answer_from_docs(query: str, top_k: int = 6) -> dict:
    chunks = top_k_chunks(query, k=top_k)
    context = "\n\n".join(
        f"[{i + 1}] (source: {c['source']}, {c['location']})\n{c['text']}" for i, c in enumerate(chunks)
    )
    resp = get_client().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context passages:\n\n{context}\n\nQuestion: {query}"},
        ],
    )
    answer = resp.choices[0].message.content
    citations = [
        {"marker": i + 1, "source": c["source"], "location": c["location"], "score": round(c["score"], 3)}
        for i, c in enumerate(chunks)
    ]
    return {"answer": answer, "citations": citations, "chunks_used": chunks}
