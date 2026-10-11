from datetime import date, timedelta

from .models import Action

# Checked top to bottom: the first phrase that matches wins.
TYPE_SCORES = {
    "BecameLaw": 100,
    "President": 90,
    "Veto": 90,
    "ResolvingDifferences": 80,
    "Calendars": 5,
    "IntroReferral": 5
}


def score_action(action):
    """How important is one action? Everything else is paperwork (5)."""
    t = action.text.lower()
    if "became public law" in t:
        return 100
    if "presented to president" in t:
        return 90
    if "vetoed" in t:
        return 90
    
    if action.action_type == "Floor":
        if "failed" in t or "not agreed to" in t:
            return 30           # a vote happened, but it lost
        if "passed" in t or "agreed to" in t:
            return 60
        if "cloture" in t:
            return 50
        return 30               # debate, motions

    if action.action_type == "Committee":
        if "reported" in t:
            return 40
        if "hearings" in t:
            return 20
        return 15               # markups, other committee steps

    return TYPE_SCORES.get(action.action_type, 5)

		
    # for phrase, points in TYPE_SCORES.items():
    #     if phrase in t:
    #         return points
    # return 5


def top_bills(days=7, limit=10, min_score=80):
    """The week's most important bills: top `limit`, only those scoring min_score or more."""
    since = date.today() - timedelta(days=days)
    best = {}  # bill_id -> (score, action)
    for action in Action.objects.filter(action_date__gte=since).select_related("bill"):
        score = score_action(action)
        if action.bill_id not in best or score > best[action.bill_id][0]:
            best[action.bill_id] = (score, action)
    qualified = [pair for pair in best.values() if pair[0] >= min_score]
    ranked = sorted(qualified, key=lambda pair: (pair[0], pair[1].action_date), reverse=True)
    return ranked[:limit]
