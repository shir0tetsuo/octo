from __future__ import annotations

# NOTE : This is the frontend server, it will serve as the proxy behind Caddy;
#        It will handle User Authentication, db communication (with Key),

# internal
from engine import (
    verbose, versioning, mapmath,
    jsonsafe, security, validation, 
    ratelimits, databases
)

import sqlite3
import httpx
import asyncio
import os, json, enum, inspect, subprocess, uuid, threading, time, base64

DB_KEY = str(os.getenv('DB_X_API_KEY', ''))
DB_SERVER = str(os.getenv('DB_SERVER', 'http://localhost:9401'))

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
from fastapi                 import FastAPI, Header, HTTPException, status, BackgroundTasks, Depends, Request, Cookie
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

blacklist = databases.Blacklist(ExtendToParentResource('engine', 'blacklist.json'))

class ServerOkayResponse(BaseModel):
    message: Literal['OK', 'ERROR']
    version: str = versioning.distribution_version
    db_health: dict

class APIKeyCheckRequest(BaseModel):
    APIKey: str

class EntititesRequest(BaseModel):
    x_axis: int
    y_axis: int
    z_axis: Literal[0, 1, 2, 3, 4, 5, 6, 7] # 8 Zones
    time_axis: float | None

class EntityRequest(BaseModel):
    x_pos: int
    y_pos: int
    zone: Literal[0, 1, 2, 3, 4, 5, 6, 7] # 8 Zones
    iter: Optional[int]

class KeyOkayResponse(BaseModel):
    valid_key: bool = False

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
strict_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True, scheme_name="APIKeyAuth")
loose_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="APIKeyAuth")
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
# NOTE : But this doesn't work right from Github Pages through Caddy anyway!!
def Authorization(api_key = Depends(strict_api_key_header)) -> security.DecryptedToken:
    global key_storage_file, blacklist

    ThrowIf(ratelimits.within_key_rate_limit(api_key) == False, 'Too many requests', status_code=status.HTTP_429_TOO_MANY_REQUESTS)

    decrypted:security.DecryptedToken = security.decrypt_api_key(api_key, key_storage_file)
    
    for datakey in decrypted.data:
        ThrowIf(datakey in blacklist.banned_ids, 'Blacklisted Key.')

    if any([
        decrypted.decryption_success == False,
        decrypted.days_old >= 365,
        validation.is_valid_uuid4(decrypted.ID) == False
    ]):
        ThrowIf(True, 'Invalid API Key')
    
    return decrypted

# NOTE : This segment is new, doesn't work as intended.
# TODO : Debug why cookie is not seen by server.
#        Could bypass by passing it directly in the request.

nil_account = security.DecryptedToken(
    decryption_success=False,
    data=[],
    days_old=0,
    ID=security.NoneID
)

def APIKeyPresence(
        x_api_key_header: str | None = Header(None, alias="X-API-Key"),
        x_api_key_cookie: str | None = Cookie(None, alias="X-API-Key")
    ) -> security.DecryptedToken:
    '''
    Checks for an API key either in the header or in a cookie.
    Returns a DecryptedToken if valid, otherwise returns nil_account.
    '''
    # Use header first, then fallback to cookie
    api_key = x_api_key_header or x_api_key_cookie
    if not api_key:
        return nil_account

    decrypted: security.DecryptedToken = security.decrypt_api_key(api_key, key_storage_file)

    # Validate decrypted token
    if any([
        decrypted.decryption_success is False,
        decrypted.days_old >= 365,
        validation.is_valid_uuid4(decrypted.ID) is False
    ]):
        return nil_account

    return decrypted

# NOTE : More security checks can be expanded here, such as blacklisting ...
@server.post("/api/CheckAPIKey", response_model=KeyOkayResponse)
async def general_key_check(payload: APIKeyCheckRequest):
    global key_storage_file, blacklist
    decrypted:security.DecryptedToken = security.decrypt_api_key(payload.APIKey, key_storage_file)

    for datakey in decrypted.data:
        ThrowIf(datakey in blacklist.banned_ids)

    if any([
        decrypted.decryption_success is False,
        decrypted.days_old >= 365,
        validation.is_valid_uuid4(decrypted.ID) is False
    ]):
        return KeyOkayResponse(valid_key=False)

    return KeyOkayResponse(valid_key=True)

@server.post('/api/render')
async def render_provider(
        request: Request, 
        payload: EntititesRequest, 
        user_context:security.DecryptedToken = Depends(APIKeyPresence)
    ):

    # TODO : time axis not yet implemented

    client_host = request.client.host
    if not ratelimits.within_ip_rate_limit(client_ip=client_host):
        return ServerOkayResponse(
            message='ERROR',
            db_health={"message": "Rate Limit Exceeded"}
        )

    x = mapmath.expand_sequence(payload.x_axis)
    y = mapmath.expand_sequence(payload.y_axis)
    min_x = x[0]
    max_x = x[-1]
    min_y = y[0]
    max_y = y[-1]
    z = payload.z_axis  # ZONE

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DB_SERVER + f"/range/{z}",
                headers={"X-API-Key": DB_KEY},
                timeout=5.0,
                json={
                    'min_x': min_x,
                    'max_x': max_x,
                    'min_y': min_y,
                    'max_y': max_y,
                    'limit': 64
                }
            )

            if response.status_code == status.HTTP_200_OK:
                
                data = response.json()

                # Index DB results by (x, y)
                entity_map = {
                    (ent["positionX"], ent["positionY"]): databases.normalize_entity(ent, z)
                    for ent in data
                }

                result_grid = []

                for _y in y:
                    row = []
                    for _x in x:
                        ent = entity_map.get((_x, _y))
                        if ent is None:
                            ent = databases.entity_genesis(_x, _y, z)
                        row.append(ent)
                    result_grid.append(row)

                # TODO : Commit genesis entities. (Not on seen.)
                return {
                    'message': 'OK',
                    'x': x,
                    'y': y,
                    'entities': result_grid,
                    'user_context': user_context,
                    'banner': databases.ZONE_COLORS[z]
                }
            
            else:
                return ServerOkayResponse(
                    message="ERROR",
                    db_health={"message": f"DB returned {response.status_code}"}
                )
    
    except httpx.ConnectError:
        return ServerOkayResponse(
            message="ERROR",
            db_health={"message": "Database server unreachable"}
        )

    return ServerOkayResponse(
        message="ERROR",
        db_health={"message": "Unexpected error."}
    )

@server.post('/api/render/one')
async def provide_single_render(
        request: Request, 
        payload: EntityRequest, 
        user_context:security.DecryptedToken = Depends(APIKeyPresence)
    ):

    client_host = request.client.host
    if not ratelimits.within_ip_rate_limit(client_ip=client_host, RATE=15):
        return ServerOkayResponse(
            message='ERROR',
            db_health={"message": "Rate Limit Exceeded"}
        )
    
    _xpos=int(payload.x_pos)
    _ypos=int(payload.y_pos)
    _zone=int(payload.zone)
    _iter=int(payload.iter)

    try:
        async with httpx.AsyncClient() as client:
            # TODO : ROUTE NOT BUILT YET
            response = await client.post(
                DB_SERVER + f"/expand",
                headers={"X-API-Key": DB_KEY},
                timeout=5.0,
                json={
                    'x': _xpos,
                    'y': _ypos,
                    'z': _zone,
                    'i': _iter  # intended_iter
                }
            )

            if response.status_code == status.HTTP_200_OK:

                data = response.json()

                entities = data["entities"]

                entity_normals = {
                    int(ent["iter"]): databases.normalize_entity(ent, _zone)
                    for ent in entities
                }

                sorted_normals = dict(sorted(entity_normals.items()))
                #iter_is_latest = data["is_latest_on_file"]

                # NOTE : Commit Entity not done here.
                return {
                    'message': 'OK',
                    'x': _xpos,
                    'y': _ypos,
                    'z': _zone,
                    'entity': (
                        { 
                            0 : databases.entity_genesis(_xpos, _ypos, _zone) 
                        }
                        if not entity_normals else
                        sorted_normals
                    ),
                    'intended_iter': data["intended_iter"],
                    'iter_is_latest': data["is_latest_on_file"],
                    'user_context': user_context,
                    'banner': databases.ZONE_COLORS[_zone]
                }
            
            else:
                return ServerOkayResponse(
                    message="ERROR",
                    db_health={
                        "message": "Unexpected error occurred.", 
                        "status_code": response.status_code,
                        "server_message": response.text
                    }
                )
    
    except httpx.ConnectError:
        return ServerOkayResponse(
            message="ERROR",
            db_health={"message": "Database server unreachable"}
        )
    
    return ServerOkayResponse(
        message="ERROR",
        db_health={"message": "Unexpected error occurred."}
    )
    
    

@server.get("/api/health", response_model=ServerOkayResponse)
async def system_health_check():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                DB_SERVER + "/health",
                headers={"X-API-Key": DB_KEY},
                timeout=5.0
            )

        if response.status_code == status.HTTP_200_OK:
            return ServerOkayResponse(
                message="OK",
                db_health=response.json()
            )

        return ServerOkayResponse(
            message="ERROR",
            db_health={"message": f"DB returned {response.status_code}"}
        )

    except httpx.ConnectError:
        return ServerOkayResponse(
            message="ERROR",
            db_health={"message": "Database server unreachable"}
        )

if __name__ == "__main__":
    import uvicorn
    # Use loop="asyncio" to prevent uvloop conflicts with generic thread pools if needed
    uvicorn.run(server, host="0.0.0.0", port=9300, workers=1, loop="asyncio")