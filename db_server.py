from __future__ import annotations

# internal
from engine import jsonsafe, verbose, versioning, security, validation, databases

import sqlite3
import asyncio
import os, json, enum, inspect, subprocess, uuid, threading, time, base64

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

# NOTE : Each "zone" will have a default aesthetic map with deterministic randomness.
ZONES = {
    i : databases.EntityStore(
        ExtendToParentResource('db', f'zone{i}.sqlite'), databases.POOL_SIZE) 
        for i in databases.ZONE_INTEGER
}

db_path = ExtendToParentResource('db')
if not db_path.exists():
    db_path.mkdir(parents=True, exist_ok=True)

key_storage_file = ExtendToParentResource('engine', 'key.json')  # Where the private decryption key is stored

class HelloResponse(BaseModel):
    data : list
    days_old : int
    ID : str

class EntityIn(BaseModel):
    index: Optional[int] = Field(None, description="Entity Unique (auto-generated if not provided)")
    iter: int = Field(..., description="Version Iteration Number")
    uuid: str
    state: int
    name: str
    description: str = ""
    positionX: int
    positionY: int
    positionZ: int
    aesthetics: Dict[str, Any] | str = Field(default_factory=dict, description="JSON object or string")
    ownership: str
    minted: bool
    timestamp: float

class RangeQuery(BaseModel):
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    limit: int = 1000

class DBEntityRequest(BaseModel):
    x: int
    y: int
    z: int
    i: int

@asynccontextmanager
async def lifespan(server: FastAPI):
    global ZONES
    for store in ZONES.values():
        await store.init()
    yield
    for store in ZONES.values():
        await store.close()

server = FastAPI(title='Database Server', version=versioning.distribution_version, lifespan=lifespan)
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

# Entity Routes ───────────────────────────

@server.get("/get_max_index/{zone}", dependencies=[Depends(Authorization)])
async def get_max_index(zone: int):
    """Get the highest index number in a zone to auto-generate next index."""
    global ZONES
    ThrowIf(zone not in ZONES, f"Invalid zone ID: {zone}", status.HTTP_400_BAD_REQUEST)
    
    store = ZONES[zone]
    # Query database for max index in this zone
    async with store._conn() as conn:
        cursor = await anyio.to_thread.run_sync(
            conn.execute,
            'SELECT MAX("index") FROM entities'
        )
        row = cursor.fetchone()
        max_index = row[0] if row and row[0] is not None else 0
    
    return {"max_index": max_index}

@server.post("/set/{zone}", dependencies=[Depends(Authorization)])
async def set_entity(zone: int, entity: EntityIn):
    """Upsert an entity version into a specific zone."""
    global ZONES
    ThrowIf(zone not in ZONES, f"Invalid zone ID: {zone}", status.HTTP_400_BAD_REQUEST)
    
    store = ZONES[zone]
    entity_dict = entity.model_dump()
    
    Tee.log(f"[/set/{zone}] Received entity: {entity_dict}")
    
    # Auto-generate index if not provided
    if entity_dict['index'] is None:
        async with store._conn() as conn:
            cursor = await anyio.to_thread.run_sync(
                conn.execute,
                'SELECT MAX("index") FROM entities'
            )
            row = cursor.fetchone()
            max_index = row[0] if row and row[0] is not None else 0
            entity_dict['index'] = max_index + 1
        Tee.log(f"[/set/{zone}] Auto-generated index: {entity_dict['index']}")
    
    await store.set(entity_dict)
    
    # Fetch and return the full entity stack for this index
    all_iterations = await store.get_iters_of_one(
        entity_dict['positionX'],
        entity_dict['positionY'],
        entity_dict['iter']
    )
    
    response_data = {
        "status": "ok",
        "id": f"{entity_dict['index']}v{entity_dict['iter']}",
        "index": entity_dict['index'],
        "entities": all_iterations.get('entities', []),
        "is_latest_on_file": all_iterations.get('is_latest_on_file', False)
    }
    Tee.log(f"[/set/{zone}] Returning {len(all_iterations.get('entities', []))} entities")
    return response_data

# NOTE : Might be a good idea to call the "whole" group with all iters, not currently implemented

@server.get("/get/{zone}/{index}", dependencies=[Depends(Authorization)])
async def get_latest_entity(zone: int, index: int):
    """Get the highest iteration (latest version) for a given index in a zone."""
    global ZONES
    ThrowIf(zone not in ZONES, f"Invalid zone ID: {zone}", status.HTTP_400_BAD_REQUEST)

    store = ZONES[zone]
    ent = await store.get(index)
    if not ent:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ent

@server.post("/expandall", dependencies=[Depends(Authorization)])
async def get_all_at_location(payload: DBEntityRequest):
    global ZONES
    ThrowIf(payload.z not in ZONES, f"Invalid zone ID: {payload.z}", status.HTTP_400_BAD_REQUEST)

    store = ZONES[payload.z]

    return await store.get_iters_of_one(
        payload.x, 
        payload.y
    )

# This is more useful for time-based requests.
@server.post("/expand", dependencies=[Depends(Authorization)])
async def get_specific_location(payload: DBEntityRequest):
    global ZONES
    ThrowIf(payload.z not in ZONES, f"Invalid zone ID: {payload.z}", status.HTTP_400_BAD_REQUEST)

    store = ZONES[payload.z]

    return await store.get_iters_of_one(
        payload.x, 
        payload.y, 
        payload.i#+1 
        # NOTE : If iter is lower (0) -> max is 0,
        # should have another db function: Is latest iter? bool.
        # This may change in the future, due to this note.
    )

@server.get("/get/{zone}/{index}/{iter}", dependencies=[Depends(Authorization)])
async def get_specific_version(zone: int, index: int, iter: int):
    """Get a specific iteration of an entity in a zone."""
    global ZONES
    ThrowIf(zone not in ZONES, f"Invalid zone ID: {zone}", status.HTTP_400_BAD_REQUEST)

    store = ZONES[zone]
    ent = await store.get(index, iter)
    if not ent:
        raise HTTPException(status_code=404, detail=f"Entity version {index}v{iter} not found")
    return ent

@server.post("/range/{zone}", dependencies=[Depends(Authorization)])
async def query_range(zone: int, query: RangeQuery):
    """Query for entities within a 3D bounding box in a specific zone."""
    global ZONES
    ThrowIf(zone not in ZONES, f"Invalid zone ID: {zone}", status.HTTP_400_BAD_REQUEST)

    store = ZONES[zone]
    return await store.range_query(query.model_dump())

# Health and Auth Routes ───────────────────────────

@server.get("/hello", response_model=HelloResponse)
def server_hello(decrypted_token: security.DecryptedToken = Depends(Authorization)):
    return HelloResponse(
        data=jsonsafe.JSONSafe(decrypted_token.data), 
        days_old=decrypted_token.days_old, 
        ID=decrypted_token.ID
    )

@server.get("/health", dependencies=[Depends(Authorization)])
async def health():
    """Get metrics for all zones."""
    global ZONES
    return {i : store.metrics for i, store in ZONES.items()}

@server.get("/health/{zone}", dependencies=[Depends(Authorization)])
async def zone_health(zone: int):
    """Get metrics for a specific zone."""
    global ZONES
    ThrowIf(zone not in ZONES, f"Invalid zone ID: {zone}", status.HTTP_400_BAD_REQUEST)
    
    store = ZONES[zone]
    return store.metrics

if __name__ == "__main__":
    import uvicorn
    # Use loop="asyncio" to prevent uvloop conflicts with generic thread pools if needed
    uvicorn.run(server, host="0.0.0.0", port=9401, workers=1, loop="asyncio")