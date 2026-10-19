"""Brief generation, shared by the generate_briefs command and the editor desk.

Facts (stage, status, what's next) come from code. Claude writes only the explanation,
and only when the CRS summary has changed since the last approved brief.
"""
import os
import re

import anthropic
import requests

from .models import Brief
from .status import facts_as_of

CONGRESS_API = "https://api.congress.gov/v3"
MODEL = os.environ.get("BRIEF_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = """You write short, plain-language explanations of bills in the U.S. Congress
for busy policy professionals. Your style is scannable and neutral, like a good
newsroom briefing: short sentences, no jargon, no opinions, no partisan framing.

Rules:
- Use ONLY the information provided (title, sponsor, CRS summary, action timeline).
- Never invent numbers, names, dollar amounts, or effects that the input does not support.
- If the input does not say something, leave it out rather than guessing.
- Describe what the measure does, not whether it is good or bad.
- Explain what the measure does, not where it is in the process. Status is handled separately.
- Refer to it by its short title or as "the measure", not "the bill" or "the law",
  because this explanation is reused as the measure moves through Congress.
- Write for readers. Never mention "the input", "the data", or what information is missing.
- Always respond by calling the save_brief tool."""

BRIEF_TOOL = {
    "name": "save_brief",
    "description": "Save a structured explanation of a bill.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "At most 2 short sentences (under 45 words total): what the measure does, in plain language. Spell out acronyms.",
            },
            "why_it_matters": {
                "type": "string",
                "description": "1 to 2 sentences on the real-world impact for a policy reader. Do not repeat the summary.",
            },
            "who_is_affected": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2 to 4 short labels, each 2 to 5 words, one group per item (e.g. 'Commercial fishers').",
            },
        },
        "required": ["summary", "why_it_matters", "who_is_affected"],
    },
}


class BriefError(Exception):
    """Something stopped a draft from being created. The message is safe to show an editor."""


def fetch_crs_summary(bill):
    """Return (text, version) for the latest CRS summary, or ("", "") if there is none."""
    api_key = os.environ.get("CONGRESS_API_KEY")
    url = f"{CONGRESS_API}/bill/{bill.congress}/{bill.bill_type.lower()}/{bill.number}/summaries"
    resp = requests.get(url, params={"api_key": api_key, "format": "json"}, timeout=30)
    resp.raise_for_status()
    summaries = resp.json().get("summaries", [])
    if not summaries:
        return "", ""
    latest = summaries[-1]
    text = re.sub(r"<[^>]+>", " ", latest.get("text", "")).strip()  # strip HTML tags
    version = f'{latest.get("actionDesc", "")} ({latest.get("actionDate", "")})'
    return text, version


def build_bill_context(bill, crs_summary, as_of):
    lines = [
        f"Bill: {bill.bill_type} {bill.number} ({bill.congress}th Congress)",
        f"Title: {bill.title}",
        f"Sponsor: {bill.sponsor or 'Unknown'}",
        f"Policy area: {bill.policy_area or 'Not listed'}",
        "CRS summary:",
        crs_summary or "(No CRS summary available yet.)",
        "",
        "Action timeline (oldest first):",
    ]
    for a in bill.actions.filter(action_date__lte=as_of).order_by("action_date"):
        lines.append(f"- {a.action_date}: {a.text}")
    return "\n".join(lines)


def write_explanation(bill, crs_summary, as_of):
    """One AI call: returns summary, why_it_matters, who_is_affected."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise BriefError("Set ANTHROPIC_API_KEY in your .env")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[BRIEF_TOOL],
        tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": build_bill_context(bill, crs_summary, as_of)}],
    )
    tool_calls = [b for b in response.content if b.type == "tool_use"]
    if not tool_calls:
        raise BriefError(
            "Claude answered without calling save_brief. "
            f"Stop reason: {response.stop_reason}. Try again."
        )
    return tool_calls[0].input


def create_draft(bill, rewrite=False):
    """Create one draft brief version for `bill`.

    Returns (brief, reused): `reused` is True when the explanation was copied from the
    last approved brief because the CRS summary hasn't changed (no AI call).
    """
    as_of = bill.actions.order_by("-action_date").values_list("action_date", flat=True).first()
    if as_of is None:
        raise BriefError(f"{bill} has no actions yet. Run sync_bills first.")
    stage, status_text, whats_next = facts_as_of(bill, as_of)

    crs_summary, crs_version = fetch_crs_summary(bill)
    previous = (
        bill.briefs.filter(status=Brief.Status.APPROVED)
        .order_by("-created_at")
        .first()
    )
    reused = bool(previous and previous.crs_version == crs_version and not rewrite)
    if reused:
        data = {
            "summary": previous.summary,
            "why_it_matters": previous.why_it_matters,
            "who_is_affected": previous.who_is_affected,
        }
        model_name = previous.model_name
    else:
        data = write_explanation(bill, crs_summary, as_of)
        model_name = MODEL

    brief = Brief.objects.create(
        bill=bill,
        summary=data["summary"],
        why_it_matters=data["why_it_matters"],
        who_is_affected=data["who_is_affected"],
        policy_area=bill.policy_area,
        stage=stage,
        as_of=as_of,
        crs_version=crs_version,
        status_text=status_text,
        whats_next=whats_next,
        model_name=model_name,
        reused_from=previous if reused else None,
    )
    return brief, reused