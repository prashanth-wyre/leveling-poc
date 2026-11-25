"""Author project-wide test evidence and build the independent TCJC-style tally."""

from copy import deepcopy
import csv
from io import BytesIO
from pathlib import Path
import math
import re
import tempfile
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import complications
import core
import styles
from award_policy import policy_text
from ranking import rank_bids

STATES = ["Priced", "Included", "Excluded", "Not mentioned"]
BID, GC_COST, REMOVED = "Solicit bids", "GC-carried cost", "Removed from project"
DEFAULT_POLICY = dict(
    template=core.POLICIES[0],
    label="Lowest eligible leveled cost",
    low=0.05,
    high=10.0,
    min_years=1.0,
    budget=550000.0,
    deadline=60.0,
    window=3.0,
    weight=70.0,
    event_year=5.0,
    probability=0.1,
    repair=100000.0,
    event_coverage="Labor and materials",
    beneficiary="Owner",
)


def new_bidder(name, items, index=0):
    b = deepcopy(core.preset("Roofing stress test")["bidders"][0])
    b.update(
        firm=name,
        format=core.FORMS[index % 3],
        scope="As itemized below",
        coverage_map={},
        post_bid=0.0,
        tax=0.0,
        sdi=0.0,
    )
    for item in items:
        b["coverage_map"][item["id"]] = cell(item, index)
    return b


def cell(item, index=0):
    amount = item["estimate"]
    return dict(
        status="Priced",
        amount=round((amount or 0) * (1 + 0.02 * index), 2),
        carrying="",
        allowance=None,
    )


def package(code, trade, specifications, firms):
    items = [
        dict(id=f"I{i + 1:02}", description=name, quantity=qty, unit=unit, estimate=est)
        for i, (name, qty, unit, est) in enumerate(specifications)
    ]
    return dict(
        code=code,
        trade=trade,
        items=items,
        bidders=[new_bidder(n, items, i) for i, n in enumerate(firms)],
        lots=[],
    )


def school_demo():
    firms = ["Alder Works", "Birch Assembly", "Cedar Group", "Dune Construction"]
    concrete = package(
        "03.30",
        "Cast-in-Place Concrete",
        [
            ("Tower crane pad", 1, "LS", 30000),
            ("Slab on grade", 9000, "SF", 180000),
            ("Concrete wall at control desk", 41, "LF", 21200),
        ],
        firms[:2],
    )
    electrical = package(
        "26.00",
        "Electrical",
        [
            ("Building electrical and lighting", 1, "LS", 310000),
            ("Site electrical and lighting", 1, "LS", 82000),
            ("BDA / First Responder DAS testing and rough-in", 1, "LS", 43475),
        ],
        firms,
    )
    landscape = package(
        "32.90",
        "Landscaping and Irrigation",
        [
            ("Backfilling and grading", 1, "LS", 6850),
            ("New irrigation", 13250, "SF", 19660),
            ("Irrigation sleeving", 160, "LF", 3500),
        ],
        firms[:2],
    )
    for b, state in zip(electrical["bidders"], STATES):
        b["coverage_map"]["I03"].update(
            status=state, carrying="I01" if state == "Included" else ""
        )
    landscape["bidders"][0]["coverage_map"]["I03"].update(
        status="Included", carrying="I02"
    )
    landscape["bidders"][1]["coverage_map"]["I03"]["amount"] = 3500
    return dict(name="School Expansion", packages=[concrete, electrical, landscape])


def starter():
    firms = ["Alder Works", "Birch Assembly", "Cedar Group", "Dune Construction"]
    packages = []
    with Path(__file__).with_name("tcjc_packages.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            estimate = float(row["estimate_usd"])
            names = row["representative_scope_items"].split(" | ")
            # Allocate the source total across editable fixture items. Keep the
            # fractional-cent residual so package and project baselines reconcile.
            share = round(estimate / len(names), 2)
            specs = [(name, 1, "LS", share) for name in names[:-1]]
            specs.append((names[-1], 1, "LS", estimate - share * (len(names) - 1)))
            pkg = package(
                row["code"], row["trade"], specs, firms if estimate else firms[:2]
            )
            if estimate:
                item = pkg["items"][-1 if pkg["code"] != "26.00" else 2]["id"]
                for b, state in zip(pkg["bidders"], STATES):
                    b["coverage_map"][item].update(
                        status=state, carrying="I01" if state == "Included" else ""
                    )
                    if state == "Included":
                        cells = b["coverage_map"]
                        cells["I01"]["amount"] = round(
                            cells["I01"]["amount"] + cells[item]["amount"], 2
                        )
            if pkg["code"] == "13.49":
                pkg["treatment"] = REMOVED
            elif pkg["code"] in ("99.10", "99.15"):
                pkg["treatment"] = GC_COST
            packages.append(pkg)
    return dict(
        name="Teton County Justice Center",
        packages=packages,
        document_completion_rate=0.01,
        sdi_included=True,
    )


def large_starter(item_count=12, bidder_count=8):
    """Build a repeatable multi-trade project with independent pricing lines."""
    if not 4 <= item_count <= 30 or not 2 <= bidder_count <= 20:
        raise ValueError(
            "Choose 4–30 items and 2–20 bidding firms per solicited trade."
        )
    project = starter()
    with (
        Path(__file__)
        .with_name("tcjc_additional_items.csv")
        .open(encoding="utf-8") as f
    ):
        extra = {r["code"]: r["scope_items"].split(" | ") for r in csv.DictReader(f)}
    firms = (
        "Alder Birch Cedar Dune Elm Fir Garnet Harbor Iron Juniper Keystone Linden "
        "Mesa Northstar Oak Pine Quartz Ridge Summit Timber"
    ).split()
    for index, pkg in enumerate(project["packages"]):
        if pkg.get("treatment", BID) != BID:
            continue
        names = [i["description"] for i in pkg["items"]]
        for name in extra[pkg["code"]]:
            if name.casefold() not in {n.casefold() for n in names}:
                names.append(name)
        names = names[:item_count]
        # When the requested count exceeds the catalog, divide work into releases.
        # Keep the original item order so preconfigured scenarios still address it.
        counts = [
            item_count // len(names) + (j < item_count % len(names))
            for j in range(len(names))
        ]
        labels = [
            name if count == 1 else f"{name} (release 1 of {count})"
            for name, count in zip(names, counts)
        ]
        labels.extend(
            f"{name} (release {k} of {count})"
            for name, count in zip(names, counts)
            for k in range(2, count + 1)
        )
        estimate = package_estimate(pkg)
        each = round(estimate / item_count, 2)
        specs = [(name, 1, "LS", each) for name in labels[:-1]]
        specs.append((labels[-1], 1, "LS", estimate - each * (item_count - 1)))
        trade = pkg["trade"].split()[0].strip(",")
        companies = [f"{firms[j]} {trade}" for j in range(bidder_count)]
        expanded = package(pkg["code"], pkg["trade"], specs, companies)
        items = expanded["items"]
        for j, b in enumerate(expanded["bidders"][1:], 1):
            cells = b["coverage_map"]
            for k in range(j % 3 + 1, len(items), 4):
                cell = cells[items[k]["id"]]
                state = ("Excluded", "Included", "Not mentioned")[(j - 1) % 3]
                cell["status"] = state
                if state == "Included":
                    carrier = cells[items[0]["id"]]
                    cell["carrying"] = items[0]["id"]
                    carrier["amount"] = round(carrier["amount"] + cell["amount"], 2)
        expanded["bidders"][-1]["response"] = "Revised"
        decline = new_bidder(f"Willow {trade}", items)
        decline["response"] = "Regret"
        expanded["bidders"].append(decline)
        project["packages"][index] = expanded
    project["name"] = "Teton County Justice Center – large bid set"
    return project


def package_estimate(pkg):
    return (
        0.0
        if pkg.get("treatment") == REMOVED
        else math.fsum(i["estimate"] or 0 for i in pkg["items"])
    )


def project_costs(project):
    rows = []
    if project.get("sdi_included"):
        rows.append(("Subcontractor Default Insurance", "Included", None))
    if "document_completion_rate" in project:
        rate = number(project["document_completion_rate"], "Document completion rate")
        base = math.fsum(package_estimate(pkg) for pkg in project["packages"])
        rows.append(
            (
                "Document Completion Allowance",
                f"{rate * 100:g}% of package estimates",
                round(base * rate, 2),
            )
        )
    return rows


def number(value, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{label} needs a finite, nonnegative number.")
    return value


def prepare(pkg, project_name):
    items = pkg["items"]
    by_id = {i["id"]: i for i in items}
    if not pkg["trade"].strip() or not project_name.strip():
        raise ValueError("Name the project and each trade.")
    if (
        not items
        or len(by_id) != len(items)
        or any(not i["id"] or not i["description"].strip() for i in items)
    ):
        raise ValueError("Provide a description and distinct ID for every scope item.")
    for i in items:
        number(i["quantity"], "GC quantity")
        if i["estimate"] is not None:
            number(i["estimate"], "GC estimate")
    estimate = package_estimate(pkg)
    s = dict(
        name=project_name,
        trade=pkg["trade"],
        scope=pkg["trade"],
        estimate=estimate,
        scope_lines=items,
        instructions=pkg.get("instructions", []),
        commitment_records=pkg.get("commitment_records", []),
        lots=pkg.get("lots", []),
        bidders=[],
    )
    treatment = pkg.get("treatment", BID)
    if treatment not in (BID, GC_COST, REMOVED):
        raise ValueError("Choose a recognized package treatment.")
    if treatment != BID:
        return dict(s, treatment=treatment)
    for original in pkg["bidders"]:
        b = deepcopy(original)
        cells = b["coverage_map"]
        if set(cells) != set(by_id):
            raise ValueError(f"Reconcile the coverage rows for {b['firm']}.")
        total = number(b.get("lump_sum", 0), "Lump sum")
        plug = 0
        lines = (
            [
                dict(
                    description="Lump sum",
                    quantity=1,
                    unit="LS",
                    rate=total,
                    amount=total,
                )
            ]
            if total
            else []
        )
        pending = []
        for k, i in by_id.items():
            v = cells[k]
            state = v["status"]
            if state not in STATES and state != "Ambiguous price":
                raise ValueError("Unknown item coverage status.")
            desc = i["description"]
            if state == "Ambiguous price" or (
                state == "Included" and v.get("raw") == "Included"
            ):
                lines.append(
                    dict(
                        description=desc, quantity="", unit="", rate="", amount=v["raw"]
                    )
                )
                if state == "Ambiguous price":
                    pending.append(k)
            elif state == "Priced":
                amount = number(v["amount"], desc)
                total += amount
                lines.append(
                    dict(
                        description=desc,
                        quantity=i["quantity"],
                        unit=i["unit"],
                        rate=round(amount / i["quantity"], 4) if i["quantity"] else "",
                        amount=amount,
                    )
                )
            elif state == "Included":
                carrier = v["carrying"]
                if carrier == "Lump sum" and b.get("lump_sum", 0) > 0:
                    carrier_name = "Lump sum"
                elif carrier in cells and cells[carrier]["status"] == "Priced":
                    carrier_name = by_id[carrier]["description"]
                else:
                    raise ValueError(
                        f"{b['firm']}: choose a priced carrying line for {desc}."
                    )
                lines.append(
                    dict(
                        description=desc,
                        quantity="",
                        unit="",
                        rate="",
                        amount="Included in " + carrier_name,
                    )
                )
            elif state == "Excluded":
                allowance = (
                    v.get("allowance")
                    if v.get("allowance") is not None
                    else i["estimate"]
                )
                if allowance is None or v.get("unresolved"):
                    pending.append(k)
                else:
                    plug += number(allowance, desc + " allowance")
                lines.append(
                    dict(
                        description=desc,
                        quantity="",
                        unit="",
                        rate="",
                        amount="Excluded",
                    )
                )
            else:
                pending.append(k)
        for field in ("post_bid", "tax", "sdi"):
            number(b.get(field, 0), field)
        for offer in b.get("offers", []):
            number(offer["price"], "Lot offer")
            if not offer["lots"] or not set(offer["lots"]) <= set(s["lots"]):
                raise ValueError("Each offer must refer to defined package lots.")
        if b["match"] == "Unrelated":
            lines = []
            total = pkg.get("estimate", estimate) * b["multiplier"]
            plug = 0
        total = number(b.get("submitted_override", total), "Submitted price")
        b.update(
            submitted=round(total, 2),
            multiplier=total / estimate if estimate else 0,
            lines=lines,
            plug=round(plug, 2),
            pending=pending,
        )
        s["bidders"].append(b)
    if not s["bidders"]:
        raise ValueError("Add at least one invitee to each package.")
    core.validate(s)
    return s


def generate(project, models, draft):
    packages = complications.compile_draft(project)
    codes = [p["code"] for p in packages]
    if (
        not codes
        or len(set(codes)) != len(codes)
        or any(not re.fullmatch(r"[0-9A-Za-z_-][0-9A-Za-z_.-]{0,24}", x) for x in codes)
        or len({x.lower() for x in codes}) != len(codes)
        or any(
            x.lower()
            in (
                "estimate summary",
                "item coverage",
                "documents",
                "history",
                "policies",
                "alternates",
                "scenario checks",
            )
            for x in codes
        )
    ):
        raise ValueError(
            "Use distinct package codes of up to 25 letters, digits, dots or dashes."
        )
    result = dict(project=project, files=[], packages={})
    with tempfile.TemporaryDirectory(dir=core.RUNS) as scratch:
        root = Path(scratch)
        dest = root / "project"
        dest.mkdir()
        for pkg in packages:
            s = prepare(pkg, project["name"])
            s.update(
                code=pkg["code"],
                proposal_styles=project.get("proposal_styles", "Standard"),
            )
            if project.get("complications"):
                s["include_scope_ids"] = True
            code = pkg["code"]
            result["packages"][code] = s
            if not s["bidders"]:
                title = (
                    "Scope withdrawal"
                    if s["treatment"] == REMOVED
                    else "GC cost estimate"
                )
                file = f"gc/{code}/{title}.xlsx"
                (dest / file).parent.mkdir(parents=True, exist_ok=True)
                core.write_document(
                    dest / file,
                    code + " · " + s["trade"],
                    [
                        ["Package status", s["treatment"]],
                        ["GC estimate (USD)", s["estimate"]],
                        *(
                            [
                                [i["description"], i["estimate"]]
                                for i in s["scope_lines"]
                            ]
                            if s["treatment"] == GC_COST
                            else []
                        ),
                    ],
                )
                result["files"].append(
                    dict(
                        file=file,
                        title=code + " · " + title,
                        kind="scope_sheet",
                        package=code,
                        firm="",
                        expected=None,
                    )
                )
                continue
            temp = root / core.generate(s, models, draft, output_root=root)
            for doc in core.read(temp / "run.json")["files"]:
                group = "gc" if not doc["firm"] else "bids"
                path = Path(group) / code / doc["file"]
                (dest / path.parent).mkdir(parents=True, exist_ok=True)
                (temp / doc["file"]).rename(dest / path)
                result["files"].append(
                    dict(
                        doc,
                        file=path.as_posix(),
                        package=code,
                        title=code + " · " + doc["title"],
                    )
                )
        costs = project_costs(project)
        if costs:
            file = "gc/Project estimate.xlsx"
            core.write_document(
                dest / file,
                project["name"] + " estimate summary",
                [
                    ["Package", "Description", "Basis", "GC estimate (USD)"],
                    *[
                        [k, s["trade"], s.get("treatment", BID), s["estimate"]]
                        for k, s in result["packages"].items()
                    ],
                    *[["", name, basis, value] for name, basis, value in costs],
                ],
            )
            result["files"].append(
                dict(
                    file=file,
                    title="Project estimate summary",
                    kind="scope_sheet",
                    package="",
                    firm="",
                    expected=None,
                )
            )
        key = "project-" + uuid4().hex[:12]
        core.save(dest / "run.json", result)
        dest.rename(core.RUNS / key)
    return key


def results(run, policies):
    summary = []
    coverage = []
    tallies = {}
    for code, s in run["packages"].items():
        p = policies.get(code, DEFAULT_POLICY)
        rows, winner = core.evaluate(s, p)
        if not rows:
            winner = "No award — " + s["treatment"].lower()
        rank_bids(rows, p["template"])
        for b, r in zip(s["bidders"], rows):
            active = r["Submitted"] is not None
            r["Plug"] = b["plug"] if active else None
            r["Base bid value"] = (
                round(b["submitted"] + b["plug"], 2) if active else None
            )
            r["Subcontract value"] = (
                round(r["Base bid value"] + b["post_bid"], 2) if active else None
            )
            if "completion" in b:
                r["GC costs to complete"] = b["completion"] if active else None
            r["Total package value"] = r["Leveled"]
            for field in ("post_bid", "tax", "sdi"):
                r[field] = b[field] if active else None
            docs = [
                d
                for d in run["files"]
                if d["package"] == code and d["firm"] == b["firm"]
            ]
            source = next(
                (d["file"] for d in reversed(docs) if d["kind"] == "bid"),
                next(
                    d["file"]
                    for d in run["files"]
                    if d["package"] == code and "Invitation register" in d["title"]
                ),
            )
            if b["response"] in ("Withdrawn", "Clarified") and docs:
                source += "; " + docs[-1]["file"]
            # A lump-sum style states no line prices, so its priced and included
            # items read as included in the lump sum.
            itemized = styles.ITEMIZED.get(
                b.get("rendered_style", styles.STANDARD), True
            )
            for i in s["scope_lines"]:
                v = b["coverage_map"][i["id"]]
                status = (
                    v["status"]
                    if active and b["match"] != "Unrelated"
                    else (b["response"] if not active else "Unrelated scope")
                )
                carrying = v["carrying"]
                if not itemized and status in ("Priced", "Included"):
                    status, carrying = "Included", "Lump sum"
                priced = status == "Priced"
                coverage.append(
                    {
                        "Package": code,
                        "Item ID": i["id"],
                        "Item": i["description"],
                        "Firm": b["firm"],
                        "Confirm": status,
                        "Qty": i["quantity"] if priced else None,
                        "Unit": i["unit"] if priced else None,
                        "Unit Price": round(v["amount"] / i["quantity"], 4)
                        if priced and i["quantity"]
                        else None,
                        "Value": v["amount"] if priced else None,
                        "Included in": carrying if status == "Included" else "",
                        "Allowance": (
                            v["allowance"]
                            if v.get("allowance") is not None
                            else i["estimate"]
                        )
                        if status == "Excluded" and not v.get("unresolved")
                        else None,
                        "Evidence": source,
                    }
                )
        selected = next((r for r in rows if r["Bidder"] == winner), None)
        split_value = (
            float(winner.rsplit(" • USD ", 1)[1].replace(",", ""))
            if p["template"] == "Split or combined packages" and " • USD " in winner
            else None
        )
        package_value = selected["Leveled"] if selected else split_value
        if not rows:
            package_value = s["estimate"]
        summary.append(
            {
                "Package": code,
                "Description of work": s["trade"],
                "GC estimate": s["estimate"],
                "Expected award": winner,
                "Package value": package_value,
                "Review": "Pending clarification"
                if any(r["Status"].startswith("Clarify") for r in rows)
                else "",
            }
        )
        tallies[code] = rows
    for name, basis, value in project_costs(run["project"]):
        summary.append(
            {
                "Package": "",
                "Description of work": name,
                "GC estimate": value,
                "Expected award": "",
                "Package value": None,
                "Review": basis,
            }
        )
    return summary, coverage, tallies


def extraction_notes(run):
    """One row per styled proposal: where its facts are and what to watch for."""
    return [
        {
            "Package": d.get("package", ""),
            "Firm": d["firm"],
            "File": d["file"],
            "Style": d["style"],
            "Price location": d["notes"]["price_location"],
            "Line prices shown": d["notes"]["line_prices"],
            "Numbers that are not prices": d["notes"]["not_prices"],
            "Watch for": d["notes"]["watch_for"],
        }
        for d in run["files"]
        if d.get("style")
    ]


def exports(folder, run, policies, summary, coverage, tallies):
    zipbuf = BytesIO()
    with ZipFile(zipbuf, "w", ZIP_DEFLATED) as archive:
        for d in run["files"]:
            archive.write(folder / d["file"], d["file"])
        for code in tallies:
            if not tallies[code]:
                continue
            archive.writestr(
                f"gc/{code}/Award policy.txt",
                policy_text(policies.get(code, DEFAULT_POLICY)),
            )
    wb = Workbook()
    ws = wb.active
    ws.title = "Estimate Summary"

    def records(sheet, rows):
        if rows:
            sheet.append(list(rows[0]))
            for row in rows:
                sheet.append(list(row.values()))
            sheet.auto_filter.ref = sheet.dimensions

    records(ws, summary)
    scenarios = complications.checks(run, summary, tallies)
    if scenarios:
        records(wb.create_sheet("Scenario checks"), scenarios)
    records(wb.create_sheet("Item Coverage"), coverage)
    records(
        wb.create_sheet("Documents"),
        [
            dict(
                {k: d.get(k) for k in ("package", "firm", "kind", "title", "file")},
                **{
                    k: (d.get("expected") or {}).get(k)
                    for k in ("doc_type", "stated_total", "revision", "effective")
                },
            )
            for d in run["files"]
        ],
    )
    extra = []
    for code, s in run["packages"].items():
        for bidder in s["bidders"]:
            for alt in bidder.get("alternates", []):
                extra.append(
                    {
                        "Package": code,
                        "Firm": bidder["firm"],
                        "Alternate": alt["description"],
                        "Optional amount": alt["amount"],
                    }
                )
    if extra:
        records(wb.create_sheet("Alternates"), extra)
    notes = extraction_notes(run)
    if notes:
        records(wb.create_sheet("Extraction notes"), notes)
    records(
        wb.create_sheet("Policies"),
        [
            dict(Package=code, **policies.get(code, DEFAULT_POLICY))
            for code, rows in tallies.items()
            if rows
        ],
    )
    for code, rows in tallies.items():
        ws = wb.create_sheet(code)
        ws.append(["Bid Tally Sheet", run["packages"][code]["trade"]])
        if not rows:
            ws.append([run["packages"][code]["treatment"], "No subcontract award"])
            ws.append(["GC estimate (USD)", run["packages"][code]["estimate"]])
            continue
        for index, r in enumerate(rows):
            col = 3 + 5 * index
            ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + 4)
            ws.cell(1, col, r["Bidder"])
        fields = ["Confirm", "Qty", "Unit", "Unit Price", "Value"]
        ws.append(["Item ID", "Scope of work"] + fields * len(rows))
        cells = {(v["Item ID"], v["Firm"]): v for v in coverage if v["Package"] == code}
        for i in run["packages"][code]["scope_lines"]:
            ws.append(
                [i["id"], i["description"]]
                + [cells[i["id"], r["Bidder"]][k] for r in rows for k in fields]
            )
        for k in (
            "Submitted",
            "Plug",
            "Base bid value",
            "post_bid",
            "Subcontract value",
            "tax",
            "sdi",
            *(["GC costs to complete"] if "GC costs to complete" in rows[0] else []),
            "Total package value",
            *(["Exposure", "Adjusted"] if "Adjusted" in rows[0] else []),
            "Rank",
            "Status",
        ):
            ws.append(
                ["", k] + [v for r in rows for v in [None, None, None, None, r.get(k)]]
            )
        ws.freeze_panes = "C3"
    for ws in wb:
        if not ws.freeze_panes:
            ws.freeze_panes = "B2"
        for row in ws.iter_rows():
            for v in row:
                if ws.title == "Scenario checks":
                    v.alignment = Alignment(vertical="top", wrap_text=True)
                if v.data_type == "f":
                    v.data_type = "s"
                if v.row == 1 or (ws.title in tallies and v.row == 2):
                    v.fill = PatternFill("solid", fgColor="185453")
                    v.font = Font(color="FFFFFF", bold=True)
        for j in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(j)].width = min(
                72,
                max(
                    13,
                    max(
                        (
                            len(str(ws.cell(i, j).value or ""))
                            for i in range(1, ws.max_row + 1)
                        ),
                        default=10,
                    )
                    + 2,
                ),
            )
    buf = BytesIO()
    wb.save(buf)
    return zipbuf.getvalue(), buf.getvalue()
