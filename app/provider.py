import json
import math
from datetime import datetime, timezone
import httpx
from app.config import settings
from app.errors import AppError


async def request(path, payload):
    key = settings.openai_api_key.get_secret_value()
    if not key:
        raise AppError("API_NOT_CONFIGURED", "Для нового embedding или ответа нужен серверный ключ OpenAI.", 503)
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.openai.com/v1/" + path, json=payload,
                headers={"Authorization": "Bearer " + key},
            )
    except httpx.HTTPError:
        raise AppError("UPSTREAM_TIMEOUT", "OpenAI не ответил вовремя. Повторите позже.", 504) from None
    if response.status_code != 200:
        raise AppError(
            "UPSTREAM_LIMIT" if response.status_code == 429 else "UPSTREAM_ERROR",
            "OpenAI ограничил запросы; проверьте баланс и повторите позже."
            if response.status_code == 429 else "Не удалось получить ответ OpenAI.",
            429 if response.status_code == 429 else 502,
        )
    try:
        return response.json()
    except ValueError:
        raise AppError("INVALID_RESPONSE", "OpenAI вернул некорректный ответ.", 502) from None


async def embed(text):
    result = await request("embeddings", {
        "model": settings.embedding_model, "dimensions": settings.embedding_dimensions, "input": text,
    })
    try:
        vector = result["data"][0]["embedding"]
        if len(vector) != 256 or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in vector):
            raise ValueError()
        return vector
    except (KeyError, TypeError, ValueError, IndexError):
        raise AppError("INVALID_EMBEDDING", "Получен некорректный embedding.", 502) from None


async def structured(instruction, payload, schema, name, tokens=1800):
    data = await request("chat/completions", {
        "model": settings.chat_model, "temperature": 0, "max_completion_tokens": tokens,
        "messages": [{"role": "system", "content": instruction},
                     {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": name, "strict": True, "schema": schema,
        }},
    })
    try:
        result = json.loads(data["choices"][0]["message"]["content"])
        return {**result, "model": data["model"], "usage": data.get("usage", {}),
                "generatedAt": datetime.now(timezone.utc).isoformat()}
    except (KeyError, TypeError, ValueError, IndexError):
        raise AppError("INVALID_RESPONSE", "Модель не вернула ожидаемую структуру.", 502) from None
