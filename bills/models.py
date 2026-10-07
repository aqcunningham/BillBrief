from django.db import models


class Member(models.Model):
    """A member of Congress, keyed by their Bioguide ID from Congress.gov."""

    bioguide_id = models.CharField(max_length=10, unique=True)
    full_name = models.CharField(max_length=200)
    party = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=2, blank=True)

    def __str__(self):
        return self.full_name


class Bill(models.Model):
    """A bill, identified by congress + type + number (e.g. 119 HR 1234)."""

    congress = models.PositiveSmallIntegerField()
    bill_type = models.CharField(max_length=10)  # HR, S, HJRES, SRES, ...
    number = models.PositiveIntegerField()
    title = models.TextField()
    origin_chamber = models.CharField(max_length=20, blank=True)
    policy_area = models.CharField(max_length=200, blank=True)
    introduced_date = models.DateField(null=True, blank=True)
    latest_action_date = models.DateField(null=True, blank=True)
    latest_action_text = models.TextField(blank=True)
    sponsor = models.ForeignKey(
        Member,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sponsored_bills",
    )
    api_update_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["congress", "bill_type", "number"], name="unique_bill"
            )
        ]
        ordering = ["-latest_action_date"]

    def __str__(self):
        return f"{self.bill_type} {self.number} ({self.congress}th)"

    @property
    def slug(self):
        return f"{self.congress}-{self.bill_type.lower()}-{self.number}"


class Action(models.Model):
    """One step in a bill's history: introduced, referred, passed, etc.
    New Action rows are what change tracking will hook into later."""

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="actions")
    action_date = models.DateField()
    text = models.TextField()
    action_type = models.CharField(max_length=100, blank=True)
    action_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["bill", "action_date", "text"], name="unique_action"
            )
        ]
        ordering = ["-action_date"]

    def __str__(self):
        return f"{self.action_date}: {self.text[:60]}"