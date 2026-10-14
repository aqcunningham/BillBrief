from .deadlines import president_deadline

STAGES = ["Introduced", "Passed one chamber", "Passed both chambers",
          "Presented to President", "Became law"]


def facts_as_of(bill, as_of):
    """Stage, status and what's next, using only actions up to `as_of`."""
    actions = bill.actions.filter(action_date__lte=as_of).order_by("-action_date")
    texts = [a.text.lower() for a in actions]

    def latest(phrase):
        return actions.filter(text__icontains=phrase).first()

    if a := latest("became public law"):
        return "Became law", f"{a.text.rstrip('.')} on {a.action_date:%b. %-d, %Y}.", ""
    if a := latest("vetoed"):
        return ("Vetoed", f"Vetoed on {a.action_date:%b. %-d, %Y}.",
                "Congress can override with a two-thirds vote in both chambers.")
    if a := latest("presented to president"):
        due = president_deadline(a.action_date)
        return ("Presented to President",
                f"Presented to the President on {a.action_date:%b. %-d, %Y}.",
                f"The President has until {due:%A, %b. %-d, %Y}, to sign or veto it.")

    house = any("passed house" in t or "passed/agreed to in house" in t or "on passage passed" in t for t in texts)
    senate = any("passed senate" in t or "passed/agreed to in senate" in t for t in texts)
    stage = "Passed both chambers" if house and senate else "Passed one chamber" if house or senate else "Introduced"
    a = actions.first()
    return stage, (f"{a.text} ({a.action_date:%b. %-d, %Y})" if a else ""), ""