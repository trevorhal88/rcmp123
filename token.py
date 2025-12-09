import jwt
from datetime import datetime, timedelta
from config import RESET_TOKEN_SECRET

def create_reset_token(username: str):
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    return jwt.encode(payload, RESET_TOKEN_SECRET, algorithm="HS256")

def verify_reset_token(token: str):
    try:
        decoded = jwt.decode(token, RESET_TOKEN_SECRET, algorithms=["H256", "HS256"])
        return decoded["sub"]
    except:
        return None