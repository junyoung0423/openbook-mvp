# Vercel 배포 안내

같은 저장소로 **Vercel 프로젝트 2개**를 만든다.

| 프로젝트 | Root Directory | 프레임워크 | 하는 일 |
|---|---|---|---|
| `openbook-api` | 저장소 루트 (비워 둠) | FastAPI (자동 인식) | 백엔드 API. 루트의 `app.py`, `requirements.txt`, `vercel.json` 사용 |
| `openbook-web` | `frontend` | Next.js (자동 인식) | 화면 |

DB는 Vercel Marketplace의 **Neon (Postgres)** 를 `openbook-api`에 연결한다.

## 왜 이렇게 바꿨나 (2026-11-25)

Vercel 함수는 서버가 계속 떠 있는 방식이 아니라서 로컬과 다른 점이 있다 (Vercel 문서 2026-11 기준).

| Vercel 제약 | 바꾼 것 |
|---|---|
| 응답을 보낸 뒤 작업(FastAPI BackgroundTasks)이 끝까지 돈다는 보장이 없음 | Vercel에서는(`VERCEL=1`) 계약서 처리를 **요청 안에서 끝내고** 응답한다 (약 15–60초). 로컬은 그대로 202 → 백그라운드 |
| 함수 실행 최대 300초 (Hobby) | `vercel.json` `maxDuration: 300` |
| 요청 본문 4.5MB까지 | 파일 업로드를 **4MB**로 낮춤 (화면에서도 미리 막음). 큰 파일은 본문 붙여넣기 |
| 파일 시스템이 읽기 전용, `/tmp`는 사라짐 → SQLite 못 씀 | Postgres(Neon). `postgres://` 주소도 자동으로 psycopg 주소로 바꿈 |
| 배포는 git에 있는 파일만 실림 | 법령 색인 `data/law/index.json`을 float16으로 줄여(30MB → 4.9MB) **저장소에 넣음** |
| 함수 인스턴스가 쉬었다 깨어남 | DB 연결 `pool_pre_ping`, 작은 풀 |

로컬에서 Vercel처럼 돌려 보기: 저장소 루트에서
`VERCEL=1 backend/.venv/Scripts/python -m uvicorn app:app --port 8001`
(2026-11-25 확인: 데모 2 본문 붙여넣기 → 15초 뒤 '조건 확인 대기'로 응답, 법령 Q&A 정상).

## 처음 한 번 (계정 주인이 직접)

1. **Vercel 가입·로그인**, GitHub 저장소 `junyoung0423/openbook-mvp` 접근 허용
2. **API 프로젝트** 만들기: Add New → Project → 저장소 선택
   - Root Directory: 비워 둠 (저장소 루트), Framework: FastAPI로 잡히는지 확인
   - Region(Settings → Functions): `icn1` (서울) 권장 — Upstage·사용자와 가깝게
3. **DB 연결**: API 프로젝트 → Storage → Neon (Postgres) 만들기 → 프로젝트에 연결
   - `DATABASE_URL`이 환경변수로 자동 들어간다. 리전은 아시아에서 가장 가까운 곳
4. **API 환경변수** (Settings → Environment Variables, Production)

   | 이름 | 값 |
   |---|---|
   | `UPSTAGE_API_KEY` | Upstage 키 (`.env`와 같은 값, 채팅·커밋에 붙이지 않는다) |
   | `DATABASE_URL` | 3번에서 자동 |
   | `CORS_ORIGINS` | 화면 주소, 예: `https://openbook-web.vercel.app` (5번 뒤에 채움) |

   넣지 않는 것: `OPENBOOK_AUTH_DISABLED` (Postgres에서는 어차피 무시된다), `LAW_OC` (색인을 만들 때만 필요, 배포에는 필요 없음)
5. **화면 프로젝트** 만들기: 같은 저장소로 Add New → Project
   - Root Directory: `frontend`
   - 환경변수 `NEXT_PUBLIC_API_URL` = API 주소, 예: `https://openbook-api.vercel.app` (빌드 때 들어가므로 바꾸면 다시 배포)
   - 데모로 공개할 때만 `NEXT_PUBLIC_DEMO_MODE` = `1`: 모든 화면 위에 '데모 버전 · 가상 데이터' 띠가 나온다. 첫 화면의 '데모로 둘러보기'는 이 값과 상관없이 `데모1`·`데모2`·`데모3`으로 시작하는 확정 계약서가 있으면 나온다 (`backend/scripts/seed_demo.py`로 넣음)
6. API 프로젝트의 `CORS_ORIGINS`에 화면 주소를 넣고 API 다시 배포
7. **DB 테이블 만들기** (내 컴퓨터에서, Neon 주소로 한 번):
   ```powershell
   $env:DATABASE_URL = "<Neon 연결 주소>"; backend/.venv/Scripts/alembic -c backend/alembic.ini upgrade head; Remove-Item Env:DATABASE_URL
   ```

## 배포 뒤 확인

1. `https://<API 주소>/health` → `{"status":"ok"}`
2. 화면 주소 → 회원가입 → 로그인
3. 데모 2 본문 붙여넣기 → 조건 화면 (약 15–60초, 그동안 '읽는 중' 표시)
4. 정산서 붙여넣기 → 대조 결과 → Q&A "저작인격권을 양도할 수 있나요?" → 저작권법 제14조

## 그다음부터

- main에 합치면 두 프로젝트가 자동으로 다시 배포된다.
- DB 구조가 바뀌는 PR(새 alembic 마이그레이션)을 합치면 7번 명령을 다시 돌린다.
- 법령이 개정되면 `python -m openbook.law build` → `data/law/index.json` 커밋.

## 알려진 한계

- 계약서 처리 중에는 업로드 요청이 끝나지 않는다 (최대 300초). 처리가 300초를 넘으면 504가 나고 계약서는 '처리중'으로 남는다.
- 파일은 4MB까지. 사진을 여러 장 찍은 스캔 PDF는 넘을 수 있다 → 본문 붙여넣기.
- 법령 색인은 함수가 깨어날 때마다 읽는다 (약 1초).
