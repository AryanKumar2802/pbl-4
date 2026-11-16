
import os

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

COUNCIL_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "baidu/ernie-5.5-flash-preview:free",
    "inclusionai/ling-3.2-flash:free"
]

CHAIRMAN_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

DATA_DIR = "data/conversations"

