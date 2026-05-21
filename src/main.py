import asyncio
import contextlib
import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langchain_google_genai import ChatGoogleGenerativeAI

from agent import graph as agent_graph
from routers import getMessage, postMessage
from models import process_requests
from utils import memory_state, persistence


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_path = os.getenv("MEMORY_DB_PATH", "./memory.sqlite")
    flush_interval = int(os.getenv("MEMORY_FLUSH_INTERVAL_SECONDS", "60"))

    await persistence.init_db(db_path)
    loaded = await persistence.load_all(db_path)
    memory_state.MEMORY.update(loaded)

    model = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        temperature=1.0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        thinking_level="low",
    )
    process_requests.set_model(model)
    process_requests.set_agent(agent_graph.build_agent(model))

    flush_task = asyncio.create_task(persistence.periodic_flush_task(db_path, flush_interval))

    try:
        yield
    finally:
        flush_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await flush_task
        await persistence.flush_dirty(db_path, memory_state.MEMORY)


app = FastAPI(lifespan=lifespan)
app.include_router(getMessage.router)
app.include_router(postMessage.router)


if __name__ == "__main__":
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=int(os.environ["SERVICE_PORT"]),
        timeout_keep_alive=30,
        reload=True,
    )
