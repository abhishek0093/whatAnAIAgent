from __future__ import annotations

import asyncio
import logging
import time

import aiosqlite

from utils.agentMemory import UserMemory
from utils import memory_state

SCHEMA = """
CREATE TABLE IF NOT EXISTS user_memory (
    user_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(SCHEMA)
        await db.commit()


async def load_all(db_path: str) -> dict[str, UserMemory]:
    out: dict[str, UserMemory] = {}
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT user_id, payload_json FROM user_memory") as cursor:
            async for user_id, payload in cursor:
                try:
                    out[user_id] = UserMemory.model_validate_json(payload)
                except Exception:
                    logging.exception("Skipping unreadable memory row for %s", user_id)
    return out


async def flush_dirty(db_path: str, memory: dict[str, UserMemory]) -> int:
    dirty_ids = [uid for uid, mem in memory.items() if mem.dirty]
    if not dirty_ids:
        return 0

    now = time.time()
    rows = [(uid, memory[uid].to_persist_json(), now) for uid in dirty_ids]

    async with aiosqlite.connect(db_path) as db:
        await db.executemany(
            "INSERT INTO user_memory(user_id, payload_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at",
            rows,
        )
        await db.commit()

    for uid in dirty_ids:
        memory[uid].dirty = False
    return len(dirty_ids)


async def periodic_flush_task(db_path: str, interval_s: int) -> None:
    while True:
        try:
            await asyncio.sleep(interval_s)
            written = await flush_dirty(db_path, memory_state.MEMORY)
            if written:
                logging.info("flush_dirty wrote %d user(s) to %s", written, db_path)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("periodic_flush_task iteration failed; continuing")
