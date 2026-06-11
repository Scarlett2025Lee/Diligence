.PHONY: install serve ingest test lint

install:
	pip install -e ".[dev]"

serve:
	uvicorn src.api.main:app --reload --port 8000

ingest:
	python -m scripts.ingest --tickers $(TICKERS) --forms $(FORMS)

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/
