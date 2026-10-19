FROM apache/spark:3.5.3 AS spark

FROM python:3.11.10-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SPARK_HOME=/opt/spark PATH=/opt/spark/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends curl openjdk-17-jre-headless && rm -rf /var/lib/apt/lists/*
COPY --from=spark /opt/spark /opt/spark
WORKDIR /opt/iip
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .
RUN mkdir -p data reports models
EXPOSE 8000
