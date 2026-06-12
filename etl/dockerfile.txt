FROM python:3.13-slim

WORKDIR /app-etl

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PG_HOST=cinema-db
ENV PG_PORT=5432

COPY docker-entrypoint.sh docker-entrypoint.sh
COPY requirements.txt requirements.txt

RUN  apt-get update \
     && apt-get install -y --no-install-recommends \
          netcat-openbsd \
          curl \
     && apt-get install -y --no-install-recommends vim \
     && pip install --upgrade pip \
     && pip install -r requirements.txt \
     &&  apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . .

RUN ["chmod", "+x", "docker-entrypoint.sh"]
ENTRYPOINT ["./docker-entrypoint.sh"]
