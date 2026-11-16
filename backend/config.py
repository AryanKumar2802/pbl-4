
"""Configuration for the LLM Council."""

import os

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

OPENROUTER_API_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)

# Three independent free council models
COUNCIL_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "inclusionai/ling-3.2-flash:free",
    "baidu/ernie-5.5-flash-preview:free",
]

# Separate Chairman model
CHAIRMAN_MODEL = (
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
)

DATA_DIR = "data/conversations"

