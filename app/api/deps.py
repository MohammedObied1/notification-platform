from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

DBSession = Annotated[Session, Depends(get_db)]

# Auth dependencies (CurrentUser, ApiKeyPrincipal, etc.) land in Step 2 once Organization/User/
# ApiKey models exist — nothing to depend on yet.


class Pagination:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        size: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    ) -> None:
        self.page = page
        self.size = size
        self.offset = (page - 1) * size

    def build(self, items: list, total: int) -> dict:
        return {"items": items, "total": total, "page": self.page, "size": self.size, "pages": max(1, -(-total // self.size))}


PageParams = Annotated[Pagination, Depends()]
