import secrets
from fastapi import Header
from app.config import settings
from app.errors import AppError


def editor_configured():
    value = settings.editor_token.get_secret_value()
    return bool(value and value != "replace_with_a_private_editor_password")


async def editor(x_editor_token: str = Header(default="")):
    configured = settings.editor_token.get_secret_value()
    if not editor_configured():
        raise AppError("EDITOR_NOT_CONFIGURED", "Задайте EDITOR_TOKEN в .env и перезапустите приложение.", 503)
    if not secrets.compare_digest(x_editor_token.encode(), configured.encode()):
        raise AppError("EDITOR_REQUIRED", "Неверный пароль редактора. Используйте значение EDITOR_TOKEN из .env.", 403)
