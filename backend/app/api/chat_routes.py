"""POST /chat/ask — natural language Q&A over the current rental comp data.

Design decisions (per user):
  - Fresh chat every request. No conversation history, no memory.
  - Full dashboard state injected into system prompt every turn.
  - Compact data format: aggregates + per-unit-line CSV-ish list.
  - Claude Sonnet 3.5 via the same anthropic==0.39.0 SDK as incentive parser.
  - Failures return a friendly error string, never a 500.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import Building, Unit, User


log = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
TIMEOUT_SECONDS = 30.0


SYSTEM_PROMPT_TEMPLATE = """You are the Fitzrovia Asset Management rental comp assistant. You answer questions from the asset management team about competitive rental data for the Toronto midtown buildings they track.

Every building in the data below is a competitor property being monitored. The user works at Fitzrovia \u2014 when they ask "which building is cheapest" or "how many units are available", they mean across the whole tracked set, not a subset.

Use ONLY the data shown below to answer. If a question cannot be answered from the data, say so plainly \u2014 do not speculate or invent numbers.

Be concise. Answer in one to three sentences unless the user explicitly asks for detail. Use plain prose, not bullet points, unless the user asks for a list. Format money as $2,450 with a comma and no decimals.

CURRENT DATA (as of {generated_at}):

{data_block}
"""


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    error: str | None = None


def _build_data_block(db: Session) -> str:
    """Compose the compact data string for the system prompt."""
    buildings = db.query(Building).order_by(Building.name).all()

    lines: list[str] = []
    lines.append("=== AGGREGATE STATS ===")
    all_available_units = [
        u for b in buildings for u in b.units if u.is_currently_available
    ]
    lines.append(f"Total buildings tracked: {len(buildings)}")
    lines.append(f"Total available units: {len(all_available_units)}")

    succeeded = sum(1 for b in buildings if b.last_scrape_status == "success")
    failed = sum(1 for b in buildings if b.last_scrape_status == "failed")
    lines.append(f"Scrape status: {succeeded} success, {failed} failed")

    # Per-unit-type rollup
    from collections import defaultdict
    type_units: dict[str, list[Unit]] = defaultdict(list)
    for u in all_available_units:
        type_units[u.unit_type].append(u)

    lines.append("")
    lines.append("=== UNITS BY TYPE (across all buildings) ===")
    for utype in sorted(type_units.keys()):
        units = type_units[utype]
        rents = [u.rent for u in units if u.rent]
        sqfts = [u.sqft for u in units if u.sqft]
        rent_str = f"${min(rents):,.0f}-${max(rents):,.0f}" if rents else "n/a"
        sqft_str = f"{min(sqfts)}-{max(sqfts)} sqft" if sqfts else "n/a"
        lines.append(
            f"{utype}: {len(units)} units, rent {rent_str}, {sqft_str}"
        )

    # Per-building detail
    lines.append("")
    lines.append("=== BY BUILDING ===")
    for b in buildings:
        avail = [u for u in b.units if u.is_currently_available]
        rents = [u.rent for u in avail if u.rent]
        rent_str = f"${min(rents):,.0f}-${max(rents):,.0f}" if rents else "no units"

        from collections import Counter
        by_type = Counter(u.unit_type for u in avail)
        type_str = ", ".join(f"{n} {t}" for t, n in sorted(by_type.items())) or "none"

        status_bit = ""
        if b.last_scrape_status == "failed":
            status_bit = f" [SCRAPE FAILED: {b.last_scrape_error or 'unknown reason'}]"

        lines.append(
            f"- {b.name} ({b.address}): "
            f"{len(avail)} units available ({type_str}), rent {rent_str}{status_bit}"
        )

    # Active incentives verbatim
    lines.append("")
    lines.append("=== ACTIVE INCENTIVES ===")
    any_inc = False
    for b in buildings:
        if b.current_incentive_raw:
            any_inc = True
            lines.append(f"-- {b.name}:")
            lines.append(b.current_incentive_raw.strip())
            lines.append("")
    if not any_inc:
        lines.append("(no active incentives captured in latest scrape)")

    # Per-unit detail, compact format: id|type|rent|sqft|floor|avail|building
    lines.append("")
    lines.append("=== INDIVIDUAL UNITS ===")
    lines.append("Format: building | unit_id | type | rent | sqft | floor | available")
    for b in buildings:
        for u in sorted(
            [u for u in b.units if u.is_currently_available],
            key=lambda u: (u.unit_type, u.rent or 0),
        ):
            lines.append(
                f"{b.name} | {u.unit_identifier} | {u.unit_type} | "
                f"${u.rent:,.0f} | {u.sqft or '-'} | {u.floor if u.floor is not None else '-'} | "
                f"{u.available_date or '-'}"
            )

    return "\n".join(lines)


@router.post("/ask", response_model=ChatResponse)
def ask(
    req: ChatRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    question = req.question.strip()
    if not question:
        return ChatResponse(answer="", error="Empty question.")

    try:
        data_block = _build_data_block(db)
    except Exception as e:
        log.exception("chat: failed to build data block")
        return ChatResponse(answer="", error=f"Could not read data: {e.__class__.__name__}")

    system = SYSTEM_PROMPT_TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_block=data_block,
    )

    try:
        client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=TIMEOUT_SECONDS,
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": question}],
        )
    except anthropic.APIConnectionError as e:
        log.warning(f"chat: connection error: {e!r}")
        return ChatResponse(answer="", error="Couldn't reach the AI service. Try again in a moment.")
    except anthropic.RateLimitError:
        return ChatResponse(answer="", error="Rate limited by the AI service. Try again shortly.")
    except anthropic.APIStatusError as e:
        body = ""
        try:
            body = e.response.text[:300]
        except Exception:
            pass
        log.warning(f"chat: API {e.status_code}: {body}")
        # Credit-balance errors are the common real-world case — surface them readably.
        if "credit balance" in body.lower():
            return ChatResponse(answer="", error="Anthropic account is out of credits.")
        return ChatResponse(answer="", error=f"AI service error ({e.status_code}).")
    except Exception as e:
        log.exception("chat: unexpected error")
        return ChatResponse(answer="", error=f"Unexpected error: {e.__class__.__name__}")

    try:
        text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        answer = "".join(text_parts).strip()
    except Exception as e:
        log.exception("chat: response extraction failed")
        return ChatResponse(answer="", error="Couldn't parse AI response.")

    return ChatResponse(answer=answer or "(no response)", error=None)
