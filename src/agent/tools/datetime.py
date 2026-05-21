import logging
import datetime
from langchain_core.tools import tool



@tool("get_date_time")
async def get_date_time():
    """Get the current date and time.
    Use this to answer questions that require awareness of the current date and time, like "what's the date today?" "How much time elapsed since some past instance?" etc.
    Returns current date and time as YYYY-MM-DD HH:MM:SS. The model should use this and do any necessary formatting or calculations before replying.
    """
    try:
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logging.error(f"Error in get_date_time: {e}")
        return "Not able to get current date and time at the moment"