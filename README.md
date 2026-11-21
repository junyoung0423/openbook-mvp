# 오픈북 (OpenBook)

계약서에서 MG·RS 조건을 읽어 내고, 사용자가 확정한 조건으로 계산한 금액을 플랫폼 정산서 금액과 나란히 보여 주는 웹앱입니다.

> 핵심 원칙: LLM은 계약서를 읽고 설명하는 데에만 쓰고, 금액과 날짜는 코드가 계산하며, 사용자가 확정한 값만 씁니다.

상세 설계는 [docs/오픈북 MVP 개발명세서.docx](docs/오픈북%20MVP%20개발명세서.docx)를 봅니다.

## 레포 구조

```
.
├── backend/                 # Python (FastAPI + AI 파이프라인 + 계산 엔진)
│   ├── src/openbook/
│   │   ├── api/             # FastAPI 라우터·앱             (박다연)
│   │   ├── schemas/         # 공용 pydantic 스키마 (JSON 계약) (전원 합의)
│   │   ├── parsing/         # M1 문서 수집·파싱              (박다연)
│   │   ├── clauses/         # M2 조항 분할·유형 분류          (정준영)
│   │   ├── comparison/      # M3 표준계약서 비교              (정준영)
│   │   ├── terms/           # M4 MG·RS 조건 추출              (정준영, 검증 박다연)
│   │   ├── engine/          # M5 계산 엔진 — LLM 사용 금지     (박다연)
│   │   ├── reconcile/       # M6 대조·설명                    (박다연 로직, 정준영 문장)
│   │   ├── qa/              # M7 조항 Q&A                     (정준영)
│   │   └── alerts/          # M8 알림 (P2)                    (박다연)
│   └── tests/
├── frontend/                # Next.js + TypeScript + Tailwind (신민주)
└── docs/                    # 명세서, 스키마 합의 기록, 계산 규칙 명세 (허정민)
```

## 팀

| 담당 | 역할 |
|---|---|
| 허정민 | 기획·PM·검증 |
| 정준영 | AI 파이프라인 |
| 박다연 | 백엔드 |
| 신민주 | 프론트엔드 |
| 전시준 | 디자인 |

## 시작하기

### 백엔드

Python 3.11 이상이 필요합니다.

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash. macOS/Linux는 .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env      # API 키 입력
uvicorn openbook.api.main:app --reload
```

`http://localhost:8000/docs`에서 API 문서를 볼 수 있습니다. 테스트는 `pytest`로 돌립니다.

#### DB: SQLite로 빠르게 시작

`DATABASE_URL`을 설정하지 않으면 개발 DB는 `sqlite:///./openbook.db`를 사용합니다.

```bash
cd backend
alembic upgrade head
```

SQLite는 개발 편의를 위한 경로입니다. 금액 컬럼은 SQLAlchemy `NUMERIC`/Python `Decimal`로 선언되어 있지만 SQLite 자체의 정밀도 특성은 PostgreSQL과 다르므로, 배포 전 PostgreSQL 왕복 테스트를 실행합니다.

#### DB: PostgreSQL

루트에서 PostgreSQL을 띄웁니다.

```bash
docker compose up -d db
```

`.env`의 `DATABASE_URL`을 PostgreSQL로 두고 마이그레이션합니다.

```bash
cd backend
alembic upgrade head
```

마이그레이션 도구는 **Alembic**을 사용합니다. SQLAlchemy 모델과 같은 생태계이고 SQLite/PostgreSQL 모두 같은 마이그레이션 경로를 사용할 수 있기 때문입니다.

### 프론트엔드

[frontend/README.md](frontend/README.md)를 봅니다.

## 협업 규칙

- `main`에 직접 push하지 않습니다. 기능마다 브랜치를 따고 PR로 합칩니다.
  - 브랜치 이름: `feat/m2-clause-split`, `fix/engine-rounding`, `docs/schema-v1`처럼 `종류/모듈-내용`
- PR은 한 명 이상 리뷰를 받고 합칩니다. 스키마(`backend/src/openbook/schemas/`)를 바꾸는 PR은 프론트·백엔드 담당이 모두 확인합니다.
- **실제 계약서·정산서는 절대 커밋하지 않습니다.** 로컬의 `data/private/`에 두면 git이 무시합니다. 가상·익명화한 샘플만 `data/samples/`에 둡니다.
- API 키는 `.env`에만 두고 커밋하지 않습니다.
- 금지 표현(위반, 부당, 불리, 유리, 위험도 점수)은 사용자에게 보이는 어떤 문장에도 쓰지 않습니다.
