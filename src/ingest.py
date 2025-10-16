import os
import pymongo
import pickle
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from datetime import datetime

# -----------------------------
# 1. Load environment variables
# -----------------------------
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")  # Mongo connection
DB_NAME = os.getenv("DB_NAME", "company_chatbot")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "processed_data")
VECTORSTORE_DIR = "../vectorstore"
os.makedirs(VECTORSTORE_DIR, exist_ok=True)

# -----------------------------
# 2. Connect to MongoDB
# -----------------------------
client = pymongo.MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

# -----------------------------
# 3. Preprocessing helpers
# -----------------------------
def clean_string(val):
    if val is None:
        return ""
    return str(val).replace('"', '').replace("'", '').strip()

def clean_numeric(val):
    try:
        return float(val)
    except:
        return None

def preprocess_document(doc):
    """Convert MongoDB doc to LangChain Document with full structured metadata"""
    project_name = clean_string(doc.get("projectName"))
    project_type = clean_string(doc.get("projectType"))
    project_category = clean_string(doc.get("projectCategory"))
    slug = clean_string(doc.get("slug"))
    status = clean_string(doc.get("status"))
    bhk = clean_string(doc.get("type") or doc.get("customBHK"))
    price = clean_numeric(doc.get("price"))
    carpet_area = clean_numeric(doc.get("carpetArea"))
    bathrooms = clean_numeric(doc.get("bathrooms"))
    balcony = clean_numeric(doc.get("balcony"))
    furnished = clean_string(doc.get("furnishedType"))
    lift = doc.get("lift", False)
    possession_date = clean_string(doc.get("possessionDate"))
    amenities = clean_string(doc.get("aboutProperty"))
    address = clean_string(doc.get("Address info"))

    # Extract city/locality from slug (fallback if missing)
    parts = slug.split("-") if slug else []
    locality = parts[-3].capitalize() if len(parts) >= 3 else ""
    city = parts[-2].capitalize() if len(parts) >= 2 else ""

    # Page content for embeddings (can include any text you want LLM to use)
    content = f"""
    Project Name: {project_name}
    Type: {bhk}
    Status: {status}
    Price: {price}
    Carpet Area: {carpet_area}
    Bathrooms: {bathrooms}
    Balcony: {balcony}
    Furnishing: {furnished}
    Lift: {lift}
    Location: {locality}, {city}
    Address: {address}
    Amenities: {amenities}
    """

    # Structured metadata
    metadata = {
        "id": str(doc.get("_id")),
        "slug": slug,
        "projectName": project_name,
        "projectType": project_type,
        "projectCategory": project_category,
        "status": status,
        "BHK": bhk,
        "price": price,
        "price_in_cr": round(price / 10000000, 2) if price else None,
        "carpetArea": carpet_area,
        "bathrooms": bathrooms,
        "balcony": balcony,
        "furnishedType": furnished,
        "lift": lift,
        "possessionDate": possession_date,
        "city": city,
        "locality": locality,
        "address": address,
        "amenities": amenities,
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt")
    }

    return Document(page_content=" ".join(content.split()), metadata=metadata)


# -----------------------------
# 4. Fetch & preprocess all docs
# -----------------------------
raw_docs = list(collection.find({}))
documents = [preprocess_document(doc) for doc in raw_docs]
print(f"Fetched {len(documents)} documents from MongoDB")

# -----------------------------
# 5. Chunk documents
# -----------------------------
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)
docs = text_splitter.split_documents(documents)
print(f"After chunking → {len(docs)} chunks")

# -----------------------------
# 6. Generate embeddings
# -----------------------------
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = FAISS.from_documents(docs, embedding_model)

# -----------------------------
# 7. Save FAISS index & metadata separately
# -----------------------------
# Save FAISS vectorstore (index + metadata) into the folder
vectorstore.save_local(VECTORSTORE_DIR)
print(f"✅ FAISS vectors and metadata saved in {VECTORSTORE_DIR}")

