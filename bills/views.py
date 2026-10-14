from django.shortcuts import render

# Create your views here.
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import Bill, Brief


def parse_slug(slug):
    """'119-s-283' -> (119, 'S', 283)."""
    try:
        congress, bill_type, number = slug.split("-")
        return int(congress), bill_type.upper(), int(number)
    except ValueError:
        raise Http404("Bill not found")

def tracker_position(bill, as_of=None):
    """Where the bill is, from its recorded actions up to `as_of`. No AI involved."""
    actions = bill.actions.all()
    if as_of:
        actions = actions.filter(action_date__lte=as_of)
    texts = [a.text.lower() for a in actions]

    def any_has(*phrases):
        return any(p in t for t in texts for p in phrases)

    if any_has("became public law"):
        return 4
    if any_has("presented to president", "vetoed"):
        return 3
    passed_house = any_has("passed house", "passed/agreed to in house", "on passage passed")
    passed_senate = any_has("passed senate", "passed/agreed to in senate")
    if passed_house and passed_senate:
        return 2
    if passed_house or passed_senate:
        return 1
    return 0


def tracker_steps(bill, as_of=None):
    """Build the 5-step tracker. Order depends on which chamber the bill started in."""
    first, second = ("Senate", "House") if bill.origin_chamber == "Senate" else ("House", "Senate")
    labels = ["Introduced", f"Passed {first}", f"Passed {second}", "To President", "Became Law"]
    position = tracker_position(bill, as_of)
    return [
        {"label": label, "done": i < position, "current": i == position}
        for i, label in enumerate(labels)
    ]


def bill_detail(request, slug):
    congress, bill_type, number = parse_slug(slug)
    bill = get_object_or_404(
        Bill.objects.select_related("sponsor"),
        congress=congress,
        bill_type=bill_type,
        number=number,
    )

    # Public pages only show the latest APPROVED brief, and only actions up to its as_of date.
    brief = bill.briefs.filter(status=Brief.Status.APPROVED).order_by("-created_at").first()
    as_of = brief.as_of if brief else None

    actions = bill.actions.order_by("-action_date")
    if as_of:
        actions = actions.filter(action_date__lte=as_of)

    return render(
        request,
        "bills/bill_detail.html",
        {
            "bill": bill,
            "brief": brief,
            "actions": actions,
            "tracker": tracker_steps(bill, as_of),
        },
    )