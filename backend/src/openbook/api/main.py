from fastapi import FastAPI

from openbook import __version__
from openbook.api.routes import ai, terms

app = FastAPI(title="OpenBook API", version=__version__)
app.include_router(terms.router)
app.include_router(ai.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
