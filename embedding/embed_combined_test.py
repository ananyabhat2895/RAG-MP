"""Embed isolated combined chunks into a new test-only Chroma database."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import chromadb
import ollama


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHUNKS = ROOT / "DataExtraction" / "chunks_combined_test"
DEFAULT_VECTOR_DB = ROOT / "vector_db_combined_test"
MODEL = "qwen3-embedding:0.6b"
COLLECTION = "medicinal_plants_combined_test"
BATCH_SIZE = 32


def embedding_text(chunk: dict[str, Any]) -> str:
    return "\n".join([
        f"Plant Name: {chunk.get('plant_name', '')}",
        f"Botanical Name: {chunk.get('botanical_name', '')}",
        f"Botanical Authority: {chunk.get('botanical_authority', '')}",
        f"Family: {chunk.get('family', '')}",
        f"Section: {chunk.get('section', '')}",
        "",
        "Content:",
        str(chunk.get("content", "")),
    ]).strip()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def metadata(chunk: dict[str, Any], content_hash: str) -> dict[str, str]:
    sepasal = chunk.get("sepasal", {})
    source = chunk.get("sepasal_source", {})
    return {
        "chunk_id": safe(chunk.get("chunk_id")),
        "plant_id": safe(chunk.get("plant_id")),
        "plant_name": safe(chunk.get("plant_name")),
        "botanical_name": safe(chunk.get("botanical_name")),
        "family": safe(chunk.get("family")),
        "section": safe(chunk.get("section")),
        "content_hash": content_hash,
        "sepasal_source_name": safe(source.get("name")),
        "sepasal_license": safe(source.get("license")),
        "sepasal_attribution": safe(source.get("attribution")),
        "sepasal_tax_key": safe(sepasal.get("tax_key")),
        "sepasal_use_category": safe(sepasal.get("use_category")),
        "sepasal_references": safe(sepasal.get("references", [])),
        "sepasal_source_record_id": safe(sepasal.get("source_record_id")),
        "sepasal_source_file": safe(sepasal.get("source_file")),
    }


def chunk_files(directory: Path) -> Iterable[Path]:
    return (
        path for path in sorted(directory.glob("*.json"))
        if path.name not in {"index.json", "chunk_validation.json"}
    )


def batches(items: Iterable[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def load_batch(paths: list[Path]) -> list[dict[str, Any]]:
    chunks = []
    for path in paths:
        chunk = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(chunk, dict) or not chunk.get("chunk_id") or not str(chunk.get("content", "")).strip():
            raise ValueError(f"Invalid chunk: {path}")
        chunks.append(chunk)
    return chunks


def main(args: argparse.Namespace) -> None:
    if not args.chunks.exists():
        raise FileNotFoundError(args.chunks)
    test = ollama.embed(model=MODEL, input="combined dataset embedding availability test")
    dimensions = len(test.get("embeddings", [[]])[0])
    if not dimensions:
        raise RuntimeError(f"Ollama returned no embedding for {MODEL}")

    client = chromadb.PersistentClient(path=str(args.vector_db))
    collection = client.get_or_create_collection(
        name=args.collection,
        metadata={"description": "Isolated combined IMPPAT + SEPASAL test embeddings", "embedding_model": MODEL},
    )
    embedded = 0
    skipped = 0
    seen = set()
    for paths in batches(list(chunk_files(args.chunks)), args.batch_size):
        chunks = load_batch(paths)
        ids = [chunk["chunk_id"] for chunk in chunks]
        if seen.intersection(ids):
            raise ValueError("Duplicate chunk IDs in source directory")
        seen.update(ids)
        existing = collection.get(ids=ids, include=["metadatas"])
        existing_hashes = {
            item_id: meta.get("content_hash")
            for item_id, meta in zip(existing.get("ids", []), existing.get("metadatas", []))
            if meta
        }
        pending = []
        for chunk in chunks:
            text = embedding_text(chunk)
            content_hash = hash_text(text)
            if existing_hashes.get(chunk["chunk_id"]) == content_hash:
                skipped += 1
            else:
                pending.append((chunk, text, content_hash))
        if not pending:
            continue
        texts = [item[1] for item in pending]
        response = ollama.embed(model=MODEL, input=texts)
        vectors = response.get("embeddings", [])
        if len(vectors) != len(pending):
            raise RuntimeError(f"Ollama returned {len(vectors)} embeddings for {len(pending)} chunks")
        collection.upsert(
            ids=[item[0]["chunk_id"] for item in pending],
            embeddings=vectors,
            documents=texts,
            metadatas=[metadata(item[0], item[2]) for item in pending],
        )
        embedded += len(pending)

    print(json.dumps({
        "model": MODEL,
        "vector_db": str(args.vector_db),
        "collection": args.collection,
        "chunk_files_seen": len(seen),
        "embedded_now": embedded,
        "skipped_unchanged": skipped,
        "collection_count": collection.count(),
        "embedding_dimension": dimensions,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--vector-db", type=Path, default=DEFAULT_VECTOR_DB)
    parser.add_argument("--collection", default=COLLECTION)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    main(parser.parse_args())
