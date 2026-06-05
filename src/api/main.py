from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routers import ingesta
from src.services.documents import DocumentoError

app = FastAPI(
    title="Semantic Classification API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DocumentoError)
async def documento_error_handler(request: Request, exc: DocumentoError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.codigo_http,
        content={"detail": exc.mensaje},
    )


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ingesta.router)
