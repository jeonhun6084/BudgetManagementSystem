from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..database.db import get_db
from ..models.models import SalaryRecord
from ..services.salary_calculator import SalaryCalculator, SalaryInput

router = APIRouter(prefix="/api/salary", tags=["salary"])
calculator = SalaryCalculator()


class SalaryCalculateRequest(BaseModel):
    base_salary: float
    work_days: int = 20
    work_hours: float = 160
    overtime_hours_125: float = 0
    overtime_hours_135: float = 0
    holiday_work_hours: float = 0
    commute_allowance: float = 0
    other_allowances: float = 0
    resident_tax_monthly: float = 0
    dependents: int = 0
    year: int = datetime.now().year
    month: int = datetime.now().month
    save: bool = False


@router.post("/calculate")
async def calculate_salary(req: SalaryCalculateRequest, db: AsyncSession = Depends(get_db)):
    """給与計算を実行する"""
    inp = SalaryInput(
        base_salary=req.base_salary,
        work_days=req.work_days,
        work_hours=req.work_hours,
        overtime_hours_125=req.overtime_hours_125,
        overtime_hours_135=req.overtime_hours_135,
        holiday_work_hours=req.holiday_work_hours,
        commute_allowance=req.commute_allowance,
        other_allowances=req.other_allowances,
        resident_tax_monthly=req.resident_tax_monthly,
        dependents=req.dependents,
        year=req.year,
        month=req.month,
    )

    result = calculator.calculate(inp)
    estimate = calculator.estimate_next_month(inp)

    if req.save:
        record = SalaryRecord(
            year=req.year,
            month=req.month,
            base_salary=req.base_salary,
            work_days=req.work_days,
            work_hours=req.work_hours,
            overtime_hours_125=req.overtime_hours_125,
            overtime_hours_135=req.overtime_hours_135,
            holiday_work_hours=req.holiday_work_hours,
            commute_allowance=req.commute_allowance,
            other_allowances=req.other_allowances,
            gross_salary=result.gross_salary,
            health_insurance=result.health_insurance,
            pension=result.pension,
            employment_insurance=result.employment_insurance,
            income_tax=result.income_tax,
            resident_tax=result.resident_tax,
            net_salary=result.net_salary,
        )
        db.add(record)
        await db.commit()

    return estimate


@router.get("/records")
async def get_salary_records(db: AsyncSession = Depends(get_db)):
    """過去の給与記録を取得する"""
    result = await db.execute(
        select(SalaryRecord).order_by(desc(SalaryRecord.year), desc(SalaryRecord.month))
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "year": r.year,
            "month": r.month,
            "base_salary": r.base_salary,
            "overtime_hours_125": r.overtime_hours_125,
            "overtime_hours_135": r.overtime_hours_135,
            "gross_salary": r.gross_salary,
            "net_salary": r.net_salary,
            "total_deductions": (r.health_insurance or 0) + (r.pension or 0) + (r.employment_insurance or 0) + (r.income_tax or 0) + (r.resident_tax or 0),
        }
        for r in records
    ]


@router.delete("/records/{record_id}")
async def delete_salary_record(record_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SalaryRecord).where(SalaryRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    await db.delete(record)
    await db.commit()
    return {"deleted": record_id}
