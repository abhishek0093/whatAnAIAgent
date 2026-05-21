from __future__ import annotations

import re

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

from agent.tools import ALL_TOOLS

TOOLS_HINT = (
    "\n\n# Tools\n"
    "You can call tools when you need to look up live information. "
    "Use `get_weather` whenever the user asks about weather, temperature, rain, humidity, wind, "
    "or whether a trip / outdoor plan is fine condition-wise. "
    "If the user doesn't name a city, use the location from their profile above. "
    "If there's no location anywhere, ask them which city they mean. "
    "Don't mention tools by name in the reply — just answer naturally. "
    "Use `get_date_time` whenever you need to know today's date or the current time."
)


def build_agent(model):
    """Wrap the LLM in a LangChain agent bound to all registered tools.

    The per-user system prompt isn't baked into the agent — it's prepended to
    the message list on each call (in `run_turn`) since it depends on user
    memory at the time of the turn.
    """
    return create_agent(model, tools=ALL_TOOLS)


def _coerce_content(content) -> str:
    """Gemini sometimes returns content as a list of parts; flatten to str."""
    if isinstance(content, list):
        return "".join(p if isinstance(p, str) else p.get("text", "") for p in content)
    return content if isinstance(content, str) else str(content)


def _normalise_for_whatsapp(text: str) -> str:
    """Convert common Markdown to WhatsApp's text formatting.

    WhatsApp uses *bold*, _italic_, ~strike~ (single delimiter). The model
    sometimes emits Markdown's **bold** / __bold__ / `## heading` / [text](url)
    instead — WhatsApp leaves those as literal characters, which looks ugly.
    """

    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__", r"*\1*", text, flags=re.DOTALL)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    return text


async def run_turn(agent, system_prompt: str, history_msgs: list, user_text: str) -> str:
    """Run one agent turn and return the final assistant text.

    The agent may call tools internally; we only care about the last AIMessage.
    """
    messages = [SystemMessage(system_prompt + TOOLS_HINT), *history_msgs, HumanMessage(user_text)]
    result = await agent.ainvoke({"messages": messages})
    final = result["messages"][-1]
    return _normalise_for_whatsapp(_coerce_content(getattr(final, "content", "")))
