"""Embed Chunk JSON files into a persistent ChromaDB collection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

import chromadb
import ollama


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHUNKS = ROOT / "Chunk" / "chunks"
DEFAULT_VECTOR_DB = Path(__file__).resolve().parent / "chroma_db"
MODEL = "qwen3-embedding:0.6b"
COLLECTION = "medicinal_plants"
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


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def metadata_for(chunk: dict[str, Any], digest: str) -> dict[str, str]:
    return {
        "chunk_id": str(chunk["chunk_id"]),
        "plant_id": str(chunk["plant_id"]),
        "plant_name": str(chunk.get("plant_name") or ""),
        "botanical_name": str(chunk.get("botanical_name") or ""),
        "botanical_authority": str(chunk.get("botanical_authority") or ""),
        "family": str(chunk.get("family") or ""),
        "section": str(chunk.get("section") or ""),
        "source_urls": json.dumps(
            chunk.get("source_urls", []), ensure_ascii=False
        ),
        "source_record_ids": json.dumps(
            chunk.get("source_record_ids", []), ensure_ascii=False
        ),
        "content_hash": digest,
    }


def load_batches(
    chunks_dir: Path,
    batch_size: int,
) -> Iterator[list[dict[str, Any]]]:
    files = sorted(chunks_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No plant chunk JSON files found in {chunks_dir}")

    batch: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in {path}: {error}") from error
        if not isinstance(data, list):
            raise ValueError(f"Expected a JSON array in {path}.")

        for chunk in data:
            if not isinstance(chunk, dict):
                raise ValueError(f"Expected a chunk object in {path}.")
            chunk_id = chunk.get("chunk_id")
            plant_id = chunk.get("plant_id")
            if not chunk_id or not plant_id:
                raise ValueError(f"Chunk is missing chunk_id or plant_id in {path}.")
            if str(plant_id) != path.stem:
                raise ValueError(
                    f"Chunk plant_id {plant_id!r} does not match file {path.name}."
                )
            if chunk_id in seen_ids:
                raise ValueError(f"Duplicate chunk_id: {chunk_id}")
            if not str(chunk.get("content") or "").strip():
                raise ValueError(f"Chunk has empty content: {chunk_id}")

            seen_ids.add(chunk_id)
            batch.append(chunk)
            if len(batch) == batch_size:
                yield batch
                batch = []

    if batch:
        yield batch


def embed_chunks(
    chunks_dir: Path,
    vector_db_dir: Path,
    collection_name: str,
    batch_size: int,
) -> None:
    if batch_size < 1:
        raise ValueError("Batch size must be at least 1.")

    if not chunks_dir.is_dir():
        raise FileNotFoundError(f"Chunk directory not found: {chunks_dir}")

    test_response = ollama.embed(
        model=MODEL,
        input="Embedding availability check.",
    )
    test_vectors = test_response.get("embeddings", [])
    if len(test_vectors) != 1 or not test_vectors[0]:
        raise RuntimeError(f"Ollama returned no test embedding for {MODEL}.")
    dimensions = len(test_vectors[0])

    client = chromadb.PersistentClient(path=str(vector_db_dir))
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={
            "description": "Medicinal plant chunk embeddings",
            "embedding_model": MODEL,
        },
    )

    embedded = 0
    skipped = 0
    chunks_seen = 0
    for batch_number, batch in enumerate(
        load_batches(chunks_dir, batch_size), start=1
    ):
        chunks_seen += len(batch)
        ids = [str(chunk["chunk_id"]) for chunk in batch]
        existing = collection.get(ids=ids, include=["metadatas"])
        existing_hashes = {
            chunk_id: item_metadata.get("content_hash")
            for chunk_id, item_metadata in zip(
                existing.get("ids", []), existing.get("metadatas", [])
            )
            if item_metadata
        }

        pending = []
        for chunk in batch:
            text = embedding_text(chunk)
            digest = content_hash(text)
            if existing_hashes.get(str(chunk["chunk_id"])) == digest:
                skipped += 1
            else:
                pending.append((chunk, text, digest))

        if pending:
            response = ollama.embed(
                model=MODEL,
                input=[item[1] for item in pending],
            )
            vectors = response.get("embeddings", [])
            if len(vectors) != len(pending):
                raise RuntimeError(
                    f"Ollama returned {len(vectors)} embeddings for "
                    f"{len(pending)} chunks in batch {batch_number}."
                )
            if any(len(vector) != dimensions for vector in vectors):
                raise RuntimeError(
                    f"Ollama returned inconsistent vector dimensions in "
                    f"batch {batch_number}; expected {dimensions}."
                )

            collection.upsert(
                ids=[str(item[0]["chunk_id"]) for item in pending],
                embeddings=vectors,
                documents=[item[1] for item in pending],
                metadatas=[
                    metadata_for(item[0], item[2]) for item in pending
                ],
            )
            embedded += len(pending)

        if batch_number % 10 == 0:
            print(
                f"Processed {chunks_seen} chunks; "
                f"embedded {embedded}, skipped unchanged {skipped}."
            )

    total = collection.count()
    if total < chunks_seen:
        raise RuntimeError(
            f"ChromaDB contains {total} records, fewer than the "
            f"{chunks_seen} input chunks."
        )

    print(json.dumps({
        "model": MODEL,
        "embedding_dimension": dimensions,
        "chunks_seen": chunks_seen,
        "embedded_now": embedded,
        "skipped_unchanged": skipped,
        "collection": collection_name,
        "collection_count": total,
        "vector_db": str(vector_db_dir),
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--vector-db", type=Path, default=DEFAULT_VECTOR_DB)
    parser.add_argument("--collection", default=COLLECTION)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()
    embed_chunks(
        args.chunks,
        args.vector_db,
        args.collection,
        args.batch_size,
    )


if __name__ == "__main__":
    main()
