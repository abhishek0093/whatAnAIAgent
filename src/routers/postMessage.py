import json
import logging
import os
import time

from fastapi import APIRouter, BackgroundTasks, Request, Response, status

from models import process_requests

router = APIRouter()

QUOTE_DELAY_THRESHOLD_SECONDS = int(os.getenv("QUOTE_DELAY_THRESHOLD_SECONDS", "5"))


def _quote_if_slow(message: dict, reply_time: float) -> str | None:
    """Return the message id to quote if the reply is slower than the threshold.

    WhatsApp inbound payloads include a `timestamp` (unix seconds, string) and
    `id` (wamid). If we're replying more than QUOTE_DELAY_THRESHOLD_SECONDS
    after the message was sent, the user may have moved on — quote the
    original so they know which message we're answering.
    """
    msg_id = message.get("id")
    ts_raw = message.get("timestamp")
    if not msg_id or not ts_raw:
        return None
    try:
        sent_at = float(ts_raw)
    except (TypeError, ValueError):
        return None
    if reply_time - sent_at > QUOTE_DELAY_THRESHOLD_SECONDS:
        return msg_id
    return None


@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        logging.info(json.dumps(body, indent=2))

        entry = body.get("entry", [])
        if not entry:
            return Response("ok", status_code=status.HTTP_200_OK)

        changes = entry[0].get("changes", [])
        if not changes:
            return Response("ok", status_code=status.HTTP_200_OK)

        value = changes[0].get("value", {})
        messages = value.get("messages")

        if not messages:
            return Response("ok", status_code=status.HTTP_200_OK)

        message = messages[0]
        sender = message.get("from")

        if message.get("type") != "text":
            process_requests.send_whatsapp_message(sender, "Currently I support text messages only.")
            return Response("ok", status_code=status.HTTP_200_OK)

        incoming_text = message["text"]["body"]
        logging.info(f"Message from {sender}: {incoming_text}")

        reply = await process_requests.process_message(sender, incoming_text)
        quote_id = _quote_if_slow(message, time.time())
        process_requests.send_whatsapp_message(sender, reply, reply_to_message_id=quote_id)

        background_tasks.add_task(process_requests.update_memory, sender, incoming_text, reply)

        return Response("ok", status_code=status.HTTP_200_OK)

    except Exception:
        logging.exception("Error processing webhook")
        return Response("error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
