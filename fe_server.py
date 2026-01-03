from __future__ import annotations

# NOTE : This is the frontend server, it will serve as the proxy behind Caddy;
#        It will handle User Authentication, db communication (with Key),

# internal
from engine import (
    verbose, versioning, mapmath,
    jsonsafe, security, validation, 
    ratelimits, databases, tarot
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
from pydantic                import BaseModel, Field, field_validator

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

listloop = lambda data, index: data[index % len(data)]

blacklist = databases.Blacklist(ExtendToParentResource('engine', 'blacklist.json'))

class ServerOkayResponse(BaseModel):
    message: Literal['OK', 'ERROR']
    version: str = versioning.distribution_version
    db_health: dict

class ServerRenewResponse(BaseModel):
    message: Literal['OK', 'ERROR']
    api_key: str

class APIKeyCheckRequest(BaseModel):
    APIKey: str

def validate_zone_int(v: int) -> int:
    max_zone = len(databases.ZONE_COLORS) - 1
    if v < 0 or v > max_zone:
        raise ValueError(f"Zone must be between 0 and {max_zone}")
    return v

class EntititesRequest(BaseModel):
    x_axis: int  # map X
    y_axis: int  # map Y

    z_axis: int
    _validate_z_axis = field_validator("z_axis")(validate_zone_int)
    
    time_axis: float | None

class EntityRequest(BaseModel):
    x_pos: int  # absolute position
    y_pos: int  # absolute position
    
    zone: int
    _validate_zone = field_validator("zone")(validate_zone_int)
        
    iter: Optional[int]

class AreaRequest(BaseModel):
    xyzs: list  # [(x,y,z,string),(...)]

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
@server.post("/api/CheckAPIKey")
async def general_key_check(
        request: Request,
        payload: APIKeyCheckRequest
    ):
    global key_storage_file, blacklist

    client_host = request.client.host
    if not ratelimits.within_ip_rate_limit(client_ip=client_host, RATE=10, WINDOW=40):
        return ServerOkayResponse(
            message='ERROR',
            db_health={"message": "Rate Limit Exceeded"}
        )

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

@server.get("/api/APIKey/renew")
async def renew_api_key(
        request: Request,
        user_context:security.DecryptedToken = Depends(Authorization)
    ):
    global key_storage_file, blacklist

    client_host = request.client.host
    if not ratelimits.within_ip_rate_limit(client_ip=client_host, RATE=10, WINDOW=60):
        return ServerOkayResponse(
            message='ERROR',
            db_health={"message": "Rate Limit Exceeded"}
        )
    
    for datakey in user_context.data:
        ThrowIf(datakey in blacklist.banned_ids, "Banned User")
    
    ThrowIf( 
        any(
            [
                user_context.decryption_success is False,
                user_context.days_old >= 365,
                validation.is_valid_uuid4(user_context.ID) is False
            ]
        ),
        "Banned ID.",
        status.HTTP_403_FORBIDDEN
    )

    new_key = security.create_api_key(
        *user_context.data,
        key_storage_file=key_storage_file,
        ID=user_context.ID
    ).decode()

    return ServerRenewResponse(
        message='OK',
        api_key=new_key
    )

@server.post("/api/APIKey")
async def give_decrypted_key(
        request: Request,
        payload: APIKeyCheckRequest
    ):
    global key_storage_file, blacklist

    client_host = request.client.host
    if not ratelimits.within_ip_rate_limit(client_ip=client_host, RATE=10, WINDOW=40):
        return ServerOkayResponse(
            message='ERROR',
            db_health={"message": "Rate Limit Exceeded"}
        )
    
    decrypted:security.DecryptedToken = security.decrypt_api_key(payload.APIKey, key_storage_file)

    for datakey in decrypted.data:
        ThrowIf(datakey in blacklist.banned_ids)

    if any([
        decrypted.decryption_success is False,
        decrypted.days_old >= 365,
        validation.is_valid_uuid4(decrypted.ID) is False
    ]):
        return nil_account

    return decrypted

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

@server.post('/api/render/areas')
async def provide_area_render(
        request: Request,
        payload: AreaRequest,
        user_context:security.DecryptedToken = Depends(APIKeyPresence)
    ):
    
    client_host = request.client.host
    if not ratelimits.within_ip_rate_limit(client_ip=client_host, RATE=15):
        return ServerOkayResponse(
            message='ERROR',
            db_health={"message": "Rate Limit Exceeded"}
        )
    
    ents = []
    for req in payload.xyzs:
        if isinstance(req, str):
            req = str(req).split(',')
            #req=[int(i) for i in str(req).split(',')]
        x=mapmath.expand_sequence(int(req[0]))[0]
        y=mapmath.expand_sequence(int(req[1]))[0]
        z=int(req[2])
        s=str(req[3])
        if z not in databases.ZONE_INTEGERS:
            continue
        ent = databases.normalize_entity(databases.entity_genesis(x, y, z), z)
        ent['repr'] = {'x': int(req[0]), 'y': int(req[1]), 's': s}
        ents.append(ent)
    
    return { 'entities': ents, 'user_context': user_context }

@server.post('/api/newiter')
async def iter_request(
        request: Request,
        payload: EntityRequest,
        user_context: security.DecryptedToken = Depends(Authorization)
    ):

    client_host = request.client.host
    if not ratelimits.within_ip_rate_limit(client_ip=client_host, RATE=10, WINDOW=60):
        return ServerOkayResponse(
            message='ERROR',
            db_health={"message": "Rate Limit Exceeded"}
        )
    
    _xpos, _ypos, _zone, _iter = ([int(n) for n in [payload.x_pos, payload.y_pos, payload.zone, payload.iter]])

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DB_SERVER + "/expandall",
                headers={"X-API-Key": DB_KEY},
                timeout=5.0,
                json={
                    'x': _xpos, 'y': _ypos, 'z': _zone, 'i': _iter
                }
            )

            if response.status_code != status.HTTP_200_OK:
                return ServerOkayResponse(
                    message="ERROR",
                    db_health={"message": f"Failed to fetch entity: {response.status_code}"}
                )
            
            data = response.json()
            entities = data['entities']

            if not entities:
                return ServerOkayResponse(
                    message="ERROR",
                    db_health={"message": f"No #0 mint, not allowed"}
                )

            # Require that the requester is the owner of the genesis iteration (#0)
            genesis = entities[0] if len(entities) > 0 else None
            if not genesis or genesis.get('ownership') != user_context.ID:
                return ServerOkayResponse(
                    message="ERROR",
                    db_health={"message": "Only the owner of genesis may create new iterations."}
                )
            
            last_iter = len(entities) - 1 # 0 <mint>
            next_iter = len(entities)     # 1
            tarot_card = listloop(tarot.deterministic_shuffle(tarot._all_cards, f'{_xpos}:{_ypos}:{_zone}'), last_iter)
            new_entity = databases.entity_genesis(_xpos, _ypos, _zone)
            new_entity["ownership"] = user_context.ID
            new_entity["iter"] = next_iter
            new_entity["name"] = tarot_card
            new_entity["description"] = tarot.card_meanings.get(tarot_card, "Genesis")
            new_entity["state"] = 2

            # Remove UI flag
            new_entity.pop('exists', None)

            # Index should always be generated by the server in this case
            new_entity.pop('index', None)

            set_response = await client.post(
                DB_SERVER + f"/set/{_zone}",
                headers={"X-API-Key": DB_KEY},
                timeout=5.0,
                json=new_entity
            )

            Tee.log(f"[/api/newiter] Response status: {set_response.status_code}")
            if set_response.status_code != status.HTTP_200_OK:
                Tee.log(f"[/api/newiter] Error response: {set_response.text}")
                return ServerOkayResponse(
                    message="ERROR",
                    db_health={"message": f"Failed to commit entity: {set_response.text}"}
                )
            
            set_data = set_response.json()
            returned_entities = set_data.get('entities', [])


            # Build entity dict from all returned iterations
            entity_dict = {}
            if returned_entities:
                Tee.log(f"[/api/newiter] Returned Ent: {len(returned_entities)}")
                for ent in returned_entities:
                    iter_num = int(ent.get('iter', 0))
                    entity_dict[iter_num] = databases.normalize_entity(ent, _zone)

            # User must be owner of #0 mint
            

            # Determine if this is the latest iteration
            all_iters = [int(ent.get('iter', 0)) for ent in returned_entities] if returned_entities else []
            iter_is_latest = _iter == max(all_iters) if all_iters else True

            # Return complete entity stack with all iterations
            return {
                'message': 'OK',
                'x': _xpos,
                'y': _ypos,
                'z': _zone,
                'entity': entity_dict,
                'intended_iter': _iter,
                'iter_is_latest': iter_is_latest,
                'user_context': user_context,
                'banner': databases.ZONE_COLORS[_zone]
            }
        
    except httpx.ConnectError:
        return ServerOkayResponse(
            message="ERROR",
            db_health={"message": "Database server unreachable"}
        )

@server.post('/api/mint') # Mint applies ownership over entity stack and disables editing.
async def mint_entity(
        request: Request,
        payload: EntityRequest,
        user_context: security.DecryptedToken = Depends(Authorization)
    ):
    """
    Mints an entity (commits to database with ownership).
    Only iteration #0 (genesis) can be minted.
    Ownership is set to the minting user, and further editing is disabled.
    """
    client_host = request.client.host
    if not ratelimits.within_ip_rate_limit(client_ip=client_host, RATE=10, WINDOW=60):
        return ServerOkayResponse(
            message='ERROR',
            db_health={"message": "Rate Limit Exceeded"}
        )
    
    _xpos, _ypos, _zone, _iter = ([int(n) for n in [payload.x_pos, payload.y_pos, payload.zone, payload.iter]])
    
    try:
        async with httpx.AsyncClient() as client:
            # Fetch current entity state from database
            response = await client.post(
                DB_SERVER + "/expandall",
                headers={"X-API-Key": DB_KEY},
                timeout=5.0,
                json={
                    'x': _xpos, 'y': _ypos, 'z': _zone, 'i': _iter
                }
            )

            if response.status_code != status.HTTP_200_OK:
                return ServerOkayResponse(
                    message="ERROR",
                    db_health={"message": f"Failed to fetch entity: {response.status_code}"}
                )

            data = response.json()
            entities = data['entities']

            # Extract existing entity or create genesis
            if entities:
                entity_to_mint = entities[_iter]
            else:
                entity_to_mint = databases.entity_genesis(_xpos, _ypos, _zone)

            # Validate ownership (must be unowned or owned by current user)
            current_owner = entity_to_mint.get('ownership')
            ThrowIf(
                current_owner and current_owner != user_context.ID,
                "You do not own this entity",
                status.HTTP_403_FORBIDDEN
            )

            # Check if already minted
            ThrowIf(
                entity_to_mint.get('minted') == True,
                "Entity is already minted",
                status.HTTP_400_BAD_REQUEST
            )

            # Apply ownership and mint status
            entity_to_mint['ownership'] = user_context.ID
            entity_to_mint['minted'] = True

            if (_iter == 0):
                entity_to_mint["state"] = 1
            
            # Remove UI flag (always remove)
            entity_to_mint.pop('exists', None)
            
            # Only remove index if it's None (new genesis), let db use existing or auto-generate
            if entity_to_mint.get('index') is None:
                entity_to_mint.pop('index', None)
            
            Tee.log(f"[/api/mint] Sending to /set/{_zone}: {entity_to_mint}")

            # Commit to database (without index - db will auto-generate)
            # Ensure required position fields exist for the DB model
            entity_to_mint['positionX'] = int(entity_to_mint.get('positionX', _xpos))
            entity_to_mint['positionY'] = int(entity_to_mint.get('positionY', _ypos))
            entity_to_mint['positionZ'] = int(entity_to_mint.get('positionZ', _zone))

            set_response = await client.post(
                DB_SERVER + f"/set/{_zone}",
                headers={"X-API-Key": DB_KEY},
                timeout=5.0,
                json=entity_to_mint
            )
            
            Tee.log(f"[/api/mint] Response status: {set_response.status_code}")
            if set_response.status_code != status.HTTP_200_OK:
                Tee.log(f"[/api/mint] Error response: {set_response.text}")
                return ServerOkayResponse(
                    message="ERROR",
                    db_health={"message": f"Failed to commit entity: {set_response.text}"}
                )

            # Get response from db_server with full entity stack and index
            set_data = set_response.json()
            returned_entities = set_data.get('entities', [])
            
            Tee.log(f"[/api/mint] set_data keys: {set_data.keys()}")
            Tee.log(f"[/api/mint] returned_entities type: {type(returned_entities)}")
            Tee.log(f"[/api/mint] returned_entities: {returned_entities}")
            
            # Build entity dict from all returned iterations
            entity_dict = {}
            if returned_entities:
                for ent in returned_entities:
                    Tee.log(f"[/api/mint] Processing ent: {ent} (type: {type(ent)})")
                    iter_num = int(ent.get('iter', 0))
                    entity_dict[iter_num] = databases.normalize_entity(ent, _zone)

            # Defensive: ensure the iteration we just minted reports `minted: True` and `exists: True`.
            try:
                if entity_dict and _iter in entity_dict:
                    entity_dict[_iter]['minted'] = True
                    entity_dict[_iter]['exists'] = True
                elif not entity_dict:
                    # Fallback when DB didn't return iterations — ensure payload reflects minted state
                    entity_to_mint['minted'] = True
                    entity_to_mint['exists'] = True
            except Exception:
                pass
            
            # Determine if this is the latest iteration
            all_iters = [int(ent.get('iter', 0)) for ent in returned_entities] if returned_entities else []
            iter_is_latest = _iter == max(all_iters) if all_iters else True

            # Return complete entity stack with all iterations
            return {
                'message': 'OK',
                'x': _xpos,
                'y': _ypos,
                'z': _zone,
                'entity': entity_dict if entity_dict else {_iter: entity_to_mint},
                'intended_iter': _iter,
                'iter_is_latest': iter_is_latest,
                'user_context': user_context,
                'banner': databases.ZONE_COLORS[_zone]
            }

    except httpx.ConnectError:
        return ServerOkayResponse(
            message="ERROR",
            db_health={"message": "Database server unreachable"}
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
    
    _xpos, _ypos, _zone, _iter = ([int(n) for n in [payload.x_pos, payload.y_pos, payload.zone, payload.iter]])

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DB_SERVER + f"/expandall",
                headers={"X-API-Key": DB_KEY},
                timeout=5.0,
                json={
                    'x': _xpos, 'y': _ypos, 'z': _zone, 'i': _iter  # intended_iter
                }
            )

            if response.status_code == status.HTTP_200_OK:

                data = response.json()

                entities = data["entities"]
                
                Tee.log(f"[/api/render/one] entities: {entities}")
                Tee.log(f"[/api/render/one] entities type: {type(entities)}")

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
                    'intended_iter': _iter,
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