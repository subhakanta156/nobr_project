import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# Path to your saved FAISS vectorstore
VECTORSTORE_DIR = "../vectorStore"

def query_faiss():
    # Load embeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Load FAISS vectorstore
    db = FAISS.load_local(VECTORSTORE_DIR, embeddings, allow_dangerous_deserialization=True)

    print("✅ FAISS vectorstore loaded successfully.")
    print(f"Total chunks in DB: {len(db.docstore._dict)}")

    while True:
        query = input("\nEnter your query (or type 'exit' to quit): ").strip()
        if query.lower() == "exit":
            print("Exiting...")
            break

        # Perform similarity search
        results = db.similarity_search(query, k=5)  # top 5 results

        if not results:
            print("❌ No matching documents found.")
        else:
            print(f"\n🔹 Top {len(results)} matches:")
            for i, doc in enumerate(results, 1):
                # Print metadata + first 200 chars of content
                content_preview = doc.page_content[:200].replace("\n", " ")
                print(f"{i}. {content_preview}")
                print(f"   Metadata: {doc.metadata}\n")

if __name__ == "__main__":
    query_faiss()
