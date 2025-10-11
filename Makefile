# === Development server ===
dev-back:
	uvicorn app.server.main:app --reload

# === Train ΔScore model ===
train-delta:
	python -m app.server.train_delta_score

# === Run tests ===
tests:
	pytest -v
