import csv
import os
from typing import List, Dict, Optional

class TransactionStore:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.transactions: List[Dict[str, str]] = []
        self.load_transactions()

    def load_transactions(self):
        if not os.path.exists(self.csv_path):
            self.transactions = []
            return
        
        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.transactions = [row for row in reader]

    def get_all(self) -> List[Dict[str, str]]:
        return self.transactions

    def find_by_identifier(self, query: str) -> Optional[Dict[str, str]]:
        q = query.strip().lower()
        for txn in self.transactions:
            if (q in txn.get("utr_number", "").lower() or 
                q in txn.get("transaction_id", "").lower() or 
                q in txn.get("customer_name_or_vpa", "").lower()):
                return txn
        return None

    def search_by_amount_or_keyword(self, amount: Optional[float] = None, keyword: Optional[str] = None) -> List[Dict[str, str]]:
        results = []
        for txn in self.transactions:
            matched = False
            if amount is not None:
                try:
                    txn_amt = float(txn.get("amount", 0))
                    if abs(txn_amt - amount) < 0.01:
                        matched = True
                except ValueError:
                    pass
            if keyword and keyword.lower() in str(txn).lower():
                matched = True
            if matched:
                results.append(txn)
        return results

    def format_txn_context(self, txn: Dict[str, str]) -> str:
        return (
            f"=== MATCHED PHONEPE MERCHANT TRANSACTION ===\n"
            f"Transaction ID: {txn.get('transaction_id')}\n"
            f"12-Digit UTR: {txn.get('utr_number')}\n"
            f"Timestamp: {txn.get('timestamp')}\n"
            f"Customer / VPA: {txn.get('customer_name_or_vpa')}\n"
            f"Amount: ₹{txn.get('amount')}\n"
            f"Current Status on PhonePe Terminal: {txn.get('status')}\n"
            f"Soundbox Voice Alert Broadcasted: {txn.get('soundbox_announced')}\n"
            f"Failure / Terminal Reason: {txn.get('failure_reason')}\n"
            f"Counter Terminal: {txn.get('counter_terminal')}\n"
            f"============================================="
        )
