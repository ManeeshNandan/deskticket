from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

def _fernet():
    key=getattr(settings,"MAILBOX_ENCRYPTION_KEY","")
    if not key: raise RuntimeError("MAILBOX_ENCRYPTION_KEY is not configured.")
    try: return Fernet(key.encode() if isinstance(key,str) else key)
    except Exception as exc: raise RuntimeError("MAILBOX_ENCRYPTION_KEY is invalid. Generate it with Fernet.generate_key().") from exc

def encrypt(value):
    if not value: return ""
    return _fernet().encrypt(value.encode()).decode()

def decrypt(value):
    if not value: return ""
    try: return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc: raise RuntimeError("Invalid mailbox encryption key or encrypted secret.") from exc
