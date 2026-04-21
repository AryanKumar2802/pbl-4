# LLM Council

![llmcouncil](header.jpg)

Instead of querying a single LLM provider (e.g. OpenAI GPT-4, Google Gemini, Anthropic Claude, xAI Grok), this project lets you assemble an "LLM Council" — a panel of models that collaborate to produce a better final answer. It's a simple, local web app that resembles ChatGPT in interface, but uses OpenRouter under the hood to dispatch your query to multiple LLMs simultaneously. The models then review and rank each other's responses, and a designated Chairman LLM synthesizes everything into a single, well-considered final answer.

## How It Works

When you submit a query, three stages unfold:

1. **Stage 1: First Opinions** — Your query is sent to all council LLMs individually. Their responses are collected and displayed in a tab view so you can read and compare them side by side.
2. **Stage 2: Peer Review** — Each LLM is shown the responses of its peers (with identities anonymized to prevent bias) and asked to rank them by accuracy and depth of insight.
3. **Stage 3: Final Response** — The designated Chairman of the Council reviews all responses and rankings, then compiles a single, authoritative final answer for the user.

## Setup

### 1. Install Dependencies

The project uses [uv](https://docs.astral.sh/uv/) for Python project management.

**Backend:**
```bash
uv sync
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 2. Configure API Key

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

Get your API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase credits or enable automatic top-up.

### 3. Configure Models (Optional)

Edit `backend/config.py` to customize your council:

```python
COUNCIL_MODELS = [
    "openai/gpt-4o",
    "google/gemini-pro",
    "anthropic/claude-sonnet-4-5",
    "x-ai/grok-3",
]

CHAIRMAN_MODEL = "google/gemini-pro"
```

## Running the Application

**Option 1: Use the start script**
```bash
./start.sh
```

**Option 2: Run manually**

Terminal 1 — Backend:
```bash
uv run python -m backend.main
```

Terminal 2 — Frontend:
```bash
cd frontend
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173) in your browser.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.10+), async httpx, OpenRouter API |
| Frontend | React + Vite, react-markdown |
| Storage | JSON files in `data/conversations/` |
| Package Management | uv (Python), npm (JavaScript) |
