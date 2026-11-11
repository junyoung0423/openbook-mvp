# frontend

Next.js + TypeScript + Tailwind (담당: 신민주)

이 폴더에서 프로젝트를 생성해 시작합니다.

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir
```

- 서버와는 JSON API로만 통신합니다. 스키마가 합의되기 전에는 목 데이터로 개발합니다.
- API 명세는 백엔드 실행 후 `http://localhost:8000/docs`에서 확인합니다.
