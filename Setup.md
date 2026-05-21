
## Setup

### Prerequisites
- Python 3.14
- Conda Installed
- A Meta Developer account with a WhatsApp Business app and a sandbox phone number — see Meta's [WhatsApp Cloud API getting started](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started).
    - You can skip Jasper Sample app and can directly move ahead with creating your sample app and using api section. 
    - Meta provides generous free tier for api, so should be okay for app testing, development and prototyping.  
- Any LLM provider/model api key with model able to support function calling. 
- `ngrok` (or any tunnel) for local development so Meta can reach your webhook.

### Install dependencies

```bash
conda create -n "whatAnAIAgent" python=3.14    
conda activate whatAnAIAgent
pip install -r requirements.txt 
```

### Environment variables

Create a `.env` file at the project root and add correct values for variables in `.env.example`

| Variable | Required | Default | What it does |
| --- | --- | --- | --- |
| `VERIFY_TOKEN` | yes | — | Token Meta sends in the webhook verification handshake. Must match the value you set in Meta's dashboard. |
| `WHATSAPP_TOKEN` | yes | — | Bearer token for the WhatsApp Cloud API. |
| `PHONE_NUMBER_ID` | yes | — | The Cloud API phone number id that messages are sent through. |
| `GOOGLE_API_KEY` | yes | — | Gemini API key. |
| `SERVICE_PORT` | yes | — | Port `uvicorn` binds to. |
| `MEMORY_DB_PATH` | no | `./memory.sqlite` | Path to the SQLite file used for periodic persistence. |
| `MEMORY_FLUSH_INTERVAL_SECONDS` | no | `60` | How often the background task writes dirty `UserMemory` entries to disk. |
| `MEMORY_HISTORY_LIMIT` | no | `50` | Soft cap on user turns (so `MEMORY_HISTORY_LIMIT * 2` entries total: human + AI). |
| `QUOTE_DELAY_THRESHOLD_SECONDS` | no | `5` | If a reply takes longer than this, the WhatsApp send quotes the original inbound message. |
