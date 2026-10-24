import uvicorn
import os
import sys

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting PhonePe Merchant UPI Helpdesk RAG on http://localhost:{port}")
    uvicorn.run("app.server:app", host="127.0.0.1", port=port, reload=True)
