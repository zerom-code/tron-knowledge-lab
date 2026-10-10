import hashlib
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import insert
from app.config import settings
from app.db import Session
from app.errors import AppError
from app.models import RateBucket


async def reserve(request):
    day = datetime.now(timezone.utc).date().isoformat()
    peer = request.client.host if request.client else "local"
    visitor = hashlib.sha256((day + peer).encode()).hexdigest()[:24]
    async with Session.begin() as session:
        for bucket, limit in [(day + ":global", settings.daily_global_limit),
                              (day + ":" + visitor, settings.daily_visitor_limit)]:
            statement = insert(RateBucket).values(bucket=bucket, used=1).on_conflict_do_update(
                index_elements=[RateBucket.bucket],
                set_={"used": RateBucket.used + 1},
                where=RateBucket.used < limit,
            ).returning(RateBucket.used)
            if await session.scalar(statement) is None:
                raise AppError("DAILY_LIMIT", "Дневной лимит операций API исчерпан. Сохранённые примеры доступны.", 429)
