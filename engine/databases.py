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
        index:dict={
            "'index'" : 'INTEGER PRIMARY KEY',  # Master Entity Key, queue is INTEGER NOT NULL
        }, 
        is_queue:bool=False
    ):
    schema_indent = ' '*8
    
    init_lines = [f'CREATE TABLE IF NOT EXISTS {table_name} (']

    if is_queue:
        init_lines.append('queue_id INTEGER PRIMARY KEY AUTOINCREMENT')

    init_lines.append(f'{schema_indent}{k} {v}' for k,v in index.items())

    sqlcommand = (
        init_lines + [f'{schema_indent}{k} {v}' for k,v in kv.items()] + [')']
    )

    return '\n'.join(sqlcommand)

ENTITYSCHEMA = {
    # "'index'" : (Updated Dynamically; INTEGER PRIMARY KEY)
    'uuid'       : 'TEXT UNIQUE',          # Master UUID
    'state'      : 'INTEGER',              # State is an integer for extra control
    'iter'       : 'INTEGER',              # Iter is the iteration number of the location for history traceback
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
    # "'index'" : (Updated Dynamically; INTEGER PRIMARY KEY)
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

        # Read-throough LRU cache
        self._cache = OrderedDict[str, Any] = OrderedDict()
        
        # Metrics
        self.started      = time.time()
        self.flushes      = 0
        self.writes       = 0
        self.cache_hits   = 0
        self.cache_misses = 0
        self.queue_depth  = 0

        pass

class EntityStore(BaseStore):
    def __init__(
            self, 
            path: Path,
            pool_size: int = POOL_SIZE
        ):
        super().__init__(path, pool_size)

    async def init(self):
        global ENTITYSCHEMA
        if self._running:
            return
        
        logger.info(f"Initializing DB at {str(self.path.resolve())} with pool size {self.pool_size}")

        for _ in range(self.pool_size):
            conn = sqlite3.connect(
                self.path,
                check_same_thread=False,  # Required for anyio thread pool usage
                isolation_level=None      # Autocommit mode (we manage tx manually)
            )
            # Performance Optimizations
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            conn.execute("PRAGMA mmap_size=30000000000;") # Memory map up to ~30GB
            
            # main table
            conn.execute(unwrap_kv_to_create_schema(ENTITYSCHEMA, 'entities'))
            
            # queue table
            conn.execute(unwrap_kv_to_create_schema(ENTITYSCHEMA, 'write_queue', {"'index'": 'INTEGER NOT NULL'}))
            
            # Fast lookup by UUID
            conn.execute("CREATE INDEX IF NOT EXISTS idx_uuid ON entities(uuid)")
            # Fast 3D range queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pos ON entities(positionX, positionY, positionZ)")
            
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
        # row structure matches 'entities' table columns order
        # 0: index, 1: uuid, 2: state, 3: name, 4: desc, 5: X, 6: Y, 7: Z, 8: aes, 9: owner, 10: minted, 11: ts
        try:
            aes = json.loads(row[8]) if row[8] else {}
        except:
            aes = row[8] # Fallback

        return {
            "index": row[0],
            "uuid": row[1],
            "state": row[2],
            "name": row[3],
            "description": row[4],
            "positionX": row[5],
            "positionY": row[6],
            "positionZ": row[7],
            "aesthetics": aes,
            "ownership": row[9],
            "minted": bool(row[10]),
            "timestamp": row[11]
        }

    # CRUD Operations ───────────────────────────
    async def set(self, data: dict):
        '''
        Upsert an entity.
        Data must contain 'index' as the Primary Key.
        '''
        # Update the Cache
        idx = data['index']
        if idx in self._cache:
            self._cache.move_to_end(idx)
        self._cache[idx] = data
        if len(self._cache) > LRU_CACHE_SIZE:
            self._cache.popitem(last=False)
        
        # Serialize JSON fields to DB
        # Shallow copy to safely stringify 'aesthetics' without breaking the cached dict
        db_row = data.copy()
        if isinstance(db_row.get('aesthetics'), (dict, list)):
            db_row['aesthetics'] = json.dumps(db_row['aesthetics'])

        # Enqueue
        async with self._conn() as conn:
            await anyio.to_thread.run_sync(
                conn.execute,
                """
                INSERT INTO write_queue (
                    'index', uuid, state, name, description,
                    positionX, positionY, positionZ,
                    aesthetics, ownership, minted, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    db_row['index'], db_row['uuid'], db_row['state'], db_row['name'], db_row['description'],
                    db_row['positionX'], db_row['positionY'], db_row['positionZ'],
                    db_row['aesthetics'], db_row['ownership'], int(db_row['minted']), db_row['timestamp']
                )
            )

        self.writes += 1
        self.queue_depth += 1
        if self.queue_depth >= MAX_QUEUE_ROWS:
            await self._flush()

    async def get(self, index: int) -> Optional[dict]:

        # 1. Cache
        if index in self._cache:
            self._cache.move_to_end(index)
            self.cache_hits += 1
            return self._cache[index]
        
        self.cache_misses += 1

        # DB (Check Queue then Table)
        async with self._conn() as conn:
            def _fetch():
                # Check Queue First (newest version)
                cur = conn.execute(
                    "SELECT * FROM write_queue WHERE 'index'=? ORDER BY queue_id DESC LIMIT 1",
                    (index,)
                )
                row = cur.fetchone()
                if row:
                    # queue_id is col 0, we slice it off to match schema or map manually. 
                    # Queue table has 'queue_id' at index 0, so real data starts at 1
                    return self._row_to_dict(row[1:])
                
                # Check Main Table
                cur = conn.execute("SELECT * FROM entities WHERE 'index'=?", (index,))
                row = cur.fetchone()
                return self._row_to_dict(row) if row else None
            
            result = await anyio.to_thread.run_sync(_fetch)

        if result:
            self._cache[index] = result
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
                        # Insert/Replace into main table
                        # Note: rows in write_queue have queue_id at index 0. 
                        # We pass row[1:] to match entity table columns.
                        data_tuples = [r[1:] for r in rows]
                        
                        conn.executemany("""
                            INSERT OR REPLACE INTO entities (
                                'index', uuid, state, name, description, 
                                positionX, positionY, positionZ, 
                                aesthetics, ownership, minted, timestamp
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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