# frontend

오픈북 화면입니다. Next.js(App Router) + TypeScript + Tailwind CSS v4로 만들었고, 서버와는 JSON API로만 통신합니다.
디자인은 `docs/design/mockup/`의 시안을 따릅니다(구현 기준과 규칙: [`docs/work-orders/05-디자인-적용.md`](../docs/work-orders/05-디자인-적용.md)).

## 실행

Node.js 22 이상이 필요합니다(CI와 같은 버전).

```bash
cd frontend
npm ci          # 처음 한 번
npm run dev     # http://localhost:3000
```

화면은 API 서버가 켜져 있어야 동작합니다. 기본 주소는 `http://localhost:8000`입니다.

```bash
# 백엔드 (다른 터미널). 로그인 없이 "로컬 사용자"로 쓰려면 OPENBOOK_AUTH_DISABLED=1
cd backend
OPENBOOK_AUTH_DISABLED=1 uvicorn openbook.api.main:app --reload
```

백엔드 설치와 DB 준비는 [루트 README](../README.md)를 봅니다. API 키 없이 화면만 볼 때의 방법은
[작업지시서 8절](../docs/work-orders/05-디자인-적용.md)에 있습니다.

### 데모 데이터

```bash
python backend/scripts/seed_demo.py   # 데모 1~3(가상 계약서·정산서)을 확정 상태로 넣음
```

넣고 나면 첫 화면에 "데모로 둘러보기"가 나타납니다. 심사 진행 순서는 [`docs/demo-script.md`](../docs/demo-script.md)입니다.

## 환경변수

| 이름 | 쓰임 | 기본값 |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | API 서버 주소. 빌드 때 들어가므로 바꾸면 다시 빌드합니다 | `http://localhost:8000` |
| `NEXT_PUBLIC_DEMO_MODE` | `1`이면 모든 화면 위에 "데모 버전 · 가상 데이터" 띠를 보입니다 | 꺼짐 |

비밀 값(API 키 등)은 프런트엔드에 두지 않습니다. 배포 방법은 [`docs/deploy-vercel.md`](../docs/deploy-vercel.md)입니다.

## 검사

```bash
npm run lint
npm test        # lib/format.test.ts — 금액·비율 변환 함수
npm run build   # 타입 검사 포함
```

CI(`.github/workflows/ci.yml`)가 같은 세 가지를 돌립니다. PR 전에 아래 네 검사도 결과가 없어야 합니다.

```bash
grep -rnE "위반|부당|불리|유리|위험|손해|불공정|문제 있" src --include=*.tsx          # 금지 표현
grep -rnE "Number\(|parseFloat|parseInt" src --include=*.tsx --include=*.ts           # 금액을 숫자로 바꾸는 코드
grep -rnE "(text|bg|border)-(red|green|emerald|rose|amber|yellow)-" src               # 판단을 암시하는 색
grep -rnE "rounded-full|999px|50%" src --include=*.tsx --include=*.css                # 완전 둥근 모양
```

## 지켜야 할 것 (요약)

자세한 내용은 작업지시서 2절과 [공통 규칙](../docs/work-orders/00-공통-규칙.md)입니다.

- **금액은 문자열**로 주고받고 `Number`로 바꿔 계산하지 않습니다. 콤마·% 표시는 `src/lib/format.ts`의 문자열 함수로만 합니다.
- **서버가 준 숫자를 그대로** 보여 줍니다(반올림·축약 금지). 차이의 부호와 뜻은 서버 문장(`diff_meaning`)을 따릅니다.
- **색으로 좋고 나쁨을 표현하지 않습니다.** 차이는 숫자와 글로만 보이고, 상태 라벨(`추출됨` / `찾지 못함` / `직접 입력`)은 색이 아니라 모양(채움·점선·실선)으로 구분합니다. `--color-error`는 입력·네트워크 오류 문구에만 씁니다.
- 사용자에게 보이는 모든 문장에서 금지 표현을 쓰지 않습니다.

## 폴더

```
src/
  app/
    layout.tsx          # 글꼴(Pretendard)과 AppShell
    globals.css         # 디자인 토큰(@theme), .num(고정폭 숫자)
    page.tsx            # 첫 화면: 계약서 올리기
    terms/              # 조건 확인
    statements/         # 정산서 입력
    results/            # 대조 결과
    qa/                 # 계약서에 질문하기
    login/              # 로그인·회원가입
  components/
    AppShell.tsx        # 바깥 배경 + 앱 창 + 사이드바 + 본문 (로그인은 앱 창 없음)
    Sidebar.tsx         # 내 계약서 목록, 계약서 올리기, 삭제 메뉴, 모바일 서랍
    ContractHeader.tsx  # 계약서 이름 + 탭(조건 확인 / 정산서 입력 / 대조 결과 / 질문하기)
    ShellContext.tsx    # 지금 계약서와 내 계약서 목록 (상태가 바뀌면 reload로 갱신)
    …                   # Card, Button, MoneyInput, RateInput, StatusBadge, SourceQuote, InfoPanel 등 공용 부품
  lib/
    api.ts              # API 호출과 응답 타입
    format.ts           # 금액·비율·날짜 표시 변환 (테스트 있음)
    ui.ts               # 버튼·입력칸 클래스
```

- 화면은 모두 클라이언트 컴포넌트이고, 계약서는 주소의 `?id=`로 가리킵니다.
- 계약서 상태(`처리중` / `조건 확인 대기` / `확정` / `처리 실패`)가 바뀌는 화면은 `useContract().reload()`와 `useContracts().reloadContracts()`를 불러 탭 바와 사이드바가 새로고침 없이 바뀌게 합니다.
- 새 UI 라이브러리는 들이지 않습니다. 아이콘은 `lucide-react`만 쓰고, 결과·조건 상태에는 판단을 암시하는 아이콘(체크, 경고 삼각형, X)을 쓰지 않습니다.
