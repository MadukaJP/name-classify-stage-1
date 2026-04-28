# utils/state_store.py
import json, hashlib, base64, secrets
import redis

from core.config import settings

TTL = 300

r = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,    # returns strings instead of bytes
)

def generate_pkce():
    code_verifier  = secrets.token_urlsafe(64)
    digest         = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge

def save_state(state: str, code_verifier: str, mode: str = "web"):
    r.setex(
        f"oauth_state:{state}",
        TTL,
        json.dumps({ "mode": mode, "code_verifier": code_verifier })
    )

def consume_state(state: str) -> dict | None:
    key  = f"oauth_state:{state}"
    data = r.get(key)

    if not data:
        return None

    r.delete(key)          # one time use — delete immediately after reading
    return json.loads(data)