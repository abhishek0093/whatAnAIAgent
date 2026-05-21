from __future__ import annotations

import asyncio
import os
from collections import defaultdict

from utils.agentMemory import UserMemory

MEMORY: dict[str, UserMemory] = {}
USER_LOCKS: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

HISTORY_LIMIT = int(os.getenv("MEMORY_HISTORY_LIMIT", "50"))


def get_memory(sender: str) -> UserMemory:
    mem = MEMORY.get(sender)
    if mem is None:
        mem = UserMemory()
        MEMORY[sender] = mem
    return mem


def reset() -> None:
    """For tests: drop all in-memory state."""
    MEMORY.clear()
    USER_LOCKS.clear()
