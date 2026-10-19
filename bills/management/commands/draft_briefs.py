from django.core.management.base import BaseCommand

from bills.briefs import draft_missing_briefs


class Command(BaseCommand):
    help = "Draft briefs for this week's final-stage bills that don't have one yet."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **opts):
        for bill, brief, note in draft_missing_briefs(opts["days"]):
            label = f"draft {brief.id}" if brief else "skipped"
            self.stdout.write(f"{bill}: {label} ({note})")