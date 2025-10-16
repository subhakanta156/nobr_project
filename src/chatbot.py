# chatbot.py
import os
import re
import json
from typing import Dict, Any, List, Tuple, Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import HumanMessage
from langchain_groq import ChatGroq   # groq LLM wrapper
from langchain.schema import Document
from dotenv import load_dotenv
load_dotenv()

# -------- Safe absolute path ----------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
VECTORSTORE_DIR = os.getenv("VECTORSTORE_DIR", os.path.join(PROJECT_ROOT, "vectorStore"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Load embeddings & vectorstore
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
faiss_index_path = os.path.join(VECTORSTORE_DIR, "index.faiss")
if not os.path.exists(faiss_index_path):
    raise FileNotFoundError(f"FAISS index not found at {faiss_index_path}")
db = FAISS.load_local(VECTORSTORE_DIR, embeddings, allow_dangerous_deserialization=True)

# Instantiate Groq LLM

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.1-8b-instant"  
)
# ---------------------------
# 1) Query parsing helpers
# ---------------------------
def parse_budget(text: str) -> Optional[float]:
    """
    Parse budgets like:
      - "under ₹1.2 Cr" -> returns numeric rupees (float) e.g. 12000000
      - "under 1.2cr", "under 12000000"
    Returns numeric rupee value or None.
    """
    if not text:
        return None
    s = text.replace(",", "").lower()
    # find ₹ or rupee symbols and numbers
    m = re.search(r"under\s*[₹rs\.]*\s*([0-9]+(?:\.[0-9]+)?)\s*(cr|crore|l|lakhs|lakh|k)?", s)
    if m:
        num = float(m.group(1))
        unit = (m.group(2) or "").lower()
        if unit in ("cr", "crore"):
            return num * 1e7
        if unit in ("l", "lakh", "lakhs"):
            return num * 1e5
        if unit in ("k",):
            return num * 1e3
        # if no unit assume rupees raw
        return num
    # alternative: find direct rupee integers like 12000000
    m2 = re.search(r"([0-9]{6,})", s)
    if m2:
        return float(m2.group(1))
    return None


def parse_bhk(text: str) -> Optional[str]:
    """Return like '2BHK' or '3BHK' if mentioned."""
    if not text:
        return None
    m = re.search(r"(\d+)\s*-?\s*bhk", text.lower())
    if m:
        return f"{m.group(1)}BHK"
    return None


def parse_city(text: str) -> Optional[str]:
    """Very simple city detection — looks for common city names in text."""
    if not text:
        return None
    s = text.lower()
    # extend this list as you need
    cities = ["pune", "mumbai", "delhi", "bangalore", "bangaluru", "chennai", "hyderabad", "kolkata"]
    for c in cities:
        if c in s:
            # standardize "bangaluru" -> "Bangalore" etc if you prefer
            return c.capitalize() if c != "bangaluru" else "Bangalore"
    return None


def parse_status(text: str) -> Optional[str]:
    """Detect readiness intents"""
    s = text.lower()
    if "ready" in s or "ready to move" in s or "ready-to-move" in s:
        return "READY_TO_MOVE"
    if "under construction" in s or "uc" in s or "under-construction" in s:
        return "UNDER_CONSTRUCTION"
    return None


def parse_locality_or_project(text: str) -> Optional[str]:
    """Pick up locality words (heuristic). Returns substring if found after 'in' or 'near'."""
    if not text:
        return None
    m = re.search(r"(?:in|near|at)\s+([a-zA-Z0-9\- ]{3,30})", text.lower())
    if m:
        return m.group(1).strip().title()
    return None


def parse_query(query: str) -> Dict[str, Any]:
    """Aggregate all parsed filters."""
    return {
        "raw": query,
        "budget_rupees": parse_budget(query),
        "bhk": parse_bhk(query),
        "city": parse_city(query),
        "status": parse_status(query),
        "locality_or_project": parse_locality_or_project(query),
    }


# ---------------------------
# 2) Search + deterministic filter
# ---------------------------
def semantic_search(query: str, k: int = 10) -> List[Document]:
    """
    Run similarity search over FAISS and return top-k Document objects.
    """
    return db.similarity_search(query, k=k)


def apply_filters(docs: List[Document], filters: Dict[str, Any]) -> List[Document]:
    """Filter retrieved docs using structured metadata (price, city, BHK, status, locality)."""
    budget = filters.get("budget_rupees")
    bhk = filters.get("bhk")
    city = filters.get("city")
    status = filters.get("status")
    locality = filters.get("locality_or_project")

    def keep(doc: Document) -> bool:
        md = doc.metadata or {}
        # city filter
        if city:
            md_city = (md.get("city") or "").lower()
            if city.lower() not in md_city:
                return False
        # bhk filter
        if bhk:
            md_bhk = (md.get("BHK") or md.get("bhk") or "").lower()
            if bhk.lower() not in md_bhk:
                return False
        # price filter (budget_rupees)
        if budget is not None:
            price = md.get("price") or md.get("price_in_cr")
            if price is None:
                return False
            # price might be stored either in rupees (price) or in crores (price_in_cr)
            if md.get("price") is not None:
                try:
                    if float(md.get("price")) > float(budget):
                        return False
                except:
                    return False
            else:
                # price_in_cr present
                try:
                    if float(md.get("price_in_cr")) * 1e7 > float(budget):
                        return False
                except:
                    return False
        # status filter
        if status:
            md_status = (md.get("status") or "").lower()
            if status.lower() not in md_status:
                return False
        # locality filter — check in metadata locality or address or slug
        if locality:
            found = False
            for key in ("locality", "address", "slug", "projectName"):
                if key in md and md.get(key):
                    if locality.lower() in str(md.get(key)).lower():
                        found = True
                        break
            if not found:
                return False
        return True

    filtered = [d for d in docs if keep(d)]
    return filtered


# ---------------------------
# 3) Create summary + cards input (no hallucination)
# ---------------------------
def build_context_for_llm(docs: List[Document]) -> str:
    """
    Build a compact, plain text context from the retrieved docs.
    We'll pass this to Groq LLM and instruct it to only use this data.
    """
    lines = []
    for i, d in enumerate(docs, 1):
        md = d.metadata or {}
        title = md.get("projectName") or md.get("slug") or "Unknown"
        locality = md.get("locality") or ""
        city = md.get("city") or ""
        bhk = md.get("BHK") or md.get("bhk") or ""
        price_cr = md.get("price_in_cr")
        price_rupee = md.get("price")
        price_str = (f"₹{round(price_cr,2)} Cr" if price_cr else (f"₹{int(price_rupee)}" if price_rupee else "N/A"))
        status = md.get("status") or ""
        amenities = md.get("amenities") or ""
        possession = md.get("possessionDate") or ""
        slug = md.get("slug") or ""

        lines.append(
            f"ITEM_{i} || title: {title} || city: {city} || locality: {locality} || bhk: {bhk} || price: {price_str} || status: {status} || possession: {possession} || amenities: {amenities} || slug: {slug}"
        )
    return "\n".join(lines)


# ---------------------------
# 4) Prompt to Groq (strict, grounded)
# ---------------------------
from langchain.schema import HumanMessage
import json, re

def generate_summary_and_cards(user_query: str, records_text: str) -> dict:
    SUMMARY_PROMPT = f"""
You are an assistant for NoBrokerage.com. You will be given property records.
**INSTRUCTIONS:**
- Use ONLY the information in the provided records (do not hallucinate).
- Produce a JSON object with two keys: "summary" and "cards".
- "summary": 2-4 sentences summarizing matching properties, including price, BHK, readiness, localities, counts.
- "cards": list of at most 6 objects with keys: title, city_locality, bhk, price, project_name, possession_status, top_amenities (list of 1-3 strings), cta_url.
- If no records match, return:
{{"summary":"No matching properties found. I expanded the search and found X alternatives.","cards":[]}}
Records:
{records_text}

User query:
{user_query}
"""

    # Call Groq LLM
    resp = llm.generate([[HumanMessage(content=SUMMARY_PROMPT)]])
    
    # Extract text
    try:
        text = resp.generations[0][0].text
    except Exception:
        text = str(resp)

    # Parse JSON
    try:
        result_json = json.loads(text)
    except json.JSONDecodeError:
        # Attempt to extract JSON blob
        match = re.search(r"(\{.*\})", text, re.S)
        if match:
            try:
                result_json = json.loads(match.group(1))
            except:
                result_json = {"summary": "Error: Could not parse LLM output as JSON.", "cards": []}
        else:
            result_json = {"summary": "Error: Could not parse LLM output as JSON.", "cards": []}

    # Ensure summary fallback is strictly formatted
    if not result_json.get("summary"):
        result_json["summary"] = f"No matching properties found for '{user_query}'."

    return result_json



# ---------------------------
# 5) Main handler
# ---------------------------
def handle_query(query: str, k: int = 12) -> Dict[str, Any]:
    """
    Full pipeline:
    - parse query
    - semantic search (k)
    - deterministic filter
    - pass filtered results to LLM for summary + cards (LLM is forced to use only these records)
    """
    parsed = parse_query(query)
    sem_docs = semantic_search(query, k=k)

    # apply deterministic metadata filter
    filtered = apply_filters(sem_docs, parsed)

    # If none after filtering, optionally expand search: use original sem_docs as fallback
    to_use = filtered if filtered else sem_docs[:6]  # keep up to 6 for LLM context

    # Build plain records text for LLM
    records_text = build_context_for_llm(to_use)

    # If absolutely no documents at all:
    if len(to_use) == 0:
        return {"summary": "No matching properties found and no alternatives available.", "cards": []}

    llm_result = generate_summary_and_cards(query, records_text)

    # Ensure cards also include CTA built from slug if missing formatting
    cards = llm_result.get("cards", [])
    for c, doc in zip(cards, to_use):
        # ensure cta_url exists
        if not c.get("cta_url") or c.get("cta_url") == "":
            slug = doc.metadata.get("slug") or ""
            c["cta_url"] = f"/project/{slug}"
    return llm_result


# ---------------------------
# CLI interactive usage
# ---------------------------
if __name__ == "__main__":
    print("NoBrokerage Chatbot (Groq) — demo (grounded summary + cards).")
    print("Type 'exit' to quit.")
    while True:
        q = input("\nEnter user query: ").strip()
        if q.lower() in ("exit", "quit"):
            break
        out = handle_query(q)
        print("\n=== Summary ===")
        print(out.get("summary"))
        # print("\n=== Cards ===")
        # print(json.dumps(out.get("cards", []), indent=2))
