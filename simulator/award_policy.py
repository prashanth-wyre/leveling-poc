def policy_text(policy):
    clauses = [
        [policy["label"], policy["template"]],
        ["Exclude unrelated bids, declines, budget quotes, and withdrawals."],
        [
            f"Seek clarification when price / GC estimate is outside {policy['low']} to {policy['high']}."
        ],
        [f"Minimum warranty: {policy['min_years']} years."],
    ]
    rule = {
        "Lowest submitted price": "Rank eligible bids by submitted price.",
        "Lowest eligible leveled cost": "Rank eligible bids by leveled cost including scope plugs.",
        "Budget ceiling": f"Apply a USD {policy['budget']} ceiling, then minimize leveled cost.",
        "Schedule priority": f"Require completion within {policy['deadline']} days, then minimize leveled cost.",
        "Weighted best value": f"Weight relative lowest cost at {policy['weight']} percent and relative fastest duration for the balance.",
        "Best value within window": f"Shortlist all eligible bidders within {policy['window']} percent of the lowest leveled cost.",
        "Split or combined packages": "Minimize combined package price, cover all lots exactly once and honor bundle conditions.",
        "Warranty-adjusted cost": f"Minimize leveled cost plus expected retained repair cost for {policy['beneficiary']}. Claim probability {policy['probability']} in year {policy['event_year']}, repair cost USD {policy['repair']}, requiring {policy['event_coverage']}. Apply coverage caps and deductibles.",
    }
    return "\n".join(str(row[0]) for row in clauses)+"\n"+rule[policy["template"]]+"\n"

