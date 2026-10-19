from django.core.management.base import BaseCommand, CommandError

from bills.briefs import BriefError, create_draft
from bills.models import Bill


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

        try:
            brief, reused = create_draft(bill, rewrite=opts["rewrite"])
        except BriefError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(f"Draft brief {brief.id} created for {bill}"))
        self.stdout.write(f"  As of: {brief.as_of}")
        self.stdout.write(f"  CRS summary: {brief.crs_version or 'none'}")
        self.stdout.write(f"  Explanation: {'reused from brief ' + str(brief.reused_from_id) if reused else 'written by Claude'}")
        self.stdout.write(f"  Stage (code): {brief.stage}")
        self.stdout.write(f"  Status (code): {brief.status_text}")
        self.stdout.write(f"  What's next (code): {brief.whats_next or '-'}")
        self.stdout.write(f"  Summary: {brief.summary}")
        self.stdout.write(f"  Why it matters: {brief.why_it_matters}")
        self.stdout.write(f"  Who's affected: {', '.join(brief.who_is_affected)}")