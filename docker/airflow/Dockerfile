FROM apache/airflow:2.10.2-python3.11
USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless && rm -rf /var/lib/apt/lists/*
USER airflow
COPY pyproject.toml README.md /opt/iip/
COPY src /opt/iip/src
RUN pip install --no-cache-dir /opt/iip 'pyspark==3.5.3'
ENV PYTHONPATH=/opt/iip/src
