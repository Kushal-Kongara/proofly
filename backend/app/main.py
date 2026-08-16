from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analysis, documents, o1

app = FastAPI(title="Proofly API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(o1.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "proofly-api"}
