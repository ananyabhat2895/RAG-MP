from pathlib import Path
import chromadb

# Get the project root
# view.py is inside:
# RAG-MP/embedding/
# so .parent.parent = RAG-MP/
BASE_DIR = Path(__file__).resolve().parent.parent

VECTOR_DB_DIR = BASE_DIR / "vector_db"

print("Connecting to:")
print(VECTOR_DB_DIR)

# Connect to the SAME ChromaDB used by embed.py
client = chromadb.PersistentClient(
    path=str(VECTOR_DB_DIR)
)

# Show available collections
print("\nAvailable collections:")

collections = client.list_collections()

for collection in collections:
    print(" -", collection.name)

# Get your collection
collection = client.get_collection(
    name="medicinal_plants"
)

print("\nTotal records:", collection.count())

# Get one record
result = collection.get(
    limit=1,
    include=[
        "documents",
        "metadatas",
        "embeddings"
    ]
)

print("\n" + "=" * 60)
print("EMBEDDING DETAILS")
print("=" * 60)

print("\nChunk ID:")
print(result["ids"][0])

print("\nDocument:")
print(result["documents"][0])

print("\nMetadata:")
print(result["metadatas"][0])

embedding = result["embeddings"][0]

print("\nEmbedding dimension:")
print(len(embedding))

print("\nFirst 20 embedding values:")
print(embedding[:20])

print("\nComplete embedding:")
print(embedding)