from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, desc
from datetime import date, datetime, timedelta
from typing import Optional
import tempfile, os

from ..database.db import get_db
from ..models.models import Transaction, TransactionType, DataSource
from ..scrapers.smbc import SMBCScraper
from ..scrapers.vpass import VpassScraper

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("")
async def get_transactions(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    source: Optional[str] = None,
    transaction_type: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Transaction).order_by(desc(Transaction.date))

    if from_date:
        stmt = stmt.where(Transaction.date >= from_date)
    if to_date:
        stmt = stmt.where(Transaction.date <= to_date)
    if source:
        stmt = stmt.where(Transaction.source == source)
    if transaction_type:
        stmt = stmt.where(Transaction.transaction_type == transaction_type)
    if category:
        stmt = stmt.where(Transaction.category == category)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar()

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    transactions = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": t.id,
                "date": t.date.isoformat(),
                "description": t.description,
                "amount": t.amount,
                "transaction_type": t.transaction_type,
                "category": t.category,
                "source": t.source,
                "account": t.account,
                "balance": t.balance,
                "memo": t.memo,
            }
            for t in transactions
        ],
    }


@router.get("/summary")
async def get_summary(
    year: int = Query(default=datetime.now().year),
    month: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """月別・カテゴリ別の収支サマリーを取得する"""
    if month:
        from_date = date(year, month, 1)
        if month == 12:
            to_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            to_date = date(year, month + 1, 1) - timedelta(days=1)
    else:
        from_date = date(year, 1, 1)
        to_date = date(year, 12, 31)

    # 収入合計
    income_stmt = select(func.sum(Transaction.amount)).where(
        Transaction.transaction_type == TransactionType.income,
        Transaction.date.between(from_date, to_date),
    )
    total_income = (await db.execute(income_stmt)).scalar() or 0

    # 支出合計
    expense_stmt = select(func.sum(Transaction.amount)).where(
        Transaction.transaction_type == TransactionType.expense,
        Transaction.date.between(from_date, to_date),
    )
    total_expense = (await db.execute(expense_stmt)).scalar() or 0

    # カテゴリ別支出
    category_stmt = (
        select(Transaction.category, func.sum(Transaction.amount).label("total"))
        .where(
            Transaction.transaction_type == TransactionType.expense,
            Transaction.date.between(from_date, to_date),
        )
        .group_by(Transaction.category)
        .order_by(desc("total"))
    )
    category_result = await db.execute(category_stmt)
    category_breakdown = [
        {"category": row.category or "未分類", "amount": row.total}
        for row in category_result
    ]

    # 月別推移（年間表示の場合）
    monthly_trend = []
    if not month:
        for m in range(1, 13):
            m_from = date(year, m, 1)
            m_to = date(year, m + 1, 1) - timedelta(days=1) if m < 12 else date(year, 12, 31)
            m_income = (await db.execute(
                select(func.sum(Transaction.amount)).where(
                    Transaction.transaction_type == TransactionType.income,
                    Transaction.date.between(m_from, m_to)
                )
            )).scalar() or 0
            m_expense = (await db.execute(
                select(func.sum(Transaction.amount)).where(
                    Transaction.transaction_type == TransactionType.expense,
                    Transaction.date.between(m_from, m_to)
                )
            )).scalar() or 0
            monthly_trend.append({"month": m, "income": m_income, "expense": m_expense})

    return {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
        "category_breakdown": category_breakdown,
        "monthly_trend": monthly_trend,
    }


@router.post("/import/smbc-csv")
async def import_smbc_csv(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """SMBCのCSVファイルをインポートする"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        transactions = await SMBCScraper.import_from_csv(tmp_path)
        added = 0
        categorized = 0
        for t in transactions:
            tx = Transaction(
                date=t["date"],
                description=t["description"],
                amount=t["amount"],
                transaction_type=t["transaction_type"],
                category=t.get("category"),
                source=DataSource.smbc,
                balance=t.get("balance"),
            )
            db.add(tx)
            added += 1
            if t.get("category"):
                categorized += 1
        await db.commit()
        return {"imported": added, "message": f"{added}件インポート（うち{categorized}件を自動分類）"}
    finally:
        os.unlink(tmp_path)


@router.post("/import/vpass-csv")
async def import_vpass_csv(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """VpassのCSVファイルをインポートする"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        transactions = await VpassScraper.import_from_csv(tmp_path)
        added = 0
        for t in transactions:
            tx = Transaction(
                date=t["date"],
                description=t["description"],
                amount=t["amount"],
                transaction_type=TransactionType.expense,
                source=DataSource.vpass,
                category=t.get("category"),
            )
            db.add(tx)
            added += 1
        await db.commit()
        return {"imported": added, "message": f"{added}件のデータをインポートしました"}
    finally:
        os.unlink(tmp_path)


@router.patch("/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """取引のカテゴリ・メモを更新する"""
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if "category" in data:
        tx.category = data["category"]
    if "memo" in data:
        tx.memo = data["memo"]

    await db.commit()
    return {"id": tx.id, "category": tx.category, "memo": tx.memo}


@router.delete("/{transaction_id}")
async def delete_transaction(transaction_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await db.delete(tx)
    await db.commit()
    return {"deleted": transaction_id}
