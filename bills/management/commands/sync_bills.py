import os
import time
from datetime import datetime, timedelta, timezone

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

from bills.models import Action, Bill, Member

API_BASE = "https://api.congress.gov/v3"

class CongressClient:
    """Thin wrapper around the Congress.gov v3 API."""

    def __init__(self, api_key):
        self.session = requests.Session()
        self.session.params = {"api_key": api_key, "format": "json"}

    def get(self, path, **params):
        resp = self.session.get(f"{API_BASE}{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()


class Command(BaseCommand):
    help = "Sync recently updated bills, sponsors, and actions from Congress.gov"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=3, help="Look back N days")
        parser.add_argument("--limit", type=int, default=50, help="Max bills to sync")
        parser.add_argument("--congress", type=int, default=119, help="Congress number")

    def handle(self, *args, **opts):
        api_key = os.environ.get("CONGRESS_API_KEY")
        if not api_key:
            raise CommandError("Set CONGRESS_API_KEY in your environment or .env")

        client = CongressClient(api_key)
        since = datetime.now(timezone.utc) - timedelta(days=opts["days"])
        listing = client.get(
            # "/bill",
            f"/bill/{opts['congress']}",
            fromDateTime=since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            limit=opts["limit"],
        )

        bills = listing.get("bills", [])
        self.stdout.write(f"Found {len(bills)} bills updated since {since:%Y-%m-%d}")

        for item in bills:
            try:
                self.sync_bill(client, item)
            except requests.HTTPError as exc:
                self.stderr.write(f"Skipped {item.get('type')} {item.get('number')}: {exc}")
            time.sleep(0.2)  # stay polite; the API allows ~5,000 requests/hour

    def sync_bill(self, client, item):
        congress = item["congress"]
        bill_type = item["type"].upper()
        number = int(item["number"])
        path = f"/bill/{congress}/{bill_type.lower()}/{number}"

        detail = client.get(path)["bill"]
        actions = client.get(f"{path}/actions", limit=250).get("actions", [])

        with transaction.atomic():
            sponsor = None
            sponsors = detail.get("sponsors") or []
            if sponsors:
                s = sponsors[0]
                sponsor, _ = Member.objects.update_or_create(
                    bioguide_id=s["bioguideId"],
                    defaults={
                        "full_name": s.get("fullName", ""),
                        "party": s.get("party", ""),
                        "state": s.get("state", ""),
                    },
                )

            latest = detail.get("latestAction") or {}
            policy = detail.get("policyArea") or {}
            bill, created = Bill.objects.update_or_create(
                congress=congress,
                bill_type=bill_type,
                number=number,
                defaults={
                    "title": detail.get("title", ""),
                    "origin_chamber": detail.get("originChamber", ""),
                    "policy_area": policy.get("name", ""),
                    "introduced_date": parse_date(detail.get("introducedDate") or ""),
                    "latest_action_date": parse_date(latest.get("actionDate") or ""),
                    "latest_action_text": latest.get("text", ""),
                    "sponsor": sponsor,
                    "api_update_date": parse_datetime(detail.get("updateDate") or ""),
                },
            )

            new_actions = 0
            for a in actions:
                _, made = Action.objects.get_or_create(
                    bill=bill,
                    action_date=parse_date(a["actionDate"]),
                    text=a["text"],
                    defaults={
                        "action_type": a.get("type", ""),
                        "action_code": a.get("actionCode", ""),
                    },
                )
                new_actions += made

        status = "new" if created else "updated"
        self.stdout.write(f"  {bill} [{status}], {new_actions} new actions")