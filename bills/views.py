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

def tracker_steps(bill, stage):
    """Build the 5-step tracker. Order depends on which chamber the bill started in."""
    first, second = ("Senate", "House") if bill.origin_chamber == "Senate" else ("House", "Senate")
    labels = ["Introduced", f"Passed {first}", f"Passed {second}", "To President", "Became Law"]
    position = {
        "Passed one chamber": 1,
        "Resolving differences": 2,
        "Passed both chambers": 2,
        "Presented to President": 3,
        "Vetoed": 3,
        "Became law": 4,
    }.get(stage, 0)  # Introduced, committee, floor, failed → step 0
    return [{"label": label, "done": i < position, "current": i == position}
            for i, label in enumerate(labels)]

def bill_detail(request, slug):
    congress, bill_type, number = parse_slug(slug)
    bill = get_object_or_404(
        Bill.objects.select_related("sponsor"),
        congress=congress,
        bill_type=bill_type,
        number=number,
    )

    # Public pages only ever show APPROVED briefs.
    approved = bill.briefs.filter(status=Brief.Status.APPROVED)
    overview = approved.filter(kind=Brief.Kind.OVERVIEW).first()
    change = approved.filter(kind=Brief.Kind.CHANGE).first()

    return render(
        request,
        "bills/bill_detail.html",
        {
            "bill": bill,
            "overview": overview,
            "change": change,
            "actions": bill.actions.order_by("-action_date"),
            "tracker": tracker_steps(bill, overview.stage if overview else ""),
        },
    )