from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import os

from ..database.db import get_db
from ..models.models import ExpenseReport, ExpenseReportItem
from ..scrapers.rakuraku import RakurakuScraper

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


class ExpenseItemCreate(BaseModel):
    date: date
    description: str
    amount: float
    category: Optional[str] = None


class ExpenseReportCreate(BaseModel):
    date: date
    title: str
    category: Optional[str] = None
    amount: float
    description: Optional[str] = None
    items: list[ExpenseItemCreate] = []
    submit_to_rakuraku: bool = False


@router.get("")
async def get_expense_reports(db: AsyncSession = Depends(get_db)):
    """経費申請一覧を取得する"""
    result = await db.execute(
        select(ExpenseReport).order_by(desc(ExpenseReport.date))
    )
    reports = result.scalars().all()
    return [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "title": r.title,
            "category": r.category,
            "amount": r.amount,
            "description": r.description,
            "rakuraku_submitted": r.rakuraku_submitted,
            "rakuraku_submission_date": r.rakuraku_submission_date.isoformat() if r.rakuraku_submission_date else None,
            "rakuraku_report_id": r.rakuraku_report_id,
        }
        for r in reports
    ]


@router.post("")
async def create_expense_report(
    req: ExpenseReportCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """経費申請を作成する"""
    report = ExpenseReport(
        date=req.date,
        title=req.title,
        category=req.category,
        amount=req.amount,
        description=req.description,
    )
    db.add(report)
    await db.flush()

    for item in req.items:
        db_item = ExpenseReportItem(
            report_id=report.id,
            date=item.date,
            description=item.description,
            amount=item.amount,
            category=item.category,
        )
        db.add(db_item)

    await db.commit()
    await db.refresh(report)

    # 楽楽清算への自動送信
    if req.submit_to_rakuraku:
        background_tasks.add_task(submit_to_rakuraku, report.id, req.dict())

    return {
        "id": report.id,
        "title": report.title,
        "amount": report.amount,
        "message": "経費申請を作成しました" + ("。楽楽清算への送信を開始します。" if req.submit_to_rakuraku else ""),
    }


async def submit_to_rakuraku(report_id: int, expense_data: dict):
    """バックグラウンドで楽楽清算に申請を送信する"""
    login_id = os.getenv("RAKURAKU_LOGIN_ID", "")
    password = os.getenv("RAKURAKU_PASSWORD", "")
    company_code = os.getenv("RAKURAKU_COMPANY_CODE", "")

    if not login_id or not password:
        print("[楽楽清算] 認証情報が設定されていません")
        return

    async with RakurakuScraper(login_id, password, company_code) as scraper:
        if await scraper.login():
            result = await scraper.submit_expense({
                "date": expense_data.get("date"),
                "title": expense_data.get("title"),
                "amount": expense_data.get("amount"),
                "description": expense_data.get("description"),
                "category": expense_data.get("category"),
            })
            print(f"[楽楽清算] 申請結果: {result}")


@router.post("/{report_id}/submit-rakuraku")
async def submit_to_rakuraku_api(
    report_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """既存の経費申請を楽楽清算に送信する"""
    result = await db.execute(select(ExpenseReport).where(ExpenseReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    expense_data = {
        "date": report.date,
        "title": report.title,
        "amount": report.amount,
        "description": report.description,
        "category": report.category,
    }
    background_tasks.add_task(submit_to_rakuraku, report_id, expense_data)

    return {"message": "楽楽清算への送信を開始しました"}


@router.delete("/{report_id}")
async def delete_expense_report(report_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExpenseReport).where(ExpenseReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    await db.delete(report)
    await db.commit()
    return {"deleted": report_id}


@router.get("/categories")
async def get_expense_categories():
    """経費カテゴリ一覧を返す"""
    return {
        "categories": [
            "交通費",
            "宿泊費",
            "食費・接待費",
            "通信費",
            "消耗品費",
            "光熱費",
            "雑費",
            "その他",
        ]
    }
