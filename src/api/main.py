from fastapi import FastAPI

app = FastAPI(
    title="Semantic Classification API",
    description="API para procesamiento documental y análisis territorial",
    version="0.1.0"
)

@app.get("/")
def root():
    return {"message": "Semantic Classification API", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
