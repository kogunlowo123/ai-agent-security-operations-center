"""
Faithfulness evaluation for RAG-based SOC agent outputs.

Uses an LLM-as-judge approach (via LiteLLM/Bedrock) to determine whether
a generated claim is supported by the retrieved context documents.

Faithfulness Score = fraction of claims in the generated output that are
directly supported by (or can be inferred from) the provided context.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM_PROMPT = """\
You are an expert fact-checker for a Security Operations Centre (SOC) AI system.
Your task is to evaluate whether a given CLAIM is faithfully supported by the
provided CONTEXT documents.

A claim is FAITHFUL if:
- It is explicitly stated in the context, OR
- It can be directly and unambiguously inferred from the context.

A claim is UNFAITHFUL if:
- It contradicts the context, OR
- It introduces new facts not present in the context, OR
- It is an unsupported speculation or hallucination.

Respond ONLY with a JSON object:
{
  "faithful": true | false,
  "reasoning": "<one sentence explanation>",
  "confidence": <float 0.0-1.0>
}
"""

_JUDGE_USER_TEMPLATE = """\
CLAIM:
{claim}

CONTEXT:
{context}

Is the claim faithful to the context?"""


async def _call_llm_judge(
    claim: str,
    context_text: str,
    model: str = "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Call the LLM judge via LiteLLM and parse the structured response.

    Parameters
    ----------
    claim:
        The claim to evaluate.
    context_text:
        Concatenated context documents.
    model:
        LiteLLM model string (default: Claude Haiku via Bedrock for cost efficiency).
    timeout:
        Maximum seconds to wait for the LLM response.

    Returns
    -------
    dict with keys: faithful (bool), reasoning (str), confidence (float)
    """
    try:
        import litellm  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "litellm is required for faithfulness evaluation. "
            "Install it with: pip install litellm"
        ) from exc

    user_message = _JUDGE_USER_TEMPLATE.format(
        claim=claim.strip(),
        context=context_text.strip()[:8000],  # cap to avoid token overflow
    )

    response = await asyncio.wait_for(
        litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=256,
        ),
        timeout=timeout,
    )

    content = response.choices[0].message.content
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # Attempt to extract JSON from response that may have surrounding text
        match = re.search(r"\{.*?\}", content, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            logger.warning("LLM judge returned non-JSON response: %s", content)
            # Default to unfaithful when parsing fails
            return {"faithful": False, "reasoning": "parse error", "confidence": 0.0}

    return {
        "faithful": bool(result.get("faithful", False)),
        "reasoning": str(result.get("reasoning", "")),
        "confidence": float(result.get("confidence", 0.5)),
    }


async def evaluate_faithfulness(
    claim: str,
    context_docs: list[str],
    model: str = "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    separator: str = "\n\n---\n\n",
) -> float:
    """
    Evaluate whether a claim is supported by the provided context documents.

    Uses an LLM as a judge (Claude Haiku via AWS Bedrock by default) to check
    if the claim can be derived from the context without hallucination.

    Parameters
    ----------
    claim:
        The claim extracted from agent output to verify.
    context_docs:
        List of retrieved document strings that the agent used as context.
    model:
        LiteLLM model identifier. Defaults to Claude Haiku via Bedrock.
    separator:
        String used to join multiple context documents.

    Returns
    -------
    float
        Faithfulness score in [0.0, 1.0]:
        - 1.0 → claim is fully supported by context
        - 0.0 → claim contradicts or is unsupported by context
        - Values between represent the judge's confidence in faithfulness.

    Raises
    ------
    ImportError
        If litellm is not installed.
    asyncio.TimeoutError
        If the LLM judge does not respond within 30 seconds.

    Examples
    --------
    >>> import asyncio
    >>> docs = ["The CVE-2024-1234 has CVSS score 9.8 (Critical)."]
    >>> score = asyncio.run(evaluate_faithfulness(
    ...     "CVE-2024-1234 is rated Critical with score 9.8",
    ...     docs
    ... ))
    >>> assert score > 0.9
    """
    if not context_docs:
        logger.warning("evaluate_faithfulness called with empty context_docs")
        return 0.0

    if not claim.strip():
        logger.warning("evaluate_faithfulness called with empty claim")
        return 0.0

    context_text = separator.join(doc.strip() for doc in context_docs if doc.strip())

    try:
        result = await _call_llm_judge(claim, context_text, model=model)
    except Exception as exc:
        logger.error("LLM judge call failed: %s", exc, exc_info=True)
        return 0.0

    if result["faithful"]:
        return result["confidence"]
    else:
        return 1.0 - result["confidence"]


async def batch_evaluate_faithfulness(
    claim_context_pairs: list[tuple[str, list[str]]],
    model: str = "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    max_concurrency: int = 5,
) -> list[float]:
    """
    Evaluate faithfulness for multiple claim-context pairs concurrently.

    Parameters
    ----------
    claim_context_pairs:
        List of (claim, context_docs) tuples.
    model:
        LiteLLM model identifier.
    max_concurrency:
        Maximum number of concurrent LLM calls to avoid rate limits.

    Returns
    -------
    list[float]
        Faithfulness scores, one per input pair, in the same order.
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded_eval(claim: str, docs: list[str]) -> float:
        async with semaphore:
            return await evaluate_faithfulness(claim, docs, model=model)

    tasks = [_bounded_eval(claim, docs) for claim, docs in claim_context_pairs]
    return list(await asyncio.gather(*tasks))


def mean_faithfulness(scores: list[float]) -> float:
    """
    Compute the mean faithfulness score across a set of evaluations.

    Parameters
    ----------
    scores:
        List of faithfulness scores in [0.0, 1.0].

    Returns
    -------
    float
        Mean faithfulness, or 0.0 if the list is empty.
    """
    if not scores:
        return 0.0
    return sum(scores) / len(scores)
