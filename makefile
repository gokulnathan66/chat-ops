.PHONY: run dev test e2e ingest

run:
	uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

dev:
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest tests/ -v

e2e:
	bash scripts/local_e2e_test.sh

ingest:
	uv run python -c "\
import pathlib; \
from src.services.embedding import EmbeddingService; \
from src.services.qdrant import QdrantService; \
emb = EmbeddingService(); qs = QdrantService(); \
[qs.upsert_points(qs.build_points(full_text=(t:=f.read_text()), chunks=(c:=emb.chunk_text(t)), vectors=emb.embed_texts(c), source='local', title=f.stem, url_or_file_path=str(f), tags=['csv','financials'], section_prefix=f.stem)[1]) or print(f'{f.name}: done') for f in pathlib.Path('data/csv').glob('*.csv')]"