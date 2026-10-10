"""API FastAPI du projet LPC : implémente openapi.proposed.yaml (P0 + P1 + /expirations + /sources + /ask).

Lancer depuis la racine du dépôt :
    uvicorn backend.app.main:app --port 3000
Documentation interactive : http://localhost:3000/docs

- Toutes les routes existent à la racine (/health) ET sous /api (/api/health) : le nginx du
  frontend n'enlève pas le préfixe /api.
- Lecture seule sur la base. Les noms de champs viennent des modèles générés (models.py).
- Sécurité : si API_KEY (fichier .env) est vide, accès libre ; sinon en-tête X-API-Key obligatoire,
  sauf pour /health.
"""
import hmac
import os
import unicodedata
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

from fastapi import APIRouter, FastAPI, Query, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyHeader
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import db  # noqa: F401  (charge le fichier .env)
from . import agent
from . import opportunities as opp
from . import models as m
from . import schemas as s
from . import services
from . import warmup
from .services import DISCLAIMER, NO_MATCH, NotFound

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Au démarrage : préchauffe en arrière-plan les requêtes de démo (voir warmup.py ; WARMUP=0 pour désactiver)."""
    warmup.start(_app)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="LPC Global Regulatory AI API",
    version="0.2.1",
    description="Contrat : openapi.proposed.yaml. Pas une source réglementaire officielle : "
                "validation Regulatory Affairs requise. Un résultat vide n'est jamais une preuve d'absence d'homologation.",
    servers=[{"url": "/api", "description": "Les routes sont aussi disponibles à la racine (sans /api)."}],
    generate_unique_id_function=lambda route: route.name,   # operationId = nom de la fonction (= contrat)
)

# CORS ouvert (le frontend et le connecteur Power Platform appellent depuis un autre domaine)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------------------
# Erreurs : toujours un JSON `Problem` {code, message}, jamais de 500 non gérée
# ---------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def problem(status, code, message):
    return JSONResponse(status_code=status, content={"code": code, "message": message})


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return problem(exc.status, exc.code, exc.message)


@app.exception_handler(NotFound)
async def not_found_handler(request: Request, exc: NotFound):
    return problem(404, "not_found", NO_MATCH)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p != "query")
    return problem(422, "invalid_request", f"Invalid request ({where}): {first.get('msg', 'bad value')}")


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return problem(exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    return problem(503, "database_unavailable",
                   "Database temporarily unavailable, please retry. This is not proof of no registration.")


@app.exception_handler(RuntimeError)
async def config_error_handler(request: Request, exc: RuntimeError):
    return problem(503, "service_not_configured", str(exc))


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    return problem(500, "internal_error", "Unexpected error. This is not proof of no registration.")


# Les en-têtes HTTP doivent rester en ASCII : version sans accents (le texte exact est dans le corps JSON)
DISCLAIMER_HEADER = unicodedata.normalize("NFKD", DISCLAIMER).encode("ascii", "ignore").decode()


@app.middleware("http")
async def add_disclaimer_header(request: Request, call_next):
    """Chaque réponse (même celles sans champ `disclaimer` dans le contrat) porte le disclaimer."""
    response = await call_next(request)
    response.headers["X-Disclaimer"] = DISCLAIMER_HEADER
    return response


# ---------------------------------------------------------------------------
# Sécurité : clé API optionnelle
# ---------------------------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="ApiKeyAuth")


def require_api_key(key: str | None = Security(api_key_header)):
    expected = os.environ.get("API_KEY", "").strip()
    if expected and not (key and hmac.compare_digest(key, expected)):
        raise ApiError(401, "unauthorized", "Missing or invalid X-API-Key header.")


public = APIRouter()                                   # /health : sans clé
secured = APIRouter(dependencies=[Security(require_api_key)])

PROBLEM = {"model": m.Problem}
COUNTRY = Query(None, pattern=r"^[A-Z]{2}$", description="ISO 3166-1 alpha-2 country code.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@public.get("/health", tags=["system"], response_model=s.HealthResponse, summary="Health check")
def getHealth():
    return {"status": "ok"}


@secured.get("/products", tags=["products"], response_model=s.ProductsResponse, response_model_exclude_unset=True,
             responses={401: PROBLEM}, summary="Search products")
def searchProducts(
        q: str | None = Query(None, description="Free text matched against commercial names and aliases."),
        activeEntity: str | None = Query(None, description="Microorganism or active substance (aliases are expanded)."),
        crop: str | None = Query(None, description="Crop as an EPPO code or a name in any language."),
        target: str | None = Query(None, description="Pest or disease as an EPPO code or a name in any language."),
        country: str | None = COUNTRY,
        includeCompetitors: bool = Query(True, description="Include non-LPC products."),
        includeSynthetic: bool = Query(False, description="Show synthetic (fictional) data, always flagged isSynthetic."),
        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return services.search_products(q, activeEntity, crop, target, country, includeCompetitors,
                                    includeSynthetic, limit, offset)


@secured.get("/products/{productId}/registrations", tags=["products"], response_model=s.RegistrationsResponse,
             response_model_exclude_unset=True, responses={401: PROBLEM, 404: PROBLEM},
             summary="Registrations of a product by country")
def getProductRegistrations(
        productId: str, country: str | None = COUNTRY,
        includeSynthetic: bool = Query(False), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
        usesLimit: int = Query(50, ge=1, le=1000, description="Maximum number of uses returned per registration.")):
    return services.product_registrations(productId, country, includeSynthetic, limit, offset, usesLimit)


@secured.get("/products/{productId}/sisters", tags=["products"], response_model=m.SisterCandidatesResponse,
             response_model_exclude_unset=True, responses={401: PROBLEM, 404: PROBLEM},
             summary="Sister-product candidates (hypotheses)")
def getSisterCandidates(productId: str, includeSynthetic: bool = Query(False)):
    return services.sister_candidates(productId, includeSynthetic)


@secured.get("/compare", tags=["comparison"], response_model=s.ComparisonResponseOut, response_model_exclude_unset=True,
             responses={200: {"content": {"text/csv": {}}}, 401: PROBLEM, 404: PROBLEM},
             summary="Compare authorized uses across countries")
def compareProductUses(
        productId: str,
        countries: str = Query(..., description="Comma-separated ISO 3166-1 alpha-2 codes.", examples=["CA,US,BR"]),
        crop: str | None = Query(None, description="Optional crop filter, EPPO code or name."),
        target: str | None = Query(None, description="Optional pest or disease filter, EPPO code or name."),
        granularity: Literal["use", "crop"] = Query("use", description="use = one row per crop x target (default); crop = one row per normalized crop (per country: use count, original targets, min-max doses per ORIGINAL unit). Added outside the contract."),
        format: Literal["json", "csv"] = Query("json", description="csv returns one line per country x use with evidence columns."),
        includeSynthetic: bool = Query(False), limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)):
    codes = []
    for part in countries.split(","):
        code = part.strip().upper()
        if not code:
            continue
        if len(code) != 2 or not code.isalpha():
            raise ApiError(422, "invalid_request", f"Invalid country code: {part!r} (two letters expected).")
        if code not in codes:
            codes.append(code)
    if not codes:
        raise ApiError(422, "invalid_request", "At least one country code is required.")
    data = services.compare_uses(productId, codes, crop, target, includeSynthetic, limit, offset, granularity)
    if format == "csv":
        return Response(content=services.comparison_csv(data), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="compare-{productId}.csv"'})
    return data


@secured.get("/issues", tags=["quality"], response_model=m.IssuesResponse, response_model_exclude_unset=True,
             responses={401: PROBLEM}, summary="Missing, uncertain or unvalidated fields")
def listDataIssues(
        productId: str | None = None, country: str | None = COUNTRY, issueType: m.IssueType | None = None,
        includeSynthetic: bool = Query(False), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    return services.data_issues(productId, country, issueType.value if issueType else None,
                                includeSynthetic, limit, offset)


@secured.get("/expirations", tags=["quality"], response_model=m.ExpirationsResponse, response_model_exclude_unset=True,
             responses={401: PROBLEM}, summary="Registrations expired, withdrawn or expiring soon")
def listExpirations(
        withinMonths: int = Query(12, ge=1, le=60),
        referenceDate: date | None = Query(None, description="Defaults to today (UTC)."),
        country: str | None = COUNTRY,
        crop: str | None = Query(None, description="Only registrations with a use on this crop (EPPO code or name)."),
        includeSynthetic: bool = Query(False), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    return services.expirations(withinMonths, referenceDate, country, crop, includeSynthetic, limit, offset)


@secured.get("/opportunities", tags=["market"], response_model=s.OpportunitiesResponse, response_model_exclude_unset=True,
             responses={401: PROBLEM, 404: PROBLEM},
             summary="Free spaces for biocontrol: crop x target pairs with many active chemical uses and few biological ones (outside the contract)")
def listOpportunities(
        country: str | None = COUNTRY,
        crop: str | None = Query(None, description="Crop, EPPO code or name in any language."),
        target: str | None = Query(None, description="Pest or disease, EPPO code or name in any language."),
        productId: str | None = Query(None, description="Only crop x target pairs where the substance of this LPC product already has an active use in some country."),
        minChemicalUses: int = Query(5, ge=1, le=1000, description="Minimum number of active chemical uses for a pair to be listed."),
        lpcOnly: bool = Query(False, description="Only pairs where an LPC product, a sister candidate or a product with the same substance is already authorized."),
        limit: int = Query(20, ge=1, le=100)):
    """Aide à l'analyse, pas une décision réglementaire. Hors contrat (voir docs/openapi-changes.md)."""
    return opp.opportunities(country, crop, target, limit, productId, minChemicalUses, lpcOnly)


@secured.get("/sources", tags=["sources"], response_model=s.SourcesResponse, response_model_exclude_unset=True,
             responses={401: PROBLEM}, summary="Integrated official sources and freshness")
def listSources():
    return services.list_sources()


@secured.post("/ask", tags=["agent"], response_model=s.AnswerOut, responses={401: PROBLEM},
              summary="Ask a regulatory question in natural language")
def askRegulatoryQuestion(body: m.AskRequest):
    """Agent : l'IA comprend et rédige, le code fournit et vérifie les données (voir agent.py). Marche sans clé IA."""
    return agent.ask(body)


# Chaque route est publiée à la racine (visible dans /docs) et sous /api (hors /docs, même code)
for router in (public, secured):
    app.include_router(router)
    app.include_router(router, prefix="/api", include_in_schema=False)
