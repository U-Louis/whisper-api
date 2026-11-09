ARG BASE_IMAGE=python:3.11-slim-bookworm
FROM ${BASE_IMAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt requirements-whisper.txt ./
COPY wheels/ /tmp/wheels/
# pip's bundled CA list rejects some networks. Prefer a prefetched wheel when one is present.
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
RUN set -eu; \
    pip install --no-cache-dir -r requirements.txt; \
    if ls /tmp/wheels/*.whl >/dev/null 2>&1; then \
      pip install --no-cache-dir --no-index --find-links /tmp/wheels torch; \
    else \
      pip install --no-cache-dir --cert /etc/ssl/certs/ca-certificates.crt torch --index-url https://download.pytorch.org/whl/cpu; \
    fi; \
    pip install --no-cache-dir numba numpy tiktoken more-itertools tqdm; \
    pip install --no-cache-dir 'setuptools==69.5.1'; \
    pip install --no-cache-dir --no-build-isolation --no-deps openai-whisper==20240930; \
    rm -rf /tmp/wheels

RUN useradd --create-home --uid 10001 whisper
USER whisper
ENV HOME=/home/whisper \
    WHISPER_MODEL=small \
    PYTHONUNBUFFERED=1

RUN python -c "import whisper; whisper.load_model('small', device='cpu')"

COPY --chown=whisper:whisper app ./app
COPY --chown=whisper:whisper whisper-api.conf ./whisper-api.conf

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8080"]
