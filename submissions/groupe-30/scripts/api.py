"""HTTP facade for equipment failure predictions."""

import logging
from contextlib import asynccontextmanager
import os
from datetime import date, datetime
import psycopg

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from scripts.shared_api import router, member
from scripts.database import connection, source_rows
from scripts.scoring import predict_rows, MODEL_TABLES

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    interrupted_calculations()
    yield


app = FastAPI(title="BatIA Prediction API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ],
    allow_methods=["POST", "GET", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(router)


@app.exception_handler(psycopg.OperationalError)
@app.exception_handler(RuntimeError)
async def unavailable_database(request, error):
    logger.error("Connexion serveur indisponible : %s", type(error).__name__)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "La connexion à la base est indisponible. Réessayez ou vérifiez la configuration serveur."
        },
    )


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    equipment_id: str = Field(min_length=1, max_length=128)
    as_of_date: date

    @field_validator("as_of_date", mode="before")
    @classmethod
    def validate_date(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("as_of_date doit être une date YYYY-MM-DD.")
        parsed = date.fromisoformat(value)
        if value != parsed.isoformat():
            raise ValueError("as_of_date doit être une date YYYY-MM-DD.")
        return parsed


class FailureTypeCandidate(BaseModel):
    type_intervention: str
    type_panne: str
    conditional_probability: float
    joint_probability: float
    prix: float | None


class FailureTypePrediction(BaseModel):
    status: str
    predictions: list[FailureTypeCandidate]
    other_conditional_probability: float = 0.0
    expected_price_if_failure: float | None
    expected_cost_within_horizon: float | None


class PredictionResponse(BaseModel):
    equipment_id: str
    as_of_date: date
    residence_id: str
    batiment_id: str
    libelle_famille: str
    failure_probability_90d: float
    alert_threshold_90d: float
    predicted_alert_90d: bool
    risk_level_90d: str
    failure_probability_180d: float
    alert_threshold_180d: float
    predicted_alert_180d: bool
    risk_level_180d: str
    failure_probability_365d: float
    alert_threshold_365d: float
    predicted_alert_365d: bool
    risk_level_365d: str
    failure_probability_730d: float
    alert_threshold_730d: float
    predicted_alert_730d: bool
    risk_level_730d: str
    recommended_action: str
    failure_types_90d: FailureTypePrediction
    failure_types_180d: FailureTypePrediction
    failure_types_365d: FailureTypePrediction
    failure_types_730d: FailureTypePrediction


@app.get("/health")
def health() -> dict[str, str]:
    """Check HTTP availability; does not check models or data."""
    return {"status": "ok"}


@app.post("/api/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest, user=Depends(member)) -> dict[str, object]:
    try:
        with connection(user["id"], snapshot=True) as conn:
            rows = source_rows(conn, MODEL_TABLES)
        item = next(
            (
                r
                for r in rows["equipements"]
                if r["equipement_id"] == request.equipment_id
            ),
            None,
        )
        if item is None:
            raise ValueError(f"Unknown equipment_id: {request.equipment_id}.")
        if not item["dans_perimetre_prediction"]:
            raise ValueError(
                f"{request.equipment_id} is excluded because dans_perimetre_prediction is not 'Oui'."
            )
        rows["equipements"] = [item]
        return predict_rows(
            rows, datetime.combine(request.as_of_date, datetime.min.time())
        )[0]
    except (psycopg.OperationalError, RuntimeError):
        raise  # Le gestionnaire commun répond 503 sans exposer le secret serveur.
    except ValueError as error:
        # Only domain errors from equipment lookup should be exposed to clients.
        if str(error).startswith("Unknown equipment_id:"):
            raise HTTPException(status_code=404, detail=str(error)) from error
        if "is excluded because dans_perimetre_prediction" in str(error):
            raise HTTPException(status_code=422, detail=str(error)) from error
        logger.exception("Prediction failed")
        raise HTTPException(
            status_code=500, detail="Échec de la prédiction."
        ) from error
    except FileNotFoundError as error:
        logger.exception("Prediction files unavailable")
        raise HTTPException(
            status_code=503, detail="Données ou modèles indisponibles."
        ) from error
    except Exception as error:
        logger.exception("Prediction failed")
        raise HTTPException(
            status_code=500, detail="Échec de la prédiction."
        ) from error


def interrupted_calculations():
    if not os.getenv("DATABASE_URL"):
        return
    try:
        with connection() as conn:
            conn.execute(
                "update public.calculs set statut='echec',erreur='Serveur interrompu. Relancez le calcul.',termine_le=now() where statut in ('en_attente','en_cours')"
            )
    except Exception:
        logger.exception("Vérification des calculs interrompus indisponible")
