# BostonHacks

My solo AI/ML project for BostonHacks.

## Quick start

```bash
# 1️⃣  Clone and create venv
git clone <repo_url>
cd <repo_name>
python -m venv venv
source venv/bin/activate        # (Windows: venv\Scripts\activate)

# 2️⃣  Install deps
pip install -r requirements.txt

# 3️⃣  Run backend
make dev-back                   # or npm run dev-back

# 4️⃣  Train ΔScore model (S3.3)
make train-delta

# 5️⃣  Run tests
make tests
```

Expected output when starting the dev server:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```
