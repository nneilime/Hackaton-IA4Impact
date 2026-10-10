"""API HTTP du calcul d'itinéraire.

    uvicorn app.main:app --reload        (depuis backend/)

Jeu de données : variable d'environnement IA_DATASET, nom d'un sous-dossier de data/ (défaut « train_lio » :
trains TER liO seulement). IA_DATASET=full charge la base complète (data/ : cars TER et liO, Intercités, TGV…).

    GET /health
    GET /stations?q=mont&limit=20
    GET /places                          gares + coordonnées
    GET /network                         liaisons
    GET /modes                           types de transport disponibles
    GET /networks                        réseaux liO départementaux
    GET /info                            source des horaires, validité, jour de référence
    GET /route?from=Toulouse&to=Perpignan[&exclude=Car TER&exclude=INTERCITES][&exclude_network=liO 34][&transfer_min=5]
    POST /chat                           assistant du site (OpenAI, clé dans backend/.env), voir app/chat.py
    POST /transcribe                     dictée du chat : corps = l'enregistrement (audio/webm, audio/mp4…) → {"text"}

Les erreurs renvoient {"detail": {"code": ..., "message": ...}} : le front traduit
à partir de `code`, `message` (anglais) n'est là que pour le débogage.
"""
import json
import os

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import chat
from .routing import DATA_DIR, DEFAULT_TRANSFER_MIN, Network, SamePlace, UnknownPlace

app = FastAPI(title="IA Impact — routing API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

DATASET = os.environ.get("IA_DATASET", "train_lio")
data_dir = DATA_DIR if DATASET == "full" else DATA_DIR / DATASET
network = Network(data_dir)
build_info = json.loads((data_dir / "build_info.json").read_text(encoding="utf-8"))


def error(status, code, message):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


@app.get("/health")
def health():
    return {"status": "ok", "stations": len(network.name)}


@app.get("/info")
def info():
    """D'où viennent les horaires : version du GTFS SNCF, période de validité, jour de référence des fréquences."""
    return build_info


@app.get("/stations")
def stations(q: str = "", limit: int = Query(20, ge=1, le=500)):
    return {"stations": network.stations(q, limit)}


@app.get("/places")
def places():
    """Gares avec coordonnées et département, pour la carte."""
    return {"places": network.places()}


@app.get("/network")
def network_edges():
    """Tronçons entre arrêts consécutifs, pour tracer le réseau."""
    return {"edges": network.edges()}


@app.get("/modes")
def modes():
    """Types de transport (Train TER, Car TER, INTERCITES…) avec leur nombre de tronçons et de missions."""
    return {"modes": network.modes()}


@app.get("/networks")
def networks():
    """Réseaux de cars liO : un par département (liO 09 … liO 82) et les lignes régionales (liO TIL)."""
    return {"networks": network.networks()}


@app.get("/route")
def route(departure: str = Query(..., alias="from", min_length=1),
          destination: str = Query(..., alias="to", min_length=1),
          exclude: list[str] = Query([], description="Types de transport à ignorer (voir /modes)"),
          exclude_network: list[str] = Query([], description="Réseaux liO à ignorer (voir /networks)"),
          transfer_min: float = Query(DEFAULT_TRANSFER_MIN, ge=0, le=60,
                                      description="Minutes de changement par correspondance, en plus de l'attente estimée")):
    unknown = set(exclude) - {m["id"] for m in network.modes()}
    if unknown:
        error(400, "unknown_mode", f"Unknown transport mode(s): {', '.join(sorted(unknown))}")
    unknown = set(exclude_network) - {n["id"] for n in network.networks()}
    if unknown:
        error(400, "unknown_network", f"Unknown liO network(s): {', '.join(sorted(unknown))}")
    try:
        r = network.route(departure, destination, exclude=set(exclude), exclude_networks=set(exclude_network),
                          transfer_min=transfer_min)
    except UnknownPlace as e:
        error(404, "unknown_place", f"Unknown city or station: {e.args[0]}")
    except SamePlace:
        error(400, "same_place", "Departure and destination are the same place.")
    if r is None:
        error(404, "no_route", f"No route between {departure} and {destination}.")
    return r


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=2000)


class CatalogPlace(BaseModel):
    id: str = Field(max_length=60)
    title: str = Field(max_length=120)
    category: str = Field(max_length=30)
    station: str = Field(max_length=80)
    summary: str = Field(max_length=300)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)
    catalog: list[CatalogPlace] = Field([], max_length=120)


def client_ip(request):
    return request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip() \
        or (request.client.host if request.client else "")


@app.post("/chat")
def chat_reply(body: ChatRequest, request: Request):
    """Réponse de l'assistant + actions pour le site : [{"type": "route", "from", "to"} | {"type": "places", "items"}]."""
    if not chat.allow(client_ip(request)):
        error(429, "chat_rate_limit", "Too many messages, try again in a few minutes.")
    try:
        return chat.reply(network, [m.model_dump() for m in body.messages[-12:]], [p.model_dump() for p in body.catalog])
    except chat.ChatUnavailable as e:
        print("chat unavailable:", e)
        error(503, "chat_unavailable", "The assistant is not available.")


@app.post("/transcribe")
async def transcribe(request: Request):
    """Dictée : le corps brut est l'enregistrement du navigateur (pas de multipart, donc pas de dépendance de plus).
    Compte dans le même quota que /chat : chaque dictée est une transcription payante."""
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in chat.AUDIO_TYPES:
        error(415, "audio_format", "Unsupported audio format.")
    if int(request.headers.get("content-length") or 0) > chat.MAX_AUDIO_BYTES:
        error(413, "audio_too_large", "Recording too large.")
    audio = await request.body()
    if len(audio) > chat.MAX_AUDIO_BYTES:
        error(413, "audio_too_large", "Recording too large.")
    if len(audio) < 1000:
        error(400, "audio_empty", "Empty recording.")
    if not chat.allow(client_ip(request)):
        error(429, "chat_rate_limit", "Too many messages, try again in a few minutes.")
    try:
        return {"text": await run_in_threadpool(chat.transcribe, audio, content_type)}
    except chat.EmptyTranscript:
        error(422, "audio_empty", "Nothing was understood in the recording.")
    except chat.ChatUnavailable as e:
        print("transcription unavailable:", e)
        error(503, "chat_unavailable", "The assistant is not available.")
