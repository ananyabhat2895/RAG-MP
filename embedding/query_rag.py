from pathlib import Path
import chromadb
import ollama

BASE_DIR = Path(__file__).resolve().parent.parent
VECTOR_DB_DIR = BASE_DIR / "vector_db"

COLLECTION_NAME = "medicinal_plants"
EMBEDDING_MODEL = "qwen3-embedding:0.6b"
LLM_MODEL = "qwen3:8b"
TOP_K = 5

client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
collection = client.get_collection(name=COLLECTION_NAME)

print(f"Connected to ChromaDB. Stored chunks: {collection.count()}")


def retrieve_chunks(question: str, top_k: int = TOP_K):
    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=question
    )
    query_embedding = response["embeddings"][0]

    return collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )


def build_context(results):
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    parts = []

    for i, (document, metadata, distance) in enumerate(
        zip(documents, metadatas, distances), start=1
    ):
        parts.append(f"""
SOURCE {i}
Plant Name: {metadata.get("plant_name", "")}
Botanical Name: {metadata.get("botanical_name", "")}
Family: {metadata.get("family", "")}
Section: {metadata.get("section", "")}
Chunk ID: {metadata.get("chunk_id", "")}
Distance: {distance}
Source URL(s): {metadata.get("source_urls", "")}

Content:
{document}
""")

    return "\n".join(parts)


def generate_answer(question: str, context: str):
    prompt = f"""
You are a medicinal-plants information assistant.

Answer the user's question using ONLY the provided context.

Rules:
1. Do not invent facts that are not present in the context.
2. If the context does not contain enough information, say that
   you could not find enough information in the provided database.
3. Give a concise, clear answer.
4. Preserve botanical names exactly when relevant.
5. Do not provide diagnosis, treatment instructions, or personalized
   medical advice.

CONTEXT:
{context}

USER QUESTION:
{question}

ANSWER:
"""

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1}
    )

    return response["message"]["content"]


def display_retrieved_chunks(results):
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    print("\n" + "=" * 70)
    print("RETRIEVED CHUNKS")
    print("=" * 70)

    for i, (document, metadata, distance) in enumerate(
        zip(documents, metadatas, distances), start=1
    ):
        print(f"\n--- RESULT {i} ---")
        print(f"Distance: {distance}")
        print(f"Chunk ID: {metadata.get('chunk_id', '')}")
        print(f"Plant: {metadata.get('plant_name', '')}")
        print(f"Botanical Name: {metadata.get('botanical_name', '')}")
        print(f"Family: {metadata.get('family', '')}")
        print(f"Section: {metadata.get('section', '')}")
        print("\nContent:")
        print(document[:1500])
        if len(document) > 1500:
            print("...")


def main():
    print("\n" + "=" * 70)
    print("MEDICINAL PLANTS RAG - QWEN3 8B")
    print("=" * 70)
    print("Type your question. Type 'exit' to stop.\n")

    while True:
        question = input("You: ").strip()

        if question.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        if not question:
            continue

        try:
            results = retrieve_chunks(question)
            display_retrieved_chunks(results)

            context = build_context(results)

            print("\n" + "=" * 70)
            print("QWEN3 8B ANSWER")
            print("=" * 70)

            answer = generate_answer(question, context)
            print("\n" + answer)

        except Exception as e:
            print("\nERROR:")
            print(e)
            print("\nCheck that Ollama is running and these models exist:")
            print(f"  {EMBEDDING_MODEL}")
            print(f"  {LLM_MODEL}")


if __name__ == "__main__":
    main()