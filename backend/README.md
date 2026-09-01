# Backend

FastAPI service for music library, metadata, and streaming.

## Run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set AUTH_SECRET_KEY (openssl rand -hex 32)
uvicorn app.main:app --reload
```
