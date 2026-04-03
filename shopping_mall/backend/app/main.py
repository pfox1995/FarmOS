import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import products, categories, cart, orders, users, reviews, stores, wishlists
from app.routers import shipments, calendar, reports, analytics, chatbot

logger = logging.getLogger(__name__)

# Create tables on startup
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle: start and stop APScheduler."""
    try:
        from jobs.scheduler import setup_scheduler
        sched = setup_scheduler()
        sched.start()
        logger.info("APScheduler started.")
    except Exception as e:
        logger.warning(f"Failed to start scheduler: {e}")
        sched = None

    yield

    if sched is not None:
        sched.shutdown(wait=False)
        logger.info("APScheduler stopped.")


app = FastAPI(title="Shopping Mall API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing routers
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(users.router)
app.include_router(reviews.router)
app.include_router(stores.router)
app.include_router(wishlists.router)

# Backoffice routers
app.include_router(shipments.router)
app.include_router(calendar.router)
app.include_router(reports.router)
app.include_router(analytics.router)
app.include_router(chatbot.router)


@app.get("/")
def root():
    return {"message": "Shopping Mall API is running", "docs": "/docs"}
