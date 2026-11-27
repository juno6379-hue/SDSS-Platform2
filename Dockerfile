FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv/sdss
RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY services ./services
RUN python -m pip install --no-cache-dir ".[geo,climate,storage,inference]" \
    && groupadd --gid 10001 sdss \
    && useradd --uid 10001 --gid 10001 --no-create-home sdss \
    && mkdir -p evidence data/curated \
    && chown -R 10001:10001 data
COPY web ./web
USER 10001:10001
CMD ["python", "-m", "uvicorn", "services.api.app:app", "--host", "127.0.0.1", "--port", "8014", "--no-proxy-headers"]
