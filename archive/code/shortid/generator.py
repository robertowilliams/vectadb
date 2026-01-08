import string, secrets, hashlib, base64

ALPHABET = string.ascii_letters + string.digits

def generate_short_id(length=6, deterministic=False, seed=None):
    if deterministic:
        if not seed:
            raise ValueError("A seed is required in deterministic mode.")
        h = hashlib.sha1(seed.encode()).digest()
        b64 = base64.b64encode(h).decode()
        b64 = b64.replace("+", "A").replace("/", "B").replace("=", "")
        return b64[:length]
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
