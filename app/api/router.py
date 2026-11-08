from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.versioned_router)

# Further routers (auth, organizations, api-keys, notifications, templates, ...) are added as
# their respective roadmap steps (ARCHITECTURE.md §12) are implemented.
