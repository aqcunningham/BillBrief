from django.core.management.base import BaseCommand

from bills.importance import top_bills


class Command(BaseCommand):
    help = "Rank bills by their most important action in the last N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **opts):
        for score, action in top_bills(opts["days"], opts["limit"]):
            self.stdout.write(f"{score:>3}  {action.action_date}  {action.bill}  {action.text[:80]}")