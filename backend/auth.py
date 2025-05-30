from jose import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
import hmac
import hashlib
import time
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Dict
from config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    BOT_TOKEN,
)
import re

# ---------------------------------------------------------------------------
# logging setup
# ---------------------------------------------------------------------------
# Create logs directory if it doesn't exist
import os
os.makedirs('logs', exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Clear existing handlers
if logger.handlers:
    logger.handlers = []

# Add console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Add file handler
file_handler = RotatingFileHandler(
    'logs/auth.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info("="*80)
logger.info("Authentication module initialized")
logger.info(f"BOT_TOKEN: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]} (length: {len(BOT_TOKEN)})")
logger.info("="*80)

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
        logger.debug("BOT_TOKEN length: %d", len(BOT_TOKEN))
        logger.debug("init_data (repr): %r", init_data)
        logger.debug("received_hash: %s", received_hash)
        
        # Check for test mode - ТОЛЬКО для тестирования!
        if "test_mode=true" in init_data or "test" in init_data:
            logger.warning("TEST MODE detected - bypassing hash verification!")
            return True
            
        # Remove hash from the data string for verification
        # Format: key=value&key=value&key=value&hash=hash_value
        
        # 1. Check if hash is in the data
        if "hash=" not in init_data:
            logger.error("No hash found in init_data")
            return False
        
        # 2. Разбиваем строку на пары key=value
        params = init_data.split('&')
        
        # 3. Удаляем пары с hash и signature (если она есть)
        params_without_hash = [p for p in params if not (p.startswith("hash=") or p.startswith("signature="))]
        
        # 4. Сортируем пары в лексикографическом порядке
        params_without_hash.sort()
        
        # 5. Соединяем через \n
        data_check_string = "\n".join(params_without_hash)
        logger.debug("Data check string: %s", data_check_string)
        
        # 6. Создаем секретный ключ - SHA-256 хеш от BOT_TOKEN
        # Проверяем, что используется правильный метод (SHA-256 от BOT_TOKEN)
        secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
        logger.debug("Secret key created using hashlib.sha256 (first 5 bytes): %r", secret_key[:5])
        
        # 7. Вычисляем HMAC-SHA-256 хеш от data_check_string с использованием секретного ключа
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        logger.debug("Calculated hash: %s", calculated_hash)
        
        # 8. Сравниваем вычисленный хеш с полученным
        result = calculated_hash == received_hash
        logger.debug("Hash verification result: %s", result)
        logger.debug("="*50 + "\n")
        
        return result
    except Exception as e:
        logger.error("Error during hash verification: %s", str(e))
        logger.exception(e)
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
