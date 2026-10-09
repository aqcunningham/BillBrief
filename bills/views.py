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
        },
    )