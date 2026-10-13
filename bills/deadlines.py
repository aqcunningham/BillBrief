from datetime import timedelta


def president_deadline(presented_date):
    """10 days, Sundays excepted, counting from the day after presentment (Art. I, Sec. 7)."""
    day, counted = presented_date, 0
    while counted < 10:
        day += timedelta(days=1)
        if day.weekday() != 6:  # 6 = Sunday
            counted += 1
    return day