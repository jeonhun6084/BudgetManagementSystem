"""
楽楽清算 自動入力スクレイパー
経費申請を自動化する
"""
import asyncio
from datetime import date, datetime
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser


class RakurakuScraper:
    BASE_URL = "https://www.rakurakuseisan.jp"

    def __init__(self, login_id: str, password: str, company_code: str = ""):
        self.login_id = login_id
        self.password = password
        self.company_code = company_code
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        # headless=False でユーザーが確認できるようにする
        self._browser = await self._playwright.chromium.launch(headless=False)
        self._page = await self._browser.new_page()
        return self

    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
        await self._playwright.stop()

    async def login(self) -> bool:
        """楽楽清算にログインする"""
        page = self._page
        await page.goto(f"{self.BASE_URL}/login")
        await page.wait_for_load_state("networkidle")

        # 会社コードがある場合は入力
        if self.company_code:
            try:
                await page.fill('input[name*="company"], input[id*="company"]', self.company_code)
            except Exception:
                pass

        await page.fill('input[name*="loginId"], input[name*="userId"], input[type="text"]', self.login_id)
        await page.fill('input[name*="password"], input[type="password"]', self.password)
        await page.click('button[type="submit"], input[type="submit"]')

        await page.wait_for_load_state("networkidle")
        content = await page.content()
        return "経費" in content or "申請" in content or "ダッシュボード" in content

    async def submit_expense(self, expense_data: dict) -> dict:
        """
        経費を申請する
        expense_data: {
            date: date,
            title: str,
            category: str,
            amount: float,
            description: str,
        }
        """
        page = self._page
        result = {"success": False, "report_id": None, "message": ""}

        try:
            # 経費申請ページへ移動
            await page.click('a:has-text("経費申請"), a:has-text("新規申請"), a[href*="expense"]')
            await page.wait_for_load_state("networkidle")

            # 申請タイトル入力
            await page.fill('input[name*="title"], input[placeholder*="タイトル"]', expense_data.get("title", ""))

            # 日付入力
            date_obj = expense_data.get("date", date.today())
            date_str = date_obj.strftime("%Y/%m/%d") if isinstance(date_obj, date) else str(date_obj)
            try:
                await page.fill('input[name*="date"], input[type="date"]', date_str)
            except Exception:
                pass

            # 金額入力
            amount = str(int(expense_data.get("amount", 0)))
            await page.fill('input[name*="amount"], input[placeholder*="金額"]', amount)

            # 説明・備考入力
            description = expense_data.get("description", "")
            if description:
                try:
                    await page.fill('textarea[name*="note"], textarea[name*="memo"], textarea[placeholder*="備考"]', description)
                except Exception:
                    pass

            # カテゴリ選択
            category = expense_data.get("category", "")
            if category:
                try:
                    await page.select_option('select[name*="category"], select[name*="type"]', label=category)
                except Exception:
                    pass

            # 申請ボタンをクリック（ユーザーが確認できるよう少し待機）
            await page.wait_for_timeout(2000)
            await page.click('button:has-text("申請"), button:has-text("提出"), input[value*="申請"]')
            await page.wait_for_load_state("networkidle")

            # 申請番号を取得
            content = await page.content()
            import re
            report_id_match = re.search(r'申請番号[：:]\s*([A-Z0-9\-]+)', content)
            if report_id_match:
                result["report_id"] = report_id_match.group(1)

            result["success"] = True
            result["message"] = "申請が完了しました"

        except Exception as e:
            result["message"] = f"申請エラー: {str(e)}"

        return result

    async def submit_bulk_expenses(self, expenses: list[dict]) -> list[dict]:
        """複数の経費を一括申請する"""
        results = []
        for expense in expenses:
            result = await self.submit_expense(expense)
            results.append({**expense, **result})
            await asyncio.sleep(2)  # サーバー負荷軽減のため少し待機
        return results

    async def get_submitted_reports(self) -> list[dict]:
        """提出済み申請一覧を取得する"""
        page = self._page
        reports = []

        try:
            await page.click('a:has-text("申請一覧"), a:has-text("一覧"), a[href*="list"]')
            await page.wait_for_load_state("networkidle")

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(await page.content(), "lxml")
            tables = soup.find_all("table")

            for table in tables:
                rows = table.find_all("tr")
                for row in rows[1:]:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 3:
                        reports.append({
                            "report_id": cells[0].get_text(strip=True),
                            "title": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                            "amount": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                            "status": cells[3].get_text(strip=True) if len(cells) > 3 else "",
                            "date": cells[4].get_text(strip=True) if len(cells) > 4 else "",
                        })
        except Exception:
            pass

        return reports
