"""
Vpass (三井住友カード) スクレイパー
クレジットカード利用明細を自動取得する
"""
import asyncio
import re
from datetime import date, datetime
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser


class VpassScraper:
    LOGIN_URL = "https://www.smbc-card.com/mem/index.jsp"
    STATEMENT_URL = "https://www.smbc-card.com/mem/detail/index.jsp"

    def __init__(self, user_id: str, password: str):
        self.user_id = user_id
        self.password = password
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
        """Vpassにログインする"""
        page = self._page
        await page.goto(self.LOGIN_URL)
        await page.wait_for_load_state("networkidle")

        await page.fill('input[name="userId"], input[id*="userId"]', self.user_id)
        await page.fill('input[name="password"], input[type="password"]', self.password)
        await page.click('button[type="submit"], input[type="submit"], a:has-text("ログイン")')

        await page.wait_for_load_state("networkidle")
        return "ご利用明細" in await page.content() or "残高" in await page.content()

    async def get_statements(self, year: int, month: int) -> list[dict]:
        """指定月のカード利用明細を取得する"""
        page = self._page
        await page.goto(self.STATEMENT_URL)
        await page.wait_for_load_state("networkidle")

        # 月選択
        try:
            month_selector = f"{year}年{month:02d}月"
            await page.select_option("select[name*='month'], select[id*='month']", label=month_selector)
            await page.wait_for_load_state("networkidle")
        except Exception:
            pass

        content = await page.content()
        return self._parse_statements(content, year, month)

    async def get_current_month_statements(self) -> list[dict]:
        """当月の利用明細を取得する"""
        now = datetime.now()
        return await self.get_statements(now.year, now.month)

    def _parse_statements(self, html: str, year: int, month: int) -> list[dict]:
        """HTMLから利用明細を解析する"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        statements = []

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 3:
                    try:
                        date_text = cells[0].get_text(strip=True)
                        description = cells[1].get_text(strip=True)
                        amount_text = cells[-1].get_text(strip=True).replace(",", "").replace("円", "")

                        if not date_text or not description or not amount_text:
                            continue

                        parsed_date = self._parse_date(date_text, year, month)
                        if not parsed_date:
                            continue

                        amount = float(re.sub(r"[^\d.]", "", amount_text))
                        if amount <= 0:
                            continue

                        # カテゴリ推定
                        category = self._estimate_category(description)

                        statements.append({
                            "date": parsed_date,
                            "description": description,
                            "amount": amount,
                            "transaction_type": "expense",
                            "source": "vpass",
                            "category": category,
                        })
                    except (ValueError, IndexError):
                        continue

        return statements

    def _parse_date(self, date_text: str, default_year: int, default_month: int) -> Optional[date]:
        """日付テキストを解析する"""
        patterns = [
            (r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", None),
            (r"(\d{1,2})[/\-月](\d{1,2})", None),
        ]
        for pattern, _ in patterns:
            match = re.search(pattern, date_text)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    return date(int(groups[0]), int(groups[1]), int(groups[2]))
                elif len(groups) == 2:
                    return date(default_year, int(groups[0]), int(groups[1]))
        return None

    def _estimate_category(self, description: str) -> str:
        """説明文からカテゴリを推定する"""
        category_map = {
            "食": "食費",
            "スーパー": "食費",
            "コンビニ": "食費",
            "飲食": "食費",
            "レストラン": "食費",
            "交通": "交通費",
            "電車": "交通費",
            "バス": "交通費",
            "タクシー": "交通費",
            "医療": "医療費",
            "病院": "医療費",
            "薬": "医療費",
            "ショッピング": "買い物",
            "amazon": "買い物",
            "電気": "光熱費",
            "ガス": "光熱費",
            "水道": "光熱費",
            "通信": "通信費",
            "携帯": "通信費",
            "保険": "保険",
            "娯楽": "娯楽",
        }
        desc_lower = description.lower()
        for keyword, category in category_map.items():
            if keyword.lower() in desc_lower:
                return category
        return "その他"

    @classmethod
    async def import_from_csv(cls, csv_path: str) -> list[dict]:
        """VpassのCSVファイルから明細をインポートする"""
        import csv
        transactions = []
        with open(csv_path, encoding="shift_jis", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                try:
                    if len(row) < 3:
                        continue
                    date_text = row[0].strip()
                    description = row[1].strip()
                    amount_text = row[2].strip().replace(",", "").replace("円", "")

                    if not date_text or not description:
                        continue

                    parsed_date = SMBCScraper._parse_date_static(date_text)
                    if not parsed_date:
                        continue

                    amount = float(re.sub(r"[^\d.]", "", amount_text))
                    transactions.append({
                        "date": parsed_date,
                        "description": description,
                        "amount": amount,
                        "transaction_type": "expense",
                        "source": "vpass",
                    })
                except (ValueError, IndexError):
                    continue
        return transactions
