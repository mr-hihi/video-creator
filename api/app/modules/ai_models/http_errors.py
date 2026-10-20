from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.ai_models.ai_calls import AiProviderNotSetUpError, GoogleModelRequiredError


def register_ai_model_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AiProviderNotSetUpError, handle_ai_model_not_ready)
    app.add_exception_handler(GoogleModelRequiredError, handle_ai_model_not_ready)


async def handle_ai_model_not_ready(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(error)})
