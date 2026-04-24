"""AI-powered incentive parser.

Takes a raw incentive string (scraped verbatim from a building's website) and
returns structured data using Claude via the Anthropic API.

Return contract:
    Success: {"promos": [...], "_model": str, "_parsed_at": iso, "_ok": True}
    Failure: {"promos": [], "_error": str, "_raw_length": int, "_ok": False}

CRITICAL: This function must NEVER raise. persist_result() runs it inside a DB
transaction with no try/except around it. An uncaught exception here would roll
back the building's entire unit inventory for that run. Every failure mode
returns a fallback dict instead.

The caller (persist.py) uses the "_ok" flag to decide whether to advance
incentive_hash. Failed parses leave the hash stale, so the next scrape retries
automatically without any manual intervention.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import anthropic

from backend.app.config import settings

log = logging.getLogger(__name__)


MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
TIMEOUT_SECONDS = 30.0


SYSTEM_PROMPT = """You extract structured data from rental incentive text. You are precise.

You will receive the raw text of one building's rental incentives, scraped verbatim from a property website. The text may describe one promotion or several concurrent promotions (often separated by blank lines or conditional on different lease terms).

Return ONLY a JSON object — no prose, no markdown, no code fences. The schema is:

{
  "promos": [
    {
      "months_free": integer or null,
      "months_free_is_estimate": boolean,
      "cash_bonus": integer or null,
      "free_perks": [list of strings],
      "deadline": "YYYY-MM-DD" or null,
      "conditions": string or null
    }
  ]
}

RULES:

1. months_free is the number of free months. If the text gives a specific number ("2 months free", "one month free"), use that integer with months_free_is_estimate=false. If the text uses a vague quantifier ("up to 2 months", "as much as 2 months"), use the stated ceiling as the integer but set months_free_is_estimate=true. Only set months_free=null if no quantity is given at all.

2. cash_bonus is the dollar amount as an integer with no currency symbol. "$500 move in bonus" -> 500. "$2,000 moving bonus" -> 2000. If absent, null.

3. free_perks is a list of non-monetary concessions: gift cards, free utilities, free internet, waived fees, branded experiences. Examples: "Othership gift card", "Bell Fibe Internet", "waived amenity fee". One perk per list item. Empty list if none.

4. deadline is a strict ISO date YYYY-MM-DD. "April 30th, 2026" -> "2026-04-30". "Sign by June 1" without year -> null (do not invent a year). If no deadline is given, null.

5. conditions captures qualifying fine print: lease-term requirements ("on 2-year leases"), unit restrictions ("on select suites"), vague quantifier language ("up to" offers), or other caveats. Plain English, one or two sentences. Null if truly unconditional.

6. One promo object per distinct offer. If the text describes three lease-length-dependent promos (different concessions for 1-year vs 2-year leases), return three promo objects. If it describes a single offer with multiple stacked components (months free AND cash bonus AND deadline, all together), return one promo object. The test: would a renter treat them as separate choices, or as one bundled package?

7. If the text contains no actual incentive (empty, marketing fluff with no real concession), return {"promos": []}.

Return only the JSON object. No surrounding text."""


CODE_FENCE_PATTERN = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _fallback(reason: str, raw: str) -> dict:
    return {
        "promos": [],
        "_error": reason,
        "_raw_length": len(raw) if raw else 0,
        "_ok": False,
    }


def _validate_promo(p: dict) -> dict | None:
    """Coerce one promo dict into expected types. None if unsalvageable."""
    if not isinstance(p, dict):
        return None

    months_free = p.get("months_free")
    if months_free is not None:
        try:
            months_free = int(months_free)
        except (TypeError, ValueError):
            months_free = None

    is_estimate = bool(p.get("months_free_is_estimate", False))

    cash_bonus = p.get("cash_bonus")
    if cash_bonus is not None:
        try:
            cash_bonus = int(cash_bonus)
        except (TypeError, ValueError):
            cash_bonus = None

    free_perks = p.get("free_perks") or []
    if not isinstance(free_perks, list):
        free_perks = []
    free_perks = [str(x).strip() for x in free_perks if x and str(x).strip()]

    deadline = p.get("deadline")
    if deadline is not None:
        if not isinstance(deadline, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline):
            deadline = None

    conditions = p.get("conditions")
    if conditions is not None:
        if not isinstance(conditions, str):
            conditions = str(conditions)
        conditions = conditions.strip() or None

    return {
        "months_free": months_free,
        "months_free_is_estimate": is_estimate,
        "cash_bonus": cash_bonus,
        "free_perks": free_perks,
        "deadline": deadline,
        "conditions": conditions,
    }


def parse_incentive(raw: str) -> dict | None:
    """Parse a raw incentive string into structured promos via Claude.

    Never raises. Returns a dict on success or failure — caller inspects _ok.
    """
    if not raw or not raw.strip():
        return None

    try:
        client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=TIMEOUT_SECONDS,
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": raw}],
        )
    except anthropic.APIConnectionError as e:
        log.warning(f"incentive_parser: connection error: {e!r}")
        return _fallback(f"connection_error: {e.__class__.__name__}", raw)
    except anthropic.RateLimitError:
        log.warning("incentive_parser: rate limited")
        return _fallback("rate_limited", raw)
    except anthropic.APIStatusError as e:
        # Surface the response body — without it, 400s are invisible.
        body = ""
        try:
            body = e.response.text[:500]
        except Exception:
            pass
        log.warning(f"incentive_parser: API status {e.status_code}: {body}")
        print(f"  [API {e.status_code}] {body}")
        return _fallback(f"api_status_{e.status_code}: {body[:200]}", raw)
    except Exception as e:
        log.exception(f"incentive_parser: unexpected error on API call")
        return _fallback(f"unexpected_api: {e.__class__.__name__}", raw)

    # Extract text from response. content is a list of blocks.
    try:
        text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        text = "".join(text_parts).strip()
    except Exception as e:
        log.exception("incentive_parser: failed to extract text from response")
        return _fallback(f"response_extraction: {e.__class__.__name__}", raw)

    if not text:
        return _fallback("empty_response", raw)

    # Strip accidental code fences if the model ignored instructions.
    cleaned = CODE_FENCE_PATTERN.sub("", text).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.warning(f"incentive_parser: JSON decode failed: {e}; text was {cleaned[:200]!r}")
        return _fallback(f"json_decode: {e.msg}", raw)

    if not isinstance(parsed, dict):
        return _fallback("response_not_object", raw)

    promos_raw = parsed.get("promos")
    if not isinstance(promos_raw, list):
        return _fallback("promos_not_list", raw)

    promos = []
    for p in promos_raw:
        validated = _validate_promo(p)
        if validated is not None:
            promos.append(validated)

    return {
        "promos": promos,
        "_model": MODEL,
        "_parsed_at": datetime.now(timezone.utc).isoformat(),
        "_ok": True,
    }
