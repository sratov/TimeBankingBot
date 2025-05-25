import hmac, hashlib, urllib.parse, binascii, textwrap, json, time

# Telegram bot token
BOT_TOKEN = "8022193791:AAEAt9a6kBmP28XN60P8d0HmPKG4n9_4-bU"

def verify_telegram_web_app_data(init_data: str, bot_token: str) -> bool:
    """
    Verify Telegram Web App init_data according to official documentation:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    
    Args:
        init_data: The init_data string from Telegram Web App
        bot_token: Your bot token
        
    Returns:
        bool: True if verification is successful, False otherwise
    """
    # 1. Parse the init_data
    params = {}
    for pair in init_data.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            params[key] = value
    
    hash_value = params.pop('hash', None)
    if not hash_value:
        print("Error: No hash found in init_data")
        return False
    
    # 2. Build data_check_string
    # Sort params by key in alphabetical order and join with \n
    data_check_string = '\n'.join([f"{k}={params[k]}" for k in sorted(params.keys())])
    
    # 3. Generate secret key
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()
    
    # 4. Calculate hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # 5. Compare hashes
    return hmac.compare_digest(calculated_hash, hash_value)

def debug_telegram_web_app_data(init_data: str, bot_token: str) -> None:
    """
    Debug Telegram Web App init_data verification
    
    Args:
        init_data: The init_data string from Telegram Web App
        bot_token: Your bot token
    """
    print("=== Telegram Web App Data Verification Debug ===")
    
    # 1. Parse the init_data
    params = {}
    for pair in init_data.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            params[key] = value
    
    hash_value = params.pop('hash', None)
    if not hash_value:
        print("Error: No hash found in init_data")
        return
    
    # 2. Build data_check_string
    # Sort params by key in alphabetical order and join with \n
    data_check_string = '\n'.join([f"{k}={params[k]}" for k in sorted(params.keys())])
    
    # 3. Generate secret key
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()
    
    # 4. Calculate hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    print("\nBot Token:", bot_token)
    
    print("\nExtracted params:")
    for k, v in params.items():
        print(f"{k}: {v}")
    
    print("\ndata_check_string:")
    print(repr(data_check_string))
    
    print("\nsecret_key (hex):")
    print(binascii.hexlify(secret_key).decode())
    
    print("\nHashes:")
    print("calculated:", calculated_hash)
    print("received  :", hash_value)
    print("match?    :", hmac.compare_digest(calculated_hash, hash_value))

def generate_test_init_data(bot_token: str) -> str:
    """
    Generate test init_data for Telegram Web App
    
    Args:
        bot_token: Your bot token
        
    Returns:
        str: The generated init_data string
    """
    # Create test data
    test_params = {
        "auth_date": str(int(time.time())),
        "query_id": "test_query",
        "user": json.dumps({"id": 887978091, "first_name": "Test", "username": "test_user"})
    }
    
    # Sort params by key
    sorted_params = sorted(test_params.items())
    
    # Create data_check_string
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted_params])
    
    # Generate secret key
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()
    
    # Calculate hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Add hash to params
    test_params["hash"] = calculated_hash
    
    # Create init_data string
    init_data = "&".join([f"{k}={v}" for k, v in test_params.items()])
    
    return init_data

if __name__ == "__main__":
    # Example usage
    print("=== Telegram Web App Data Verification Tool ===")
    
    # 1. Generate test init_data
    print("\n1. Generating test init_data...")
    test_init_data = generate_test_init_data(BOT_TOKEN)
    print("Generated init_data:", test_init_data)
    
    # 2. Verify test init_data
    print("\n2. Verifying test init_data...")
    is_valid = verify_telegram_web_app_data(test_init_data, BOT_TOKEN)
    print("Verification result:", "Valid" if is_valid else "Invalid")
    
    # 3. Debug test init_data
    print("\n3. Debugging test init_data...")
    debug_telegram_web_app_data(test_init_data, BOT_TOKEN)
    
    # 4. Original init_data from Telegram
    original_init_data = "query_id=AAFreO00AAAAAGt47TSUjGWL&user=%7B%22id%22%3A887978091%2C%22first_name%22%3A%22.%22%2C%22last_name%22%3A%22.%22%2C%22username%22%3A%22sar_a_to_v%22%2C%22language_code%22%3A%22ru%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2F1RamL_iAFcdZ2kGPxN7DFOtBN-utHaDkfIu1okZ2zsA.svg%22%7D&auth_date=1748190517&hash=76070fd24ea872b66814099082c32438c42206f18cb1cdad14f9b2a47ebaa7cb"
    
    # 5. Verify original init_data
    print("\n4. Verifying original init_data...")
    is_valid = verify_telegram_web_app_data(original_init_data, BOT_TOKEN)
    print("Verification result:", "Valid" if is_valid else "Invalid")
    
    # 6. Debug original init_data
    print("\n5. Debugging original init_data...")
    debug_telegram_web_app_data(original_init_data, BOT_TOKEN)
    
    print("\nConclusion:")
    print("If the test init_data verification succeeds but the original init_data fails,")
    print("it means that either:")
    print("1. The original init_data was signed with a different bot token")
    print("2. The original init_data was modified after signing")
    print("3. There is an issue with the format of the original init_data")
    
    print("\nFor your FastAPI implementation, use code like this:")
    print("""
from fastapi import FastAPI, Depends, HTTPException, Query
from typing import Dict, Any

app = FastAPI()

def verify_telegram_data(init_data: str = Query(...)) -> Dict[str, Any]:
    # Parse the init_data
    params = {}
    for pair in init_data.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            params[key] = value
    
    hash_value = params.pop('hash', None)
    if not hash_value:
        raise HTTPException(status_code=400, detail="No hash in init_data")
    
    # Build data_check_string
    data_check_string = '\\n'.join([f"{k}={params[k]}" for k in sorted(params.keys())])
    
    # Generate secret key
    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()
    
    # Calculate hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Compare hashes
    if not hmac.compare_digest(calculated_hash, hash_value):
        raise HTTPException(status_code=401, detail="Invalid hash")
    
    # Return parsed data
    return params

@app.get("/webapp-auth")
async def webapp_auth(data: Dict[str, Any] = Depends(verify_telegram_data)):
    return {"message": "Authentication successful", "user_id": data.get("user", {}).get("id")}
""") 