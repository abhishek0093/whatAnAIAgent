from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    name: str | None = None
    age: int | None = None
    location: str | None = None
    occupation: str | None = None
    talking_style: str | None = None
    interests: list[str] = Field(default_factory=list)
    ongoing_topics: list[str] = Field(default_factory=list)


class HistoryEntry(BaseModel):
    role: Literal["human", "ai"]
    content: str
    ts: float


class Note(BaseModel):
    ts: float
    content: str


class UserMemory(BaseModel):
    profile: UserProfile = Field(default_factory=UserProfile)
    notes: list[Note] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    last_seen_at: float = 0.0

    dirty: bool = Field(default=False, exclude=True)

    def to_persist_json(self) -> str:
        return self.model_dump_json(exclude={"dirty"})


class ExtractedMemory(BaseModel):
    """LLM-returned diff after a turn. Unset fields = no change."""

    profile_updates: UserProfile = Field(default_factory=UserProfile)
    new_notes: list[str] = Field(default_factory=list)


def render_system_prompt(profile: UserProfile, notes: list[Note], note_limit: int = 25) -> str:
    style = profile.talking_style or "neutral; mirror the user's energy and slang"
    interests = ", ".join(profile.interests) if profile.interests else "unknown"
    topics = ", ".join(profile.ongoing_topics) if profile.ongoing_topics else "none yet"

    lines = [
        "You are a personal assistant chatting with the user on WhatsApp.",
        "Be warm, brief, and match the user's preferred tone. WhatsApp messages should feel like a friend texting — not a formal email.",
        "Write in plain text. WhatsApp does NOT render Markdown — never use `**bold**`, `##` headings, or `[text](url)` links. If you want emphasis, use WhatsApp's single-character syntax: *bold*, _italic_, ~strike~.",
        "",
        "# About the user",
        f"- Name: {profile.name or 'unknown'}",
        f"- Talking style: {style} or 'casual'",
        f"- Age: {profile.age if profile.age is not None else 'unknown'}",
        f"- Location: {profile.location or 'unknown'}",
        f"- Occupation: {profile.occupation or 'unknown'}",
        f"- Interests: {interests}",
        f"- Ongoing topics: {topics}",
    ]

    if notes:
        recent = notes[-note_limit:]
        lines.append("")
        lines.append("# Things they've shared")
        for n in recent:
            lines.append(f"- {n.content}")

    lines.append("")
    lines.append("Use this context to personalise replies. Don't recite it or tell user that you used it unless specifically asked.")
    return "\n".join(lines)


def render_extractor_prompt(profile: UserProfile, user_text: str, ai_reply: str) -> str:
    return (
        "You are a memory extractor for a personal WhatsApp assistant. "
        "Read the latest user message and the assistant's reply, then decide what to remember about the user.\n\n"
        "Rules:\n"
        "- Only set a profile field if it is clearly and confidently stated by the user. Leave it null otherwise.\n"
        "- For lists (interests, ongoing_topics), include ONLY items to ADD. Do not repeat items already in the existing profile.\n"
        "- new_notes: short, specific facts worth remembering long-term (e.g. 'has a dog named Mango', 'flying to Goa next week', 'works on a side-project called X'). "
        "Skip small talk, greetings, or anything the assistant said.\n"
        "- If nothing new is learnable, return empty fields.\n\n"
        f"# Current profile\n{profile.model_dump_json(indent=2)}\n\n"
        f"# Latest exchange\nUser: {user_text}\nAssistant: {ai_reply}\n"
    )


def merge_profile(current: UserProfile, updates: UserProfile) -> None:
    """In-place merge. Scalars overwrite when non-None; lists union (preserve order, dedupe)."""
    for field in ("name", "age", "location", "occupation", "talking_style"):
        new_val = getattr(updates, field)
        if new_val is not None:
            setattr(current, field, new_val)

    for field in ("interests", "ongoing_topics"):
        existing: list[str] = getattr(current, field)
        seen = {x.lower() for x in existing}
        for item in getattr(updates, field):
            if item.lower() not in seen:
                existing.append(item)
                seen.add(item.lower())


def append_note(memory: UserMemory, content: str) -> None:
    memory.notes.append(Note(ts=time.time(), content=content))
