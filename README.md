# BostonHacks

My solo ML project for BostonHacks! FoldIt is a citizen-science puzzle game that turns protein folding into an interactive challenge, where players manipulate 3D protein structures to find low-energy conformations. For this hackathon’s “Upgrade” track—where participants reimagine an older application using modern technology—I built a web-based, FoldIt-inspired platform that lets users visualize proteins, edit torsion angles (φ, ψ, χ), and receive real-time feedback using biophysical scoring terms like rotamer, Ramachandran, and hydrogen-bond energies. I developed the core frontend and backend systems—including the Next.js PlayScreen, residue coordinate parsing, linear backbone generation, and dynamic level loading/scoring APIs—and integrated machine learning models to predict optimal folding states and guide users toward more biologically realistic configurations.

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
