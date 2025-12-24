import os
import logging
from pathlib import Path
import json
import contextlib
import uuid
import random
import time
from datetime import datetime, timezone
import signal
import hashlib
import asyncio
import anyio
import sqlite3
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Any, Optional
import threading
from typing import NewType, Any, Union
import atexit

DiscordUserID = NewType('DiscordUserID', str)
'''For ID component of `'user:00000...'`'''

# These are global defaults for longevity of disk
POOL_SIZE      = int(os.getenv("POOL_SIZE", 4))
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", 2.0))
MAX_QUEUE_ROWS = int(os.getenv("MAX_QUEUE_ROWS", 100)) # or 1000
LRU_CACHE_SIZE = int(os.getenv("LRU_CACHE_SIZE", 2048))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("db")

ReadableTS = lambda ts : datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

ZONE_INTEGER = list(range(0, 8))
'''List int of Database, where last integer is n zones.'''

ZONE_COLORS = {
    0 : [
        '#7489c9',        '#74c9c5',        '#74bcc9',        '#74abc9',
        '#749ac9',        '#7489c9',        '#7478c9',        '#8174c9',
        '#9274c9',        '#a374c9'
    ],
    1 : [
        '#d74a49',        '#183e4b',        '#1a424f',        '#294f5b',
        '#375c67',        '#53737b',        '#6f8a90',        '#8ba0a4',
        '#bbc5c7',        '#eaeaea'
    ],
    2 : [
        '#c0decc',        '#9ccbad',        '#77b88f',        '#53a675',
        '#34b768',        '#4d9a6c',        '#3ba364',        '#478e64',
        '#3f905f',        '#41825b'
    ],
    3 : [
        '#732ff6',        '#7657eb',        '#7972df',        '#7e89d2',
        '#849dc4',        '#8bb1b3',        '#93c3a0',        '#9cd488',
        '#a5e569',        '#aff631'
    ],
    4 : [
        '#e6d1a8',        '#e6cb92',        '#e6c47c',        '#e0ba6a',
        '#d7ae5b',        '#cea34c',        '#c5983c',        '#ba8e32',
        '#ab8538',        '#9c7c3c',        '#8c6c30'
    ],
    5 : [
        '#1F1A2B',        '#211735',        '#250F46',
        '#362A55',        '#4F3A87',        '#5828A6',
        '#5F10B8',        '#7434E0',        '#782AEA',
        '#7C17F4'
    ],
    6 : [
        '#3C0325',        '#5F1036',        '#8B1742', 
        '#BC1756',        '#E62D6A',        '#FF417F',
        '#FF6E97',        '#FFA9B8',        '#FFD3D9'
    ],
    7 : [
        '#98dadb',        '#98c8e5',        '#98b6ee',        '#a5ade7',
        '#bdadd1',        '#d4acba',        '#e6a48f',        '#dfc090',
        '#d5db90',        '#c2dea3',        '#accac3'
    ]
}

ZONE_GLYPH_TABLES = {
    'birds': [
        '𓄿','𓅀','𓅱','𓅷','𓅾','𓅟','𓅮','𓅙','𓅰','𓅚',
        '𓅞','𓅪','𓅜','𓅛','𓅘','𓅓','𓅔','𓅃','𓅂'
    ],
    'sea': [
        '𓆛','𓆜','𓆝','𓆞','𓆟','𓆡','𓆠','𓅻','𓈖','𓆢'
    ],
    'jackals': [
        '𓃢','𓃦','𓃥','𓃣','𓁢','𓃤','𓃧','𓃨'
    ],
    'misc': [
        '𓇌','𓆝','𓍝','𓇋','𓃣','𓍚','𓏢','𓐤','𓌬','𓆣','𓆥',
        '𓆗','𓆏','𓆋','𓄇','𓃕','𓆉','𓅱'
    ],
    'reptiles': [
        '𓆈','𓆉','𓆊','𓆌','𓆏','𓆇','𓆑','𓆓','𓆗','𓆙',
        '𓆚','𓆘'
    ],
    'deities': [
        '𓁛','𓁠','𓁦','𓁥','𓁮','𓁭','𓁤','𓁩','𓁳','𓁴','𓁧','𓁨',
        '𓁱','𓁣','𓁚','𓁫','𓁟','𓁢','𓁵','𓁜'
    ],
        
}

ZONE_GLYPHS = {
    0 : [
        *ZONE_GLYPH_TABLES['birds']
    ],
    1 : [
        *ZONE_GLYPH_TABLES['jackals'],
        *ZONE_GLYPH_TABLES['sea']
    ],
    2 : [
        *ZONE_GLYPH_TABLES['reptiles'],
        *ZONE_GLYPH_TABLES['sea'],
    ],
    3 : [
        *ZONE_GLYPH_TABLES['misc']
    ],
    4 : [
        *ZONE_GLYPH_TABLES['jackals'],
        *ZONE_GLYPH_TABLES['deities']
    ],
    5 : [
        *ZONE_GLYPH_TABLES['jackals'],
        *ZONE_GLYPH_TABLES['reptiles']
    ],
    6 : [
        *ZONE_GLYPH_TABLES['sea'],
        *ZONE_GLYPH_TABLES['birds'],
        *ZONE_GLYPH_TABLES['deities']
    ],
    7 : [
        *ZONE_GLYPH_TABLES['misc'],
        *ZONE_GLYPH_TABLES['reptiles']
    ]
}


def _deterministic_rng(*parts) -> random.Random:
    key = ":".join(map(str, parts))
    seed = int(hashlib.sha256(key.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)

def DeterministicAesthetic(
        x:int,
        y:int,
        z:int
    ) -> dict:

    rng = _deterministic_rng(x, y, z)
    # rng.randint(0,3), rng.choice([1,2,3]), noise=rng.random()
    
    # TODO : Hieroglyphs
    return {
        'bar' : {
            f'channel_{i}' : rng.choice(ZONE_COLORS[z])
            for i in list(range(0,8))
        },
        'glyphs' : {
            f'glyph_{i}' : rng.choice(ZONE_GLYPHS[z])
            for i in list(range(0, 8))
        }
    }

def unwrap_kv_to_create_schema(
        kv:dict, 
        table_name:str, 
        index_cols:dict={
            "'index'" : 'INTEGER NOT NULL',  
            "'iter'" : 'INTEGER NOT NULL',
        }, 
        is_queue:bool=False
    ):
    schema_indent = ' '*8
    
    init_lines = [f'CREATE TABLE IF NOT EXISTS {table_name} (']
    
    # 1. Handle queue_id for the write buffer
    if is_queue:
        init_lines.append(f'{schema_indent}queue_id INTEGER PRIMARY KEY AUTOINCREMENT,')

    # 2. Add Index Columns (e.g., 'index', 'iter')
    # All lines here get a trailing comma
    init_lines.extend([f'{schema_indent}{k} {v},' for k,v in index_cols.items()])

    # 3. Add the remaining schema fields (e.g., uuid, state, aesthetics)
    data_lines = [f'{schema_indent}{k} {v},' for k,v in kv.items()]
    init_lines.extend(data_lines)

    # 4. Handle the PRIMARY KEY constraint (Main table only)
    if not is_queue:
        # A. Remove the comma from the *last* data line to make it the final column definition
        init_lines[-1] = init_lines[-1].rstrip(',') 

        # B. Append the PRIMARY KEY definition, ensuring it is preceded by a comma (required by SQLite)
        init_lines.append(f'{schema_indent}, PRIMARY KEY (\'index\', \'iter\')')
    else:
        # For the queue table, just clean the trailing comma off the final column
        init_lines[-1] = init_lines[-1].rstrip(',')

    init_lines.append(')')

    return '\n'.join(init_lines)

ENTITYSCHEMA = {
    'uuid'       : 'TEXT',                 # NOTE: Removed UNIQUE to allow multiple versions/iters in history
    'state'      : 'INTEGER',              # State is an integer for extra control
    # 'iter' is now part of the primary key in EntityStore.init
    'name'       : 'TEXT',                 # Generic Name Field (sanitized user input)
    'description': 'TEXT',                 # Generic Description Field (sanitized user input)
    
    'positionX'  : 'INTEGER',              # X, Y ...
    'positionY'  : 'INTEGER',
    #'positionZ'  : 'INTEGER',
    
    'aesthetics' : 'TEXT',                 # Stringified JSON with address overrides
    'ownership'  : 'TEXT',                 # The Ownership ID
    'minted'     : 'INTEGER',              # Special status
    'timestamp'  : 'INTEGER'               # Long Integer 
}

USERSCHEMA = {
    'uuid'       : 'TEXT UNIQUE',
    'emoji'      : 'TEXT',
}

class Blacklist:
    # Expected to be low-write
    def __init__(
            self,
            path: Path    
        ):

        self.path = path
        self.name = path.name
        self.lock = threading.RLock()
        self.cache: dict[str, dict[str, float | str]] = self.read_file()
        self._banned_cache: set[str] = set(['user:'+k for k in self.cache])
        self.queue = 0
        self.register_shutdown_hooks()

    @property
    def banned_ids(self) -> set[str]:
        return self._banned_cache

    def read_file(self):
        if not self.path.exists():
            return {}
        try:
            with self.lock:
                with self.path.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
        
    def add_entry(self, user_id: DiscordUserID):
        with self.lock:
            self.cache[str(user_id)] = {
                "user": str(user_id),
                "added_at": time.time()
            }
            self._banned_cache.add(f"user:{user_id}")

            self.queue += 1

            if self.queue >= 100:
                self.flush()

        return
    
    def flush(self):
        with self.lock:
            if not self.cache:
                return

            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=4)

            tmp.replace(self.path)
            self.queue = 0

    def _shutdown_handler(self, signum=None, frame=None):
        self.flush()

    def register_shutdown_hooks(self):
        atexit.register(self.flush)

        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, self._shutdown_handler)

def normalize_entity(ent: dict) -> dict:
    '''Adds exists to entity dict outputs'''
    ent["exists"] = True
    return ent

def entity_genesis(
        x: int, 
        y: int,
        z: int  # zone integer
    ) -> dict:
    return {
        "index": None,
        "iter": 0,
        "uuid": str(
            uuid.UUID(
                int=_deterministic_rng(x,y,z).getrandbits(128), 
                version=4
            )
        ),
        "state": 0,
        "name": "Void",
        "description": "Genesis",
        "positionX": x,
        "positionY": y,
        "aesthetics": DeterministicAesthetic(x, y, z),
        "ownership": None,
        "minted": False,
        "timestamp": time.time(),
        "exists": False,
    }

class BaseStore:
    def __init__(
            self,
            path: Path,
            pool_size: int = POOL_SIZE
        ):

        self.path = path
        self.name = path.name
        self.pool_size = pool_size

        self._pool: asyncio.Queue[sqlite3.Connection] = asyncio.Queue()
        self._write_lock = anyio.Lock()
        self._running = False
        self._flush_task: asyncio.Task | None = None

        # Read-throough LRU cache. Key: "index:iter"
        self._cache: OrderedDict[str, Any] = OrderedDict()
        
        # Metrics
        self.started      = time.time()
        self.flushes      = 0
        self.writes       = 0
        self.cache_hits   = 0
        self.cache_misses = 0
        self.queue_depth  = 0

    @property
    def metrics(self):
        return {
            'started': self.started,
            'flushes': self.flushes,
            'writes': self.writes,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'queue_depth': self.queue_depth
        }

class EntityStore(BaseStore):
    def __init__(
            self, 
            path: Path,
            pool_size: int = POOL_SIZE
        ):
        super().__init__(path, pool_size) # __init>

    async def init(self):
        global ENTITYSCHEMA
        if self._running:
            return
        
        logger.info(f"Initializing DB at {str(self.path.resolve())} with pool size {self.pool_size}")

        index_cols = {"'index'": 'INTEGER NOT NULL', "'iter'": 'INTEGER NOT NULL'}

        for _ in range(self.pool_size):
            conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
                isolation_level=None
            )
            # Performance Optimizations
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            conn.execute("PRAGMA mmap_size=30000000000;")
            
            # main table
            conn.execute(unwrap_kv_to_create_schema(ENTITYSCHEMA, 'entities', index_cols))
            
            # queue table
            conn.execute(unwrap_kv_to_create_schema(ENTITYSCHEMA, 'write_queue', index_cols, is_queue=True))
            
            # Fast lookup by UUID
            conn.execute("CREATE INDEX IF NOT EXISTS idx_uuid ON entities(uuid)")
            # Fast 2D spatial queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pos ON entities(positionX, positionY)")
            # Index for fast retrieval of latest versions
            conn.execute("CREATE INDEX IF NOT EXISTS idx_latest ON entities('index', 'iter' DESC)")
            
            await self._pool.put(conn)
        
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def close(self):
        logger.info("Stopping...")
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
        await self._flush(force=True)
        while not self._pool.empty():
            (await self._pool.get()).close()

    @asynccontextmanager
    async def _conn(self):
        conn = await self._pool.get()
        try:
            yield conn
        finally:
            await self._pool.put(conn)

    async def range_query(self, bounds: dict):
        '''
        >>> bounds = { 'min_x': 0, 'max_x': 100, ... }
        Returns the LATEST (max iter) version for every entity within bounds.
        '''
        sql = """
            SELECT e.*
            FROM entities e
            JOIN (
                SELECT "index", MAX("iter") AS max_iter
                FROM entities
                WHERE positionX BETWEEN ? AND ?
                AND positionY BETWEEN ? AND ?
                GROUP BY "index"
            ) latest
            ON e."index" = latest."index"
            AND e."iter" = latest.max_iter
            LIMIT ?
        """
        params = (
            bounds['min_x'], bounds['max_x'],
            bounds['min_y'], bounds['max_y'],
            bounds.get('limit', 8*8)
        )

        async with self._conn() as conn:
            rows = await anyio.to_thread.run_sync(
                lambda: conn.execute(sql, params).fetchall()
            )
        
        return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row: tuple) -> dict:
        """Helper to map tuple -> dict and parse JSON."""
        # Order: index(0), iter(1), uuid(2), state(3), name(4), description(5), 
        # positionX(6), positionY(7), aesthetics(8), ownership(9), minted(10), timestamp(11)
        try:
            # Aesthetics is at index 8 now
            aes = json.loads(row[8]) if row[8] else {}
        except json.JSONDecodeError:
            aes = {} # Fallback

        return {
            "index": row[0],
            "iter": row[1],
            "uuid": row[2],
            "state": row[3],
            "name": row[4],
            "description": row[5],
            "positionX": row[6],
            "positionY": row[7],
            "aesthetics": aes,
            "ownership": row[9],
            "minted": bool(row[10]),
            "timestamp": row[11]
        }

    # CRUD Operations ───────────────────────────
    async def set(self, data: dict):
        '''
        Upsert a specific version (index + iter).
        '''
        # Update the Cache. Key: "index:iter"
        idx = data['index']
        iteration = data['iter']
        cache_key = f"{idx}:{iteration}"

        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
        self._cache[cache_key] = data
        if len(self._cache) > LRU_CACHE_SIZE:
            self._cache.popitem(last=False)
        
        # Serialize JSON fields to DB
        db_row = data.copy()
        if isinstance(db_row.get('aesthetics'), (dict, list)):
            db_row['aesthetics'] = json.dumps(db_row['aesthetics'])

        # Enqueue - UPDATED placeholders to 12
        async with self._conn() as conn:
            await anyio.to_thread.run_sync(
                conn.execute,
                """
                INSERT INTO write_queue (
                    'index', 'iter', uuid, state, name, description,
                    positionX, positionY,
                    aesthetics, ownership, minted, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    db_row['index'], db_row['iter'], db_row['uuid'], db_row['state'], db_row['name'], db_row['description'],
                    db_row['positionX'], db_row['positionY'],
                    db_row['aesthetics'], db_row['ownership'], int(db_row['minted']), db_row['timestamp']
                )
            )

        self.writes += 1
        self.queue_depth += 1
        # Normal flush threshold
        if self.queue_depth >= MAX_QUEUE_ROWS:
            await self._flush()

        # Hard backpressure cap (safety valve)
        elif self.queue_depth > MAX_QUEUE_ROWS * 10:
            logger.warning(
                f"Write queue overloaded ({self.queue_depth}), forcing flush"
            )
            await self._flush(force=True)

    async def get(self, index: int, iteration: Optional[int] = None) -> Optional[dict]:
        '''
        If iteration is None: Returns the LATEST (highest iter) version.
        If iteration is set: Returns that specific version.
        '''
        cache_key = f"{index}:{iteration}" if iteration is not None else None

        # 1. Cache Hit
        if cache_key and cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            self.cache_hits += 1
            return self._cache[cache_key]
        
        self.cache_misses += 1

        # DB (Check Queue then Table)
        async with self._conn() as conn:
            def _fetch():
                query_suffix = ""
                params = []
                
                if iteration is not None:
                    query_suffix = "WHERE 'index'=? AND 'iter'=?"
                    params = (index, iteration)
                else:
                    # Get the LATEST version for this index
                    query_suffix = "WHERE 'index'=? ORDER BY 'iter' DESC LIMIT 1"
                    params = (index,)

                # Check Queue First (newest version)
                cur = conn.execute(f"SELECT * FROM write_queue {query_suffix}", params)
                row = cur.fetchone()
                if row:
                    # Queue table has 'queue_id' at index 0, real data starts at 1
                    return self._row_to_dict(row[1:])
                
                # Check Main Table
                cur = conn.execute(f"SELECT * FROM entities {query_suffix}", params)
                row = cur.fetchone()
                return self._row_to_dict(row) if row else None
            
            result = await anyio.to_thread.run_sync(_fetch)

        if result:
            # Cache the specific version found
            found_key = f"{result['index']}:{result['iter']}"
            self._cache[found_key] = result
        return result

    # Background Flush ──────────────────────────
    async def _flush_loop(self):
        while self._running:
            try:
                await asyncio.sleep(FLUSH_INTERVAL)
                if self.queue_depth > 0:
                    await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush loop error: {e}")

    async def _flush(self, force: bool = False):
        async with self._write_lock:
            async with self._conn() as conn:

                def _do_flush():
                    # Dynamic batch sizing
                    if force:
                        batch_limit = MAX_QUEUE_ROWS * 10
                    else:
                        batch_limit = MAX_QUEUE_ROWS * 2

                    total_flushed = 0

                    while True:
                        rows = conn.execute(
                            "SELECT * FROM write_queue ORDER BY queue_id LIMIT ?",
                            (batch_limit,)
                        ).fetchall()

                        if not rows:
                            break

                        conn.execute("BEGIN IMMEDIATE")
                        try:
                            data_tuples = [r[1:] for r in rows]  # strip queue_id

                            conn.executemany("""
                                INSERT OR REPLACE INTO entities (
                                    'index', 'iter', uuid, state, name, description,
                                    positionX, positionY,
                                    aesthetics, ownership, minted, timestamp
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, data_tuples)

                            ids = [(r[0],) for r in rows]
                            conn.executemany(
                                "DELETE FROM write_queue WHERE queue_id=?",
                                ids
                            )

                            conn.execute("COMMIT")
                            total_flushed += len(rows)

                            # WAL hygiene
                            if self.flushes % 20 == 0:
                                conn.execute("PRAGMA wal_checkpoint(PASSIVE);")

                            # Normal flush exits after one batch
                            if not force:
                                break

                            # If force flushing but we didn't fill the batch,
                            # the queue is effectively drained
                            if len(rows) < batch_limit:
                                break

                        except Exception as e:
                            conn.execute("ROLLBACK")
                            logger.error(f"Flush failed: {e}")
                            raise

                    return total_flushed

                flushed = await anyio.to_thread.run_sync(_do_flush)

                if flushed > 0:
                    self.flushes += 1
                    self.queue_depth = conn.execute(
                        "SELECT COUNT(*) FROM write_queue"
                    ).fetchone()[0]

                    if force:
                        logger.warning(
                            f"Forced flush completed, flushed={flushed}, remaining={self.queue_depth}"
                        )
