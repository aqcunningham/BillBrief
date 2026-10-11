from django.core.management.base import BaseCommand

from bills.importance import top_bills


class Command(BaseCommand):
    help = "Rank bills by their most important action in the last N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--min_score", type=int, default=80)

    def handle(self, *args, **opts):
        results = top_bills(opts["days"], opts["limit"], opts["min_score"])
        results = sorted(results, key=lambda pair: pair[1].action_date, reverse=True)
        for score, action in results:
            self.stdout.write(f"{action.action_date}  {score:>3}  {action.bill}  {action.text[:80]}")