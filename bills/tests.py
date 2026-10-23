from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .deadlines import president_deadline
from .importance import score_action
from .models import Action, Bill, Brief, Member


class PresidentDeadlineTests(TestCase):
    """10 days, Sundays excepted, counting from the day after presentment."""

    def test_presented_monday_oct_5(self):
        self.assertEqual(president_deadline(date(2026, 10, 5)), date(2026, 10, 16))

    def test_presented_wednesday_oct_14_skips_two_sundays(self):
        self.assertEqual(president_deadline(date(2026, 10, 14)), date(2026, 10, 26))


class ScoringTests(TestCase):
    """Final-stage milestones are found by text, because Congress.gov's types don't match them."""

    def score(self, text, action_type):
        return score_action(Action(text=text, action_type=action_type))

    def test_became_law_is_100(self):
        self.assertEqual(self.score("Became Public Law No: 119-121.", "President"), 100)
        
    def test_signed_by_president_counts_as_law(self):
            self.assertEqual(self.score("Signed by President.", "President"), 100)

    def test_presented_to_president_is_90_even_though_typed_floor(self):
        self.assertEqual(self.score("Presented to President.", "Floor"), 90)

    def test_vetoed_is_90(self):
        self.assertEqual(self.score("Vetoed by President.", "Veto"), 90)

    def test_passed_one_chamber_is_below_the_80_cutoff(self):
        self.assertLess(self.score("Passed Senate without amendment by Unanimous Consent.", "Floor"), 80)

    

class DeskAccessTests(TestCase):
    """Only editors can open the desk."""

    def setUp(self):
        self.url = reverse("bills:desk")
        self.editor = User.objects.create_user("editor", password="pw-editor-123")
        self.editor.groups.add(Group.objects.create(name="Editors"))
        self.reader = User.objects.create_user("reader", password="pw-reader-123")

    def test_logged_out_goes_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_regular_user_is_blocked(self):
        self.client.login(username="reader", password="pw-reader-123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_editor_gets_in(self):
        self.client.login(username="editor", password="pw-editor-123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class DraftsStayPrivateTests(TestCase):
    """The public bill page shows approved briefs only."""

    def setUp(self):
        sponsor = Member.objects.create(bioguide_id="T000001", full_name="Sen. Test", party="I", state="DC")
        self.bill = Bill.objects.create(
            congress=119, bill_type="S", number=9999,
            title="Test Measure Act", origin_chamber="Senate", policy_area="Government Operations and Politics",
            introduced_date=date(2026, 1, 5),
            latest_action_date=date(2026, 10, 14), latest_action_text="Presented to President.",
            sponsor=sponsor, api_update_date=timezone.now(),
        )
        Action.objects.create(bill=self.bill, action_date=date(2026, 10, 14),
                              text="Presented to President.", action_type="Floor")
        self.url = reverse("bills:bill_detail", args=[self.bill.slug])

    def make_brief(self, summary, status):
        return Brief.objects.create(
            bill=self.bill, summary=summary, why_it_matters="Test.", who_is_affected=["Testers"],
            policy_area=self.bill.policy_area, stage="Presented to President",
            as_of=date(2026, 10, 14), status_text="Presented to the President on Oct. 14, 2026.",
            whats_next="", crs_version="Introduced in Senate (2026-01-05)", model_name="test",
            status=status,
        )

    def test_draft_is_not_shown(self):
        self.make_brief("SECRET DRAFT TEXT", Brief.Status.DRAFT)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "SECRET DRAFT TEXT")

    def test_rejected_is_not_shown(self):
        self.make_brief("REJECTED TEXT", Brief.Status.REJECTED)
        response = self.client.get(self.url)
        self.assertNotContains(response, "REJECTED TEXT")

    def test_approved_is_shown(self):
        self.make_brief("APPROVED TEXT", Brief.Status.APPROVED)
        response = self.client.get(self.url)
        self.assertContains(response, "APPROVED TEXT")