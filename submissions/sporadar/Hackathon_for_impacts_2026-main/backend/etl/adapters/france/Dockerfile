FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home adapter && mkdir /state && chown adapter:adapter /state
COPY main.py exporter.py validate.py ./
USER adapter
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/state
CMD ["python", "main.py"]
