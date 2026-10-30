FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SILLAGE_HOST=0.0.0.0 \
    SILLAGE_PORT=8000 \
    SILLAGE_DATABASE=/app/data/sillage.db

WORKDIR /app
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt \
    && groupadd --gid 10001 sillage \
    && useradd --uid 10001 --gid sillage --no-create-home sillage \
    && mkdir -p /app/data \
    && chown sillage:sillage /app/data

COPY run.py ./
COPY sillage/ ./sillage/
COPY static/ ./static/
COPY third_party/fragdb_sample/ ./third_party/fragdb_sample/

USER sillage
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3).close()"
CMD ["python", "run.py"]
