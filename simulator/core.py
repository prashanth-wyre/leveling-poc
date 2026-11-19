"""Scenario fixtures, document production and independent award calculations."""

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape

from docx import Document
from openpyxl import Workbook, load_workbook
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/backend"))
from wyre_level import config, ingest, llm

RUNS = config.DATA / "simulations"
RUNS.mkdir(exist_ok=True)
BASE = config.GEMINI_MODEL
HIGH = os.getenv("GEMINI_HIGHER_MODEL") or BASE
TOP = os.getenv("GEMINI_HIGHEST_MODEL") or HIGH
MODELS = dict(
    scenario=HIGH,
    generation=BASE,
    extraction=BASE,
    reconciliation=HIGH,
    policy=HIGH,
    review=TOP,
)
RESPONSES = [
    "Bid",
    "Regret",
    "Silent",
    "Partial regret",
    "Revised",
    "Withdrawn",
    "Clarified",
    "Budget",
]
FORMS = ["docx", "xlsx", "pdf"]
POLICIES = [
    "Lowest eligible leveled cost",
    "Warranty-adjusted cost",
    "Lowest submitted price",
    "Best value within window",
    "Weighted best value",
    "Schedule priority",
    "Budget ceiling",
    "Split or combined packages",
]


def save(path, data):
    tmp = path.with_suffix("." + uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False))
    tmp.replace(path)


def read(path):
    return json.loads(path.read_text())


def ask(stage, models, prompt, schema):
    token = llm.stage_models.set(models)
    try:
        return llm.generate_json(prompt, schema, kind=stage, retries=0)
    finally:
        llm.stage_models.reset(token)


def preset(name):
    names = [
        "Alder Works",
        "Birch Assembly",
        "Cedar Group",
        "Dune Construction",
        "Elm Services",
        "Fir Contracting",
    ]
    bidders = []
    for i, firm in enumerate(names):
        bidders.append(
            dict(
                firm=firm,
                response="Regret" if i == 5 else "Bid",
                scope="Landscape planting" if i == 4 else "Complete roof assembly",
                match="Unrelated" if i == 4 else "Full",
                multiplier=[1, 1.012, 0.01, 100, 1, 1][i],
                format=FORMS[i % 3],
                years=10,
                coverage="Labor and materials" if i == 1 else "Materials only",
                deductible=10000,
                cap=100000,
                days=45,
                plug=0,
                terms="",
                lines=[],
            )
        )
    if name == "All regrets":
        for row in bidders:
            row["response"] = "Regret"
    if name == "Revision and partial scope":
        bidders[0]["response"] = "Revised"
        bidders[1].update(
            response="Partial regret",
            match="Partial",
            scope="Membrane materials",
            plug=50000,
            plug_basis="Installation and remaining roof assembly work",
        )
        bidders[2]["response"] = "Withdrawn"
        bidders[3]["response"] = "Silent"
    if name == "All unrelated":
        for row in bidders:
            row.update(scope="Landscape planting", match="Unrelated", response="Bid")
    if name == "Split award":
        bidders[0]["offers"] = [
            {"lots": ["Supply"], "price": 300000},
            {"lots": ["Supply", "Installation"], "price": 500000},
        ]
        bidders[1]["offers"] = [{"lots": ["Installation"], "price": 180000}]
    if name == "Document extraction stress":
        bidders[0].update(format="xlsx", layout="Late total")
        bidders[1].update(format="xlsx", layout="Uncached formula")
        bidders[2].update(format="pdf", layout="Scanned")
        bidders[3].update(
            attachments=[
                {
                    "title": "Price clarification",
                    "text": "The cover total conflicts with our signed price of USD 500,000. Please clarify.",
                }
            ]
        )
    for b in bidders:
        b.setdefault("layout", "Standard")
        b.setdefault("attachments", [])
    return dict(
        name=name,
        trade="Roofing",
        estimate=500000,
        scope="Complete roof assembly",
        scope_lines=[],
        lots=["Supply", "Installation"] if name == "Split award" else [],
        bidders=bidders,
    )


def validate(s):
    if (
        not s["name"].strip()
        or not s["scope"].strip()
        or not math.isfinite(float(s["estimate"]))
        or s["estimate"] < 0
        or (s["estimate"] == 0 and not s.get("scope_lines"))
    ):
        raise ValueError("Enter a name, a scope and a positive estimate.")
    firms = set()
    for b in s["bidders"]:
        if not b["firm"].strip() or b["firm"].casefold() in firms:
            raise ValueError("Each invitee needs a distinct company name.")
        firms.add(b["firm"].casefold())
        if (
            b["format"] not in FORMS
            or b["response"] not in RESPONSES
            or b["match"] not in ["Full", "Partial", "Unrelated"]
        ):
            raise ValueError("Unknown document format, response or scope relationship.")
        for k in ("years", "deductible", "cap", "days", "plug", "multiplier"):
            if not math.isfinite(float(b[k])) or float(b[k]) < 0:
                raise ValueError(f"Invalid {k} for {b['firm']}")
        for line in b.get("lines", []):
            for key in ("description", "quantity", "unit", "rate", "amount"):
                if key not in line:
                    raise ValueError(f"Missing line field {key}")


def write_document(path, title, rows):
    if path.suffix == ".xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Submission"
        for row in [[title], *rows]:
            ws.append(row)
        for col in "ABCDE":
            ws.column_dimensions[col].width = 48 if col == "A" else 28
        ws.freeze_panes = "A2"
        wb.save(path)
    elif path.suffix == ".docx":
        d = Document()
        d.add_heading(title, 0)
        for row in rows:
            d.add_paragraph("   ".join(map(str, row)))
        d.save(path)
    else:
        styles = getSampleStyleSheet()
        flow = [Paragraph(escape(title), styles["Title"])]
        for row in rows:
            flow.extend(
                [
                    Paragraph(escape("   ".join(map(str, row))), styles["BodyText"]),
                    Spacer(1, 6),
                ]
            )
        SimpleDocTemplate(str(path)).build(flow)


def generate(s, models, draft, output_root=None):
    output_root = output_root or RUNS
    validate(s)
    with tempfile.TemporaryDirectory(dir=output_root) as work:
        folder = Path(work) / "package"
        folder.mkdir()
        files = []

        def emit(kind, title, rows, ext, firm="", expected=None):
            file = f"{len(files) + 1:02d}-{kind}.{ext}"
            write_document(folder / file, title, rows)
            text = ingest.read(folder / file)["text"]
            if firm and firm not in text:
                raise ValueError(f"Bidder missing from {file}")
            if (
                expected
                and "stated_total" in expected
                and format(float(expected["stated_total"]), ".2f")
                .rstrip("0")
                .rstrip(".")
                not in text
            ):
                raise ValueError(f"Quoted amount missing from {file}")
            files.append(
                dict(file=file, title=title, kind=kind, firm=firm, expected=expected)
            )

        scope_header = ["Scope", "Quantity", "Unit", "GC estimate"]
        fields = ["description", "quantity", "unit", "estimate"]
        if s.get("include_scope_ids"):
            scope_header.append("Item ID")
            fields.append("id")
        scope_rows = [[x[k] for k in fields] for x in s.get("scope_lines", [])]
        emit(
            "scope_sheet",
            s["trade"] + " scope sheet",
            [
                scope_header,
                *(scope_rows or [[s["scope"], 1, "LS", s["estimate"]]]),
                *s.get("instructions", []),
            ],
            "xlsx",
        )
        emit(
            "supporting",
            "Invitation register",
            [[b["firm"], s["trade"]] for b in s["bidders"]],
            "xlsx",
        )
        if s.get("commitment_records"):
            emit(
                "supporting",
                "GC commitment and change register",
                [["Date", "Record", "USD", "Disposition"], *s["commitment_records"]],
                "xlsx",
            )
        adjustments = [["Bidder", "Scope / adjustment basis", "Amount (USD)"]]
        for bidder in s["bidders"]:
            if bidder.get("coverage_map"):
                for item in s["scope_lines"]:
                    entry = bidder["coverage_map"][item["id"]]
                    if entry["status"] == "Excluded" and bidder["match"] != "Unrelated":
                        value = entry.get("allowance")
                        adjustments.append(
                            [
                                bidder["firm"],
                                item["description"],
                                "Unresolved"
                                if entry.get("unresolved")
                                else item["estimate"]
                                if value is None
                                else value,
                            ]
                        )
            elif bidder["plug"]:
                adjustments.append(
                    [
                        bidder["firm"],
                        bidder.get("plug_basis")
                        or bidder["terms"]
                        or "GC scope allowance",
                        bidder["plug"],
                    ]
                )
            for field, label in (
                ("post_bid", "Post-bid adjustment"),
                ("tax", "Sales tax"),
                ("completion", "GC costs to complete"),
                ("sdi", "Subcontractor default insurance"),
            ):
                if bidder.get(field):
                    adjustments.append([bidder["firm"], label, bidder[field]])
        if len(adjustments) > 1:
            emit(
                "supporting",
                "GC leveling allowances and adjustments",
                adjustments,
                "xlsx",
            )
        for b in s["bidders"]:
            response = b["response"]
            if response == "Silent":
                continue
            amount = b.get("submitted", round(s["estimate"] * b["multiplier"], 2))
            firm = b["firm"]
            head = [[firm], ["Package", s["trade"]]]
            if response == "Revised":
                reference = f"Q-{len(files) + 1:03d}"
                old = round(amount * 1.15, 2)
                emit(
                    "bid",
                    firm + " • Original proposal",
                    head
                    + [
                        ["Quotation", reference],
                        ["Revision", 0],
                        ["Issued", "2026-01-12"],
                        ["We offer to perform the following work."],
                        ["Scope offered", b["scope"]],
                        ["Submitted total USD", old],
                    ],
                    "pdf",
                    firm,
                    dict(stated_total=old, doc_type="bid", revision=0, effective=False),
                )
                head.extend(
                    [
                        ["Quotation", reference],
                        ["Revision", 1],
                        ["Issued", "2026-01-15"],
                        [
                            "Revision 1 supersedes the entire quotation dated 2026-01-12."
                        ],
                    ]
                )
            if response == "Regret":
                emit(
                    "bid",
                    firm + " • Regret letter",
                    head + [["Thank you for inviting us. We decline this package."]],
                    b["format"],
                    firm,
                    dict(doc_type="decline"),
                )
                continue
            current = [
                ["Scope offered", b["scope"]],
                ["Submitted total USD", amount],
                [
                    "Warranty",
                    (
                        (
                            "Durations as itemized"
                            if "component_years" in b
                            else f"{b['years']} years"
                        )
                        + f", {b['coverage']}. Deductible USD {b['deductible']}. Cap USD {b['cap']}."
                    ),
                ],
                ["Duration", f"{b['days']} days"],
                ["Terms", b["terms"]],
                *b.get("statements", []),
            ]
            for alt in b.get("alternates", []):
                current.append(
                    [
                        "Optional alternate (outside submitted total)",
                        alt["description"],
                        alt["amount"],
                    ]
                )
            for offer in b.get("offers", []):
                current.append(
                    ["All-or-nothing offer", ", ".join(offer["lots"]), offer["price"]]
                )
            for line in b.get("lines", []):
                current.append(
                    [
                        line[k]
                        for k in ("description", "quantity", "unit", "rate", "amount")
                    ]
                )
            if draft:
                intro = ask(
                    "generation",
                    models,
                    "Write one short contractor cover paragraph using only these facts. Omit amounts and warranty promises. "
                    + json.dumps([firm, b["scope"], response]),
                    {
                        "type": "object",
                        "properties": {"paragraph": {"type": "string"}},
                        "required": ["paragraph"],
                    },
                )
                head.append([intro["paragraph"]])
            if response == "Partial regret":
                head.append(["We decline the remaining scope."])
            emit(
                "bid",
                firm + " • " + response,
                head + current,
                b["format"],
                firm,
                dict(
                    stated_total=amount,
                    doc_type="budget" if response == "Budget" else "bid",
                    **(
                        {"revision": 1, "effective": True}
                        if response == "Revised"
                        else {}
                    ),
                ),
            )
            bid_file = folder / files[-1]["file"]
            layout = b.get("layout", "Standard")
            if layout == "Scanned" and bid_file.suffix == ".pdf":
                import pymupdf

                with pymupdf.open(bid_file) as src, pymupdf.open() as dst:
                    for page in src:
                        target = dst.new_page(
                            width=page.rect.width, height=page.rect.height
                        )
                        target.insert_image(
                            target.rect,
                            pixmap=page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)),
                        )
                    dst.save(folder / "scan.tmp")
                (folder / "scan.tmp").replace(bid_file)
            if (
                layout in ("Late total", "Uncached formula")
                and bid_file.suffix == ".xlsx"
            ):
                wb = load_workbook(bid_file)
                ws = wb.active
                total = next(
                    cell for cell in ws["A"] if cell.value == "Submitted total USD"
                )
                if layout == "Late total":
                    ws.cell(425, 1, "Submitted total USD")
                    ws.cell(425, 2, amount)
                    ws.delete_rows(total.row)
                else:
                    ws.cell(total.row, 2, f"=ROUND({amount},2)")
                wb.save(bid_file)
            for attachment in b.get("attachments", []):
                emit(
                    "supporting",
                    firm + " • " + attachment["title"],
                    [[firm], [attachment["text"]]],
                    "docx",
                    firm,
                )
            if response in ("Withdrawn", "Clarified"):
                msg = (
                    "We withdraw our proposal in full."
                    if response == "Withdrawn"
                    else "We confirm our price and scope as submitted."
                )
                emit("supporting", firm + " • Follow-up", [[firm], [msg]], "docx", firm)
        key = (
            datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
        )
        save(
            folder / "run.json",
            dict(
                scenario=s,
                models=models,
                files=files,
                drafting="Gemini" if draft else "Fixture",
            ),
        )
        folder.rename(output_root / key)
        return key


def evaluate(s, p):
    rows = []
    for b in s["bidders"]:
        amount = b.get("submitted", round(s["estimate"] * b["multiplier"], 2))
        leveled = round(
            amount
            + b["plug"]
            + b.get("post_bid", 0)
            + b.get("tax", 0)
            + b.get("sdi", 0),
            2,
        )
        active = b["response"] not in ("Regret", "Silent", "Withdrawn", "Budget")
        reason = ""
        if not active:
            reason = b["response"]
        elif b["match"] == "Unrelated":
            reason = "Unrelated scope"
        elif s["estimate"] == 0:
            reason = "Clarify zero GC estimate"
        elif not p["low"] <= b["multiplier"] <= p["high"]:
            reason = "Clarify price"
        elif b.get("pending") and p["template"] != "Split or combined packages":
            reason = "Clarify scope"
        elif any(v is None for v in b.get("component_years", {}).values()):
            reason = "Clarify component warranty"
        elif any(
            v < b["component_min"][k] for k, v in b.get("component_years", {}).items()
        ):
            reason = "Component warranty minimum"
        elif min(b.get("component_years", {"General": b["years"]}).values()) < p[
            "min_years"
        ] or (p["min_years"] > 0 and b["coverage"] == "None"):
            reason = "Warranty minimum"
        elif p["template"] == "Budget ceiling" and leveled > p["budget"]:
            reason = "Over budget"
        elif p["template"] == "Schedule priority" and b["days"] > p["deadline"]:
            reason = "Schedule minimum"
        duration = b.get("component_years", {}).get(b.get("loss_component"), b["years"])
        covered = (
            b["coverage"] in (p["event_coverage"], "Labor and materials")
            and duration is not None
            and duration >= p["event_year"]
        )
        recovery = (
            min(b["cap"], max(0, p["repair"] - b["deductible"])) if covered else 0
        )
        exposure = p["probability"] * (p["repair"] - recovery)
        rows.append(
            dict(
                Bidder=b["firm"],
                Status=reason or "Eligible",
                Submitted=amount if active else None,
                Plug=b["plug"] if active else None,
                Leveled=leveled if active else None,
                **(
                    {
                        "Exposure": round(exposure, 2)
                        if active and duration is not None
                        else None,
                        "Adjusted": round(leveled + exposure, 2)
                        if active and duration is not None
                        else None,
                    }
                    if p["template"] == "Warranty-adjusted cost"
                    else {}
                ),
                Days=b["days"],
            )
        )
    eligible = [r for r in rows if r["Status"] == "Eligible"]
    if not eligible:
        return rows, "No award"
    low = min(r["Leveled"] for r in eligible)
    t = p["template"]
    if t == "Split or combined packages":
        lots = frozenset(s.get("lots", []))
        if not lots:
            return rows, "Specify package lots and package offers"
        allowed = {r["Bidder"] for r in eligible}
        bidders = [b for b in s["bidders"] if b["firm"] in allowed]

        @lru_cache(None)
        def cheapest(index, remaining):
            if not remaining:
                return 0, ()
            if index == len(bidders):
                return math.inf, ()
            best = cheapest(index + 1, remaining)
            bidder = bidders[index]
            for offer in bidder.get("offers", []):
                bundle = frozenset(offer["lots"])
                if bundle and bundle <= remaining:
                    cost, rest = cheapest(index + 1, remaining - bundle)
                    value = offer["price"] + cost
                    if value < best[0]:
                        best = (
                            value,
                            (
                                bidder["firm"] + " (" + ", ".join(sorted(bundle)) + ")",
                                *rest,
                            ),
                        )
            return best

        total, awards = cheapest(0, lots)
        return rows, (
            " + ".join(awards) + f" • USD {total:,.2f}"
        ) if awards else "No complete package combination"
    if t == "Best value within window":
        return rows, "Shortlist • " + ", ".join(
            r["Bidder"]
            for r in eligible
            if r["Leveled"] <= low * (1 + p["window"] / 100)
        )
    field = {
        "Lowest submitted price": "Submitted",
        "Warranty-adjusted cost": "Adjusted",
    }.get(t, "Leveled")
    if t == "Weighted best value":
        fastest = min(r["Days"] for r in eligible)
        for r in eligible:
            r["Score"] = round(
                p["weight"] * low / max(0.01, r["Leveled"])
                + (100 - p["weight"]) * fastest / max(1, r["Days"]),
                4,
            )
        best = max(r["Score"] for r in eligible)
        winners = [r for r in eligible if r["Score"] == best]
    else:
        best = min(r[field] for r in eligible)
        winners = [r for r in eligible if r[field] == best]
    return rows, ", ".join(r["Bidder"] for r in winners)


def office_pdf(path, dest):
    binary = (
        shutil.which("soffice")
        or "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    )
    if not Path(binary).exists():
        return None
    dest.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [
                binary,
                "-env:UserInstallation=" + Path(profile).as_uri(),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(dest),
                str(path),
            ],
            check=True,
            timeout=60,
            capture_output=True,
        )
    return dest / (path.stem + ".pdf")


def import_file(folder, name, data, kind):
    """Create a new bid day with the original package and a supplemental upload."""
    source = read(folder / "run.json")
    suffix = Path(name).suffix.lower()
    if suffix not in (".pdf", ".doc", ".xls", ".docx", ".xlsx"):
        raise ValueError("Choose a Word, Excel or PDF file.")
    with tempfile.TemporaryDirectory(dir=RUNS) as tmp:
        clone = Path(tmp) / "package"
        clone.mkdir()
        for entry in source["files"]:
            for field in ("file", "original"):
                if entry.get(field):
                    shutil.copyfile(folder / entry[field], clone / entry[field])
        name = "import-" + uuid4().hex[:8] + "-" + Path(name).name
        original = clone / name
        original.write_bytes(data)
        path = original
        if suffix in (".doc", ".xls"):
            binary = (
                shutil.which("soffice")
                or "/Applications/LibreOffice.app/Contents/MacOS/soffice"
            )
            if not Path(binary).exists():
                raise ValueError(
                    "Install LibreOffice to convert legacy .doc and .xls files."
                )
            ext = {".doc": "docx", ".xls": "xlsx"}[suffix]
            with tempfile.TemporaryDirectory() as profile:
                subprocess.run(
                    [
                        binary,
                        "-env:UserInstallation=" + Path(profile).as_uri(),
                        "--headless",
                        "--convert-to",
                        ext,
                        "--outdir",
                        str(clone),
                        str(original),
                    ],
                    check=True,
                    timeout=60,
                    capture_output=True,
                )
            path = original.with_suffix("." + ext)
            if not path.exists():
                raise ValueError("Office conversion failed.")
        source["files"].append(
            dict(
                file=path.name,
                original=name,
                title=Path(name[16:]).name,
                kind=kind,
                firm="",
                expected=None,
            )
        )
        key = (
            datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
        )
        save(clone / "run.json", source)
        clone.rename(RUNS / key)
        return key
