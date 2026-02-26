"""Routes package — collects all sub-routers into a single list."""
from .auth import router as auth_router
from .appointments import router as appointments_router
from .clients import router as clients_router
from .payments import router as payments_router
from .calendar import router as calendar_router
from .jobs import router as jobs_router
from .public import router as public_router
from .webhooks import router as webhooks_router
from .admin import router as admin_router
from .events import router as events_router

all_routers = [
    auth_router,
    appointments_router,
    clients_router,
    payments_router,
    calendar_router,
    jobs_router,
    public_router,
    webhooks_router,
    admin_router,
    events_router,
]
