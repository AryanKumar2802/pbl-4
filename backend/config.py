"""Configuration for the LLM Council."""

OPENROUTER_API_KEY = "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"



# ⚠️ Ensure you have $10 in your OpenRouter account to unlock 1,000 requests/day
"""Configuration for the LLM Council."""

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

"""
Configuration for the LLM Council.
Selected for Redundancy: These models have 3+ providers each, 
drastically reducing 429 'Upstream' errors.
"""

COUNCIL_MODELS = [
    # 1. NVIDIA Nemotron 3 Super: Most stable free model in 2026.
    "nvidia/nemotron-3-super-120b-a12b:free",
    
    # 2. OpenAI GPT-OSS 120B: High-capacity MoE with massive uptime.
    "openai/gpt-oss-120b:free",
    
    # 3. Google Gemma 3 27B: Extremely reliable and rarely congested.
    "google/gemma-3-27b-it:free",
]

# Chairman = GPT-OSS 120B (Highest priority on OpenRouter routing)
CHAIRMAN_MODEL = "openai/gpt-oss-120b:free"

DATA_DIR = "data/conversations"