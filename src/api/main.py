from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.api.limiter import limiter          # shared instance
from src.api.routes.research import router as research_router
from src.api.routes.health import router as health_router
from src.persistence.db import _get_conn  # triggers table creation on startup

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup - creates DB + jobs table if not exists
    _get_conn()
    yield
    # Runs at shutdown - nothing to clean up currently


app = FastAPI(
    title="Argus Deep Research Engine",
    description="Multi-agent research pipeline: Planner → Researcher → Critic → Writer",
    version="1.0.0",
    lifespan=lifespan,
)

# slowapi — must be set AFTER app is defined
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(research_router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
