from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import analysis, chat, documents, o1

app = FastAPI(title="Proofly API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """A malformed request body (bad field, out-of-range length, unknown
    enum value, ...) is a 400 in this API, not FastAPI's default 422.
    """
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": jsonable_encoder(exc.errors())})


app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(o1.router)
app.include_router(chat.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "proofly-api"}
