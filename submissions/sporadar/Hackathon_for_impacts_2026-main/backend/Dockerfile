# API FastAPI du projet LPC.
#
# IMPORTANT : le contexte de build est la RACINE du dépôt (pas backend/), car l'API lit les
# fichiers de mapping de data/ (synonymes, codes EPPO). docker-compose.yml est réglé ainsi :
#   build: { context: ., dockerfile: backend/Dockerfile }
# Sans compose :  docker build -f backend/Dockerfile -t lpc-api .
FROM python:3.11-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app backend/app
COPY backend/etl backend/etl
COPY data data
# Requêtes de démo préchauffées au démarrage (backend/app/warmup.py) ; sans ce fichier, pas de préchauffage
COPY docs/demo_cases.md docs/demo_cases.md

# Port d'écoute : BACK_PORT (3000 par défaut). DATABASE_URL et API_KEY viennent de l'environnement (.env).
ENV BACK_PORT=3000
EXPOSE 3000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${BACK_PORT:-3000} --workers 1"]
