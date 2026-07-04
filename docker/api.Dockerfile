ARG DOCKER_REGISTRY_PREFIX=
FROM ${DOCKER_REGISTRY_PREFIX}python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt ./requirements.docker.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.docker.txt

COPY src ./src
COPY scripts ./scripts
COPY examples ./examples
COPY fastinfo.py ./fastinfo.py
# config/ 不存在,环境变量走 ./env_file: docker/env.docker.local + ./env volume
COPY docker/api-entrypoint.sh ./docker/api-entrypoint.sh

# 清掉本机 Python 3.14 跑过留下的 .pyc(残留 import 名 / 版本不兼容)
RUN find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

RUN mkdir -p /app/data \
    && chmod +x /app/docker/api-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/app/docker/api-entrypoint.sh"]
CMD ["python", "scripts/api_server.py", "--host", "0.0.0.0", "--port", "8000"]
