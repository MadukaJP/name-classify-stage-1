import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from utils.tokens import decode_access_token


def rate_limit_key(request):
    auth_header = request.headers.get("Authorization", "")
    token = None

    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    else:
        token = request.cookies.get("access_token")

    if token:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except jwt.InvalidTokenError:
            pass

    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=rate_limit_key)
