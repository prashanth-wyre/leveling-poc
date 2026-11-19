def rank_bids(rows, template):
    """Competition rank for individual, eligible offers under the active policy."""
    field = {
        "Lowest submitted price": "Submitted",
        "Warranty-adjusted cost": "Adjusted",
        "Weighted best value": "Score",
    }.get(template, "Leveled")
    split = template == "Split or combined packages"
    eligible = [] if split else sorted(
        (row for row in rows if row["Status"] == "Eligible"),
        key=lambda row: row[field], reverse=field == "Score",
    )
    ranks = {}
    for position, row in enumerate(eligible, start=1):
        ranks.setdefault(row[field], position)
    for row in rows:
        if row["Status"] != "Eligible":
            row["Rank"] = "Unranked"
        elif split:
            row["Rank"] = "By package"
        else:
            row["Rank"] = ranks[row[field]]
    return field
