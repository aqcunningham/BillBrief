import os
import re

import anthropic
import requests
from django.core.management.base import BaseCommand, CommandError

from bills.models import Bill, Brief
from bills.status import facts_as_of

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
        raise CommandError(
            "Claude answered without calling save_brief. "
            f"Stop reason: {response.stop_reason}. Try running it again."
        )
    return tool_calls[0].input


class Command(BaseCommand):
    help = "Create a draft brief version for a bill: facts from code, explanation from Claude."

    def add_arguments(self, parser):
        parser.add_argument("--bill", required=True, help="e.g. S-283 or HR-131")
        parser.add_argument("--congress", type=int, default=119)
        parser.add_argument("--rewrite", action="store_true",
                            help="Ask Claude for a new explanation even if the CRS summary is unchanged")

    def handle(self, *args, **opts):
        bill_type, number = opts["bill"].upper().split("-")
        try:
            bill = Bill.objects.get(congress=opts["congress"], bill_type=bill_type, number=int(number))
        except Bill.DoesNotExist:
            raise CommandError(f"{opts['bill']} not found. Run sync_bills first.")
        as_of = bill.actions.order_by("-action_date").values_list("action_date", flat=True).first()
        if as_of is None:
            raise CommandError(f"{bill} has no actions yet. Run sync_bills first.")
        stage, status_text, whats_next = facts_as_of(bill, as_of)

        crs_summary, crs_version = fetch_crs_summary(bill)
        previous = (
            bill.briefs.filter(status=Brief.Status.APPROVED)
            .order_by("-created_at")
            .first()
        )
        if previous and previous.crs_version == crs_version and not opts["rewrite"]:
            reused = True
            data = {
                "summary": previous.summary,
                "why_it_matters": previous.why_it_matters,
                "who_is_affected": previous.who_is_affected,
            }
            model_name = previous.model_name
        else:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise CommandError("Set ANTHROPIC_API_KEY in your .env")
            reused = False
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

        self.stdout.write(self.style.SUCCESS(f"Draft brief {brief.id} created for {bill}"))
        self.stdout.write(f"  As of: {as_of}")
        self.stdout.write(f"  CRS summary: {crs_version or 'none'}")
        self.stdout.write(f"  Explanation: {'reused from brief ' + str(previous.id) if reused else 'written by Claude'}")
        self.stdout.write(f"  Stage (code): {stage}")
        self.stdout.write(f"  Status (code): {status_text}")
        self.stdout.write(f"  What's next (code): {whats_next or '-'}")
        self.stdout.write(f"  Summary: {data['summary']}")
        self.stdout.write(f"  Why it matters: {data['why_it_matters']}")
        self.stdout.write(f"  Who's affected: {', '.join(data['who_is_affected'])}")
