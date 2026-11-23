import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from openbook import __version__
from openbook.api.routes import ai, auth, contracts, reconcile, terms

app = FastAPI(title="OpenBook API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    # 프론트 주소. 여러 개면 쉼표로 구분한다 (예: 배포 주소)
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(contracts.router)
app.include_router(terms.router)
app.include_router(reconcile.router)
app.include_router(ai.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
