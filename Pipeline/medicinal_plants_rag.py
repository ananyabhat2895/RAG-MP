from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import chromadb
import numpy as np
import ollama
from rank_bm25 import BM25Okapi

PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "qwen3-embedding:0.6b"
GENERATION_MODEL = "qwen2.5:3b"
TOP_K_VECTOR = 10
TOP_K_BM25 = 10
TOP_K_FINAL = 5
RRF_K = 60
OLLAMA_URL = "http://localhost:11434"


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_chroma_db_path(root: Path | None = None) -> Path:
    root = root or PROJECT_ROOT
    candidates = sorted(root.glob("chroma_db*"), key=lambda p: p.name)
    for candidate in candidates:
        if (candidate / "chroma.sqlite3").exists():
            return candidate
        nested = candidate / "chroma_db"
        if nested.exists() and (nested / "chroma.sqlite3").exists():
            return nested
    raise FileNotFoundError(
        "No existing ChromaDB persistence directory found. "
        "Check the project root for a chroma_db* folder."
    )


def find_collection_name(db_path: Path) -> str:
    client = chromadb.PersistentClient(path=str(db_path))
    collections = client.list_collections()
    if not collections:
        raise FileNotFoundError(
            f"No collections found in ChromaDB at {db_path}."
        )
    names = [c.name for c in collections]
    return names[0]


def list_models() -> List[str]:
    try:
        response = ollama.list()
        models = response.get("models", []) if isinstance(response, dict) else []
        return [m.get("name") or m.get("model") or "" for m in models if m]
    except Exception:
        return []


def ensure_model(model_name: str) -> None:
    available = list_models()
    if model_name not in available:
        print(f"Pulling missing model: {model_name}")
        ollama.pull(model_name)


def check_ollama() -> bool:
    try:
        response = ollama.list()
        return isinstance(response, dict) and "models" in response
    except Exception:
        return False


def query_embedding(text: str, model: str = EMBEDDING_MODEL) -> List[float]:
    response = ollama.embed(model=model, input=text)
    embeddings = response.get("embeddings", [])
    if not embeddings:
        raise RuntimeError(f"No embedding returned for model {model!r}.")
    return embeddings[0]


def generate_text(prompt: str, model: str = GENERATION_MODEL, temperature: float = 0.1) -> str:
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an Indian medicinal plants research assistant. "
                        "Answer only what the user asks, in clear, natural, everyday English. "
                        "Use retrieved records as the factual source for plant claims. "
                        "Never invent medicinal uses, plant parts, constituents, or benefits. "
                        "Do not infer that a plant treats a condition from a broad database category. "
                        "Distinguish documented traditional uses from established clinical evidence. "
                        "Use general knowledge only to briefly explain terminology, not to add plant claims. "
                        "Do not give dosage, prescriptions, or treatment recommendations. "
                        "Do not reveal internal IDs or private reasoning."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            options={
                "temperature": temperature,
                "num_ctx": 8192,
                "num_predict": 256,
                "top_p": 0.9,
            },
        )
    except Exception:
        logger.exception("LLM request failed for model %s", model)
        raise

    message = response.get("message", {})
    content = message.get("content")
    answer = content.strip() if isinstance(content, str) else ""
    if not answer:
        logger.warning("LLM returned an empty final response for model %s", model)

    logger.info(
        "LLM response model=%s finish_reason=%s prompt_tokens=%s "
        "completion_tokens=%s final_answer=%r",
        model,
        response.get("done_reason"),
        response.get("prompt_eval_count"),
        response.get("eval_count"),
        answer,
    )
    return answer


def build_plant_catalog(collection) -> Dict[str, Dict[str, str]]:
    try:
        all_meta = collection.get(include=["metadatas"])
    except Exception:
        all_meta = {"metadatas": []}

    catalog: Dict[str, Dict[str, str]] = {}
    for metadata in all_meta.get("metadatas", []):
        if not isinstance(metadata, dict):
            continue
        plant_id = str(metadata.get("plant_id") or "")
        if not plant_id:
            continue
        metadata = metadata.copy()
        plant_name = str(metadata.get("plant_name") or "").strip()
        botanical_name = str(metadata.get("botanical_name") or "").strip()
        if plant_name:
            catalog[normalize_text(plant_name)] = {
                "plant_id": plant_id,
                "plant_name": plant_name,
                "botanical_name": botanical_name,
            }
        if botanical_name:
            catalog[normalize_text(botanical_name)] = {
                "plant_id": plant_id,
                "plant_name": plant_name,
                "botanical_name": botanical_name,
            }
    return catalog


def resolve_plant(question: str, catalog: Dict[str, Dict[str, str]]) -> Optional[Dict[str, str]]:
    target = normalize_text(question)
    aliases = {
        "neem": "Azadirachta indica",
        "tulsi": "Ocimum tenuiflorum",
        "ashwagandha": "Withania somnifera",
    }
    for key, canonical in aliases.items():
        if normalize_text(key) in target:
            return {
                "plant_id": catalog.get(normalize_text(canonical), {}).get("plant_id"),
                "plant_name": catalog.get(normalize_text(canonical), {}).get("plant_name") or canonical,
                "botanical_name": canonical,
            }
    candidates = [
        catalog.get(target),
        catalog.get(normalize_text(re.sub(r"\bwhat\b|\bis\b|\bof\b|\bthe\b|\babout\b", " ", question, flags=re.I))),
    ]
    for candidate in candidates:
        if candidate and candidate.get("plant_id"):
            return candidate
    return None


def vector_search(collection, question: str, plant_id: Optional[str] = None, top_k: int = TOP_K_VECTOR) -> List[Dict[str, Any]]:
    embedding_vector = query_embedding(question)
    where = None if plant_id is None else {"plant_id": {"$eq": plant_id}}
    results = collection.query(
        query_embeddings=[embedding_vector],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    rows: List[Dict[str, Any]] = []
    for doc, meta, distance in zip(docs, metas, distances):
        rows.append({
            "chunk_id": meta.get("chunk_id"),
            "plant_id": meta.get("plant_id"),
            "document": doc,
            "metadata": meta,
            "score": float(distance),
        })
    return rows


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)?", text.lower())


class BM25Retriever:
    def __init__(self, collection):
        self.collection = collection
        self.documents: List[str] = []
        self.metadata_rows: List[Dict[str, Any]] = []
        self.index: Optional[BM25Okapi] = None
        self._build()

    def _build(self) -> None:
        try:
            all_docs = self.collection.get(include=["documents", "metadatas"])
        except Exception:
            all_docs = {"documents": [], "metadatas": []}
        documents = all_docs.get("documents", [])
        metadatas = all_docs.get("metadatas", [])
        self.documents = []
        self.metadata_rows = []
        for doc, meta in zip(documents, metadatas):
            if not isinstance(doc, str):
                continue
            self.documents.append(doc)
            self.metadata_rows.append(meta if isinstance(meta, dict) else {})
        tokenized = [tokenize(doc) for doc in self.documents]
        self.index = BM25Okapi(tokenized)

    def search(self, question: str, plant_id: Optional[str] = None, top_k: int = TOP_K_BM25) -> List[Dict[str, Any]]:
        if self.index is None:
            return []
        tokens = tokenize(question)
        if not tokens:
            return []
        scores = self.index.get_scores(tokens)
        results: List[Dict[str, Any]] = []
        for idx, score in enumerate(scores):
            meta = self.metadata_rows[idx] if idx < len(self.metadata_rows) else {}
            if plant_id and str(meta.get("plant_id") or "") != plant_id:
                continue
            results.append({
                "chunk_id": meta.get("chunk_id"),
                "plant_id": meta.get("plant_id"),
                "metadata": meta,
                "document": self.documents[idx],
                "score": float(score),
            })
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]


def reciprocal_rank_fusion(result_lists: Iterable[List[Dict[str, Any]]], k: int = RRF_K) -> List[Dict[str, Any]]:
    fused: Dict[str, Dict[str, Any]] = {}
    for results in result_lists:
        for rank, item in enumerate(results, start=1):
            chunk_id = item.get("chunk_id")
            if not chunk_id:
                continue
            if chunk_id not in fused:
                fused[chunk_id] = {
                    "chunk_id": chunk_id,
                    "plant_id": item.get("plant_id"),
                    "metadata": item.get("metadata", {}),
                    "document": item.get("document", ""),
                    "score": 0.0,
                }
            fused[chunk_id]["score"] += 1.0 / (k + rank)
    ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
    return ranked


def classify_intent(question: str) -> str:
    text = question.lower()
    if re.search(r"\b(botanical|scientific)\s+name\b|\bscientific\s+name\b|\bwhat\s+is\s+the\s+botanical\s+name\b", text):
        return "identity"
    if re.search(r"\bfamily\b|\bgenus\b", text):
        return "family"
    if re.search(r"\bmedicinal\s+use|\buses\b|\btherapeutic\b|\bbenefits\b|\bproperties\b", text):
        return "medicinal_uses"
    if re.search(r"\bvernacular|\bcommon\s+name|\blocal\s+name\b", text):
        return "vernacular_names"
    if re.search(r"\bdistribution\b|\bwhere\s+is\b|\bfound\b|\bhabitat\b", text):
        return "distribution"
    if re.search(r"\bsynonym\b|\balias\b", text):
        return "synonyms"
    if re.search(r"\bsanskrit\b|\bsanskrit\s+name\b", text):
        return "sanskrit_names"
    if re.search(r"\bbibliography\b|\breferences\b", text):
        return "bibliography"
    return "general"


def detect_condition(question: str) -> str:
    text = normalize_text(question)
    condition_terms = {
        "fever": ["fever"],
        "cough": ["cough"],
        "common cold": ["common cold", "cold"],
        "asthma": ["asthma"],
        "diabetes mellitus": ["diabetes mellitus", "diabetes"],
        "diabetes insipidus": ["diabetes insipidus"],
        "gastritis": ["gastritis"],
    }
    for condition, terms in condition_terms.items():
        if any(term in text for term in terms):
            return condition
    return "general"


def build_condition_context() -> Dict[str, Any]:
    condition_data = PROJECT_ROOT / "Data" / "data-analysis" / "processed"
    candidates = [
        condition_data / "enriched_plants_combined.jsonl",
        PROJECT_ROOT / "Data" / "combined" / "medicinal_plants_combined.jsonl",
    ]
    for candidate in candidates:
        if candidate.exists():
            return {"status": "available", "source": str(candidate)}
    return {"status": "missing", "source": None, "reason": "No processed condition index was found in the existing workspace."}


def retrieve(question: str, collection, bm25: BM25Retriever, top_k: int = TOP_K_FINAL, plant: Optional[str] = None) -> List[Dict[str, Any]]:
    plant_id = None
    if plant:
        plant_id = plant
    vector_results = vector_search(collection, question, plant_id=plant_id, top_k=top_k)
    bm25_results = bm25.search(question, plant_id=plant_id, top_k=top_k)
    fused = reciprocal_rank_fusion([vector_results, bm25_results])
    ranked = sorted(fused, key=lambda item: item["score"], reverse=True)[:top_k]
    return ranked


def build_context(retrieval_result: List[Dict[str, Any]]) -> str:
    parts = []
    for idx, item in enumerate(retrieval_result, start=1):
        meta = item.get("metadata", {})
        chunk = item.get("document", "")
        parts.append(
            f"SOURCE {idx}\n"
            f"Plant ID: {meta.get('plant_id', '')}\n"
            f"Plant Name: {meta.get('plant_name', '')}\n"
            f"Botanical Name: {meta.get('botanical_name', '')}\n"
            f"Family: {meta.get('family', '')}\n"
            f"Section: {meta.get('section', '')}\n"
            f"Chunk ID: {meta.get('chunk_id', '')}\n\n{chunk}\n"
        )
    return "\n---\n".join(parts)


def generate_answer(question: str, context: str) -> str:
    if not question or not question.strip():
        return "Please provide a valid question."
    if not context or not context.strip():
        return "The available database records do not provide sufficient information to answer this question."

    prompt = f"""RETRIEVED DATABASE CONTEXT:
{context}

USER QUESTION:
{question}

FINAL ANSWER INSTRUCTIONS:
Answer only the question, using the retrieved context for factual claims about plants. If the question names a plant but the context does not contain matching records for that plant, do not use records about other plants. Preserve the meaning of the records. If only a broad category is given, say that the exact medicinal application is not specified. Do not expose source IDs, chunk IDs, or metadata. When the context is insufficient, respond exactly: "The available database records do not provide sufficient information to answer this question."

For botanical-name and family questions, give the matching name or family directly. For medicinal-use and plant-part questions, include only details documented in the matching records. For general plant questions, give a short overview based on the available context.

Return only the final answer in plain text, using complete sentences in short paragraphs. Do not use bullets, numbered lists, headings, tables, or Markdown. Keep the answer concise and directly relevant."""
    answer = generate_text(prompt)
    if not answer:
        return "Unable to generate an answer at this time. Please try again."
    return answer


def build_api_app():
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is not installed.") from exc

    app = FastAPI(title="Medicinal Plants RAG API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root() -> Dict[str, str]:
        return {"status": "ok", "service": "Medicinal Plants RAG"}

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat")
    def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
        question = str(payload.get("question") or "").strip()
        top_k = int(payload.get("top_k") or TOP_K_FINAL)
        if not question:
            return {"success": False, "error": "Question is required."}
        db_path = find_chroma_db_path()
        client = chromadb.PersistentClient(path=str(db_path))
        collection = client.get_collection(name=find_collection_name(db_path))
        catalog = build_plant_catalog(collection)
        resolved = resolve_plant(question, catalog)
        qtype = "plant" if resolved else "general"
        ranked = retrieve(question, collection, BM25Retriever(collection), top_k=top_k, plant=resolved.get("plant_id") if resolved else None)
        context = build_context(ranked)
        answer = generate_answer(question, context)
        sources = []
        seen_sources = set()
        for item in ranked:
            metadata = item.get("metadata", {})
            plant_name = str(
                metadata.get("plant_name") or metadata.get("botanical_name") or ""
            ).strip()
            section = str(metadata.get("section") or "").strip()
            label = " — ".join(value for value in (plant_name, section) if value)
            if label and label not in seen_sources:
                sources.append(label)
                seen_sources.add(label)
        return {
            "success": True,
            "question": question,
            "query_type": qtype,
            "identified_plant": resolved,
            "answer": answer,
            "sources": sources,
        }

    return app


if __name__ == "__main__":
    app = build_api_app()
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
