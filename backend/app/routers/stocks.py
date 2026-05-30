from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import asyncio
import os

from ..database.db import get_db
from ..models.models import StockHolding, StockWatchlist

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

MARKET_SUFFIX = {"JP": ".T", "US": "", "KS": ".KS", "KQ": ".KQ"}


def to_yf_symbol(ticker: str, market: str) -> str:
    return f"{ticker}{MARKET_SUFFIX.get(market, '')}"


def _fetch_stock_info(symbol: str) -> dict:
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.info
        hist = t.history(period="5d")
        if hist.empty:
            return {"error": f"데이터 없음: {symbol}"}
        current_price = float(hist["Close"].iloc[-1])
        prev_price = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
        change_pct = (current_price - prev_price) / prev_price * 100 if prev_price else 0
        return {
            "price": current_price,
            "change_pct": change_pct,
            "name": info.get("longName") or info.get("shortName") or symbol,
            "currency": info.get("currency", ""),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "pbr": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "week52_high": info.get("fiftyTwoWeekHigh"),
            "week52_low": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
    except Exception as e:
        return {"error": str(e)}


async def fetch_stock_info(symbol: str) -> dict:
    return await asyncio.to_thread(_fetch_stock_info, symbol)


class HoldingCreate(BaseModel):
    ticker: str
    market: str
    name: Optional[str] = None
    quantity: float
    avg_buy_price: float
    memo: Optional[str] = None


class WatchlistCreate(BaseModel):
    ticker: str
    market: str
    name: Optional[str] = None
    memo: Optional[str] = None


class AnalyzeRequest(BaseModel):
    ticker: str
    market: str


def _build_holding_item(h, info: dict) -> dict:
    current_price = info.get("price", 0) or 0
    market_value = current_price * h.quantity
    cost_basis = h.avg_buy_price * h.quantity
    pl = market_value - cost_basis
    pl_pct = (pl / cost_basis * 100) if cost_basis else 0
    return {
        "id": h.id,
        "ticker": h.ticker,
        "market": h.market,
        "name": h.name or info.get("name", h.ticker),
        "quantity": h.quantity,
        "avg_buy_price": h.avg_buy_price,
        "current_price": current_price,
        "change_pct": info.get("change_pct", 0),
        "market_value": market_value,
        "cost_basis": cost_basis,
        "pl": pl,
        "pl_pct": pl_pct,
        "currency": info.get("currency", ""),
        "error": info.get("error"),
        "memo": h.memo,
    }


@router.get("/holdings")
async def get_holdings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StockHolding).order_by(StockHolding.created_at))
    holdings = result.scalars().all()
    if not holdings:
        return {"items": []}

    infos = await asyncio.gather(*[
        fetch_stock_info(to_yf_symbol(h.ticker, h.market)) for h in holdings
    ])
    return {"items": [_build_holding_item(h, info) for h, info in zip(holdings, infos)]}


@router.post("/holdings")
async def add_holding(body: HoldingCreate, db: AsyncSession = Depends(get_db)):
    if body.market not in MARKET_SUFFIX:
        raise HTTPException(400, "Invalid market")
    name = body.name
    if not name:
        info = await fetch_stock_info(to_yf_symbol(body.ticker, body.market))
        name = info.get("name") or body.ticker
    holding = StockHolding(
        ticker=body.ticker.upper(),
        market=body.market,
        name=name,
        quantity=body.quantity,
        avg_buy_price=body.avg_buy_price,
        memo=body.memo,
    )
    db.add(holding)
    await db.commit()
    return {"message": "추가되었습니다"}


@router.delete("/holdings/{holding_id}")
async def delete_holding(holding_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StockHolding).where(StockHolding.id == holding_id))
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(404, "Not found")
    await db.delete(holding)
    await db.commit()
    return {"message": "삭제되었습니다"}


@router.get("/watchlist")
async def get_watchlist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StockWatchlist).order_by(StockWatchlist.created_at))
    items_db = result.scalars().all()
    if not items_db:
        return {"items": []}

    infos = await asyncio.gather(*[
        fetch_stock_info(to_yf_symbol(w.ticker, w.market)) for w in items_db
    ])
    items = []
    for w, info in zip(items_db, infos):
        items.append({
            "id": w.id,
            "ticker": w.ticker,
            "market": w.market,
            "name": w.name or info.get("name", w.ticker),
            "current_price": info.get("price", 0),
            "change_pct": info.get("change_pct", 0),
            "currency": info.get("currency", ""),
            "market_cap": info.get("market_cap"),
            "pe_ratio": info.get("pe_ratio"),
            "pbr": info.get("pbr"),
            "dividend_yield": info.get("dividend_yield"),
            "week52_high": info.get("week52_high"),
            "week52_low": info.get("week52_low"),
            "error": info.get("error"),
            "memo": w.memo,
        })
    return {"items": items}


@router.post("/watchlist")
async def add_watchlist(body: WatchlistCreate, db: AsyncSession = Depends(get_db)):
    if body.market not in MARKET_SUFFIX:
        raise HTTPException(400, "Invalid market")
    name = body.name
    if not name:
        info = await fetch_stock_info(to_yf_symbol(body.ticker, body.market))
        name = info.get("name") or body.ticker
    item = StockWatchlist(
        ticker=body.ticker.upper(),
        market=body.market,
        name=name,
        memo=body.memo,
    )
    db.add(item)
    await db.commit()
    return {"message": "추가되었습니다"}


@router.delete("/watchlist/{item_id}")
async def delete_watchlist(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StockWatchlist).where(StockWatchlist.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Not found")
    await db.delete(item)
    await db.commit()
    return {"message": "삭제되었습니다"}


@router.post("/analyze")
async def analyze_stock(body: AnalyzeRequest):
    if body.market not in MARKET_SUFFIX:
        raise HTTPException(400, "Invalid market")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY가 .env에 설정되지 않았습니다. aistudio.google.com에서 무료 발급 가능합니다.")

    symbol = to_yf_symbol(body.ticker, body.market)
    info = await fetch_stock_info(symbol)

    def fmt(val, decimals=2):
        if val is None:
            return "N/A"
        if isinstance(val, float):
            return f"{val:.{decimals}f}"
        return str(val)

    stock_data = f"""종목: {body.ticker} ({body.market} / {symbol})
회사명: {info.get('name', 'N/A')}
현재가: {fmt(info.get('price'))} {info.get('currency', '')}
전일 대비: {fmt(info.get('change_pct'))}%
시가총액: {fmt(info.get('market_cap'), 0)}
PER: {fmt(info.get('pe_ratio'))}
PBR: {fmt(info.get('pbr'))}
배당수익률: {fmt(info.get('dividend_yield'))}
52주 최고: {fmt(info.get('week52_high'))}
52주 최저: {fmt(info.get('week52_low'))}
섹터: {info.get('sector', 'N/A')}
업종: {info.get('industry', 'N/A')}"""

    prompt = f"""아래 주식을 일본 거주 개인 투자자 관점에서 한국어로 분석해주세요.

{stock_data}

다음 항목으로 분석해주세요:
1. **기업 개요** (2-3줄)
2. **투자 포인트** (3가지)
3. **리스크 요인** (2-3가지)
4. **밸류에이션 평가** (PER/PBR 기준, 업종 평균 대비)
5. **투자 의견** (매수/관망/보류 + 한 줄 이유)

마크다운 형식으로 간결하게 답변해주세요."""

    def _call_gemini():
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text

    analysis_text = await asyncio.to_thread(_call_gemini)
    return {
        "ticker": body.ticker,
        "market": body.market,
        "stock_info": info,
        "analysis": analysis_text,
    }
