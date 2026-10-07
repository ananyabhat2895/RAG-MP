import os
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

import ollama
import chromadb
from tqdm import tqdm


# ============================================================
# CONFIGURATION
# ============================================================

# This script lives in the embedding directory:
#
# medicinal-plants-rag/
# ├── DataExtraction/
# │   └── chunks/
# ├── embedding/
# │   └── embed.py
# └── vector_db/          <-- created automatically

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
CHUNKS_DIR = PROJECT_ROOT / "DataExtraction" / "chunks"
VECTOR_DB_DIR = PROJECT_ROOT / "vector_db"

COLLECTION_NAME = "medicinal_plants"

# IMPORTANT:
# This is the embedding model, NOT the Qwen3 8B chat model.
EMBEDDING_MODEL = "qwen3-embedding:0.6b"

# Number of chunks sent to Ollama at a time.
BATCH_SIZE = 32

# Number of nearest chunks to retrieve during validation.
TOP_K = 5


# ============================================================
# HELPERS
# ============================================================

def normalize_value(value: Any) -> str:
    """Convert metadata values into strings safe for ChromaDB."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def make_embedding_text(chunk: Dict[str, Any]) -> str:
    """
    Build the text that will actually be embedded.

    We embed the useful searchable plant information plus the
    complete chunk content. Source metadata is preserved separately.
    """
    parts = [
        f"Plant Name: {chunk.get('plant_name', '')}",
        f"Botanical Name: {chunk.get('botanical_name', '')}",
        f"Botanical Authority: {chunk.get('botanical_authority', '')}",
        f"Family: {chunk.get('family', '')}",
        f"Section: {chunk.get('section', '')}",
        "",
        "Content:",
        str(chunk.get("content", "")),
    ]

    return "\n".join(parts).strip()


def make_metadata(chunk: Dict[str, Any], content_hash: str) -> Dict[str, str]:
    """
    Preserve the chunk's important metadata.

    ChromaDB metadata values must be primitive values, so lists/dicts
    are stored as JSON strings rather than nested structures.
    """
    source_metadata = chunk.get("source_metadata", {})

    metadata = {
        "plant_id": normalize_value(chunk.get("plant_id")),
        "plant_name": normalize_value(chunk.get("plant_name")),
        "botanical_name": normalize_value(chunk.get("botanical_name")),
        "botanical_authority": normalize_value(
            chunk.get("botanical_authority")
        ),
        "family": normalize_value(chunk.get("family")),
        "section": normalize_value(chunk.get("section")),

        "source_urls": normalize_value(chunk.get("source_urls", [])),
        "source_record_ids": normalize_value(
            chunk.get("source_record_ids", [])
        ),

        # Useful nested source information flattened into JSON strings.
        "source_xplant_id": normalize_value(
            source_metadata.get("source_xplant_id")
        ),
        "source_metadata_json": normalize_value(source_metadata),

        # Used to detect whether a chunk changed.
        "content_hash": content_hash,
    }

    # Keep additional top-level fields, if they exist.
    # This makes the script tolerant of future chunk metadata.
    reserved = {
        "chunk_id",
        "content",
        "source_metadata",
        "plant_id",
        "plant_name",
        "botanical_name",
        "botanical_authority",
        "family",
        "section",
        "source_urls",
        "source_record_ids",
    }

    for key, value in chunk.items():
        if key not in reserved:
            safe_key = f"extra_{key}"
            metadata[safe_key] = normalize_value(value)

    return metadata


def calculate_hash(text: str) -> str:
    """Create a stable hash for duplicate/change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_chunks() -> List[Tuple[Path, Dict[str, Any]]]:
    """Recursively load all JSON chunk files."""
    if not CHUNKS_DIR.exists():
        raise FileNotFoundError(
            f"Chunks directory not found: {CHUNKS_DIR}\n"
            "Make sure this script is in your project root and "
            "your chunk files are inside a 'chunks' folder."
        )

    files = sorted(CHUNKS_DIR.rglob("*.json"))

    if not files:
        raise FileNotFoundError(
            f"No JSON files found inside: {CHUNKS_DIR}"
        )

    loaded = []
    errors = []

    for file_path in files:
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Support either:
            # 1. one chunk per JSON file
            # 2. a JSON file containing a list of chunks
            if isinstance(data, dict):
                chunks = [data]
            elif isinstance(data, list):
                chunks = data
            else:
                raise ValueError("JSON root must be an object or list.")

            for chunk in chunks:
                if not isinstance(chunk, dict):
                    raise ValueError("Chunk must be a JSON object.")

                chunk_id = chunk.get("chunk_id")
                content = chunk.get("content")

                if not chunk_id:
                    raise ValueError("Missing 'chunk_id'.")

                if content is None or not str(content).strip():
                    raise ValueError("Missing or empty 'content'.")

                loaded.append((file_path, chunk))

        except Exception as e:
            errors.append((file_path, str(e)))

    if errors:
        print("\nWARNING: Some files could not be loaded:")
        for path, error in errors:
            print(f"  - {path}: {error}")

    return loaded


def get_existing_hashes(
    collection,
    chunk_ids: List[str],
) -> Dict[str, str]:
    """
    Retrieve existing hashes for the supplied IDs.

    This allows unchanged chunks to be skipped.
    """
    if not chunk_ids:
        return {}

    existing = collection.get(
        ids=chunk_ids,
        include=["metadatas"],
    )

    ids = existing.get("ids", [])
    metadatas = existing.get("metadatas", [])

    result = {}

    for chunk_id, metadata in zip(ids, metadatas):
        if metadata and metadata.get("content_hash"):
            result[chunk_id] = metadata["content_hash"]

    return result


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings through the local Ollama server.

    If a batch fails, retry one text at a time so a single problematic
    chunk does not stop the entire pipeline.
    """
    try:
        response = ollama.embed(
            model=EMBEDDING_MODEL,
            input=texts,
        )

        embeddings = response.get("embeddings", [])

        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Ollama returned {len(embeddings)} embeddings "
                f"for {len(texts)} inputs."
            )

        return embeddings

    except Exception as batch_error:
        print(
            f"\nBatch embedding failed. Retrying individual chunks.\n"
            f"Reason: {batch_error}"
        )

        embeddings = []

        for text in texts:
            response = ollama.embed(
                model=EMBEDDING_MODEL,
                input=text,
            )

            one = response.get("embeddings", [])

            if not one:
                raise RuntimeError(
                    "Ollama returned no embedding for a chunk."
                )

            embeddings.append(one[0])

        return embeddings


def validate_collection(collection) -> None:
    """Validate IDs, documents, metadata and embedding dimensions."""
    count = collection.count()

    print("\n" + "=" * 60)
    print("CHROMADB VALIDATION")
    print("=" * 60)
    print(f"Total chunks stored: {count}")

    if count == 0:
        raise RuntimeError("ChromaDB collection is empty.")

    sample = collection.get(
        limit=min(5, count),
        include=["documents", "metadatas", "embeddings"],
    )

    ids = sample.get("ids", [])
    documents = sample.get("documents", [])
    metadatas = sample.get("metadatas", [])
    embeddings = sample.get("embeddings", [])

    print(f"Sample IDs preserved: {len(ids) == len(documents) == len(metadatas)}")

    if embeddings is not None and len(embeddings) > 0:
        dimensions = {
            len(vector)
            for vector in embeddings
            if vector is not None
        }

        print(f"Embedding dimensions found in sample: {dimensions}")

        if len(dimensions) != 1:
            raise RuntimeError(
                "Inconsistent embedding dimensions detected."
            )

        print(f"Embedding dimension: {next(iter(dimensions))}")
    else:
        print("WARNING: Embeddings were not returned in the sample.")

    required_metadata = [
        "plant_id",
        "botanical_name",
        "family",
        "section",
    ]

    for key in required_metadata:
        present = all(key in metadata for metadata in metadatas)
        print(f"Metadata '{key}' preserved: {present}")


def similarity_search(collection, question: str, top_k: int = TOP_K) -> None:
    """Embed a question and retrieve the closest chunks."""
    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=question,
    )

    query_embedding = response["embeddings"][0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    print("\n" + "=" * 70)
    print(f"QUERY: {question}")
    print("=" * 70)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, (document, metadata, distance) in enumerate(
        zip(documents, metadatas, distances),
        start=1,
    ):
        print(f"\n--- Result {i} ---")
        print(f"Distance: {distance}")
        print(f"Chunk ID: {metadata.get('chunk_id', 'stored as Chroma ID')}")

        print(f"Plant: {metadata.get('plant_name', '')}")
        print(f"Botanical Name: {metadata.get('botanical_name', '')}")
        print(f"Family: {metadata.get('family', '')}")
        print(f"Section: {metadata.get('section', '')}")

        print("\nRetrieved content:")
        print(document[:1200])

        if len(document) > 1200:
            print("...")


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    print("=" * 60)
    print("MEDICINAL PLANTS - EMBEDDING + CHROMADB PIPELINE")
    print("=" * 60)

    print(f"\nChunks directory: {CHUNKS_DIR}")
    print(f"Vector database:  {VECTOR_DB_DIR}")
    print(f"Embedding model:  {EMBEDDING_MODEL}")
    print(f"Batch size:       {BATCH_SIZE}")

    # --------------------------------------------------------
    # 1. Check Ollama/model
    # --------------------------------------------------------
    print("\nChecking Ollama embedding model...")

    try:
        test_response = ollama.embed(
            model=EMBEDDING_MODEL,
            input="Ollama embedding test."
        )

        test_embeddings = test_response.get("embeddings", [])

        if not test_embeddings:
            raise RuntimeError("No embedding returned by Ollama.")

        embedding_dimension = len(test_embeddings[0])

        print("Ollama connection: OK")
        print(f"Embedding dimension: {embedding_dimension}")

    except Exception as e:
        raise RuntimeError(
            "\nCould not connect to the embedding model.\n"
            f"Make sure Ollama is running and this model exists:\n"
            f"  {EMBEDDING_MODEL}\n\n"
            f"Try:\n"
            f"  ollama list\n"
            f"  ollama pull {EMBEDDING_MODEL}\n\n"
            f"Original error: {e}"
        ) from e

    # --------------------------------------------------------
    # 2. Load chunks
    # --------------------------------------------------------
    print("\nLoading chunk files...")

    loaded_chunks = load_chunks()

    print(f"Chunks loaded: {len(loaded_chunks)}")

    # --------------------------------------------------------
    # 3. Open persistent ChromaDB
    # --------------------------------------------------------
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(VECTOR_DB_DIR)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": "Medicinal plant RAG embeddings",
            "embedding_model": EMBEDDING_MODEL,
        },
    )

    print(f"ChromaDB collection: {COLLECTION_NAME}")
    print(f"Existing records: {collection.count()}")

    # --------------------------------------------------------
    # 4. Determine which chunks need embedding
    # --------------------------------------------------------
    print("\nChecking for existing/unchanged chunks...")

    all_ids = [chunk["chunk_id"] for _, chunk in loaded_chunks]

    # Detect duplicate chunk IDs in input.
    seen = set()
    duplicate_ids = set()

    for chunk_id in all_ids:
        if chunk_id in seen:
            duplicate_ids.add(chunk_id)
        seen.add(chunk_id)

    if duplicate_ids:
        raise RuntimeError(
            "Duplicate chunk_id values found in input:\n"
            + "\n".join(sorted(duplicate_ids)[:20])
        )

    existing_hashes = {}

    # Query in manageable groups.
    for start in range(0, len(all_ids), BATCH_SIZE):
        batch_ids = all_ids[start:start + BATCH_SIZE]
        existing_hashes.update(
            get_existing_hashes(collection, batch_ids)
        )

    to_process = []
    unchanged_count = 0

    for file_path, chunk in loaded_chunks:
        chunk_id = chunk["chunk_id"]

        embedding_text = make_embedding_text(chunk)
        content_hash = calculate_hash(embedding_text)

        if existing_hashes.get(chunk_id) == content_hash:
            unchanged_count += 1
            continue

        metadata = make_metadata(chunk, content_hash)

        to_process.append(
            {
                "file_path": file_path,
                "chunk": chunk,
                "chunk_id": chunk_id,
                "embedding_text": embedding_text,
                "metadata": metadata,
            }
        )

    print(f"Unchanged chunks skipped: {unchanged_count}")
    print(f"Chunks requiring embedding: {len(to_process)}")

    # --------------------------------------------------------
    # 5. Generate embeddings + store in ChromaDB
    # --------------------------------------------------------
    embedded_count = 0
    error_count = 0

    if to_process:
        print("\nGenerating embeddings and storing in ChromaDB...")

        progress = tqdm(
            range(0, len(to_process), BATCH_SIZE),
            desc="Embedding batches",
            unit="batch",
        )

        for start in progress:
            batch = to_process[start:start + BATCH_SIZE]

            texts = [item["embedding_text"] for item in batch]

            try:
                embeddings = embed_batch(texts)

                ids = [item["chunk_id"] for item in batch]
                documents = texts
                metadatas = [item["metadata"] for item in batch]

                # upsert allows both new records and changed records.
                collection.upsert(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )

                embedded_count += len(batch)

                progress.set_postfix(
                    stored=collection.count()
                )

            except Exception as e:
                error_count += len(batch)

                print(
                    f"\nERROR processing batch starting at index "
                    f"{start}: {e}"
                )

                for item in batch:
                    print(f"  Failed chunk: {item['chunk_id']}")

    # --------------------------------------------------------
    # 6. Final validation
    # --------------------------------------------------------
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    print(f"Input chunks:              {len(loaded_chunks)}")
    print(f"New/changed chunks:        {embedded_count}")
    print(f"Unchanged chunks skipped:  {unchanged_count}")
    print(f"Batch errors:              {error_count}")
    print(f"Total ChromaDB records:    {collection.count()}")

    validate_collection(collection)

    # --------------------------------------------------------
    # 7. Sample retrieval tests
    # --------------------------------------------------------
    test_questions = [
        "What are the Kannada names of Acacia arabica?",
        "What is the family of Acacia arabica?",
        "What is the botanical correlation of आभाबब्बूलक?",
    ]

    print("\n" + "=" * 60)
    print("SAMPLE SIMILARITY SEARCHES")
    print("=" * 60)

    for question in test_questions:
        try:
            similarity_search(
                collection,
                question,
                TOP_K,
            )
        except Exception as e:
            print(f"\nSearch failed for '{question}': {e}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Persistent vector database: {VECTOR_DB_DIR}")
    print("Your raw, cleaned and chunked data was not modified.")


if __name__ == "__main__":
    main()