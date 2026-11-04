PYTHON ?= python3
VENV := .venv/bin/python

.PHONY: setup api ui build serve test test-ml ml-deps docker
setup:
	$(PYTHON) -m venv .venv
	$(VENV) -m pip install -r backend/requirements.txt
	cd frontend && npm ci --no-audit --no-fund

api:
	$(VENV) -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

ui:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

serve:
	$(VENV) -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

test:
	$(VENV) -m unittest discover -s backend/tests -v
	$(VENV) -m unittest discover -s ai/tests -v
	$(VENV) -m unittest discover -s data/tests -v
	cd frontend && npm test && npm run build

ml-deps:
	$(VENV) -m pip install -r data/requirements-ml.txt

test-ml:
	$(VENV) -m unittest discover -s data/ml_tests -v

docker:
	docker compose up --build
