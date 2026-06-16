from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import strategy, publish, channel, receipt, risk, open_api


@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(strategy.router, prefix=settings.API_PREFIX)
app.include_router(publish.router, prefix=settings.API_PREFIX)
app.include_router(channel.router, prefix=settings.API_PREFIX)
app.include_router(receipt.router, prefix=settings.API_PREFIX)
app.include_router(risk.router, prefix=settings.API_PREFIX)
app.include_router(open_api.router, prefix=settings.API_PREFIX)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}
