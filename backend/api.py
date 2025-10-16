from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.chatbot import handle_query  # now safe

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    cards: list = []

app = FastAPI(title="NoBrokerage Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    result = handle_query(request.query)
    return ChatResponse(answer=result.get("summary"), cards=result.get("cards", []))

@app.get("/")
def root():
    return {"message": "✅ NoBrokerage running"}
