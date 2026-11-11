from fastapi import FastAPI

from openbook import __version__

app = FastAPI(title="OpenBook API", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
