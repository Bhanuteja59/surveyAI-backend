from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings

def hash_password(password: str) -> str:
    # Use direct bcrypt implementation, truncating to 72 bytes if necessary
    pwd_bytes = password[:72].encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    plain_bytes = plain[:72].encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def create_access_token(subject: str, extra: dict = None) -> str:
    payload = {
        "sub": subject,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
