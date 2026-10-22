from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Daily job: sync from Congress.gov, then draft briefs for new final-stage bills."

    def handle(self, *args, **opts):
        self.stdout.write("1/2 Syncing bills…")
        call_command("sync_bills", days=2)
        self.stdout.write("2/2 Drafting briefs…")
        call_command("draft_briefs")
        self.stdout.write(self.style.SUCCESS("Daily update finished."))