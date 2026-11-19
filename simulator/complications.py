"""Optional project fixtures. Compile a draft into evidence before calculating awards."""

import math
from copy import deepcopy

# Each package reference names a stable code. Item references use that package's IDs.
OPTIONS = {
    "Shared scope across trades": {
        "demolition": "02.45",
        "earthwork": "31.00",
        "item": "I04",
        "arrangement": "Earthwork only",
        "exception_trade": "Earthwork",
        "exception_firm": "",
        "gap_action": "Request clarification",
        "gc_allowance": 15000.0,
        "overlap_action": "Request clarification",
        "confirmed_credit": 10000.0,
    },
    "Ambiguous inclusion or price": {
        "package": "32.90",
        "item": "I03",
        "statement": "Included",
    },
    "Low partial bid": {
        "package": "09.67",
        "item": "I04",
        "disposition": "Document allowance",
        "allowance": 60000.0,
    },
    "Cost reconciliation": {
        "package": "09.67",
        "post_bid": 1250.0,
        "tax": 800.0,
        "sdi": 2400.0,
        "completion": 3200.0,
    },
    "Base scope and alternates": {
        "package": "26.00",
        "item": "I03",
        "second_package": "27.30",
        "electrical_amount": 157670.0,
        "communications_amount": 12000.0,
        "disposition": "Pending",
    },
    "Component warranties": {
        "package": "12.20",
        "fabric_years": 25,
        "fabric_offer": "Accepted",
        "qualified_fabric_years": 15,
        "motor_years": 10,
        "motor_offer": "Qualified",
        "qualified_years": 5,
        "loss_component": "Motor",
    },
    "Early awards and estimate changes": {
        "package": "26.00",
        "earlier_estimate": 9800000.0,
        "release": 50000.0,
        "change": 12000.0,
        "disposition": "Accepted",
        "later_price": "Includes release",
    },
}
SHARED, AMBIG, PARTIAL, COST, ALT, WARRANTY, HISTORY = OPTIONS
CHOICES = {
    "gap_action": ["Request clarification", "Carry GC allowance"],
    "overlap_action": ["Request clarification", "Deduct confirmed credit"],
    "exception_trade": ["Earthwork", "Demolition"],
    "arrangement": [
        "Earthwork only",
        "Demolition only",
        "Both",
        "Neither",
        "Split excavation and backfill",
    ],
    "statement": ["Included", "Blank", "Explicit zero", "x65000"],
    "fabric_offer": ["Accepted", "Qualified", "Silent"],
    "motor_offer": ["Accepted", "Qualified", "Silent"],
    "loss_component": ["Motor", "Fabric"],
    "later_price": ["Includes release", "Excludes release", "Unstated"],
    "disposition": ["Accepted", "Pending", "Declined"],
}
QUESTIONS = dict(
    zip(
        OPTIONS,
        [
            "Who carries backfill, and how many times is it counted?",
            "What did the bidder actually state for the item?",
            "Is the low flooring offer eligible, and what allowance supports its rank?",
            "How does the submitted price reconcile to the package value?",
            "Which alternate contributions enter the project total?",
            "Which component warranty meets the requirement and covers the modeled loss?",
            "How much was committed earlier and how much remains?",
        ],
    )
)


def choices(name, field):
    if name == PARTIAL and field == "disposition":
        return ["Document allowance", "Needs clarification"]
    return CHOICES.get(field)


def compile_draft(project):
    packages = deepcopy(project["packages"])
    lookup = {p["code"]: p for p in packages}
    coverage_edits = {}
    for name, config in project.get("complications", {}).items():
        try:
            settings = OPTIONS[name] | config
            for field, default in OPTIONS[name].items():
                value = settings[field]
                allowed = choices(name, field)
                if allowed and value not in allowed:
                    raise ValueError(f"Choose a listed {field}.")
                if isinstance(default, (float, int)) and (
                    not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or (
                        value < 0
                        and field
                        not in ("change", "electrical_amount", "communications_amount")
                    )
                ):
                    raise ValueError(f"Invalid {field}.")
            refs = [
                settings[k]
                for k in ("package", "demolition", "earthwork", "second_package")
                if k in settings
            ]
            if len(refs) != len(set(refs)):
                raise ValueError("Choose distinct packages.")
            for code in refs:
                p = lookup[code]
                if (
                    p.get("treatment", "Solicit bids") != "Solicit bids"
                    or not p["bidders"]
                ):
                    raise ValueError(
                        f"{code} needs an active bid package with invitees."
                    )
            if name in (AMBIG, PARTIAL, SHARED):
                code = settings.get("package", settings.get("earthwork"))
                items = (
                    [i["id"] for i in lookup[code]["items"]]
                    if name == PARTIAL
                    else [settings["item"]]
                )
                for item in items:
                    prior = coverage_edits.get((code, item))
                    if prior:
                        raise ValueError(
                            f"{prior} also controls {code}/{item}. Choose distinct scope items."
                        )
                    coverage_edits[code, item] = name
            configure(name, settings, lookup)
        except (KeyError, ValueError, IndexError) as exc:
            raise ValueError(
                f"{name}: repair the scenario settings or disable it. {exc}"
            ) from exc
    return packages


def configure(name, c, pkgs):
    p = pkgs[c.get("package", c.get("earthwork"))]

    def gc(pkg, detail):
        pkg.setdefault("instructions", []).append([name, detail])

    def claim(b, detail):
        b.setdefault("statements", []).append([name, detail])

    item = c.get("item")
    if item and item not in {i["id"] for i in p["items"]}:
        raise ValueError(f"Missing item {item} in {p['code']}.")
    bidders = p["bidders"]
    first = bidders[0]
    if name in (AMBIG, PARTIAL, WARRANTY) and (
        first["response"] not in ("Bid", "Revised", "Clarified")
        or first["match"] == "Unrelated"
    ):
        raise ValueError("The first invitee must submit a related firm quote.")
    if name == SHARED:
        arrangement = c["arrangement"]
        if c["exception_firm"] and c["exception_firm"] not in [
            b["firm"] for b in pkgs[c[c["exception_trade"].lower()]]["bidders"]
        ]:
            raise ValueError(
                "The exception firm must be invited to the selected trade."
            )
        for role in ("demolition", "earthwork"):
            pkg = pkgs[c[role]]
            gc(
                pkg,
                "BF-01: coordinate backfill of demolition excavation between both packages. Cross-package adjustments require documented GC disposition.",
            )
            if c["gap_action"] == "Carry GC allowance":
                gc(
                    pkg,
                    f"BF-01 project disposition: carry a GC allowance of USD {c['gc_allowance']:,.2f} once if neither selected proposal covers the work.",
                )
            if c["overlap_action"] == "Deduct confirmed credit":
                gc(
                    pkg,
                    f"BF-01 project disposition: deduct the agreed credit of USD {c['confirmed_credit']:,.2f} once if both selected proposals cover the work.",
                )
            for b in pkg["bidders"]:
                carries = (
                    arrangement == "Both"
                    or arrangement == role.title() + " only"
                    or (arrangement.startswith("Split") and role == "earthwork")
                )
                if (
                    role == c["exception_trade"].lower()
                    and b["firm"] == c["exception_firm"]
                ):
                    carries = not carries
                b["backfill"] = carries
                claim(
                    b,
                    "BF-01 backfill "
                    + (
                        "included in our base price."
                        if carries
                        else "excluded from our price."
                    ),
                )
                if arrangement.startswith("Split"):
                    claim(
                        b,
                        "BF-01 excavation "
                        + (
                            "included."
                            if role == "demolition"
                            else "by demolition contractor."
                        ),
                    )
                if role == "earthwork":
                    existing = b["coverage_map"][item]
                    if (
                        existing["status"] == "Included"
                        and existing["carrying"] in b["coverage_map"]
                    ):
                        carrier = b["coverage_map"][existing["carrying"]]
                        carrier["amount"] = max(
                            0, round(carrier["amount"] - existing["amount"], 2)
                        )
                    b["coverage_map"][item].update(
                        status="Priced" if carries else "Excluded", allowance=0
                    )
    elif name == AMBIG:
        v = first["coverage_map"][item]
        v.update(
            status={
                "Blank": "Not mentioned",
                "Included": "Included",
                "Explicit zero": "Priced",
                "x65000": "Ambiguous price",
            }[c["statement"]],
            carrying="",
            amount=0,
            raw=c["statement"],
        )
    elif name == PARTIAL:
        if len(bidders) < 2:
            raise ValueError("Invite a second firm for a comparable complete bid.")
        complete = bidders[1]["coverage_map"]
        for v in complete.values():
            if v["status"] == "Included" and v.get("carrying") in complete:
                carrier = complete[v["carrying"]]
                carrier["amount"] = max(0, round(carrier["amount"] - v["amount"], 2))
            v["status"] = "Priced"
        for k, v in first["coverage_map"].items():
            v.update(status="Priced", amount=round(v["amount"] * 0.55, 2))
        first["coverage_map"][item].update(
            status="Excluded",
            allowance=c["allowance"],
            unresolved=c["disposition"] == "Needs clarification",
        )
        gc(
            p,
            f"{item} exclusion by {first['firm']}: "
            + (
                "allowance unresolved."
                if c["disposition"] == "Needs clarification"
                else f"carry USD {c['allowance']:,.2f}."
            ),
        )
    elif name == COST:
        for b in bidders:
            for k in ("post_bid", "tax", "sdi", "completion"):
                b[k] = c[k]
        gc(
            p,
            "GC costs to complete are outside the subcontract. Apply once after tax and SDI.",
        )
    elif name == ALT:
        for pkg, field in [
            (p, "electrical_amount"),
            (pkgs[c["second_package"]], "communications_amount"),
        ]:
            gc(
                pkg,
                f"ALT-DAS expanded system: {c['disposition']}. Base testing and rough-in remains in {p['code']} item {item}.",
            )
            for b in pkg["bidders"]:
                b.setdefault("alternates", []).append(
                    {
                        "id": "ALT-DAS",
                        "description": "ALT-DAS expanded system contribution",
                        "amount": c[field],
                    }
                )
    elif name == WARRANTY:
        gc(
            p,
            f"Fabric minimum {c['fabric_years']} years; motor minimum {c['motor_years']} years. Model loss on {c['loss_component'].lower()}.",
        )
        for b in bidders:
            motor = c["motor_years"]
            if b is first and c["motor_offer"] != "Accepted":
                motor = (
                    c["qualified_years"] if c["motor_offer"] == "Qualified" else None
                )
            fabric = c["fabric_years"]
            if b is first and c["fabric_offer"] != "Accepted":
                fabric = (
                    c["qualified_fabric_years"]
                    if c["fabric_offer"] == "Qualified"
                    else None
                )
            b["component_years"] = {"Fabric": fabric, "Motor": motor}
            b["component_min"] = {
                "Fabric": c["fabric_years"],
                "Motor": c["motor_years"],
            }
            b["loss_component"] = c["loss_component"]
            for component, years in b["component_years"].items():
                if years is not None:
                    claim(b, f"{component} coverage: {years} years.")
    elif name == HISTORY:
        p["commitment_records"] = [
            [
                "2025-12-15",
                "Earlier GC estimate",
                c["earlier_estimate"],
                "Estimate only",
            ],
            ["2026-01-05", "ER-01 early release", c["release"], "Committed"],
            ["2026-01-10", "CO-01 change", c["change"], c["disposition"]],
        ]
        for b in bidders:
            claim(
                b,
                "2026-01-15 balance proposal. CO-01 outside submitted price."
                + {
                    "Includes release": " ER-01 is included.",
                    "Excludes release": " ER-01 excluded.",
                    "Unstated": "",
                }[c["later_price"]],
            )


def checks(run, summary, tallies):
    enabled = run["project"].get("complications", {})
    if not enabled:
        return []
    result = []
    awards = {s["Package"]: s for s in summary if s["Package"]}
    packages = run["packages"]
    adjustment = 0.0
    prior = 0.0
    unresolved = False

    def evidence(code, firm=None):
        docs = [
            d["file"]
            for d in run["files"]
            if d["package"] == code
            and (
                (firm and d["firm"] == firm and d["kind"] == "bid")
                or (not firm and not d["firm"])
            )
        ]
        return ", ".join(docs)

    for name, config in enabled.items():
        c = OPTIONS[name] | config
        code = c.get("package", c.get("earthwork"))
        s = packages[code]

        def add(answer, source, state="Expected", name=name):
            result.append(
                {
                    "Scenario": name,
                    "Question": QUESTIONS[name],
                    "Result": state,
                    "Answer": answer,
                    "Evidence": source,
                }
            )

        def selected(k):
            return next(
                (
                    b
                    for b in packages[k]["bidders"]
                    if b["firm"] == awards[k]["Expected award"]
                ),
                None,
            )

        if name in (SHARED, ALT):
            refs = (
                [c["demolition"], code]
                if name == SHARED
                else [code, c["second_package"]]
            )
            bids = [selected(k) for k in refs]
            if any(b is None for b in bids):
                add(
                    "Select a single award per affected package to reconcile responsibility.",
                    ", ".join(f"gc/{k}/Award policy.txt" for k in refs),
                    "Needs clarification",
                )
                unresolved = True
                continue
            src = "; ".join(
                evidence(k, b["firm"]) + "; " + evidence(k) for k, b in zip(refs, bids)
            )
            if name == SHARED:
                carriers = [
                    f"{k} {b['firm']}" for k, b in zip(refs, bids) if b["backfill"]
                ]
                count = len(carriers)
                split = (
                    f" Excavation: {refs[0]} {bids[0]['firm']}."
                    if c["arrangement"].startswith("Split")
                    else ""
                )
                resolved = count == 1
                if count == 0 and c["gap_action"] == "Carry GC allowance":
                    adjustment += c["gc_allowance"]
                    split += f" GC allowance added once: {c['gc_allowance']:,.2f}."
                    resolved = True
                if count == 2 and c["overlap_action"] == "Deduct confirmed credit":
                    adjustment -= c["confirmed_credit"]
                    split += f" Confirmed credit deducted once: {c['confirmed_credit']:,.2f}."
                    resolved = True
                add(
                    f"BF-01 backfill: {count} {'carrier' if count == 1 else 'carriers'} ({', '.join(carriers) or 'none'})."
                    + split,
                    src + " · BF-01",
                    "Expected" if resolved else "Needs clarification",
                )
                unresolved |= not resolved
            else:
                values = [
                    next(
                        v["amount"] for v in b["alternates"] if v.get("id") == "ALT-DAS"
                    )
                    for b in bids
                ]
                delta = sum(values) if c["disposition"] == "Accepted" else 0
                adjustment += delta
                add(
                    f"ALT-DAS {c['disposition']}. Selected contributions {values[0]:,.2f} and {values[1]:,.2f}; project adjustment {delta:,.2f}. Base rough-in remains in {code}/{c['item']}.",
                    src + " · ALT-DAS",
                )
        elif name == HISTORY:
            row = awards[code]
            b = selected(code)
            release = c["release"]
            change = c["change"] if c["disposition"] == "Accepted" else 0
            prior += release
            src = evidence(code) + " · ER-01 / CO-01"
            if b:
                src += "; " + evidence(code, b["firm"])
            if not b or c["later_price"] == "Unstated":
                adjustment += change
                add(
                    f"Earlier commitment {release:,.2f}; accepted change {change:,.2f}. Remaining commitment unresolved.",
                    src,
                    "Needs clarification",
                )
                unresolved = True
            else:
                extra = change + (
                    release if c["later_price"] == "Excludes release" else 0
                )
                total = row["Package value"] + extra
                adjustment += extra
                add(
                    f"Earlier estimate {c['earlier_estimate']:,.2f}; current GC estimate {s['estimate']:,.2f}. Later leveled package {row['Package value']:,.2f}; accepted change {change:,.2f}; reconciled {total:,.2f}; committed {release:,.2f}; remaining {total - release:,.2f}.",
                    src,
                )
                if total < release:
                    unresolved = True
                    result[-1]["Result"] = "Needs clarification"
        else:
            for b, r in zip(s["bidders"], tallies[code]):
                if name in (AMBIG, PARTIAL) and b is not s["bidders"][0]:
                    continue
                src = (
                    evidence(code, b["firm"])
                    + "; "
                    + evidence(code)
                    + "; gc/"
                    + code
                    + "/Award policy.txt"
                )
                state = "Expected"
                if r["Submitted"] is None:
                    add(
                        f"{b['firm']}: {r['Status']}; no effective awardable offer.",
                        src,
                    )
                    continue
                if name == AMBIG:
                    answer = {
                        "Blank": "No response; coverage unresolved.",
                        "Included": "Included; carrying line unspecified.",
                        "Explicit zero": "Explicit USD 0.00 price.",
                        "x65000": "Literal x65000; numeric price unresolved.",
                    }[c["statement"]]
                    if c["statement"] != "Explicit zero":
                        state = "Needs clarification"
                elif name == PARTIAL:
                    answer = (
                        f"{b['firm']}: {r['Status']}; rank {r['Rank']}; submitted {r['Submitted']}; allowance "
                        + (
                            "unresolved"
                            if c["disposition"] == "Needs clarification"
                            else str(b["plug"])
                        )
                        + "."
                    )
                    if r["Status"].startswith("Clarify"):
                        state = "Needs clarification"
                elif name == COST:
                    answer = (
                        f"{b['firm']}: submitted {r['Submitted']} + allowances {r['Plug']} + post-bid {r['post_bid']} = subcontract {r['Subcontract value']}; + tax {r['tax']} + SDI {r['sdi']} + GC completion {b['completion']} = package {r['Total package value']}."
                        if r["Submitted"] is not None
                        else f"{b['firm']}: {r['Status']}."
                    )
                else:
                    parts = []
                    for component, years in b["component_years"].items():
                        minimum = b["component_min"][component]
                        verdict = (
                            "unstated"
                            if years is None
                            else ("meets" if years >= minimum else "below")
                        )
                        parts.append(
                            f"{component}: {years if years is not None else 'unknown'} years ({verdict} minimum {minimum})"
                        )
                    answer = (
                        b["firm"]
                        + " — "
                        + ", ".join(parts)
                        + f". Loss component {b['loss_component']}; status {r['Status']}."
                    )
                    if "Exposure" in r:
                        answer += f" Expected exposure {r['Exposure']}; adjusted {r['Adjusted']}."
                    if None in b["component_years"].values():
                        state = "Needs clarification"
                add(answer, src + " · " + str(c.get("item", name)), state)
    subtotal = sum(row["Package value"] or 0 for row in awards.values())
    allowance = sum(row["GC estimate"] or 0 for row in summary if not row["Package"])
    unresolved |= any(row["Package value"] is None for row in awards.values())
    total = subtotal + allowance + adjustment
    result.append(
        {
            "Scenario": "Project reconciliation",
            "Question": "How much is carried and how much remains?",
            "Result": "Needs clarification" if unresolved else "Expected",
            "Answer": f"Known package values {subtotal:,.2f} + project allowances {allowance:,.2f} + documented scenario adjustments {adjustment:,.2f} = {total:,.2f}. Earlier commitments {prior:,.2f}. "
            + (
                "Final balance unresolved."
                if unresolved
                else f"Remaining {total - prior:,.2f}."
            ),
            "Evidence": "Package tallies, GC award policies and scenario records above.",
        }
    )
    return result
