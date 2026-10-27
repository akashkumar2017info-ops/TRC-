
FROM python:3.12-slim

WORKDIR /app

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "python server.py ${PORT:-8000}"]
