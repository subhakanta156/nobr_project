from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# Path of  vectorstore
DB_FAISS_PATH = "../vectorStore"

def check_faiss_index():
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    db = FAISS.load_local(DB_FAISS_PATH, embeddings, allow_dangerous_deserialization=True)

    # Number of vectors stored in index.faiss
    num_vectors = db.index.ntotal

    # Number of documents (with metadata) stored in index.pkl
    num_docs = len(db.docstore._dict)

    print(f"📦 index.faiss contains {num_vectors} vectors")
    print(f"📑 index.pkl contains {num_docs} metadata entries")

if __name__ == "__main__":
    check_faiss_index()
