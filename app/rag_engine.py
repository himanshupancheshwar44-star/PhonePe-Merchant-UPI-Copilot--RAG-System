import json
import os
from typing import List, Dict, Any, Optional

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


class MerchantRAGEngine:
    def __init__(self, kb_path: str):
        self.kb_path = kb_path
        self.raw_documents: List[Dict[str, Any]] = []
        self.documents: List[Dict[str, Any]] = []
        self.langchain_docs: List[Document] = []
        self.vector_store: Optional[InMemoryVectorStore] = None
        self.retriever = None
        self.embeddings = None
        self.current_api_key: Optional[str] = None

        self.load_documents()
        self.init_langchain_components()

    def load_documents(self):
        if not os.path.exists(self.kb_path):
            self.raw_documents = []
            self.documents = []
            return

        with open(self.kb_path, "r", encoding="utf-8") as f:
            self.raw_documents = json.load(f)
            self.documents = self.raw_documents

        self.langchain_docs = []
        for doc in self.raw_documents:
            action_steps_str = "\n- " + "\n- ".join(doc.get("action_steps", []))
            content = (
                f"Title: {doc.get('title')}\n"
                f"Publisher: {doc.get('publisher')}\n"
                f"Category: {doc.get('issue_category')}\n"
                f"Policy Text: {doc.get('chunk_text')}\n"
                f"Recommended Steps: {action_steps_str}"
            )
            self.langchain_docs.append(Document(page_content=content, metadata=doc))

    def init_langchain_components(self, api_key: Optional[str] = None):
        effective_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not effective_key:
            return

        if self.vector_store is not None and self.current_api_key == effective_key:
            return

        try:
            self.current_api_key = effective_key
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=effective_key
            )
            self.vector_store = InMemoryVectorStore(self.embeddings)
            self.vector_store.add_documents(self.langchain_docs)
            self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
            print("[LangChain] Initialized InMemoryVectorStore with gemini-embedding-001")
        except Exception as e:
            print(f"[LangChain] Embedding initialization error: {e}")
            self.vector_store = None
            self.retriever = None

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not self.vector_store:
            self.init_langchain_components()

        if self.retriever:
            try:
                retrieved_docs: List[Document] = self.retriever.invoke(query)
                results = []
                for idx, d in enumerate(retrieved_docs[:top_k]):
                    meta = dict(d.metadata)
                    meta["relevance_score"] = round(1.0 - (idx * 0.08), 2)
                    results.append(meta)
                return results
            except Exception as e:
                print(f"[LangChain] Vector retrieval error: {e}")

        q_words = set(query.lower().split())
        scored = []
        for doc in self.raw_documents:
            text = f"{doc.get('title', '')} {doc.get('chunk_text', '')} {' '.join(doc.get('action_steps', []))}".lower()
            score = sum(1 for w in q_words if w in text)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [dict(item[1]) for item in scored[:top_k]]

    def generate_response(
        self,
        query: str,
        retrieved_docs: List[Dict[str, Any]],
        txn_context: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        effective_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        context_blocks = []
        for d in retrieved_docs:
            context_blocks.append(
                f"[Source: {d.get('publisher')} | ID: {d.get('doc_id')} | Title: {d.get('title')}]\n"
                f"Policy Text: {d.get('chunk_text')}\n"
                f"Mandated Steps: {', '.join(d.get('action_steps', []))}\n"
                f"Official URL: {d.get('source_url')}"
            )
        formatted_context = "\n\n".join(context_blocks)
        if txn_context:
            formatted_context = f"{txn_context}\n\n{formatted_context}"

        if effective_key:
            try:
                llm = ChatGoogleGenerativeAI(
                    model="gemini-3.8-flash",
                    google_api_key=effective_key,
                    temperature=0.2
                )

                prompt = ChatPromptTemplate.from_messages([
                    (
                        "system",
                        "You are the 'PhonePe Merchant UPI Helpdesk' AI for Indian shopkeepers, retailers, and cashiers.\n\n"
                        "PRIMARY DIRECTIVES:\n"
                        "1. DIRECT FOCUS: Answer exactly what the user asks. Address their specific situation directly without robotic preamble or redundant boilerplate.\n"
                        "2. ADAPTIVE RESPONSE STRUCTURE:\n"
                        "   - For Payment Disputes / Counter Urgencies (e.g. pending debit, silent soundbox, customer demands cash refund, screenshot shown):\n"
                        "     * Verdict: Clear, 1-line verdict at the very top (e.g., '⚠️ **Do not hand over goods yet**' or '❌ **Do not give a cash refund**').\n"
                        "     * Action Steps: 2 to 3 concise, practical steps for the merchant to do immediately at the counter.\n"
                        "     * What to Tell Customer: 1 polite, reassuring sentence the merchant can say to the customer directly (in simple English or Hinglish).\n"
                        "   - For Informational / General Questions (e.g. 'What is UTR?', 'How does daily settlement work?', 'How to dispute a chargeback?'):\n"
                        "     * Give a direct, concise, and clear explanation answering their question directly (2-4 sentences or crisp bullets).\n"
                        "     * Do not force unneeded warnings or generic checklists if not relevant to their question.\n"
                        "3. CORE PAYMENT SAFETY RULES (Apply when relevant):\n"
                        "   - Never advise handing over goods solely based on customer phone screenshots or SMS. Only the PhonePe SmartSpeaker voice alert or PhonePe for Business App statement is valid proof of credit.\n"
                        "   - Never advise giving cash refunds from the counter drawer for failed/pending digital transactions. Remind that NPCI rules enforce auto-reversal to customer's source account.\n"
                        "   - Never ask for or mention UPI PINs or OTPs.\n"
                        "4. TONE & LANGUAGE:\n"
                        "   - Practical, crisp, respectful, and merchant-friendly.\n"
                        "   - If the merchant asks in Hindi or Hinglish, reply in clear, friendly Hinglish.\n"
                        "5. CITATIONS: Ground answers accurately in official NPCI/PhonePe policies. Keep source citations brief and unobtrusive (e.g. [Ref: NPCI_FAQ_001])."
                    ),
                    (
                        "human",
                        "MERCHANT QUERY:\n{query}\n\n"
                        "OFFICIAL CONTEXT & TRANSACTIONS:\n{context}\n\n"
                        "Provide a focused, direct response tailored specifically to what the merchant asked."
                    )
                ])

                rag_chain = prompt | llm | StrOutputParser()

                answer = rag_chain.invoke({
                    "query": query,
                    "context": formatted_context
                })

                return {
                    "answer": answer,
                    "citations": retrieved_docs,
                    "model_used": "LangChain + Gemini 3.8 Flash (Focused Adaptive RAG)",
                    "has_key": True
                }
            except Exception as e:
                print(f"[LangChain] RAG chain execution error: {e}")

        fallback_answer = self._synthesize_local_response(query, retrieved_docs, txn_context)
        return {
            "answer": fallback_answer,
            "citations": retrieved_docs,
            "model_used": "LangChain Policy Synthesizer (Local)",
            "has_key": bool(effective_key)
        }

    def _synthesize_local_response(self, query: str, docs: List[Dict[str, Any]], txn_context: Optional[str]) -> str:
        q_lower = query.lower()
        lines = []

        if any(w in q_lower for w in ["cash", "refund", "wants money", "paisa wapas"]):
            lines.append("### ❌ Verdict: Do NOT Give Cash Refund From Your Drawer")
            lines.append("Under NPCI UPI guidelines, failed or pending digital transactions are automatically reversed back to the customer's bank account (T+1 days). Giving cash from your drawer causes a direct financial loss if the bank later auto-refunds them.")
            lines.append("")
            lines.append("**Immediate Counter Actions:**")
            lines.append("1. **Check PhonePe App:** Confirm if your transaction history shows 'Failed' or 'Pending'.")
            lines.append("2. **Customer Advice:** Reassure the customer that their bank switch will auto-credit the amount within 24-48 hours.")
            lines.append("3. **If Goods Needed:** Request a fresh payment via Cash or Card, and note their UTR in your counter book.")

        elif any(w in q_lower for w in ["soundbox", "speaker", "didn't speak", "voice", "silent", "nahi bola"]):
            lines.append("### ⚠️ Verdict: Keep Goods On Hold Until Confirmed in App")
            lines.append("If the SmartSpeaker did not announce the payment, the transaction might still be in a pending state or experiencing network latency.")
            lines.append("")
            lines.append("**Immediate Counter Actions:**")
            lines.append("1. **Pull-to-Refresh App:** Open your PhonePe for Business App and check if the amount shows as 'Success'.")
            lines.append("2. **Check Speaker Light:** Ensure the soundbox has a solid green/blue light (indicating 4G signal).")
            lines.append("3. **Only Release on App Confirmation:** Do not rely on customer's screen.")

        elif any(w in q_lower for w in ["fake", "screenshot", "fraud", "spoof", "green screen"]):
            lines.append("### 🛡️ Verdict: Screenshots Are Not Proof of Credit")
            lines.append("Fraudulent spoof apps can generate fake green success screens and fake UTR numbers within seconds.")
            lines.append("")
            lines.append("**Immediate Counter Actions:**")
            lines.append("1. **Ignore Phone Screen:** Politely tell the customer you must verify against your merchant device.")
            lines.append("2. **Match 12-Digit UTR:** Look up the exact 12-digit UTR in your PhonePe for Business transaction list.")
            lines.append("3. **Hand Over Goods Only After Credit:** If not in your app history, the money has not been credited.")

        elif any(w in q_lower for w in ["settlement", "bank credit", "morning", "transfer to bank"]):
            lines.append("### 📅 Daily Settlement Guidelines")
            lines.append("PhonePe automatically settles counter collections to your registered bank account the next morning (usually between 6:00 AM and 8:00 AM).")
            lines.append("")
            lines.append("**How to Check & Resolve:**")
            lines.append("1. **View Settlement History:** Check 'Settlements' tab in PhonePe for Business App for UTR details.")
            lines.append("2. **Bank Holidays:** Settlements on non-working bank holidays may experience standard clearing delays.")
            lines.append("3. **Instant Settlement:** Use the 'Settle Now' feature in the app if you need funds immediately.")

        elif any(w in q_lower for w in ["what is utr", "utr kya hai", "utr meaning"]):
            lines.append("### 📌 What is a UTR Number?")
            lines.append("A **UTR (Unique Transaction Reference)** is a 12-digit unique number generated by the banking system for every UPI payment. It is the single official identifier used by NPCI, banks, and PhonePe to track, verify, and resolve payment disputes.")

        else:
            if docs:
                best_doc = docs[0]
                lines.append(f"### ⚡ Guidance: {best_doc.get('title', 'UPI Counter Assistance')}")
                lines.append(f"{best_doc.get('chunk_text', '')}")
                if best_doc.get("action_steps"):
                    lines.append("")
                    lines.append("**Recommended Steps:**")
                    for i, step in enumerate(best_doc.get("action_steps", [])[:3], 1):
                        lines.append(f"{i}. {step}")
            else:
                lines.append("### ⚡ Guidance for Merchant:")
                lines.append("Please verify transaction status directly in your PhonePe for Business App before releasing goods.")

        if docs:
            lines.append("")
            lines.append("**Official Citations:**")
            for d in docs[:2]:
                lines.append(f"- **[{d.get('publisher')}]** {d.get('title')} (`{d.get('doc_id')}`)")

        return "\n".join(lines)
