"""
Lazy-loaded, process-cached access to the RAG vector store and the DuckDB
structured-data store. Loaded once per warm serverless container (module
globals persist across invocations on the same instance), so repeat
requests on a warm function don't re-read the embeddings/DB from disk.
"""

import json
from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
from openai import OpenAI

STORE_DIR = Path(__file__).resolve().parent.parent / "_store"

EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    return OpenAI()


@lru_cache(maxsize=1)
def get_chunks():
    with open(STORE_DIR / "chunks.json") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_embeddings():
    return np.load(STORE_DIR / "embeddings.npy")


@lru_cache(maxsize=1)
def get_schema_description() -> str:
    return (STORE_DIR / "schema_description.md").read_text()


@lru_cache(maxsize=1)
def get_db_connection():
    # read_only=True: the SQL agent should never be able to mutate this file,
    # regardless of what SQL it generates.
    return duckdb.connect(str(STORE_DIR / "procurement.duckdb"), read_only=True)


def embed_query(text: str) -> np.ndarray:
    resp = get_client().embeddings.create(model=EMBEDDING_MODEL, input=[text])
    vec = np.array(resp.data[0].embedding, dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def top_k_chunks(query: str, k: int = 6):
    qv = embed_query(query)
    sims = get_embeddings() @ qv
    idx = np.argsort(-sims)[:k]
    chunks = get_chunks()
    return [{**chunks[i], "score": float(sims[i])} for i in idx]
