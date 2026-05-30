# 개인 예산관리 시스템

일본 거주자를 위한 개인 자산·수지·주식 통합 관리 시스템입니다.

## 실행 방법

```bash
# 1. 저장소 클론
git clone https://github.com/jeonhun6084/BudgetManagementSystem.git
cd BudgetManagementSystem

# 2. 환경설정 (.env 파일 생성)
cp .env.example .env
# .env 파일을 열어 인증정보 입력 (아래 설정 참고)

# 3. 서버 시작 (가상환경 자동 생성 포함)
./start.sh
```

브라우저에서 **http://localhost:8000** 접속

---

## 기능 목록

### 1. 대시보드 (ダッシュボード)
- 월별 / 연간 수입·지출·수지 합계 카드
- 카테고리별 지출 도넛 차트
- 월별 수지 추이 막대 차트

### 2. 수지 명세 (収支明細)
- 거래 내역 목록 (날짜·금액·카테고리·소스 필터)
- **스미토모 은행 (SMBC) CSV 임포트**
- **Vpass (三井住友カード) CSV 임포트**

### 3. 급여 계산 (給与計算)
- 기본급·시간외 수당 (25%/35% 할증) 자동 계산
- 건강보험·후생연금·고용보험·소득세·주민세 공제 자동 계산
- 급여 이력 저장 및 비교

### 4. 경비 신청 (経費申請)
- 楽楽清算 자동 제출 (Playwright 연동)
- 경비 신청 이력 관리

### 5. 주식 관리 (株式管理) ★ NEW
#### 보유 종목 포트폴리오
- 종목 추가 (일본·미국·한국·ETF)
- 실시간 현재가 자동 조회 (yfinance)
- 평가액·손익·손익률 자동 계산
- JPY / USD 합계 요약

#### 관심 종목 워치리스트
- 현재가·전일비·시가총액·PER·PBR 표시
- 배당수익률·52주 고저 표시

#### AI 주식 분석 (Claude)
- 티커 입력 → Claude가 한국어로 분석
  - 기업 개요 / 투자 포인트 / 리스크 / 밸류에이션 / 투자 의견

**지원 시장:** 일본주 (TSE), 미국주 (NYSE/NASDAQ), 한국주 (KOSPI/KOSDAQ), ETF

---

## 환경설정 (.env)

```env
# 스미토모 은행 (SMBC)
SMBC_USER_ID=
SMBC_PASSWORD=
SMBC_BRANCH_CODE=

# Vpass (三井住友カード)
VPASS_USER_ID=
VPASS_PASSWORD=

# 楽楽清算
RAKURAKU_LOGIN_ID=
RAKURAKU_PASSWORD=
RAKURAKU_COMPANY_CODE=

# AI 분석 (주식 AI 분석 사용 시 필요)
ANTHROPIC_API_KEY=sk-ant-...

# 앱 설정
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite+aiosqlite:///./budget.db
```

> Anthropic API 키는 https://console.anthropic.com 에서 발급

---

## 기술 스택

| 항목 | 내용 |
|---|---|
| Backend | Python 3 + FastAPI + uvicorn |
| Database | SQLite (aiosqlite + SQLAlchemy async) |
| Scraping | Playwright (headless=False — OTP 입력 대응) |
| 주가 데이터 | yfinance |
| AI 분석 | Anthropic Claude API (claude-sonnet-4-6) |
| Frontend | 순수 HTML/CSS/JS + Chart.js |

## 디렉토리 구조

```
BudgetManagementSystem/
├── backend/
│   ├── app/
│   │   ├── routers/       transactions.py, salary.py, expenses.py, stocks.py
│   │   ├── models/        models.py
│   │   ├── scrapers/      smbc.py, vpass.py, rakuraku.py
│   │   ├── services/      salary_calculator.py
│   │   ├── database/      db.py
│   │   └── main.py
│   └── requirements.txt
├── frontend/
│   ├── static/{css,js}
│   └── templates/index.html
├── .env.example
├── start.sh
└── README.md
```
