from __future__ import annotations

import logging
import os
import time

import requests
from langchain_core.messages import AIMessage, HumanMessage

from agent import graph as agent_graph
from utils import memory_state
from utils.agentMemory import (
    ExtractedMemory,
    HistoryEntry,
    append_note,
    merge_profile,
    render_extractor_prompt,
    render_system_prompt,
)

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

model = None
agent = None


def set_model(m):
    global model
    model = m


def set_agent(a):
    global agent
    agent = a


def _history_to_messages(history: list[HistoryEntry]) -> list:
    out = []
    for h in history:
        if h.role == "human":
            out.append(HumanMessage(h.content))
        else:
            out.append(AIMessage(h.content))
    return out


async def process_message(sender: str, text: str) -> str:
    lock = memory_state.USER_LOCKS[sender]
    async with lock:
        mem = memory_state.get_memory(sender)
        history_msgs = _history_to_messages(mem.history[-memory_state.HISTORY_LIMIT * 2 :])
        system = render_system_prompt(mem.profile, mem.notes)

        reply = await agent_graph.run_turn(agent, system, history_msgs, text)

        now = time.time()
        mem.history.append(HistoryEntry(role="human", content=text, ts=now))
        mem.history.append(HistoryEntry(role="ai", content=reply, ts=now))
        cap = memory_state.HISTORY_LIMIT * 2
        if len(mem.history) > cap:
            mem.history = mem.history[-cap:]
        mem.last_seen_at = now
        mem.dirty = True
        return reply


async def update_memory(sender: str, user_text: str, ai_reply: str) -> None:
    """Background: one structured-output call to merge profile + append notes."""
    if model is None:
        return
    lock = memory_state.USER_LOCKS[sender]
    async with lock:
        mem = memory_state.get_memory(sender)
        prompt = render_extractor_prompt(mem.profile, user_text, ai_reply)
        try:
            extractor = model.with_structured_output(ExtractedMemory)
            diff: ExtractedMemory = await extractor.ainvoke(prompt)
        except Exception:
            logging.exception("Memory extraction failed for %s", sender)
            return

        merge_profile(mem.profile, diff.profile_updates)
        for n in diff.new_notes:
            if n and n.strip():
                append_note(mem, n.strip())
        mem.dirty = True


def send_whatsapp_message(
    recipient_number: str,
    message: str,
    reply_to_message_id: str | None = None,
):
    """Send a WhatsApp text message.

    If reply_to_message_id is given, the message renders as a native WhatsApp
    quoted reply — the original message appears above the bot's text in the
    chat UI. Use this when the reply is slow enough that the user may have
    sent other messages in between.
    """
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "text",
        "text": {"body": f"{message}"},
    }
    if reply_to_message_id:
        payload["context"] = {"message_id": reply_to_message_id}

    response = requests.post(url, headers=headers, json=payload, timeout=10)
    logging.info(f"WhatsApp API Status: {response.status_code}")
    logging.info(response.text)
