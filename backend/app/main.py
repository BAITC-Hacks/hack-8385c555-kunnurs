"""HTTP boundary: validate IDs, compute on the server, then request an explanation."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai.agent import configured_mode, explain_scenario
from backend.app.seed import ROOT, get_catalog
from backend.app.services.advice import find_alternatives
from backend.app.services.simulation import InvalidScenario, baseline, evaluate, leave_one_out
from contracts.schemas import (
    AnalysisResponse, Catalog, ErrorBody, ErrorResponse, HealthResponse,
    ScenarioRequest, SimulationResult, ValidationIssue,
)

load_dotenv(ROOT / ".env")
AI_MODE = os.getenv("AI_MODE", "live")
if AI_MODE not in {"mock", "live"}:
    raise ValueError("AI_MODE must be mock or live")

app = FastAPI(title="Аким на 5 часов", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()],
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)


@app.exception_handler(InvalidScenario)
async def invalid_scenario_handler(request: Request, exc: InvalidScenario) -> JSONResponse:
    error = ErrorResponse(error=ErrorBody(
        code="invalid_scenario", message="Набор решений не прошёл проверку.", issues=exc.issues,
    ))
    return JSONResponse(status_code=422, content=error.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not echo submitted input, arbitrary strings or internal exception context.
    error = ErrorResponse(error=ErrorBody(
        code="invalid_request", message="Некорректный формат запроса.",
        issues=[ValidationIssue(code="schema_validation", message="Ожидается объект decisions со списком measure_id и district_id; лишние поля запрещены.")],
    ))
    return JSONResponse(status_code=422, content=error.model_dump())


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(dataset_version=get_catalog().version, ai_mode=configured_mode(AI_MODE))


@app.get("/api/catalog", response_model=Catalog)
def catalog() -> Catalog:
    return get_catalog()


@app.get("/api/baseline", response_model=SimulationResult)
def initial_state() -> SimulationResult:
    return baseline(get_catalog())


@app.post("/api/simulations/evaluate", response_model=SimulationResult, responses={422: {"model": ErrorResponse}})
def evaluate_scenario(request: ScenarioRequest) -> SimulationResult:
    return evaluate(request, get_catalog())


@app.post("/api/simulations/analyze", response_model=AnalysisResponse, responses={422: {"model": ErrorResponse}})
def analyze_scenario(request: ScenarioRequest) -> AnalysisResponse:
    source = get_catalog()
    result = evaluate(request, source)
    alternatives = find_alternatives(request, source)
    contributions = leave_one_out(result, source)
    return AnalysisResponse(
        result=result, alternatives=alternatives, contributions=contributions,
        analysis=explain_scenario(result, source, mode=AI_MODE, alternatives=alternatives, contributions=contributions),
    )
