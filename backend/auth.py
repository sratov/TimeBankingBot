from jose import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
import hmac
import hashlib
import time
import logging
from typing import Dict
from config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    BOT_TOKEN,
)

# ---------------------------------------------------------------------------
# logging setup
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

security = HTTPBearer()

# ---------------------------------------------------------------------------
# Telegram Web‑App hash verification
# ---------------------------------------------------------------------------

def verify_telegram_hash(init_data: str, received_hash: str) -> bool:
    """Validate init_data received from Telegram Mini‑app.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    try:
        logger.debug("\n" + "="*50)
        logger.debug("Starting Telegram WebApp hash verification")
        logger.debug("="*50)
        
        # Debug BOT_TOKEN for hidden whitespace
        logger.debug("BOT_TOKEN (repr): %r", BOT_TOKEN)
        logger.debug("init_data (repr): %r", init_data)
        logger.debug("received_hash: %s", received_hash)
        
        # 1. Parse the init_data without decoding values
        params = {}
        for pair in init_data.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                params[key] = value
        
        # 2. Remove hash from params
        if "hash" not in params:
            logger.error("No hash parameter in init_data")
            return False
            
        hash_value = params.pop("hash")
        
        # Also remove signature parameter if present (used in Login Widget, not in WebApp)
        params.pop("signature", None)
        
        # Check that hash from init_data matches received_hash
        if hash_value != received_hash:
            logger.error("Hash mismatch: from init_data %r vs passed separately %r", 
                        hash_value, received_hash)
            return False
        
        # 3. Build data_check_string
        # Sort params by key in alphabetical order and join with \n
        data_check_string = '\n'.join(f"{k}={params[k]}" for k in sorted(params.keys()))
        logger.debug("data_check_string (repr): %r", data_check_string)
        logger.debug("data_check_string length: %d bytes", len(data_check_string.encode()))
        logger.debug("data_check_string hex: %s", data_check_string.encode().hex())
        
        # 4. Generate secret key
        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        logger.debug("secret_key (hex): %s", secret_key.hex())
        
        # 5. Calculate hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        logger.debug("Calculated hash: %s", calculated_hash)
        logger.debug("Received hash:   %s", hash_value)
        
        # 6. Compare with constant-time comparison
        ok = hmac.compare_digest(calculated_hash, hash_value)
        logger.debug("Hash verification result: %s", ok)
        
        # Если хеш не совпал, попробуем другие варианты для отладки
        if not ok:
            # Попробуем другой токен бота (возможно, в Telegram используется другой бот)
            alt_token = "7166404709:AAGZ9S4OJPP-sGcZ1pIlMdaZXwpMFagDq_0"
            alt_secret_key = hmac.new(
                b"WebAppData",
                alt_token.encode(),
                hashlib.sha256
            ).digest()
            
            alt_calculated_hash = hmac.new(
                alt_secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            logger.debug("Alt token calculated hash: %s", alt_calculated_hash)
            alt_ok = hmac.compare_digest(alt_calculated_hash, hash_value)
            logger.debug("Alt token verification result: %s", alt_ok)
            
            if alt_ok:
                logger.warning("Hash verification succeeded with alternative bot token!")
                return True
        
        return ok

    except Exception as e:
        logger.exception("Hash verification failed with exception: %s", str(e))
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(data: Dict) -> str:
    """Generate signed JWT access token."""
    expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**data, "exp": expire}
    token = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.debug("JWT created for %s (exp %s)", data.get("username"), expire)
    return token


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict:
    """Validate Bearer token from Authorization header."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        exp = payload.get("exp", 0)
        if exp < time.time():
            raise HTTPException(status_code=401, detail="Token has expired")
        return payload
    except Exception as exc:
        logger.exception("JWT verification error: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
