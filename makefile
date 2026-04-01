.PHONY: run dev

run:
	uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

dev:
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000