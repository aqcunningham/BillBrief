import os
import re

import anthropic
import requests
from django.core.management.base import BaseCommand, CommandError

from bills.models import Bill, Brief

CONGRESS_API = "https://api.congress.gov/v3"
MODEL = os.environ.get("BRIEF_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = """You write short, plain-language briefs about bills in the U.S. Congress
for busy policy professionals. Your style is scannable and neutral, like a good
newsroom briefing: short sentences, no jargon, no opinions, no partisan framing.

Rules:
- Use ONLY the information provided (title, sponsor, CRS summary, action timeline).
- Never invent numbers, names, dollar amounts, or effects that the input does not support.
- If the input does not say something, leave it out rather than guessing.
- Describe what the bill does, not whether it is good or bad.
- Always respond by calling the save_brief tool."""

BRIEF_TOOL = {
    "name": "save_brief",
    "description": "Save a structured brief for a bill.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "One or two sentences: what the bill does, in plain language.",
            },
            "why_it_matters": {
                "type": "string",
                "description": "One or two sentences on why a policy reader should care.",
            },
            "who_is_affected": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2 to 4 groups, sectors, or regions directly affected.",
            },
            "stage": {
                "type": "string",
                "enum": [
                    "Introduced",
                    "In committee",
                    "Passed committee",
                    "Passed one chamber",
                    "Passed both chambers",
                    "Presented to President",
                    "Became law",
                    "Vetoed",
                ],
            },
            "latest_change": {
                "type": "string",
                "description": "One sentence on the most recent action and what it means.",
            },
            "whats_next": {
                "type": "string",
                "description": "One sentence on the next step in the process.",
            },
        },
        "required": [
            "summary",
            "why_it_matters",
            "who_is_affected",
            "stage",
            "latest_change",
            "whats_next",
        ],
    },
}


def fetch_crs_summary(bill):
    """Return the latest Congressional Research Service summary as plain text, or ''."""
    api_key = os.environ.get("CONGRESS_API_KEY")
    url = f"{CONGRESS_API}/bill/{bill.congress}/{bill.bill_type.lower()}/{bill.number}/summaries"
    resp = requests.get(url, params={"api_key": api_key, "format": "json"}, timeout=30)
    resp.raise_for_status()
    summaries = resp.json().get("summaries", [])
    if not summaries:
        return ""
    latest = summaries[-1].get("text", "")
    return re.sub(r"<[^>]+>", " ", latest).strip()  # strip HTML tags


def build_bill_context(bill, crs_summary):
    lines = [
        f"Bill: {bill.bill_type} {bill.number} ({bill.congress}th Congress)",
        f"Title: {bill.title}",
        f"Sponsor: {bill.sponsor or 'Unknown'}",
        f"Policy area: {bill.policy_area or 'Not listed'}",
        "",
        "CRS summary:",
        crs_summary or "(No CRS summary available yet.)",
        "",
        "Action timeline (oldest first):",
    ]
    for a in bill.actions.order_by("action_date"):
        lines.append(f"- {a.action_date}: {a.text}")
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Generate draft AI briefs for bills using the Claude API"

    def add_arguments(self, parser):
        parser.add_argument("--bill", required=True, help="e.g. S-283 or HR-131")
        parser.add_argument("--congress", type=int, default=119)

    def handle(self, *args, **opts):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise CommandError("Set ANTHROPIC_API_KEY in your .env")

        bill_type, number = opts["bill"].upper().split("-")
        try:
            bill = Bill.objects.get(
                congress=opts["congress"], bill_type=bill_type, number=int(number)
            )
        except Bill.DoesNotExist:
            raise CommandError(f"{opts['bill']} not found. Run sync_bills first.")

        crs_summary = fetch_crs_summary(bill)
        context = build_bill_context(bill, crs_summary)

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[BRIEF_TOOL],
            tool_choice={"type": "tool", "name": "save_brief"},
            messages=[{"role": "user", "content": context}],
        )

        data = next(b.input for b in response.content if b.type == "tool_use")

        overview = Brief.objects.create(
            bill=bill,
            kind=Brief.Kind.OVERVIEW,
            summary=data["summary"],
            why_it_matters=data["why_it_matters"],
            who_is_affected=data["who_is_affected"],
            policy_area=bill.policy_area,
            stage=data["stage"],
            model_name=MODEL,
        )
        change = Brief.objects.create(
            bill=bill,
            kind=Brief.Kind.CHANGE,
            summary=data["latest_change"],
            why_it_matters=data["whats_next"],
            who_is_affected=data["who_is_affected"],
            policy_area=bill.policy_area,
            stage=data["stage"],
            model_name=MODEL,
        )

        self.stdout.write(self.style.SUCCESS(f"Draft briefs created for {bill}"))
        self.stdout.write(f"  CRS summary used: {'yes' if crs_summary else 'no'}")
        self.stdout.write(f"  Stage: {data['stage']}")
        self.stdout.write(f"  Summary: {data['summary']}")
        self.stdout.write(f"  Why it matters: {data['why_it_matters']}")
        self.stdout.write(f"  Who's affected: {', '.join(data['who_is_affected'])}")
        self.stdout.write(f"  What changed: {data['latest_change']}")
        self.stdout.write(f"  What's next: {data['whats_next']}")
        self.stdout.write(f"  Brief IDs: overview={overview.id}, change={change.id}")