import os, json, base64, threading
from pathlib import Path
from typing import Optional
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import uuid
from pydantic import BaseModel
import re
import unicodedata

class DecryptedToken(BaseModel):
    decryption_success: bool
    data: list
    days_old: int
    ID: str

private_key = None

token_separator = '**'
NoneID = "00000000-0000-0000-0000-000000000001"

NewToken = lambda *args: f'{token_separator}'.join(args)
NewCipherBlob = lambda token, key, nonce: nonce + AESGCM(key).encrypt(nonce, token.encode(), None)

def store_private_key(key_storage_file:Path, lock=threading.RLock(), private_key:bytes=os.urandom(32)):
    try:
        with lock:
            with open(str(key_storage_file.resolve()), 'w', encoding='utf-8') as kf:
                json.dump({'key': base64.b64encode(private_key).decode('utf-8')}, kf, indent=4)
        return private_key
    except Exception as e:
        raise e
    
def read_private_key(key_storage_file:Path, lock=threading.RLock()):
    global private_key
    if not private_key:
        try:
            if not key_storage_file.exists():
                private_key = store_private_key(key_storage_file)
            else:
                with lock:
                    with key_storage_file.open('r', encoding='utf-8') as kf:
                        data = json.load(kf)
                        private_key = base64.b64decode(data['key'])
        
        except Exception as e:
            raise e
        
    return private_key

def create_api_key(
        *token_data, 
        key_storage_file:Path, 
        ID:Optional[str]=str(uuid.uuid4()), 
        ts = datetime.now().isoformat(timespec="seconds"),
        lock=threading.RLock()
    ):
    private_key = read_private_key(key_storage_file, lock)
    return base64.urlsafe_b64encode( NewCipherBlob( NewToken( *token_data, ID, ts ), private_key, os.urandom(12) ) )

def decrypt_api_key(b64_cipher, key_storage_file:Path, lock=threading.RLock()):
    global token_separator, NoneID
    private_key = read_private_key(key_storage_file, lock)
    token = []
    try:
        blob = base64.urlsafe_b64decode(b64_cipher)
        token = AESGCM(private_key).decrypt(blob[:12], blob[12:], None).decode().split(token_separator)
        ts = token.pop(-1)
        ID = token.pop(-1)
        return DecryptedToken(
            decryption_success=True, 
            data=token, 
            days_old=(datetime.now() - datetime.fromisoformat(ts)).days, 
            ID=ID
        )
    except Exception as e:
        return DecryptedToken(
            decryption_success=False, 
            data=token, 
            days_old=0, 
            ID=NoneID
        )
    
# Commonly abused characters across SQL / JS / Python injection
DANGEROUS_CHARS = re.compile(
    r'''
    [\x00-\x1F\x7F]      |  # Control chars
    ['"`\\]              |  # Quotes / escapes
    ;                    |  # Statement chaining
    --                   |  # SQL comments
    /\*|\*/              |  # SQL block comments
    <|>                  |  # HTML / JS injection
    \$\{                 |  # JS template injection
    \|\||&&              |  # Logical chaining
    \b(eval|exec|import|require|process|os|sys)\b
    ''',
    re.IGNORECASE | re.VERBOSE
)


SAFE_DEFAULT = re.compile(r"[^a-zA-Z0-9 _.\-@:/]")

def sanitize(value: str, *, max_length: Optional[int] = None) -> str:
    '''
    Aggressively sanitize text for non-executable contexts.

    - Safe for storage, display, logging
    - Unicode-aware (runes allowed)
    - NOT a replacement for parameterized SQL or escaping APIs
    '''

    if not isinstance(value, str):
        value = str(value)

    # 1. Unicode normalization (critical)
    value = unicodedata.normalize("NFKC", value)

    # 2. Strip dangerous patterns
    value = DANGEROUS_CHARS.sub("", value)

    # 3. Remove remaining control / formatting Unicode chars
    value = "".join(
        ch for ch in value
        if unicodedata.category(ch)[0] != "C"
    )

    # 4. Collapse whitespace
    value = re.sub(r"\s+", " ", value).strip()

    # 5. Clamp length if requested
    if max_length is not None:
        value = value[:max_length]

    return value