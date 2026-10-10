FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY assistant/requirements.txt /app/assistant/requirements.txt
RUN pip install --no-cache-dir -r assistant/requirements.txt
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --chown=app:app . /app
USER 10001:10001
EXPOSE 8000
# La clé GEMINI_API_KEY est fournie à l'exécution : docker run --env-file .env -p 8000:8000 <image>
CMD ["python", "-m", "assistant", "--host", "0.0.0.0", "--port", "8000"]
