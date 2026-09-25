from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.routers import (
    analysis_networks,
    documents,
    semantic_nodes,
    semantic_relationships,
)
from src.config import settings
from src.services.documents import DocumentoError

app = FastAPI(
    title="Semantic Classification API",
    version="0.1.0",
)

settings.STORAGE_GRAPHS.mkdir(parents=True, exist_ok=True)
app.mount(
    "/files/graphs",
    StaticFiles(directory=settings.STORAGE_GRAPHS),
    name="graph-files",
)
settings.STORAGE_NETWORK.mkdir(parents=True, exist_ok=True)
app.mount(
    "/files/networks",
    StaticFiles(directory=settings.STORAGE_NETWORK),
    name="network-files",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DocumentoError)
async def documento_error_handler(
    request: Request, exc: DocumentoError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.codigo_http,
        content={"detail": exc.mensaje},
    )


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(documents.router)
app.include_router(analysis_networks.router)
app.include_router(semantic_nodes.router)
app.include_router(semantic_relationships.router)
