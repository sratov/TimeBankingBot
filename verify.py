import hmac, hashlib, urllib.parse, binascii

BOT_TOKEN = "7166404709:AAGZ9S4OJPP-sGcZ1pIlMdaZXwpMFagDq_0"

RAW_INIT_DATA = (
    "query_id=AAFreO00AAAAAGt47TSUjGWL&"
    "user=%7B%22id%22%3A887978091%2C%22first_name%22%3A%22.%22%2C%22last_name%22%3A%22.%22%2C"
    "%22username%22%3A%22sar_a_to_v%22%2C%22language_code%22%3A%22ru%22%2C%22allows_write_to_pm%22%3Atrue%2C"
    "%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2F1RamL_iAFcdZ2kGPxN7DFOtBN-utHaDkfIu1okZ2zsA.svg%22%7D&"
    "auth_date=1748190517&"
    "signature=_oMdWCc-xzVnIyv8P7aRBzrwpaXcK7u5Wq5XBZcV06WDhxv8h9mQSfLv2N93SxTbxC6ONNvZ50G6qhImJ2cjCA&"
    "hash=76070fd24ea872b66814099082c32438c42206f18cb1cdad14f9b2a47ebaa7cb"
)

def debug_string(s: str, label: str = ""):
    """Print detailed debug info about a string"""
    print(f"\n=== {label} ===")
    print("Raw:", repr(s))
    print("URL-decoded once:", repr(urllib.parse.unquote(s)))
    print("URL-decoded twice:", repr(urllib.parse.unquote(urllib.parse.unquote(s))))
    print("Hex:", binascii.hexlify(s.encode()).decode())
    print("Length:", len(s))

# Parse and extract parameters
pairs = [p.split("=", 1) for p in RAW_INIT_DATA.split("&")]
data = {k: v for k, v in pairs}
recv_hash = data.pop("hash")

# Debug each parameter
for k, v in sorted(data.items()):
    debug_string(v, f"Parameter: {k}")

print("\n=== Test with raw parameters ===")
# Build data_check_string without any modifications
data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
debug_string(data_check_string, "data_check_string")

secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

print("\nHashes:")
print("calculated:", calc_hash)
print("received :", recv_hash)
print("match?   :", hmac.compare_digest(calc_hash, recv_hash))

print("\n=== Test with URL-decoded user ===")
# Try decoding just the user parameter
decoded_data = data.copy()
decoded_data["user"] = urllib.parse.unquote(data["user"])
data_check_string = "\n".join(f"{k}={decoded_data[k]}" for k in sorted(decoded_data))
debug_string(data_check_string, "data_check_string")

calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

print("\nHashes:")
print("calculated:", calc_hash)
print("received :", recv_hash)
print("match?   :", hmac.compare_digest(calc_hash, recv_hash))

# Second test - without signature
print("\n=== Test 2: Without signature ===")
pairs = [p.split("=", 1) for p in RAW_INIT_DATA.split("&")]
data = {k: v for k, v in pairs}
recv_hash = data.pop("hash")
data.pop("signature", None)  # Remove signature if present

data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))

calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

print("\ndata_check_string (utf-8 bytes -> hex):")
print(binascii.hexlify(data_check_string.encode()).decode(), "\n")

print("calculated:", calc_hash)
print("received  :", recv_hash)
print("match?    :", hmac.compare_digest(calc_hash, recv_hash))

# Third test - just auth_date and query_id
print("\n=== Test 3: Minimal parameters ===")
pairs = [p.split("=", 1) for p in RAW_INIT_DATA.split("&")]
data = {
    k: v for k, v in pairs 
    if k in ("auth_date", "query_id", "user")
}
recv_hash = dict(pairs)["hash"]

data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))

calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

print("\ndata_check_string (utf-8 bytes -> hex):")
print(binascii.hexlify(data_check_string.encode()).decode(), "\n")

print("calculated:", calc_hash)
print("received  :", recv_hash)
print("match?    :", hmac.compare_digest(calc_hash, recv_hash)) 