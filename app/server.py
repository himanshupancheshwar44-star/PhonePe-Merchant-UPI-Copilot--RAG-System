import os
import re
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

from app.transaction_store import TransactionStore
from app.rag_engine import MerchantRAGEngine

# Load .env if present
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

kb_file = os.path.join(DATA_DIR, "knowledge_base.json")
txn_file = os.path.join(DATA_DIR, "phonepe_transactions.csv")

app = FastAPI(title="PhonePe Merchant UPI Helpdesk RAG", version="1.0.0")

# Mount static directory
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

txn_store = TransactionStore(txn_file)
rag_engine = MerchantRAGEngine(kb_file)

class ChatRequest(BaseModel):
    query: str
    txn_identifier: Optional[str] = None
    api_key: Optional[str] = None

class LookupRequest(BaseModel):
    query: str

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>PhonePe Merchant UPI Helpdesk RAG Server Running</h1>")

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    query = req.query.strip()
    
    # 1. Check for transaction identifier either passed explicitly or extracted from query
    matched_txn = None
    txn_id_candidate = req.txn_identifier
    
    if not txn_id_candidate:
        # Check if 12 digit UTR or TXN_PP pattern is in the query text
        utr_match = re.search(r"\b\d{12}\b", query)
        txn_match = re.search(r"\bTXN_PP_\w+\b", query, re.IGNORECASE)
        amount_match = re.search(r"(?:rs\.?|₹|inr)\s*([0-9]+(?:\.[0-9]+)?)", query, re.IGNORECASE)
        
        if utr_match:
            txn_id_candidate = utr_match.group(0)
        elif txn_match:
            txn_id_candidate = txn_match.group(0)

    if txn_id_candidate:
        matched_txn = txn_store.find_by_identifier(txn_id_candidate)
    
    # If not found yet and an amount was mentioned, try searching by amount
    if not matched_txn:
        amt_match = re.search(r"(?:rs\.?|₹|inr)\s*([0-9]+(?:\.[0-9]+)?)", query, re.IGNORECASE)
        if amt_match:
            try:
                amt_val = float(amt_match.group(1))
                matches = txn_store.search_by_amount_or_keyword(amount=amt_val)
                if matches:
                    matched_txn = matches[0] # Pick most recent matching transaction
            except ValueError:
                pass

    # 2. Format transaction context if available
    txn_context = None
    if matched_txn:
        txn_context = txn_store.format_txn_context(matched_txn)

    # 3. Retrieve authoritative policy documents
    retrieved_docs = rag_engine.retrieve(query, top_k=3)

    # 4. Synthesize with Gemini / RAG Engine
    rag_result = rag_engine.generate_response(
        query=query,
        retrieved_docs=retrieved_docs,
        txn_context=txn_context,
        api_key=req.api_key
    )

    return {
        "status": "success",
        "answer": rag_result["answer"],
        "citations": rag_result["citations"],
        "matched_transaction": matched_txn,
        "model_used": rag_result["model_used"],
        "has_key": rag_result["has_key"]
    }

@app.get("/api/transactions")
async def get_transactions():
    return {"transactions": txn_store.get_all()}

@app.post("/api/lookup")
async def lookup_transaction(req: LookupRequest):
    txn = txn_store.find_by_identifier(req.query)
    if not txn:
        # Check by amount or keyword
        try:
            amt_cleaned = req.query.strip().replace("₹", "").replace("Rs", "").replace("rs", "")
            amt = float(amt_cleaned)
            matches = txn_store.search_by_amount_or_keyword(amount=amt)
            if matches:
                return {"found": True, "transaction": matches[0]}
        except ValueError:
            pass
        return {"found": False, "message": "No transaction found matching this UTR / ID in the terminal ledger."}
    return {"found": True, "transaction": txn}

@app.get("/api/policies")
async def get_policies():
    return {"policies": rag_engine.documents}
