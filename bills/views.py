# Create your views here.
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import Bill, Brief
from datetime import date, timedelta
 
from .importance import top_bills
from .status import facts_as_of
 


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

# --- Add these below your existing views ---

PILL_CLASSES = {"Became law": "law", "Vetoed": "veto"}


def milestone_label(text):
    """Short bell label for a final-stage action."""
    t = text.lower()
    if "became public law" in t:
        return "Became law"
    if "vetoed" in t:
        return "Vetoed"
    if "presented to president" in t:
        return "Sent to the President"
    return text[:40]


def latest_approved(bill):
    return bill.briefs.filter(status=Brief.Status.APPROVED).order_by("-created_at").first()


def home(request):
    today = date.today()

    # 1. This week's final-stage bills (score 80+), each with its approved brief if there is one.
    cards = []
    for score, action in top_bills(days=7, limit=12, min_score=40):
        bill = action.bill
        stage, status_text, whats_next = facts_as_of(bill, action.action_date)
        cards.append({
            "bill": bill,
            "brief": latest_approved(bill),   # None -> card says "awaiting editor review"
            "stage": stage,
            "pill_class": PILL_CLASSES.get(stage, ""),
            "status_text": status_text,
            "whats_next": whats_next,
            "date": action.action_date,
            "tracker": tracker_steps(bill, action.action_date),   # new
            "recent_action": bill.actions.filter(action_date__lte=action.action_date).order_by("-action_date")[:4],
        })

    # 2. Recently published briefs: newest approved brief per bill.
    recent, seen = [], set()
    approved = (Brief.objects.filter(status=Brief.Status.APPROVED)
                .select_related("bill").order_by("-created_at"))
    for brief in approved:
        if brief.bill_id not in seen:
            seen.add(brief.bill_id)
            recent.append(brief)
        if len(recent) == 10:
            break

    # 3. Bell: final-stage milestones from the last 30 days, newest first. Facts only, no AI text.
    alerts = [
        {"bill": a.bill, "label": milestone_label(a.text), "date": a.action_date}
        for _, a in top_bills(days=30, limit=5, min_score=80)
    ]
    alerts.sort(key=lambda x: x["date"], reverse=True)

    return render(request, "bills/home.html", {
        "cards": cards,
        "recent": recent,
        "alerts": alerts,
        "today": today,
        "week_start": today - timedelta(days=7),
                "law_count": sum(c["stage"] == "Became law" for c in cards),
                "president_count": sum(c["stage"] == "Presented to President" for c in cards),
                "approved_count": sum(c["brief"] is not None for c in cards),
            })
