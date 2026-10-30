# Xanh24 M4L 2.0 — hosted DEMO image (staging only, never production).
# Same app as the root Dockerfile, plus: M4L + demo mode on, and a demo database built from repo data on first boot
# (no copy of data/xanh24.db is ever baked in: .dockerignore excludes data/).
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1 \
    XANH24_DATA_DIR=/data XANH24_DB=/data/xanh24.db XANH24_M4L_ENABLED=1 XANH24_DEMO_MODE=1 \
    XANH24_SESSION_COOKIE_SECURE=true PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server ./server
COPY web ./web
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY deploy/demo/entrypoint.sh /app/entrypoint.sh
RUN sed -i "s/$//" /app/entrypoint.sh && chmod +x /app/entrypoint.sh  # survive CRLF checkouts on Windows
VOLUME ["/data"]
EXPOSE 8080
CMD ["/app/entrypoint.sh"]
