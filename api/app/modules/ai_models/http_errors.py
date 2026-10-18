from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.ai_models.ai_calls import AiProviderNotSetUpError


def register_ai_model_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AiProviderNotSetUpError, handle_ai_provider_not_set_up)


async def handle_ai_provider_not_set_up(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(error)})
