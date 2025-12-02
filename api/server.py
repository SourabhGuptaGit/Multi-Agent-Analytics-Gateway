from fastapi import FastAPI
from api.routes.health_routes import router as health_router
from api.routes.ask_routes import router as ask_router
from api.routes.sql_routes import router as sql_router

from core.config import settings

app = FastAPI(
    title="Multi-Agent Analytics Gateway API",
    description="A sophisticated framework that transforms natural language queries into executable data analyses.\nNL query → SQL → DuckDB → Answer.",
    version="1.0.0"
)

# Mount API routes
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(ask_router, prefix="/api", tags=["ask"])
app.include_router(sql_router, prefix="/api", tags=["sql"])

@app.get("/")
def index():
    return {"message": "Welcome to the MAAG API"}


if __name__ == "__main__":
    FASTAPI_HOST = settings.FASTAPI_HOST
    FASTAPI_PORT = int(settings.FASTAPI_PORT) if settings.FASTAPI_PORT.isdigit() else 8000
    uvicorn.run(app, host=FASTAPI_HOST, port=FASTAPI_PORT)