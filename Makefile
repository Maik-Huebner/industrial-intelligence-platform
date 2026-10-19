.PHONY: install test unit generate pipeline api compose-config up down spark integration full clean-data

PYTHON ?= python3
PROFILE ?= small

install:
	$(PYTHON) -m pip install -e '.[test]'

test:
	PYTHONPATH=src $(PYTHON) -m pytest -m 'not integration and not spark and not slow'

unit:
	PYTHONPATH=src $(PYTHON) -m pytest tests/unit

generate:
	PYTHONPATH=src $(PYTHON) -m industrial_intelligence.cli generate --profile $(PROFILE)

pipeline:
	PYTHONPATH=src $(PYTHON) -m industrial_intelligence.cli pipeline --profile $(PROFILE)

api:
	PYTHONPATH=src $(PYTHON) -m uvicorn industrial_intelligence.api.main:app --reload

compose-config:
	docker compose --env-file .env.example config --quiet

up:
	docker compose --env-file .env up -d --build

down:
	docker compose --env-file .env down

spark:
	docker compose --env-file .env run --rm spark-submit

integration:
	PYTHONPATH=src $(PYTHON) -m pytest -m integration

full:
	PYTHONPATH=src $(PYTHON) -m industrial_intelligence.cli pipeline --profile full

clean-data:
	find data/raw data/processed data/quarantine -type f ! -name .gitkeep -delete
	rm -f reports/*.json

