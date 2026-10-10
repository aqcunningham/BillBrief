from datetime import date, timedelta

from .models import Action

# Checked top to bottom: the first phrase that matches wins.
MILESTONES = [
    ("became public law", 100),
    ("signed by president", 100),
    ("presented to president", 90),
    ("resolving differences", 80),
    ("passed senate", 60),
    ("passed house", 60),
    ("passed/agreed to", 60),
    ("on passage passed", 60),
    ("cloture", 50),
    ("reported", 40),
    ("hearings held", 20),
]


def score_action(text):
    """How important is one action? Everything else is paperwork (5)."""
    t = text.lower()
    for phrase, points in MILESTONES:
        if phrase in t:
            return points
    return 5


def top_bills(days=7, limit=10):
    """Rank bills by their single most important action in the last N days."""
    since = date.today() - timedelta(days=days)
    best = {}  # bill_id -> (score, action)
    for action in Action.objects.filter(action_date__gte=since).select_related("bill"):
        score = score_action(action.text)
        if action.bill_id not in best or score > best[action.bill_id][0]:
            best[action.bill_id] = (score, action)
    ranked = sorted(best.values(), key=lambda pair: (pair[0], pair[1].action_date), reverse=True)
    return ranked[:limit]