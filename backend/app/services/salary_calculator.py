"""
給与計算サービス
日本の税制・社会保険に基づいた給与計算を行う
"""
from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class SalaryInput:
    base_salary: float          # 基本給
    work_days: int = 20         # 所定労働日数
    work_hours: float = 160     # 所定労働時間
    overtime_hours_125: float = 0   # 時間外労働（25%割増）
    overtime_hours_135: float = 0   # 深夜・休日労働（35%割増）
    holiday_work_hours: float = 0   # 休日労働時間
    commute_allowance: float = 0    # 通勤手当
    other_allowances: float = 0     # その他手当（住宅手当等）
    # 社会保険設定
    health_insurance_rate: float = 0.0998  # 健康保険料率（東京2024年度）
    pension_rate: float = 0.183           # 厚生年金保険料率
    employment_insurance_rate: float = 0.006  # 雇用保険料率
    # 住民税（月割り）
    resident_tax_monthly: float = 0       # 住民税月額（前年所得により確定）
    year: int = 2024
    month: int = 1
    # 扶養控除
    dependents: int = 0


@dataclass
class SalaryResult:
    # 支給額
    base_salary: float
    overtime_pay: float
    holiday_pay: float
    commute_allowance: float
    other_allowances: float
    gross_salary: float
    # 控除額
    health_insurance: float
    pension: float
    employment_insurance: float
    income_tax: float
    resident_tax: float
    total_deductions: float
    # 手取り
    net_salary: float
    # 詳細情報
    hourly_rate: float
    overtime_rate_125: float
    overtime_rate_135: float


class SalaryCalculator:
    # 2024年度 所得税速算表（源泉徴収税額表 月額表）
    INCOME_TAX_TABLE = [
        (88000, 0, 0),
        (89000, 130, 0),
        (90000, 180, 0),
        (91000, 230, 0),
        (92000, 290, 0),
        (93000, 340, 0),
        (94000, 390, 0),
        (95000, 440, 0),
        (96000, 490, 0),
        (97000, 540, 0),
        (98000, 590, 0),
        (99000, 640, 0),
        (101000, 720, 0),
        (105000, 840, 0),
        (109000, 1120, 0),
        (113000, 1270, 0),
        (117000, 1420, 0),
        (121000, 1570, 0),
        (125000, 1720, 0),
        (129000, 1870, 0),
        (133000, 2020, 0),
        (141000, 2290, 0),
        (149000, 2580, 0),
        (157000, 2850, 0),
        (169000, 3260, 0),
        (183000, 3750, 0),
        (197000, 4360, 0),
        (211000, 4900, 0),
        (225000, 5540, 0),
        (239000, 6180, 0),
        (253000, 6820, 0),
        (267000, 7460, 0),
        (281000, 8100, 0),
        (295000, 8740, 0),
        (309000, 9380, 0),
        (323000, 10020, 0),
        (337000, 10660, 0),
        (351000, 11300, 0),
        (365000, 11940, 0),
        (379000, 12580, 0),
        (393000, 13220, 0),
        (407000, 13900, 0),
        (421000, 14610, 0),
        (435000, 15320, 0),
        (449000, 16030, 0),
        (463000, 16830, 0),
        (477000, 17540, 0),
        (491000, 18280, 0),
        (505000, 19130, 0),
        (519000, 19980, 0),
        (533000, 20830, 0),
        (547000, 21680, 0),
        (561000, 22600, 0),
        (575000, 23450, 0),
        (589000, 24320, 0),
        (603000, 25190, 0),
        (617000, 26060, 0),
        (631000, 26930, 0),
        (645000, 27800, 0),
        (659000, 28670, 0),
        (673000, 29540, 0),
        (687000, 30490, 0),
        (701000, 31500, 0),
        (715000, 32510, 0),
        (729000, 33500, 0),
        (743000, 34510, 0),
        (757000, 35820, 0),
        (771000, 37130, 0),
        (785000, 38440, 0),
        (799000, 39750, 0),
        (813000, 41060, 0),
        (827000, 42370, 0),
        (841000, 43680, 0),
        (855000, 44990, 0),
        (869000, 46300, 0),
        (883000, 47610, 0),
        (897000, 48920, 0),
        (911000, 50230, 0),
        (925000, 51540, 0),
        (939000, 52850, 0),
        (953000, 54160, 0),
        (967000, 55470, 0),
        (981000, 56780, 0),
        (995000, 58090, 0),
        (1009000, 59720, 0),
        (1023000, 61680, 0),
        (1037000, 63640, 0),
        (1051000, 65600, 0),
        (1065000, 67560, 0),
        (1079000, 69520, 0),
        (1093000, 71480, 0),
        (1107000, 73440, 0),
        (1121000, 75400, 0),
        (1135000, 77360, 0),
        (1149000, 79320, 0),
        (1163000, 81280, 0),
        (1177000, 83240, 0),
        (1191000, 85200, 0),
        (1205000, 87160, 0),
        (1219000, 89440, 0),
        (1233000, 91960, 0),
        (1247000, 94480, 0),
        (float('inf'), 97000, 0),
    ]

    def calculate(self, inp: SalaryInput) -> SalaryResult:
        # 時間単価計算（月所定労働時間で割る）
        hourly_rate = inp.base_salary / inp.work_hours if inp.work_hours > 0 else 0

        # 割増賃金率（時間外25%、深夜・休日35%）
        overtime_rate_125 = hourly_rate * 1.25
        overtime_rate_135 = hourly_rate * 1.35

        # 時間外労働手当
        overtime_pay = (
            inp.overtime_hours_125 * overtime_rate_125 +
            inp.overtime_hours_135 * overtime_rate_135 +
            inp.holiday_work_hours * overtime_rate_135
        )

        # 総支給額（交通費除く）
        taxable_gross = inp.base_salary + overtime_pay + inp.other_allowances
        gross_salary = taxable_gross + inp.commute_allowance

        # 社会保険料計算（標準報酬月額ベース、ここでは簡略化）
        # 標準報酬月額（交通費含む）
        standard_monthly_compensation = self._get_standard_monthly_compensation(gross_salary)

        health_insurance = math.floor(standard_monthly_compensation * inp.health_insurance_rate / 2)
        pension = math.floor(standard_monthly_compensation * inp.pension_rate / 2)
        # 厚生年金上限（2024年: 標準報酬月額65万円が上限）
        pension = min(pension, math.floor(650000 * inp.pension_rate / 2))
        employment_insurance = math.floor(taxable_gross * inp.employment_insurance_rate)

        social_insurance_total = health_insurance + pension + employment_insurance

        # 所得税計算（社会保険料控除後の金額で計算）
        # 給与所得控除後の課税標準額
        income_after_deduction = taxable_gross - social_insurance_total
        income_tax = self._calculate_income_tax(income_after_deduction, inp.dependents)

        # 住民税（前年所得から計算された月割り額を使用）
        resident_tax = inp.resident_tax_monthly

        # 合計控除額
        total_deductions = social_insurance_total + income_tax + resident_tax

        # 手取り額
        net_salary = gross_salary - total_deductions

        return SalaryResult(
            base_salary=inp.base_salary,
            overtime_pay=overtime_pay,
            holiday_pay=inp.holiday_work_hours * overtime_rate_135,
            commute_allowance=inp.commute_allowance,
            other_allowances=inp.other_allowances,
            gross_salary=gross_salary,
            health_insurance=health_insurance,
            pension=pension,
            employment_insurance=employment_insurance,
            income_tax=income_tax,
            resident_tax=resident_tax,
            total_deductions=total_deductions,
            net_salary=net_salary,
            hourly_rate=hourly_rate,
            overtime_rate_125=overtime_rate_125,
            overtime_rate_135=overtime_rate_135,
        )

    def _get_standard_monthly_compensation(self, gross: float) -> float:
        """標準報酬月額を算出する（簡略版）"""
        # 厚生年金の標準報酬月額等級表（2024年）
        compensation_brackets = [
            88000, 98000, 104000, 110000, 118000, 126000, 134000, 142000,
            150000, 160000, 170000, 180000, 190000, 200000, 220000, 240000,
            260000, 280000, 300000, 320000, 340000, 360000, 380000, 410000,
            440000, 470000, 500000, 530000, 560000, 590000, 620000, 650000,
        ]
        for bracket in compensation_brackets:
            if gross <= bracket * 1.025:  # ±2.5%の範囲で切り上げ
                return float(bracket)
        return 650000.0

    def _calculate_income_tax(self, taxable_amount: float, dependents: int = 0) -> float:
        """源泉所得税を計算する（月額表・甲欄）"""
        # 基礎控除等の配慮（扶養控除）
        # 簡略版：月額表の甲欄に基づく
        for i, (threshold, tax_base, _) in enumerate(self.INCOME_TAX_TABLE):
            if taxable_amount < threshold:
                if i == 0:
                    return 0
                # 扶養人数による控除
                prev_threshold, prev_tax, _ = self.INCOME_TAX_TABLE[i - 1]
                tax = prev_tax
                # 扶養1人あたりの控除（概算）
                dependent_deduction = 0
                if dependents == 1:
                    dependent_deduction = tax * 0.1
                elif dependents >= 2:
                    dependent_deduction = tax * 0.2
                return max(0, math.floor(tax - dependent_deduction))
        # 上限を超えた場合
        return math.floor(self.INCOME_TAX_TABLE[-1][1])

    def estimate_next_month(self, inp: SalaryInput) -> dict:
        """来月の給与を予測する"""
        result = self.calculate(inp)
        return {
            "gross_salary": result.gross_salary,
            "net_salary": result.net_salary,
            "total_deductions": result.total_deductions,
            "breakdown": {
                "base_salary": result.base_salary,
                "overtime_pay": result.overtime_pay,
                "commute_allowance": result.commute_allowance,
                "other_allowances": result.other_allowances,
            },
            "deductions": {
                "health_insurance": result.health_insurance,
                "pension": result.pension,
                "employment_insurance": result.employment_insurance,
                "income_tax": result.income_tax,
                "resident_tax": result.resident_tax,
            },
            "hourly_info": {
                "hourly_rate": result.hourly_rate,
                "overtime_rate_125": result.overtime_rate_125,
                "overtime_rate_135": result.overtime_rate_135,
            }
        }
