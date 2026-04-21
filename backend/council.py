"""3-stage LLM Council orchestration."""

import asyncio
from typing import List, Dict, Any, Tuple
from .openrouter import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL

# Delay between stages to avoid hammering free-tier rate limits
INTER_STAGE_DELAY = 30.0  # seconds

# Max characters per response fed into the chairman prompt
RESPONSE_TRUNCATION_LIMIT = 800


async def stage1_collect_responses(user_query: str) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    print(f"\n[Stage 1] Querying {len(COUNCIL_MODELS)} council models...")
    messages = [{"role": "user", "content": user_query}]

    # Query all models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results — only include successful responses
    stage1_results = []
    for model, response in responses.items():
        if response is not None:
            stage1_results.append({
                "model": model,
                "response": response.get("content", "")
            })

    print(f"[Stage 1] {len(stage1_results)}/{len(COUNCIL_MODELS)} models responded successfully")
    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    print(f"\n[Stage 2] Collecting peer rankings from {len(COUNCIL_MODELS)} models...")

    # Create anonymized labels: Response A, Response B, ...
    labels = [chr(65 + i) for i in range(len(stage1_results))]

    # Mapping from anonymous label → real model name
    label_to_model = {
        f"Response {label}": result["model"]
        for label, result in zip(labels, stage1_results)
    }

    # Build ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Small delay before stage 2 to respect free-tier rate limits
    await asyncio.sleep(INTER_STAGE_DELAY)

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get("content", "")
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    print(f"[Stage 2] {len(stage2_results)}/{len(COUNCIL_MODELS)} models returned rankings")
    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Dict with 'model' and 'response' keys
    """
    print(f"\n[Stage 3] Chairman ({CHAIRMAN_MODEL}) synthesizing final answer...")

    # Truncate individual responses to avoid overflowing the chairman's context
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response'][:RESPONSE_TRUNCATION_LIMIT]}"
        + ("..." if len(result['response']) > RESPONSE_TRUNCATION_LIMIT else "")
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking'][:RESPONSE_TRUNCATION_LIMIT]}"
        + ("..." if len(result['ranking']) > RESPONSE_TRUNCATION_LIMIT else "")
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Delay before chairman call — stages 1+2 used up free-tier quota
    await asyncio.sleep(INTER_STAGE_DELAY)

    # Query the chairman model with extended timeout for large synthesis
    response = await query_model(CHAIRMAN_MODEL, messages, timeout=180.0)

    if response is None:
        print(f"[Stage 3] Chairman failed to respond — check logs above for the real error")
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis. Check server logs for details."
        }

    content = response.get("content", "")
    print(f"[Stage 3] Chairman responded successfully ({len(content)} chars)")

    return {
        "model": CHAIRMAN_MODEL,
        "response": content
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Match numbered list items: "1. Response A"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]
            # Fallback: any "Response X" in order
            return re.findall(r'Response [A-Z]', ranking_section)

    # Last resort fallback
    return re.findall(r'Response [A-Z]', ranking_text)


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    model_positions = defaultdict(list)

    for ranking in stage2_results:
        parsed_ranking = parse_ranking_from_text(ranking["ranking"])
        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_positions[label_to_model[label]].append(position)

    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            aggregate.append({
                "model": model,
                "average_rank": round(sum(positions) / len(positions), 2),
                "rankings_count": len(positions)
            })

    aggregate.sort(key=lambda x: x["average_rank"])
    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use a fast, reliable free model for title generation
    response = await query_model(
        "meta-llama/llama-3.3-70b-instruct:free",
        messages,
        timeout=30.0
    )

    if response is None:
        return "New Conversation"

    title = response.get("content", "New Conversation").strip().strip('"\'')

    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(user_query: str) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    print(f"\n{'='*60}")
    print(f"[Council] Starting full council run")
    print(f"[Council] Query: {user_query[:100]}{'...' if len(user_query) > 100 else ''}")
    print(f"{'='*60}")

    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(user_query)

    if not stage1_results:
        print("[Council] FAILED — no models responded in Stage 1")
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect peer rankings
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Chairman synthesis
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    )

    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    print(f"\n[Council] Run complete")
    print(f"{'='*60}\n")

    return stage1_results, stage2_results, stage3_result, metadata