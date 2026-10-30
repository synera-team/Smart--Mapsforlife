FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 XANH24_DATA_DIR=/data PORT=8024
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server ./server
COPY web ./web
VOLUME ["/data"]
EXPOSE 8024
CMD ["sh", "-c", "python server/manage.py init && cd server && exec gunicorn -w ${WORKERS:-4} --threads 4 -b 0.0.0.0:${PORT} --timeout 120 --access-logfile - wsgi:app"]
