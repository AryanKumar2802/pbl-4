
"""3-stage LLM Council orchestration."""

import asyncio
import re
from typing import List, Dict, Any, Tuple

from .openrouter import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL


# Delay between stages to respect free-tier rate limits
INTER_STAGE_DELAY = 3.0

# Maximum characters per response included in chairman prompt
RESPONSE_TRUNCATION_LIMIT = 800


async def stage1_collect_responses(
    user_query: str
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.
    """

    print(
        f"\n[Stage 1] Querying {len(COUNCIL_MODELS)} council models..."
    )

    messages = [{"role": "user", "content": user_query}]

    responses = await query_models_parallel(
        COUNCIL_MODELS,
        messages
    )

    stage1_results = []

    for model, response in responses.items():
        if response is not None:
            content = response.get("content", "").strip()

            if content:
                stage1_results.append({
                    "model": model,
                    "response": content
                })

    print(
        f"[Stage 1] {len(stage1_results)}/"
        f"{len(COUNCIL_MODELS)} models responded successfully"
    )

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each successfully responding model ranks
    the anonymized Stage 1 responses.
    """

    # Only use models that succeeded in Stage 1.
    active_models = list(dict.fromkeys(
        result["model"] for result in stage1_results
    ))

    print(
        f"\n[Stage 2] Collecting peer rankings from "
        f"{len(active_models)} active models..."
    )

    if not stage1_results:
        print("[Stage 2] No Stage 1 responses available.")

        return [], {}

    # Create anonymized labels.
    labels = [
        chr(65 + i)
        for i in range(len(stage1_results))
    ]

    label_to_model = {
        f"Response {label}": result["model"]
        for label, result in zip(labels, stage1_results)
    }

    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:

1. Evaluate each response individually.
2. Explain what each response does well and poorly.
3. Rank all responses from best to worst.

IMPORTANT: Your final ranking MUST follow this exact format:

FINAL RANKING:
1. Response A
2. Response B
3. Response C

Use only the response labels in the ranking section.
Include every available response exactly once.

Now provide your evaluation and ranking:"""

    messages = [
        {"role": "user", "content": ranking_prompt}
    ]

    await asyncio.sleep(INTER_STAGE_DELAY)

    # Query only successful Stage 1 models.
    responses = await query_models_parallel(
        active_models,
        messages
    )

    stage2_results = []

    for model, response in responses.items():
        if response is not None:
            full_text = response.get("content", "").strip()

            if full_text:
                parsed = parse_ranking_from_text(full_text)

                stage2_results.append({
                    "model": model,
                    "ranking": full_text,
                    "parsed_ranking": parsed
                })

    print(
        f"[Stage 2] {len(stage2_results)}/"
        f"{len(active_models)} models returned rankings"
    )

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes the final response.
    """

    print(
        f"\n[Stage 3] Chairman ({CHAIRMAN_MODEL}) "
        "synthesizing final answer..."
    )

    stage1_text = "\n\n".join([
        (
            f"Model: {result['model']}\n"
            f"Response: {result['response'][:RESPONSE_TRUNCATION_LIMIT]}"
            + (
                "..."
                if len(result["response"]) > RESPONSE_TRUNCATION_LIMIT
                else ""
            )
        )
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        (
            f"Model: {result['model']}\n"
            f"Ranking: {result['ranking'][:RESPONSE_TRUNCATION_LIMIT]}"
            + (
                "..."
                if len(result["ranking"]) > RESPONSE_TRUNCATION_LIMIT
                else ""
            )
        )
        for result in stage2_results
    ])

    if not stage2_results:
        stage2_text = (
            "No peer rankings were successfully generated. "
            "Base the synthesis on the available Stage 1 responses."
        )

    chairman_prompt = f"""You are the Chairman of an LLM Council.

Multiple AI models have independently answered a user's question.
Their responses may also have been evaluated and ranked by other models.

Original Question:
{user_query}

STAGE 1 - Individual Responses:

{stage1_text}

STAGE 2 - Peer Rankings:

{stage2_text}

Your task is to synthesize the available information into one
comprehensive, accurate and useful answer.

Consider:

- The individual responses and their insights.
- The peer rankings, if available.
- Areas of agreement and disagreement.
- Factual accuracy and completeness.
- Any missing or incorrect information.

Do not blindly follow rankings.
Prioritize correctness and clarity.

Provide the final synthesized answer:"""

    messages = [
        {"role": "user", "content": chairman_prompt}
    ]

    await asyncio.sleep(INTER_STAGE_DELAY)

    response = await query_model(
        CHAIRMAN_MODEL,
        messages,
        timeout=180.0
    )

    if response is None:
        print(
            "[Stage 3] Chairman failed to respond. "
            "Check OpenRouter logs."
        )

        return {
            "model": CHAIRMAN_MODEL,
            "response": (
                "The Chairman model could not generate "
                "the final synthesis. Please try again."
            )
        }

    content = response.get("content", "").strip()

    print(
        f"[Stage 3] Chairman responded successfully "
        f"({len(content)} characters)"
    )

    return {
        "model": CHAIRMAN_MODEL,
        "response": content
    }


def parse_ranking_from_text(
    ranking_text: str
) -> List[str]:
    """
    Parse the FINAL RANKING section.
    """

    if "FINAL RANKING:" in ranking_text:
        ranking_section = ranking_text.split(
            "FINAL RANKING:", 1
        )[1]

        numbered_matches = re.findall(
            r'\d+\.\s*(Response [A-Z])',
            ranking_section
        )

        if numbered_matches:
            return numbered_matches

        return re.findall(
            r'Response [A-Z]',
            ranking_section
        )

    return re.findall(
        r'Response [A-Z]',
        ranking_text
    )


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.
    """

    from collections import defaultdict

    model_positions = defaultdict(list)

    for ranking in stage2_results:
        parsed_ranking = parse_ranking_from_text(
            ranking["ranking"]
        )

        # Prevent duplicate labels from affecting rankings.
        seen = set()

        for position, label in enumerate(
            parsed_ranking,
            start=1
        ):
            if label in seen:
                continue

            seen.add(label)

            if label in label_to_model:
                model = label_to_model[label]
                model_positions[model].append(position)

    aggregate = []

    for model, positions in model_positions.items():
        if positions:
            aggregate.append({
                "model": model,
                "average_rank": round(
                    sum(positions) / len(positions),
                    2
                ),
                "rankings_count": len(positions)
            })

    aggregate.sort(
        key=lambda item: item["average_rank"]
    )

    return aggregate


async def generate_conversation_title(
    user_query: str
) -> str:
    """
    Generate a short title for a conversation.
    """

    title_prompt = f"""Generate a very short title
(3-5 words maximum) summarizing this question.

The title should be concise and descriptive.
Do not use quotes or punctuation.

Question: {user_query}

Title:"""

    messages = [
        {"role": "user", "content": title_prompt}
    ]

    # Use the updated free model for title generation.
    response = await query_model(
        "nvidia/nemotron-3.5-lightning:free",
        messages,
        timeout=30.0
    )

    if response is None:
        return "New Conversation"

    title = (
        response.get("content", "New Conversation")
        .strip()
        .strip("\"'")
    )

    if not title:
        return "New Conversation"

    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(
    user_query: str
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete three-stage council process.
    """

    print(f"\n{'=' * 60}")
    print("[Council] Starting full council run")
    print(
        f"[Council] Query: "
        f"{user_query[:100]}"
        f"{'...' if len(user_query) > 100 else ''}"
    )
    print(f"{'=' * 60}")

    # Stage 1: Individual responses.
    stage1_results = await stage1_collect_responses(
        user_query
    )

    if not stage1_results:
        print(
            "[Council] FAILED: No models responded "
            "in Stage 1."
        )

        return [], [], {
            "model": "error",
            "response": (
                "All council models failed to respond. "
                "Please try again."
            )
        }, {}

    # Stage 2: Peer rankings.
    stage2_results, label_to_model = (
        await stage2_collect_rankings(
            user_query,
            stage1_results
        )
    )

    # Aggregate rankings.
    aggregate_rankings = calculate_aggregate_rankings(
        stage2_results,
        label_to_model
    )

    # Stage 3: Final synthesis.
    # Continue even if Stage 2 returned no rankings.
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    )

    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    print("\n[Council] Run complete")
    print(f"{'=' * 60}\n")

    return (
        stage1_results,
        stage2_results,
        stage3_result,
        metadata
    )

