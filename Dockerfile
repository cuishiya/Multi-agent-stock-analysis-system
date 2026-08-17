FROM node:20-alpine AS web-builder

WORKDIR /build
COPY Financial-MCP-Agent/web/package.json Financial-MCP-Agent/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY Financial-MCP-Agent/web/ ./
RUN npm run build


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/Financial-MCP-Agent \
    SUMMARY_USE_LOCAL_MODEL=api \
    USE_LOCAL_MODEL=api

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.runtime.txt /tmp/requirements.runtime.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements.runtime.txt

RUN groupadd --system stockagent \
    && useradd --system --gid stockagent --home-dir /app --shell /usr/sbin/nologin stockagent

COPY --chown=stockagent:stockagent Financial-MCP-Agent/ /app/Financial-MCP-Agent/
COPY --chown=stockagent:stockagent a-share-mcp-is-just-i-need/ /app/a-share-mcp-is-just-i-need/
COPY --from=web-builder --chown=stockagent:stockagent /build/dist/ /app/Financial-MCP-Agent/web/dist/

RUN mkdir -p /app/Financial-MCP-Agent/logs /app/Financial-MCP-Agent/reports \
    && chown -R stockagent:stockagent /app/Financial-MCP-Agent/logs /app/Financial-MCP-Agent/reports

USER stockagent
WORKDIR /app/Financial-MCP-Agent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).read()"]

CMD ["python", "run_web.py", "--host", "0.0.0.0", "--port", "8000"]
