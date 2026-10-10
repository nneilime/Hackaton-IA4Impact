# Phone version of the banking voice assistant: the React page and the FastAPI server
# in one container (server.py serves web/dist).

FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
# WeasyPrint (the loan recap PDF) needs Pango, and a font: the slim image has none.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 \
       libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv
# RECAPS_DIR, DB_PATH: /app isn't writable by nobody. The recaps and the sessions
# (demo logins) go when the container restarts: everyone is a visitor again.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0 \
    PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 RECAPS_DIR=/tmp/recaps \
    DB_PATH=/tmp/data/compass.db
WORKDIR /app
# Only the server's dependencies: no sounddevice, PortAudio or numpy.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --only-group server --no-install-project
COPY server.py bank_tools.py bank_store.py recap_pdf.py demo_customer.py ./
COPY bank_docs/ bank_docs/
COPY --from=web /web/dist web/dist/
USER nobody
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
