import os, pathlib
_env = pathlib.Path(__file__).resolve().parents[2] / ".env"
if _env.exists():  # tiny .env loader, no extra dependency
    for line in _env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
def flag(k, d="false"): return os.getenv(k, d).lower() == "true"
DEMO_MODE = flag("DEMO_MODE", "true")
OSRM_URL = os.getenv("OSRM_URL") or "https://router.project-osrm.org"
OVERPASS_URL = os.getenv("OVERPASS_URL") or "https://overpass-api.de/api/interpreter"
ENABLE_AI = flag("ENABLE_AI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # backend only; optional
