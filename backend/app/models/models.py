from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database.db import Base


class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"
    transfer = "transfer"


class DataSource(str, enum.Enum):
    smbc = "smbc"
    vpass = "vpass"
    manual = "manual"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    category = Column(String(100))
    source = Column(Enum(DataSource), nullable=False)
    account = Column(String(100))
    balance = Column(Float)
    memo = Column(Text)
    raw_data = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SalaryRecord(Base):
    __tablename__ = "salary_records"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    base_salary = Column(Float, nullable=False)
    work_days = Column(Integer)
    work_hours = Column(Float)
    overtime_hours_125 = Column(Float, default=0)
    overtime_hours_135 = Column(Float, default=0)
    holiday_work_hours = Column(Float, default=0)
    commute_allowance = Column(Float, default=0)
    other_allowances = Column(Float, default=0)
    gross_salary = Column(Float)
    health_insurance = Column(Float)
    pension = Column(Float)
    employment_insurance = Column(Float)
    income_tax = Column(Float)
    resident_tax = Column(Float)
    net_salary = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExpenseReport(Base):
    __tablename__ = "expense_reports"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    title = Column(String(200), nullable=False)
    category = Column(String(100))
    amount = Column(Float, nullable=False)
    description = Column(Text)
    receipt_path = Column(String(500))
    rakuraku_submitted = Column(Boolean, default=False)
    rakuraku_submission_date = Column(DateTime)
    rakuraku_report_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    items = relationship("ExpenseReportItem", back_populates="report", cascade="all, delete-orphan")


class ExpenseReportItem(Base):
    __tablename__ = "expense_report_items"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("expense_reports.id"), nullable=False)
    date = Column(Date, nullable=False)
    description = Column(String(500), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100))
    report = relationship("ExpenseReport", back_populates="items")


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StockMarket(str, enum.Enum):
    JP = "JP"
    US = "US"
    KS = "KS"
    KQ = "KQ"


class StockHolding(Base):
    __tablename__ = "stock_holdings"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), nullable=False)
    market = Column(String(10), nullable=False)
    name = Column(String(200))
    quantity = Column(Float, nullable=False)
    avg_buy_price = Column(Float, nullable=False)
    memo = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class StockWatchlist(Base):
    __tablename__ = "stock_watchlist"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), nullable=False)
    market = Column(String(10), nullable=False)
    name = Column(String(200))
    memo = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
