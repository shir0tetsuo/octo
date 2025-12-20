from __future__ import annotations

# NOTE : This is the frontend server, it will serve as the proxy behind Caddy;
#        It will handle User Authentication, db communication (with Key),

# internal
from engine import jsonsafe, verbose, versioning, security, validation

import sqlite3
import asyncio
import os, json, enum, inspect, subprocess, uuid, threading, time, base64

DB_KEY = str(os.getenv('DB_X_API_KEY', ''))

from dataclasses import is_dataclass, asdict
from decimal     import Decimal
from datetime    import datetime, timedelta, timezone, date
from pathlib     import Path
from typing      import Callable, Any, Type, Union, Optional, Dict, List, Literal, NewType
from contextlib  import asynccontextmanager
from collections import OrderedDict
import anyio

# For Compatiibility Layer in JSON Safety
import numpy as np
import pandas as pd

# FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi                 import FastAPI, Header, HTTPException, status, BackgroundTasks, Depends
from fastapi.security        import APIKeyHeader
from fastapi.responses       import PlainTextResponse # might be removed later
from uvicorn                 import run as uvicorn_run
from pydantic                import BaseModel, Field

# Cryptography
from cryptography                                import x509
from cryptography.x509.oid                       import NameOID
from cryptography.hazmat.backends                import default_backend
from cryptography.hazmat.primitives              import hashes, serialization
from cryptography.hazmat.primitives.asymmetric   import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

Tee = verbose.T()

ExtendToParentResource = lambda *args: Path(os.path.join(Path(__file__).parent.resolve(), *args))
NewID = lambda: str(uuid.uuid4())
db_path = ExtendToParentResource('db')
if not db_path.exists():
    db_path.mkdir(parents=True, exist_ok=True)

class ServerOkayResponse(BaseModel):
    message: Literal['OK', 'ERROR']

key_storage_file = ExtendToParentResource('engine', 'key.json')  # Where the private decryption key is stored

@asynccontextmanager
async def lifespan(server: FastAPI):
    #global ZONES
    #for store in ZONES.values():
    #    await store.init()
    yield
    #for store in ZONES.values():
    #    await store.close()

server = FastAPI(title='Frontend Server', version=versioning.distribution_version, lifespan=lifespan)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True, scheme_name="APIKeyAuth")
server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def ThrowHTTPError(message, status_code=status.HTTP_401_UNAUTHORIZED):
    e = HTTPException(status_code=status_code, detail=message)
    Tee.exception(e, msg=message)
    raise e

ThrowIf = lambda statement, error_message='', status_code=status.HTTP_401_UNAUTHORIZED: (ThrowHTTPError(error_message, status_code) if statement else None)
'''
:param statement: Conditional boolean logic statement yielding `True` or `False`, if `True`, an error will be thrown, if `False`, `None` will be returned.
:param error_message: Error Message String
:type error_message: str
:param status_code: The HTTP Status Code to be returned. Default is `status.HTTP_401_UNAUTHORIZED` (401)
:type status_code: int
'''

# NOTE : For actions that require an API Key!
def Authorization(api_key = Depends(api_key_header)) -> security.DecryptedToken:
    global key_storage_file
    decrypted:security.DecryptedToken = security.decrypt_api_key(api_key, key_storage_file)
    
    if any([
        decrypted.decryption_success == False,
        decrypted.days_old >= 365,
        validation.is_valid_uuid4(decrypted.ID) == False
    ]):
        ThrowIf(True, 'Invalid API Key')
    
    return decrypted

@server.get("/health", response_model=ServerOkayResponse)
async def zone_health():
    return ServerOkayResponse(message='OK')

if __name__ == "__main__":
    import uvicorn
    # Use loop="asyncio" to prevent uvloop conflicts with generic thread pools if needed
    uvicorn.run(server, host="0.0.0.0", port=9300, workers=1, loop="asyncio")