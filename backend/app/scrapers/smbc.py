"""
三井住友銀行 (SMBC) CSVインポーター
インターネットバンキング → 入出金明細 → CSVダウンロード で取得したファイルを解析する
"""
import csv
import re
from datetime import date, datetime
from typing import Optional


class SMBCScraper:

    @classmethod
    async def import_from_csv(cls, csv_path: str) -> list:
        """SMBCのCSVファイルから取引データをインポートする
        実際の列順: 年月日, お引出し, お預入れ, お取り扱い内容, 残高, メモ, ラベル
        """
        transactions = []
        enc = cls._detect_encoding(csv_path)

        with open(csv_path, encoding=enc, errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                try:
                    if len(row) < 4:
                        continue
                    date_text = row[0].strip()
                    if date_text in ("年月日", "日付", "取引日", ""):
                        continue

                    parsed_date = cls._parse_date_static(date_text)
                    if not parsed_date:
                        continue

                    amount_out  = row[1].strip().replace(",", "")
                    amount_in   = row[2].strip().replace(",", "")
                    description = row[3].strip()
                    balance     = row[4].strip().replace(",", "") if len(row) > 4 else ""

                    if not description:
                        continue

                    from ..services.categorizer import categorize

                    if amount_in and amount_in not in ("", "0"):
                        transactions.append({
                            "date": parsed_date,
                            "description": description,
                            "amount": float(amount_in),
                            "transaction_type": "income",
                            "category": categorize(description, "income"),
                            "source": "smbc",
                            "balance": float(balance) if balance else None,
                        })
                    elif amount_out and amount_out not in ("", "0"):
                        transactions.append({
                            "date": parsed_date,
                            "description": description,
                            "amount": float(amount_out),
                            "transaction_type": "expense",
                            "category": categorize(description, "expense"),
                            "source": "smbc",
                            "balance": float(balance) if balance else None,
                        })
                except (ValueError, IndexError):
                    continue
        return transactions

    @staticmethod
    def _detect_encoding(path: str) -> str:
        for enc in ("cp932", "shift_jis", "utf-8-sig", "utf-8"):
            try:
                with open(path, encoding=enc, errors="strict") as f:
                    f.read()
                return enc
            except (UnicodeDecodeError, LookupError):
                pass
        return "cp932"

    @staticmethod
    def _parse_date_static(date_text: str) -> Optional[date]:
        m = re.search(r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", date_text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        return None
