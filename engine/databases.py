import os
import logging
from pathlib import Path
import json
import time
import asyncio
import anyio
import sqlite3
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Any, Optional

# These are global defaults for longevity of disk
POOL_SIZE      = int(os.getenv("POOL_SIZE", 4))
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", 2.0))
MAX_QUEUE_ROWS = int(os.getenv("MAX_QUEUE_ROWS", 100)) # or 1000
LRU_CACHE_SIZE = int(os.getenv("LRU_CACHE_SIZE", 2048))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("db")

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
    'uuid'       : 'TEXT UNIQUE',          # Master UUID. NOTE: 'uuid' is unique across all versions/iters!
    'state'      : 'INTEGER',              # State is an integer for extra control
    # 'iter' is now part of the primary key in EntityStore.init
    'name'       : 'TEXT',                 # Generic Name Field (sanitized user input)
    'description': 'TEXT',                 # Generic Description Field (sanitized user input)
    
    'positionX'  : 'INTEGER',              # X, Y, Z ...
    'positionY'  : 'INTEGER',
    'positionZ'  : 'INTEGER',
    
    'aesthetics' : 'TEXT',                 # Stringified JSON with address overrides
    'ownership'  : 'TEXT',                 # The Ownership ID
    'minted'     : 'INTEGER',              # Special status
    'timestamp'  : 'INTEGER'               # Long Integer 
}

USERSCHEMA = {
    'uuid'       : 'TEXT UNIQUE',
    'emoji'      : 'TEXT',
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
            
            # main table - CORRECTED SQL generation
            conn.execute(unwrap_kv_to_create_schema(ENTITYSCHEMA, 'entities', index_cols))
            
            # queue table - CORRECTED SQL generation
            conn.execute(unwrap_kv_to_create_schema(ENTITYSCHEMA, 'write_queue', index_cols, is_queue=True))
            
            # Fast lookup by UUID
            conn.execute("CREATE INDEX IF NOT EXISTS idx_uuid ON entities(uuid)")
            # Fast 3D range queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pos ON entities(positionX, positionY, positionZ)")
            # Index for fast retrieval of latest versions
            conn.execute("CREATE INDEX IF NOT EXISTS idx_latest ON entities('index', 'iter' DESC)")
            
            await self._pool.put(conn)
        
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def close(self):
        logger.info("Stopping...")
        self._running = False
        if self._flush_task: await self._flush_task
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
        '''
        sql = """
            SELECT * FROM entities 
            WHERE positionX BETWEEN ? AND ?
              AND positionY BETWEEN ? AND ?
              AND positionZ BETWEEN ? AND ?
            LIMIT ?
        """
        params = (
            bounds['min_x'], bounds['max_x'],
            bounds['min_y'], bounds['max_y'],
            bounds['min_z'], bounds['max_z'],
            bounds.get('limit', 1000)
        )

        async with self._conn() as conn:
            rows = await anyio.to_thread.run_sync(
                lambda: conn.execute(sql, params).fetchall()
            )
        
        return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row: tuple) -> dict:
        """Helper to map tuple -> dict and parse JSON."""
        # Row structure order in DB: index, iter, uuid, state, name, description, 
        # positionX, positionY, positionZ, aesthetics, ownership, minted, timestamp (13 columns)
        try:
            # Aesthetics is at index 9
            aes = json.loads(row[9]) if row[9] else {}
        except:
            aes = row[9] # Fallback

        return {
            "index": row[0],
            "iter": row[1],
            "uuid": row[2],
            "state": row[3],
            "name": row[4],
            "description": row[5],
            "positionX": row[6],
            "positionY": row[7],
            "positionZ": row[8],
            "aesthetics": aes,
            "ownership": row[10],
            "minted": bool(row[11]),
            "timestamp": row[12]
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

        # Enqueue - CORRECTED to include 'iter' column and placeholder
        async with self._conn() as conn:
            await anyio.to_thread.run_sync(
                conn.execute,
                """
                INSERT INTO write_queue (
                    'index', 'iter', uuid, state, name, description,
                    positionX, positionY, positionZ,
                    aesthetics, ownership, minted, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    db_row['index'], db_row['iter'], db_row['uuid'], db_row['state'], db_row['name'], db_row['description'],
                    db_row['positionX'], db_row['positionY'], db_row['positionZ'],
                    db_row['aesthetics'], db_row['ownership'], int(db_row['minted']), db_row['timestamp']
                )
            )

        self.writes += 1
        self.queue_depth += 1
        if self.queue_depth >= MAX_QUEUE_ROWS:
            await self._flush()

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
                    # Batch fetch
                    rows = conn.execute(
                        "SELECT * FROM write_queue ORDER BY queue_id LIMIT ?",
                        (MAX_QUEUE_ROWS * 2,)
                    ).fetchall()

                    if not rows: return 0

                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        # Insert/Replace into main table - CORRECTED to include 'iter'
                        # Note: rows in write_queue have queue_id at index 0. 
                        # We pass row[1:] (13 elements: index, iter, uuid, ...) to match entity table columns.
                        data_tuples = [r[1:] for r in rows]
                        
                        conn.executemany("""
                            INSERT OR REPLACE INTO entities (
                                'index', 'iter', uuid, state, name, description, 
                                positionX, positionY, positionZ, 
                                aesthetics, ownership, minted, timestamp
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, data_tuples)

                        # Clean queue
                        ids = [(r[0],) for r in rows]
                        conn.executemany("DELETE FROM write_queue WHERE queue_id=?", ids)
                        
                        conn.execute("COMMIT")
                        if self.flushes % 20 == 0:
                            conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
                        return len(rows)
                    except Exception as e:
                        conn.execute("ROLLBACK")
                        logger.error(f"Flush failed: {e}")
                        raise e
                    
                count = await anyio.to_thread.run_sync(_do_flush)
                if count > 0:
                    self.flushes += 1
                    self.queue_depth = max(0, self.queue_depth - count)