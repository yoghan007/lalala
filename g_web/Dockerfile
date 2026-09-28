# Works on Railway, Fly.io, or any VPS with Docker.
FROM python:3.12-slim
WORKDIR /app
COPY server.py index.html admin.html ./
ENV PORT=8000 DB_PATH=/data/restaurant.db
VOLUME /data
EXPOSE 8000
CMD ["python", "server.py"]
