"""
三井住友銀行 (SMBC) スクレイパー
Playwright を使用してインターネットバンキングから取引明細を取得する
"""
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser
import re


class SMBCScraper:
    LOGIN_URL = "https://direct.smbc.co.jp/aib/aibgncms/login.do"

    def __init__(self, branch_code: str, account_number: str, password: str):
        self.branch_code = branch_code      # 支店番号 (3자리)
        self.account_number = account_number  # 口座番号 (7자리)
        self.password = password            # ログインパスワード
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=False)
        self._page = await self._browser.new_page()
        return self

    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
        await self._playwright.stop()

    async def login(self) -> bool:
        """SMBCインターネットバンキングにログイン (支店番号 + 口座番号 + パスワード)"""
        page = self._page
        await page.goto(self.LOGIN_URL)
        await page.wait_for_load_state("networkidle")

        # 支店番号入力 (3桁)
        await page.fill(
            'input[name*="branch"], input[id*="branch"], input[name*="tenpo"], '
            'input[id*="tenpo"], input[placeholder*="支店"], input[placeholder*="店番"]',
            self.branch_code
        )
        # 口座番号入力 (7桁)
        await page.fill(
            'input[name*="account"], input[id*="account"], input[name*="koza"], '
            'input[id*="koza"], input[placeholder*="口座"]',
            self.account_number
        )
        # ログインパスワード入力
        await page.fill('input[name*="password"], input[type="password"]', self.password)

        # ログインボタンクリック
        await page.click(
            'button[type="submit"], input[type="submit"], '
            'a:has-text("ログイン"), button:has-text("ログイン")'
        )
        await page.wait_for_load_state("networkidle")

        # ワンタイムパスワード・乱数表が必要な場合はユーザーが手動入力
        content = await page.content()
        if "ワンタイムパスワード" in content or "乱数表" in content:
            print("[SMBC] 追加認証が必要です。ブラウザ画面で入力してください。(最大60秒)")
            await page.wait_for_timeout(60000)

        return "ログアウト" in await page.content() or "口座" in await page.content()

    async def get_transactions(self, from_date: date, to_date: date) -> list[dict]:
        """指定期間の取引明細を取得する"""
        transactions = []
        page = self._page

        # 入出金明細ページへ移動
        await page.click('a:has-text("入出金明細"), a:has-text("明細"), a[href*="nyushukkin"]')
        await page.wait_for_load_state("networkidle")

        # 期間指定
        from_str = from_date.strftime("%Y%m%d")
        to_str = to_date.strftime("%Y%m%d")

        # 期間入力フォームを探して入力
        try:
            await page.fill('input[name*="from"], input[id*="from"]', from_str)
            await page.fill('input[name*="to"], input[id*="to"]', to_str)
            await page.click('button:has-text("照会"), input[value="照会"]')
            await page.wait_for_load_state("networkidle")
        except Exception:
            pass

        # テーブルから取引データを抽出
        content = await page.content()
        transactions = self._parse_transactions(content)
        return transactions

    def _parse_transactions(self, html: str) -> list[dict]:
        """HTMLから取引データを解析する"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        transactions = []

        # 取引テーブルを探す
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # ヘッダー行をスキップ
                cells = row.find_all(["td", "th"])
                if len(cells) >= 4:
                    try:
                        date_text = cells[0].get_text(strip=True)
                        description = cells[1].get_text(strip=True)
                        amount_in = cells[2].get_text(strip=True).replace(",", "").replace("円", "")
                        amount_out = cells[3].get_text(strip=True).replace(",", "").replace("円", "")
                        balance = cells[4].get_text(strip=True).replace(",", "").replace("円", "") if len(cells) > 4 else None

                        if not date_text or not description:
                            continue

                        # 日付パース
                        parsed_date = self._parse_date(date_text)
                        if not parsed_date:
                            continue

                        if amount_in and amount_in != "-" and amount_in != "":
                            transactions.append({
                                "date": parsed_date,
                                "description": description,
                                "amount": float(amount_in),
                                "transaction_type": "income",
                                "source": "smbc",
                                "balance": float(balance) if balance and balance not in ["-", ""] else None,
                            })
                        elif amount_out and amount_out != "-" and amount_out != "":
                            transactions.append({
                                "date": parsed_date,
                                "description": description,
                                "amount": float(amount_out),
                                "transaction_type": "expense",
                                "source": "smbc",
                                "balance": float(balance) if balance and balance not in ["-", ""] else None,
                            })
                    except (ValueError, IndexError):
                        continue

        return transactions

    def _parse_date(self, date_text: str) -> Optional[date]:
        """様々な日付フォーマットを解析する"""
        patterns = [
            r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})",
            r"(\d{2})[/\-](\d{1,2})[/\-](\d{1,2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                groups = match.groups()
                year = int(groups[0])
                if year < 100:
                    year += 2000
                return date(year, int(groups[1]), int(groups[2]))
        return None

    @classmethod
    async def import_from_csv(cls, csv_path: str) -> list[dict]:
        """SMBCのCSVファイルから取引データをインポートする"""
        import csv
        transactions = []
        with open(csv_path, encoding="shift_jis", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                try:
                    if len(row) < 4:
                        continue
                    date_text = row[0].strip()
                    description = row[1].strip()
                    amount_out = row[2].strip().replace(",", "") if len(row) > 2 else ""
                    amount_in = row[3].strip().replace(",", "") if len(row) > 3 else ""
                    balance = row[4].strip().replace(",", "") if len(row) > 4 else ""

                    parsed_date = cls._parse_date_static(date_text)
                    if not parsed_date or not description:
                        continue

                    if amount_in and amount_in not in ["", "0"]:
                        transactions.append({
                            "date": parsed_date,
                            "description": description,
                            "amount": float(amount_in),
                            "transaction_type": "income",
                            "source": "smbc",
                            "balance": float(balance) if balance else None,
                        })
                    elif amount_out and amount_out not in ["", "0"]:
                        transactions.append({
                            "date": parsed_date,
                            "description": description,
                            "amount": float(amount_out),
                            "transaction_type": "expense",
                            "source": "smbc",
                            "balance": float(balance) if balance else None,
                        })
                except (ValueError, IndexError):
                    continue
        return transactions

    @staticmethod
    def _parse_date_static(date_text: str):
        patterns = [
            ("%Y/%m/%d", r"\d{4}/\d{2}/\d{2}"),
            ("%Y-%m-%d", r"\d{4}-\d{2}-\d{2}"),
            ("%Y年%m月%d日", r"\d{4}年\d{2}月\d{2}日"),
        ]
        for fmt, pattern in patterns:
            if re.search(pattern, date_text):
                try:
                    return datetime.strptime(date_text.strip(), fmt).date()
                except ValueError:
                    pass
        return None
