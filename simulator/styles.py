"""Realistic proposal layouts for generated bids.

Every style prints the same bid facts as the Standard layout: firm, prices,
coverage, warranty, schedule, terms and response notes. Only where and how the
facts appear changes, so the expected answers stay the same. The exception is a
style that states one lump sum without line prices: the answer key then reports
its items as included in the lump sum (see ITEMIZED).

Names, addresses and phone numbers are invented. Phone numbers use the
fictional 555 exchange and email addresses use example.com.
"""

import hashlib
import random
import re

from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

STANDARD = "Standard"
BID_FORM = "GC bid form"
VAGUE = "Vague"
FORMAL = "Formal"
STRUCTURED = "Structured quote"
TECHNICAL = "Technical"
INFORMAL = "Informal"
AUTO = "Auto"
STYLES = [AUTO, STANDARD, BID_FORM, FORMAL, STRUCTURED, TECHNICAL, INFORMAL, VAGUE]
MIXES = ["Standard", "Realistic mix"]
FORMATS = {
    STANDARD: ["docx", "xlsx", "pdf"],
    BID_FORM: ["pdf"],
    FORMAL: ["pdf", "docx"],
    STRUCTURED: ["pdf", "docx", "xlsx"],
    TECHNICAL: ["pdf", "docx"],
    INFORMAL: ["pdf"],
    VAGUE: ["pdf", "docx"],
}
# False: the document states one total and no line prices.
ITEMIZED = {
    STANDARD: True,
    BID_FORM: True,
    FORMAL: False,
    STRUCTURED: True,
    TECHNICAL: False,
    INFORMAL: True,
    VAGUE: False,
}
# Realistic mix weights by document format.
MIX = {
    "pdf": [
        (BID_FORM, 3),
        (FORMAL, 2),
        (STRUCTURED, 2),
        (TECHNICAL, 2),
        (INFORMAL, 2),
        (VAGUE, 2),
        (STANDARD, 1),
    ],
    "docx": [(FORMAL, 1), (STRUCTURED, 1), (TECHNICAL, 1), (VAGUE, 1), (STANDARD, 1)],
    "xlsx": [(STRUCTURED, 2), (STANDARD, 1)],
}
# Share of Informal pdf proposals that Realistic mix delivers as scans.
SCAN_SHARE = 0.3
# Standard-layout tweaks that need the Standard xlsx rows.
EXCEL_LAYOUTS = ("Late total", "Uncached formula")
GC_NAME = "Northbeam Construction"
GC_LEGAL = "NORTHBEAM CONSTRUCTION, A GENERAL PARTNERSHIP"
FORM_DATE = "12/12/2025"
BID_DATE = "01/14/2026"

FIRST = "Jordan Casey Morgan Avery Riley Quinn Taylor Jamie Drew Rowan Blake Emerson".split()
LAST = (
    "Ellison Park Navarro Whitfield Okafor Lindqvist Brennan Castillo Hayes Moreau "
    "Delgado Sato"
).split()
STREETS = [
    "Industrial Pkwy",
    "Commerce Dr",
    "Mill Rd",
    "Depot St",
    "Quarry Ln",
    "Foundry Ave",
]
CITIES = [
    ("Riverton", "WY"),
    ("Cedar Falls", "IA"),
    ("Lakewood", "CO"),
    ("Fairview", "IL"),
    ("Ashland", "VA"),
    ("Milford", "OH"),
]
GC_INCLUSIONS = [
    "Insurance requirements for this trade are per Attachment A.",
    "Rigging and hoisting for all equipment and material in this scope. The GC tower "
    "crane may be used when available; include any additional crane required.",
    "Include multiple mobilizations as required to meet the GC schedule. Denote the "
    "mobilizations included in your bid.",
    "All requirements for the project's LEED Silver goal that apply to this scope.",
    "Provide a detailed schedule for this work that shows crews and manpower and "
    "complies with the project schedule.",
    "Daily cleanup of debris from this work to GC-provided dumpsters.",
    "All warranties required by the Contract Documents for this scope.",
    "Coordination with adjacent trades, including layout, sequencing and protection "
    "of completed work.",
]
GC_EXCLUSIONS = [
    "Building permit and plan review fees (by GC).",
    "Third-party special inspections and testing (by Owner).",
]
BIDDER_EXCLUSIONS = [
    "Payment and performance bonds",
    "Overtime and shift work unless noted",
    "Winter conditions and temporary heat",
    "Patching and painting by others",
    "Engineering beyond shop drawings",
    "Removal of spoils from site",
    "Saw cutting and core drilling",
    "Traffic control and flaggers",
]
ALTERNATES = [
    "Alternate #1: Phased turnover of Level 1",
    "Alternate #2: Weekend work for tie-ins",
    "Alternate #3: Owner-furnished material storage",
]
ACKNOWLEDGEMENTS = [
    ("Instructions to Bidders", "12/12/2025"),
    ("Prime Contract between GC and Owner", "02/18/2025"),
    ("Draft Subcontract", "04/2025"),
    ("Attachment 1 - List of Subcontract Documents", "12/12/2025"),
    ("Attachment 1A - List of Plans and Specifications", "12/12/2025"),
    ("Attachment 3 - Supplemental Conditions", "12/12/2025"),
    ("Attachment 4 - Schedule", "12/09/2025"),
    ("Attachment A - Insurance Requirements", "01/2024"),
    ("Exhibit 8 - LEED Requirements", "12/12/2025"),
]


def rng(*parts):
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def chosen(b):
    """The bidder's style setting. Blank or missing (as in older bid sets) is Auto."""
    style = b.get("style")
    return style if isinstance(style, str) and style else AUTO


def check(b):
    style = chosen(b)
    if style not in STYLES:
        raise ValueError(f"Unknown proposal style for {b['firm']}.")
    if style != AUTO and b["format"] not in FORMATS[style]:
        raise ValueError(
            f"{b['firm']}: the {style} style needs a "
            + " or ".join(FORMATS[style])
            + " document."
        )
    if style not in (AUTO, STANDARD) and b.get("layout") in EXCEL_LAYOUTS:
        raise ValueError(
            f"{b['firm']}: the {b['layout']} layout works only with the Standard style."
        )


def resolve(s, b):
    """Return the style for a bidder's current proposal."""
    check(b)
    style = chosen(b)
    if style != AUTO:
        return style
    if (
        s.get("proposal_styles", "Standard") != "Realistic mix"
        or b.get("layout") in EXCEL_LAYOUTS
    ):
        return STANDARD
    names, weights = zip(*MIX[b["format"]])
    pick = rng("style", s["name"], s.get("code", ""), s["trade"], b["firm"])
    return pick.choices(names, weights)[0]


def money(value, variant=0):
    value = float(value)
    whole = value.is_integer()
    if variant == 1:
        return f"{value:,.2f}"
    if variant == 2 and whole:
        return f"${value:,.0f}"
    if variant == 3 and whole:
        return f"{value:,.0f}"
    return f"${value:,.2f}"


def contact(firm):
    r = rng("contact", firm)
    city, state = r.choice(CITIES)
    slug = re.sub(r"[^a-z0-9]", "", firm.lower())[:24] or "bidder"
    names = [f"{r.choice(FIRST)} {r.choice(LAST)}" for _ in range(2)]
    return dict(
        person=names[0],
        second=names[1],
        phone=f"({r.randint(201, 989)}) 555-{r.randint(100, 999):04d}",
        email=f"estimating@{slug}.example.com",
        street=f"{r.randint(100, 9899)} {r.choice(STREETS)}",
        city=f"{city}, {state} {r.randint(10000, 99899)}",
        license=f"{state}-{r.randint(100000, 999999)}",
    )


def number_label(value):
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def schedule_rows(d):
    """GC schedule-of-values rows as (description, quantity, amount text, amount)."""
    lines = d["lines"]
    by_desc = {line["description"]: line for line in lines}
    items = d["scope_lines"]
    numbers = {i["description"]: n for n, i in enumerate(items, 1)}
    rows = []

    def entry(description, line):
        if line is None:
            return (description, "", "", None)
        amount = line["amount"]
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            qty = (
                f"{number_label(line['quantity'])} {line['unit']}".strip()
                if line.get("quantity") not in ("", None)
                else ""
            )
            return (description, qty, None, float(amount))
        text = str(amount)
        if text.startswith("Included in "):
            carrier = text[len("Included in ") :]
            text = (
                "Incl. in lump sum"
                if carrier == "Lump sum"
                else f"Incl. in item {numbers[carrier]}"
                if carrier in numbers
                else "Incl. in " + carrier
            )
        elif text == "Excluded":
            text = "EXCLUDED"
        return (description, "", text, None)

    if items:
        for item in items:
            rows.append(entry(item["description"], by_desc.get(item["description"])))
        for line in lines:
            if line["description"] not in numbers and line["description"] != "Lump sum":
                rows.append(entry(line["description"], line))
    elif lines:
        rows = [entry(line["description"], line) for line in lines]
    else:
        rows = [(d["scope"], "1 LS", None, float(d["total"]))]
    return rows


def offered(d):
    """Descriptions the bidder includes and excludes, for prose styles."""
    if not d["scope_lines"] and not d["lines"]:
        return [d["scope"]], []
    included, excluded = [], []
    for line in d["lines"]:
        if line["description"] == "Lump sum":
            continue
        (excluded if line["amount"] == "Excluded" else included).append(
            line["description"]
        )
    return included, excluded


def clarifications(d, money_variant=0):
    notes = []
    if d.get("intro"):
        notes.append(d["intro"])
    if d["scope"] and d["scope"] != "As itemized below":
        notes.append("Our price covers: " + d["scope"] + ".")
    if d.get("revision"):
        rev = d["revision"]
        notes.append(
            f"Quotation {rev['reference']}, Revision 1, issued {rev['issued']}. "
            + rev["supersedes"]
        )
    if d["response"] == "Budget":
        notes.append(
            "Budgetary pricing for planning purposes only. This is not a firm bid."
        )
    if d["response"] == "Partial regret":
        notes.append("We decline the remaining scope.")
    notes.append("Warranty: " + d["warranty"])
    notes.append(f"Duration: {d['days']} days.")
    if d["terms"]:
        notes.append(d["terms"])
    notes.extend(d["statements"])
    for offer in d["offers"]:
        notes.append(
            "All-or-nothing offer: "
            + ", ".join(offer["lots"])
            + " for "
            + money(offer["price"], money_variant)
            + "."
        )
    return notes


class Pdf:
    """A canvas with a separate fill layer, like a flattened form.

    Template text is drawn as the page is laid out. Fill values are drawn after
    all template text on the page, so text extraction returns them apart from
    their labels."""

    L, R, TOP, BOTTOM = 50, 562, 742, 64

    def __init__(self, path, title, header=None, footer=None):
        self.c = canvas.Canvas(str(path), pagesize=letter)
        self.c.setTitle(title)
        self.header, self.footer = header, footer
        self.page = 0
        self.fills = []
        self.start()

    def start(self):
        self.page += 1
        self.y = self.TOP
        if self.header:
            self.header(self)

    def finish(self):
        if self.footer:
            self.footer(self)
        for x, y, text, font, size in self.fills:
            self.c.setFont(font, size)
            self.c.drawString(x, y, text)
        self.fills = []

    def ensure(self, height):
        if self.y - height < self.BOTTOM:
            self.finish()
            self.c.showPage()
            self.start()

    def fill(self, x, y, text, size=10, font="Helvetica"):
        self.fills.append((x, y, str(text), font, size))

    def line(self, text, font="Helvetica", size=9, x=None, lead=None, center=False):
        lead = lead or size + 3
        self.ensure(lead)
        self.c.setFont(font, size)
        base = self.y - size
        if center:
            self.c.drawCentredString((self.L + self.R) / 2, base, text)
        else:
            self.c.drawString(self.L if x is None else x, base, text)
        self.y -= lead
        return base

    def para(self, text, font="Helvetica", size=8.5, x=None, indent=None):
        x = self.L if x is None else x
        for i, part in enumerate(simpleSplit(text, font, size, self.R - x)):
            self.line(part, font, size, x if i == 0 or indent is None else indent)

    def gap(self, height=6):
        self.y -= height

    def row(self, widths, cells, fills=None, size=8, font="Helvetica", bold=False):
        """Draw a bordered table row. fills maps a column index to fill text."""
        font = "Helvetica-Bold" if bold else font
        wrapped = [
            simpleSplit(str(c or ""), font, size, w - 6) or [""]
            for c, w in zip(cells, widths)
        ]
        height = max(len(w) for w in wrapped) * (size + 2) + 6
        self.ensure(height)
        top = self.y
        x = self.L
        self.c.setFont(font, size)
        for width, lines in zip(widths, wrapped):
            self.c.rect(x, top - height, width, height, stroke=1, fill=0)
            for k, text in enumerate(lines):
                self.c.drawString(x + 3, top - 4 - size - k * (size + 2), text)
            x += width
        base = top - 4 - size
        for index, text in (fills or {}).items():
            if text not in ("", None):
                # Leave room for a printed "$" at the start of the cell.
                shift = 14 if str(cells[index] or "").startswith("$") else 4
                self.fill(self.L + sum(widths[:index]) + shift, base, text)
        self.y -= height
        return base

    def save(self):
        self.finish()
        self.c.save()


def bid_form(path, d):
    r = rng("form", d["project"], d["code"], d["trade"], d["firm"])
    who = contact(d["firm"])
    job = f"{r.randint(21, 26)}-{r.randint(1000, 9899)}"
    package = (d["code"] + " " if d["code"] else "") + d["trade"].upper()
    csi = (
        d["code"].replace(".", " ") + " 00"
        if re.fullmatch(r"\d\d\.\d\d", d["code"] or "")
        else "XX XX XX"
    )

    def header(p):
        p.c.setFont("Helvetica", 7)
        p.c.drawString(p.L, 772, "GC Job No.: " + job)
        p.c.drawString(p.L, 763, "Bid Package: " + package)
        p.c.drawCentredString(306, 772, d["project"])
        p.c.drawRightString(p.R, 772, "Date: " + FORM_DATE)
        p.c.drawRightString(p.R, 763, "Attachment 2")

    def footer(p):
        p.c.setFont("Helvetica", 7)
        p.c.drawString(p.L, 40, GC_NAME + " - Bid Form")
        p.c.drawRightString(p.R, 40, f"Page {p.page}")

    p = Pdf(path, f"Bid form {package} {d['firm']}", header, footer)
    for text in (
        "ATTACHMENT 2 - BID FORM",
        "COMMERCIAL TERMS AND SCOPE OF WORK",
    ):
        p.line(text, "Helvetica-Bold", 13, center=True, lead=16)
    for text in ("TO THE SUBCONTRACT AGREEMENT BETWEEN", GC_LEGAL, "AND SUBCONTRACTOR"):
        p.line(text, "Helvetica", 9, center=True)
    p.line("FOR: " + package, "Helvetica-Bold", 12, center=True, lead=18)
    if d["response"] == "Budget":
        p.fill(p.L, 688, "BUDGET PRICING ONLY", 10, "Helvetica-Bold")
    if d.get("revision"):
        p.fill(
            p.L, 688, "REVISION 1 - " + d["revision"]["reference"], 10, "Helvetica-Bold"
        )
    half = (p.R - p.L) / 2
    base = p.row([half, half], ["COMPANY NAME:", "PHONE:"], bold=True)
    p.fill(p.L + 110, base - 2, d["firm"])
    p.fill(p.L + half + 60, base - 2, who["phone"])
    base = p.row([half, half], ["CONTACT NAME:", "EMAIL:"], bold=True)
    p.fill(p.L + 110, base - 2, who["person"])
    p.fill(p.L + half + 60, base - 2, who["email"])
    p.gap(8)
    p.row([half, half], ["PROJECT INFORMATION:", "BID INFORMATION:"], bold=True)
    p.row([half, half], ["Project Name: " + d["project"], "Bid Date: " + BID_DATE])
    p.row([half, half], ["GC Job No.: " + job, "Submit Bid To: Online bid portal"])
    p.gap(8)
    p.line("ATTACHMENT 2 - BID FORM SECTIONS:", "Helvetica-Bold", 9, x=190)
    for text in (
        "A. COMMERCIAL TERMS (SCHEDULE OF VALUES)",
        "B. SPECIFIC SCOPE REQUIREMENTS",
        "C. ACKNOWLEDGEMENTS & ACCEPTANCE",
    ):
        p.line(text, "Helvetica", 8.5, x=200)
    p.gap(6)
    p.para(
        "This Attachment is incorporated into the Subcontract and further clarifies "
        "specific Sections of the Subcontract."
    )
    p.gap(6)
    p.line("A. COMMERCIAL TERMS:", "Helvetica-Bold", 12, lead=18)
    p.line("1. SUBCONTRACTOR PRICE BREAKDOWN", "Helvetica-Bold", 9)
    p.para(
        "The following schedule of values further clarifies how the Subcontract Price "
        "was calculated and, if approved by the Owner, may also serve as the schedule "
        "of values for processing payments in accordance with Section 4 of the "
        "Subcontract.",
        x=62,
    )
    p.gap(4)
    widths = [45, 287, 80, 100]
    p.row(widths, ["ITEM #", "DESCRIPTION", "QTY / UNIT", "$ AMOUNT"], bold=True)
    required = []
    for n, (description, qty, text, amount) in enumerate(schedule_rows(d), 1):
        shown = text if amount is None else money(amount, r.randrange(4))
        if amount is not None:
            required.append(amount)
        p.row(widths, [str(n), description, "", "$"], fills={2: qty, 3: shown})
    p.row([412, 100], ["TOTAL", "$"], bold=True)
    p.fill(p.L + 426, base, money(d["total"], r.randrange(4)), 11)
    required.append(float(d["total"]))
    p.para(
        "Quantities are for evaluation purposes only; they will not be listed in the "
        "subcontract. See Subcontract Section 3.2 for Subcontract Price.",
        size=7.5,
        x=150,
    )
    p.gap(6)
    p.line(
        "MATERIAL BREAKOUT COSTS (INCLUDED IN TOTAL ABOVE) - FOR TAX EXEMPT PURPOSES",
        "Helvetica-Bold",
        8,
    )
    for _ in range(3):
        p.row([412, 100], ["", "$"])
    p.row([412, 100], ["TOTAL", "$"], bold=True)

    p.gap(10)
    p.line("2. ALTERNATES", "Helvetica-Bold", 9)
    p.para(
        "The alternates listed below are elective scope changes and the lump sum "
        "adjustments that, at Contractor's sole discretion, may be used to adjust the "
        "scope of Work and Subcontract Price by Change Order. Amounts include all "
        "overhead and profit allowed by the Subcontract.",
        x=62,
    )
    widths = [40, 312, 70, 90]
    p.row(
        widths,
        ["ALT #", "ALTERNATE DESCRIPTION", "ADD / DEDUCT", "$ AMOUNT"],
        bold=True,
    )
    for n, text in enumerate(ALTERNATES, 1):
        p.row(widths, [f"{n}.", text, "", "$"], fills={2: "N/A"})
    alternates = d["alternates"]
    for k in range(max(2, len(alternates))):
        n = len(ALTERNATES) + k + 1
        if k < len(alternates):
            alt = alternates[k]
            p.row(
                widths,
                [f"{n}.", "", "", "$"],
                fills={1: alt["description"], 2: "ADD", 3: money(alt["amount"], 1)},
            )
        else:
            p.row(widths, [f"{n}.", "", "", "$"])

    p.gap(10)
    p.line("3. ALLOWANCES", "Helvetica-Bold", 9)
    p.para(
        "The allowances listed below are estimated amounts for scopes of Work that are "
        "not yet fully defined. These amounts are included in the Subcontract Price.",
        x=62,
    )
    widths = [70, 342, 100]
    p.row(widths, ["ALLOWANCE #", "ALLOWANCE DESCRIPTION", "$ AMOUNT"], bold=True)
    for n in range(1, 4):
        p.row(widths, [f"{n}.", "", "$"])

    p.gap(10)
    p.line("4. LABOR RATES", "Helvetica-Bold", 9)
    p.para(
        "These rates will be used to price the labor component of changes to the "
        "Subcontract Price. They include all burdens, fringes, benefits, taxes and "
        "insurance, but not overhead and profit. Bidders - list all positions.",
        x=62,
    )
    widths = [182, 110, 110, 110]
    p.row(
        widths,
        ["POSITION", "STRAIGHT TIME", "OVER TIME (TIME + 1/2)", "DOUBLE TIME"],
        bold=True,
    )
    base_rate = r.randint(45, 70)
    for title, add in (
        ("Foreman", 45),
        ("Journeyman", 35),
        ("Apprentice", 10),
        ("Laborer", 0),
    ):
        rate = base_rate + add
        p.row(
            widths,
            ["", "$            /hr.", "$            /hr.", "$            /hr."],
            fills={0: title, 1: f"{rate}", 2: f"{rate * 1.5:g}", 3: f"{rate * 2}"},
        )

    p.gap(10)
    p.line("5. UNIT PRICES", "Helvetica-Bold", 9)
    widths = [60, 282, 80, 90]
    p.row(
        widths,
        ["UNIT PRICE #", "UNIT PRICE DESCRIPTION", "UNIT", "$ / UNIT"],
        bold=True,
    )
    for n in range(1, 4):
        p.row(widths, [f"{n}.", "", "", "$"])
    p.gap(10)
    p.line("6. CHANGE ORDER MARKUPS", "Helvetica-Bold", 9)
    p.para(
        "Combined overhead and profit markups on Change Orders will not exceed the "
        "rate below: All Subcontractors 10 %.",
        x=62,
    )
    p.gap(10)
    p.line("7. KEY PERSONNEL", "Helvetica-Bold", 9)
    widths = [212, 200, 100]
    p.row(widths, ["PERSONNEL", "ROLE", "ON SITE %"], bold=True)
    p.row(
        widths, ["", "", ""], fills={0: who["person"], 1: "Project Manager", 2: "100 %"}
    )
    p.row(
        widths, ["", "", ""], fills={0: who["second"], 1: "Superintendent", 2: "50 %"}
    )
    p.gap(10)
    p.line("8. LONG LEAD ITEMS", "Helvetica-Bold", 9)
    widths = [262, 120, 130]
    p.row(widths, ["LONG LEAD MATERIAL / EQUIPMENT", "LEAD TIME", "VALUE"], bold=True)
    p.row(widths, ["", "", "$"])
    p.line(
        "- End of Section A - Commercial Terms -",
        "Helvetica-Oblique",
        8,
        center=True,
        lead=16,
    )

    p.line("B. SPECIFIC SCOPE REQUIREMENTS:", "Helvetica-Bold", 12, lead=18)
    p.para(
        "The Subcontractor's Work and Subcontract Price include, but are not limited "
        "to, all labor, supervision, materials, equipment, hoisting, layout, shop "
        "drawings, submittals, taxes, insurance and escalation required to complete "
        "this scope according to the Subcontract Documents, except as clarified in "
        "paragraphs B.2 and B.3 below."
    )
    p.gap(4)
    p.line("1. SPECIFICATION SECTIONS:", "Helvetica-Bold", 9)
    widths = [412, 100]
    p.row(widths, ["SPEC SECTION", "DATE"], bold=True)
    for text in (
        "Division 00  INFORMATION AVAILABLE TO CONTRACTORS",
        "Division 01  GENERAL REQUIREMENTS",
        f"{csi}  {d['trade'].upper()}",
    ):
        p.row(widths, [text, FORM_DATE])
    p.gap(6)
    p.line("2. SCOPE OF WORK INCLUSIONS:", "Helvetica-Bold", 9)
    scope = GC_INCLUSIONS + [
        f"{i['description']}, complete per the Contract Documents"
        + (
            f" (approx. {number_label(i['quantity'])} {i['unit']})."
            if i.get("quantity") not in ("", None, 1)
            else "."
        )
        for i in d["scope_lines"]
    ]
    if not d["scope_lines"]:
        scope.append(f"{d['trade']} scope complete per the Contract Documents.")
    for n, text in enumerate(scope, 1):
        p.para(f"2.{n}   {text}", x=62, indent=88)
    p.gap(6)
    p.line("3. SCOPE OF WORK EXCLUSIONS:", "Helvetica-Bold", 9)
    _, excluded = offered(d)
    mine = [
        f"Excludes {x.lower() if x[:1].isupper() and x[1:2].islower() else x}."
        for x in excluded
    ]
    mine += [x + "." for x in r.sample(BIDDER_EXCLUSIONS, 2)]
    for n, text in enumerate(GC_EXCLUSIONS, 1):
        p.para(f"3.{n}   {text}", x=62, indent=88)
    for k in range(max(5, len(mine))):
        base = p.line(f"3.{len(GC_EXCLUSIONS) + k + 1}", x=62, lead=13)
        p.c.line(88, base - 2, p.R, base - 2)
        if k < len(mine):
            p.fill(92, base, mine[k], 9)
    p.gap(4)
    p.para(
        "NO OTHER EXCLUSIONS, CLARIFICATIONS OR QUALIFICATIONS PROPOSED BY "
        "SUBCONTRACTOR ARE PART OF THIS AGREEMENT IF NOT EXPRESSLY ENUMERATED HEREIN.",
        "Helvetica-Bold",
        8,
    )
    p.gap(6)
    p.line("4. SUBCONTRACTOR CLARIFICATIONS AND QUALIFICATIONS:", "Helvetica-Bold", 9)
    notes = []
    for text in clarifications(d, r.randrange(4)):
        notes.extend(simpleSplit(text, "Helvetica", 9, p.R - 92))
    for k in range(max(4, len(notes))):
        base = p.line("", lead=13)
        p.c.line(88, base - 2, p.R, base - 2)
        if k < len(notes):
            p.fill(92, base, notes[k], 9)
    p.line(
        "- End of Section B - Specific Scope Requirements -",
        "Helvetica-Oblique",
        8,
        center=True,
        lead=16,
    )

    p.line("C. ACKNOWLEDGEMENTS & ACCEPTANCE:", "Helvetica-Bold", 12, lead=18)
    p.line("C1. SUBCONTRACT BID PACKAGE DOCUMENTS:", "Helvetica-Bold", 9)
    p.para(
        "The following documents have been reviewed and are incorporated in the Base "
        "Bid. Indicate agreement by checking Yes or No for each item below."
    )
    for name, dated in ACKNOWLEDGEMENTS:
        base = p.line(f"-  {name}.  Dated: {dated}", x=62, lead=14)
        p.c.drawString(470, base, "YES [   ]")
        p.c.drawString(515, base, "NO [   ]")
        p.fill(495, base, "X", 9)
    p.gap(4)
    p.line(
        "ADDENDA: We acknowledge the following Addenda and have included all costs.",
        x=62,
    )
    base = p.line(
        "Addendum #:            Dated:                       Initial:", x=80, lead=14
    )
    p.fill(135, base, "1", 9)
    p.fill(200, base, "12/19/2025", 9)
    p.fill(320, base, "".join(w[0] for w in who["person"].split()), 9)
    p.gap(4)
    p.line("C2. ACCEPTANCE OF SUBCONTRACT AGREEMENT", "Helvetica-Bold", 9)
    p.para(
        "We acknowledge that the above bid is valid for sixty (60) days after the GC's "
        "receipt of said bid and, if accepted within this duration, we will enter into "
        "the Subcontract without delay, modification or exception."
    )
    base = p.line("", lead=14)
    p.c.drawString(470, base, "YES [   ]")
    p.c.drawString(515, base, "NO [   ]")
    p.fill(495, base, "X", 9)
    p.gap(8)
    for label, value in (
        ("SIGNATURE:", who["person"]),
        ("DATE:", BID_DATE),
        ("PRINT NAME & TITLE:", who["person"] + ", Estimator"),
        ("COMPANY LEGAL NAME:", d["firm"]),
        ("STATE CONTRACTOR'S LICENSE NO:", who["license"]),
    ):
        base = p.line(label, "Helvetica-Bold", 8.5, lead=16)
        p.c.line(230, base - 2, p.R, base - 2)
        p.fill(236, base, value, 10)
    p.line("- END OF ATTACHMENT 2 -", "Helvetica-Oblique", 8, center=True, lead=16)
    p.save()
    notes = dict(
        price_location="Section A.1 price breakdown and its TOTAL row. Filled values "
        "are a separate text layer, so they read apart from their labels.",
        line_prices="Yes",
        not_prices="Labor rates (A.4), change order markup (10 %), job number, "
        "phone number, license number, dates, page numbers",
        watch_for="Section B.2 is the GC's scope list, not the bidder's. Blank price "
        "cells mean not mentioned, not $0. Bidder exclusions are in B.3 and its "
        "terms in B.4."
        + (" Alternates in A.2 are outside the total." if alternates else ""),
    )
    return notes, required


def vague_lines(d, r):
    """The vague proposal as (kind, text) blocks shared by the pdf and docx forms."""
    included, excluded = offered(d)
    excludes = [x for x in excluded] + r.sample(BIDDER_EXCLUSIONS, 4)
    blocks = [
        (
            "para",
            f"Proposal to furnish all labor, material and equipment for the "
            f"{d['trade'].lower()} work on the above project per plans and "
            "specifications, except as listed below.",
        ),
        ("head", f"{d['trade']} Scope to INCLUDE:"),
        *[("bullet", x) for x in included],
        ("head", "We would EXCLUDE:"),
        *[("bullet", x) for x in excludes],
    ]
    for alt in d["alternates"]:
        blocks.append(
            (
                "para",
                f"Add alternate: {alt['description']}. Add "
                f"{money(alt['amount'], 1)} to the lump sum. Not included in the price.",
            )
        )
    blocks.extend(("para", text) for text in clarifications(d, 1))
    blocks.append(
        (
            "para",
            "ACCEPTANCE OF PROPOSAL: All work is to be completed in a workmanlike "
            "manner according to standard practices. Any alteration involving extra cost "
            "will be executed only upon written order. A service charge of 1.5% per month "
            "applies to accounts over 30 days. This proposal may be withdrawn if not "
            "accepted within thirty (30) days.",
        )
    )
    return blocks


def vague_pdf(path, d):
    r = rng("vague", d["project"], d["code"], d["trade"], d["firm"])
    who = contact(d["firm"])
    p = Pdf(path, f"Proposal {d['trade']} {d['firm']}")
    p.line(d["firm"].upper(), "Helvetica-Bold", 16, lead=20)
    for text in (
        who["street"],
        who["city"],
        f"Phone {who['phone']}  |  {who['email']}",
    ):
        p.line(text, "Helvetica", 8.5)
    p.gap(14)
    for label, value in (
        ("Date:", "January 14, 2026"),
        ("Project:", d["project"]),
        (
            "Subject:",
            d["trade"] + " Scope" + (" - BUDGET" if d["response"] == "Budget" else ""),
        ),
    ):
        base = p.line(label, "Helvetica-Bold", 9, lead=14)
        p.fill(p.L + 60, base, value, 9)
    p.gap(10)
    for kind, text in vague_lines(d, r):
        if kind == "head":
            p.gap(4)
            p.line(text, "Helvetica-Bold", 9.5, lead=14)
        elif kind == "bullet":
            p.para("â€¢  " + text, x=66, indent=76)
        else:
            p.gap(3)
            p.para(text)
    p.gap(10)
    base = p.line("Total Lump Sum" + " ." * 52, "Helvetica-Bold", 10, lead=16)
    p.fill(470, base, money(d["total"], r.randrange(4)), 10, "Helvetica-Bold")
    p.gap(14)
    p.line("Respectfully submitted,", lead=13)
    base = p.line(d["firm"], "Helvetica-Bold", 9, lead=13)
    base = p.line("", lead=13)
    p.fill(p.L, base, who["person"] + ", Estimator", 9)
    p.gap(16)
    p.line("Accepted by: ______________________________    Date: ______________")
    p.save()
    return vague_notes(), [float(d["total"])]


def vague_docx(path, d):
    r = rng("vague", d["project"], d["code"], d["trade"], d["firm"])
    who = contact(d["firm"])
    doc = Document()
    doc.add_heading(d["firm"].upper(), 1)
    doc.add_paragraph(
        f"{who['street']}, {who['city']}\nPhone {who['phone']} | {who['email']}"
    )
    doc.add_paragraph(
        "Date: January 14, 2026\nProject: "
        + d["project"]
        + "\nSubject: "
        + d["trade"]
        + " Scope"
        + (" - BUDGET" if d["response"] == "Budget" else "")
    )
    for kind, text in vague_lines(d, r):
        if kind == "head":
            doc.add_paragraph().add_run(text).bold = True
        elif kind == "bullet":
            doc.add_paragraph(text, style="List Bullet")
        else:
            doc.add_paragraph(text)
    doc.add_paragraph().add_run(
        "Total Lump Sum ......................................... "
        + money(d["total"], r.randrange(4))
    ).bold = True
    doc.add_paragraph(
        f"Respectfully submitted,\n{d['firm']}\n{who['person']}, Estimator"
    )
    doc.add_paragraph("Accepted by: ______________________    Date: ____________")
    doc.save(path)
    return vague_notes(), [float(d["total"])]


def vague_notes():
    return dict(
        price_location="One lump sum near the end ('Total Lump Sum'). In the pdf "
        "the value is a separate text layer, apart from its label.",
        line_prices="No. Items are scope bullets without prices.",
        not_prices="Late-payment charge (1.5% per month), 30-day terms, "
        "validity (30 days), phone number, address",
        watch_for="Items listed under INCLUDE are included in the lump sum. Items "
        "under EXCLUDE are excluded. Scope items not listed are not mentioned.",
    )


STANDARD_EXCLUSIONS = [
    "Any allowances unless specifically indicated above",
    "Payment and performance bonds unless noted",
    "Permits, fees and inspections",
    "Overtime, shift or holiday work",
    "Cutting, patching and painting of other trades' work",
    "Engineering or stamped calculations unless noted",
    "Temporary protection of work by others",
    "Winter conditions, temporary heat and enclosures",
    "Hoisting beyond one mobilization",
    "Removal of hazardous materials",
    "Liquidated damages",
    "Warranties exceeding the period stated above",
]
TERMS = [
    "Deposit: 25% of the contract will be invoiced upon signing of the proposal.",
    "Progress billing is monthly. Accounts over 30 days accrue a service charge of "
    "1.5% per month.",
    "Projects of $10,000.00 and up are billed in phases; smaller projects are due in "
    "full at acceptance.",
    "Claims for damaged or missing material must be made in writing within 48 hours "
    "of delivery.",
    "Material stored more than 30 days at the purchaser's request is charged a "
    "warehousing fee of 2% per month.",
    "This proposal may be withdrawn if not accepted within sixty (60) days.",
    "Customer agrees to pay all costs of collection, including reasonable attorney's "
    "fees.",
]
TECH_NOTES = [
    "Estimate based on drawings dated 12/12/2025 and Addendum #1",
    "Normal working hours, Monday to Friday, 7:00 to 3:30",
    "Layout for our work only",
    "Submittals, shop drawings and O&M manuals",
    "One mobilization for each phase shown in the project schedule",
    "Coordination drawings for our scope",
    "Testing and start-up of systems we install",
    "Cleanup of our debris to GC dumpsters",
]


def scanned(s, b, style):
    """Whether Realistic mix delivers this proposal as a scan.

    Only Informal pdf proposals whose style the mix picked are scanned."""
    return (
        style == INFORMAL
        and b["format"] == "pdf"
        and s.get("proposal_styles") == "Realistic mix"
        and chosen(b) == AUTO
        and rng("scan", s["name"], s.get("code", ""), s["trade"], b["firm"]).random()
        < SCAN_SHARE
    )


def priced_lines(d):
    """Bid lines as (description, quantity text, unit price, amount or text)."""
    rows = []
    for line in d["lines"]:
        amount = line["amount"]
        qty = (
            f"{number_label(line['quantity'])} {line['unit']}".strip()
            if line.get("quantity") not in ("", None)
            else ""
        )
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            rate = line.get("rate")
            exact = (
                isinstance(rate, (int, float))
                and isinstance(line.get("quantity"), (int, float))
                and round(round(rate, 2) * line["quantity"], 2) == round(amount, 2)
            )
            rows.append(
                (
                    line["description"],
                    qty,
                    round(rate, 2) if exact else None,
                    float(amount),
                )
            )
        else:
            rows.append((line["description"], "", None, str(amount)))
    if not rows:
        rows = [(d["scope"], "1 LS", float(d["total"]), float(d["total"]))]
    return rows


def sections(rows):
    """Split quote lines into one or two titled sections."""
    half = (len(rows) + 1) // 2
    priced = [
        any(isinstance(a, float) for *_, a in part)
        for part in (rows[:half], rows[half:])
    ]
    if len(rows) < 4 or not all(priced):
        return [("SCOPE OF WORK", rows)]
    return [("BASE SCOPE", rows[:half]), ("ASSOCIATED WORK", rows[half:])]


def subtotal(rows):
    return round(sum(a for *_, a in rows if isinstance(a, float)), 2)


def numbered(items, style="letter"):
    out = []
    for i, text in enumerate(items):
        if style == "letter":
            tag = chr(97 + i % 26) * (i // 26 + 1) + ")"
        else:
            tag = f"{i + 1})"
        out.append(f"{tag} {text}")
    return out


def excluded_text(d):
    _, excluded = offered(d)
    return [f"Price does NOT include {x}" for x in excluded]


def formal_blocks(d, r):
    who = contact(d["firm"])
    number = f"E{r.randint(250000, 269999)}"
    included, _ = offered(d)
    items = {i["description"]: i for i in d["scope_lines"]}
    furnish = []
    for name in included:
        item = items.get(name)
        qty = (
            f" - {number_label(item['quantity'])} {item['unit']}"
            if item and item.get("quantity") not in ("", None, 1)
            else ""
        )
        furnish.append(name + qty)
    blocks = [
        ("title", d["firm"]),
        (
            "small",
            f"{who['street']}, {who['city']}  |  {who['phone']}  |  {who['email']}",
        ),
        ("gap", 10),
        ("head", f"PROPOSAL {number}"),
        ("para", f"{GC_NAME}  -  Attn: Estimating Department"),
        ("para", f"{d['project']}  -  January 14, 2026"),
        ("gap", 6),
        (
            "para",
            f"{d['firm']} is a licensed contractor (License No. {who['license']}) and "
            "carries the insurance required by the bid documents.",
        ),
        (
            "para",
            f"{d['firm']} proposes to furnish the following scope of work for the "
            "referenced project in accordance with our standard terms and conditions.",
        ),
        (
            "para",
            "REFERENCES: Drawings dated 12/12/2025. Specifications as issued. Addenda 1 and 2.",
        ),
        ("head", "FURNISH & INSTALL:"),
        *[("item", x) for x in numbered(furnish, "number")],
        ("gap", 4),
        (
            "para",
            f"All for the net sum of {money(d['total'], r.choice([0, 1]))}, "
            + (
                f"tax excluded (sales tax {tax_rate(d)} to be added). "
                if tax_rate(d)
                else "tax included. "
            )
            + "(ADD 1.28% for bond for one year if required)",
        ),
        ("gap", 4),
        *[("bullet", x) for x in clarifications(d, 1)],
        (
            "bullet",
            "Price includes ONE mobilization only. Extra mobilizations caused by "
            "delays or other trades will incur additional costs.",
        ),
        ("head", "PROJECT SPECIFIC QUALIFICATIONS / EXCLUSIONS:"),
        *[
            ("item", x)
            for x in numbered(
                excluded_text(d)
                + [
                    "Price does NOT include any overtime labor",
                    "Price does NOT include temporary protection of other trades' work",
                ]
            )
        ],
        ("head", "STANDARD EXCLUSIONS:"),
        *[("item", x) for x in numbered(STANDARD_EXCLUSIONS)],
    ]
    for alt in d["alternates"]:
        blocks.append(
            (
                "para",
                f"Optional alternate: {alt['description']}. ADD "
                f"{money(alt['amount'], 1)} (not included in the net sum above).",
            )
        )
    blocks += [
        ("page", ""),
        ("head", "STANDARD TERMS AND CONDITIONS"),
        *[("item", x) for x in numbered(TERMS, "number")],
        ("gap", 16),
        (
            "para",
            f"Respectfully submitted,  {who['person']}, Estimator  -  {d['firm']}",
        ),
        ("gap", 10),
        ("para", "Accepted by: ______________________________   Date: ______________"),
    ]
    notes = dict(
        price_location="In a sentence: 'All for the net sum of ...'. No price table.",
        line_prices="No. Scope is a numbered list without prices.",
        not_prices="Bond 1.28% (optional, not in the price), deposit 25%, service "
        "charge 1.5% per month, $10,000.00 billing threshold, 48 hours, 30 and 60 days, "
        "license number",
        watch_for="The bond add is only 'if required' and is not part of the bid. "
        "Excluded items are in 'Price does NOT include' lines among many standard "
        "exclusions. The second page is terms only.",
    )
    return blocks, notes


def technical_blocks(d, r):
    who = contact(d["firm"])
    included, _ = offered(d)
    items = {i["description"]: i for i in d["scope_lines"]}
    scope = []
    for name in included:
        item = items.get(name)
        qty = (
            f" ({number_label(item['quantity'])} {item['unit']})"
            if item and item.get("quantity") not in ("", None, 1)
            else ""
        )
        verb = (
            "Wire, furnish and install"
            if "electric" in d["trade"].lower()
            else "Furnish and install"
        )
        scope.append(f"{verb} {name}{qty}")
    base = r.randint(95, 150)
    blocks = [
        ("small", "DATE 01/14/2026"),
        ("title", d["firm"]),
        ("small", f"{who['street']}  |  {who['city']}  |  T: {who['phone']}"),
        ("gap", 8),
        ("para", f"{GC_NAME}  -  {d['project']}"),
        ("para", "Attention: Estimating  |  Email: bids@northbeam.example.com"),
        ("head", "PROPOSAL"),
        (
            "para",
            f"Scope: as per plans and specifications dated 12/12/2025 plus "
            f"Addendum #1 dated 12/19/2025. {d['trade']} work as follows:",
        ),
        *[("bullet", x) for x in scope + TECH_NOTES],
        (
            "bullet",
            f"Labor rates for changes: regular ${base:.2f}, OT ${base * 1.5:.2f}, "
            f"double time ${base * 2:.2f}",
        ),
        ("gap", 6),
        ("total", ("TOTAL PRICE", money(d["total"], r.choice([0, 2])))),
        ("gap", 6),
        ("head", "Notes:"),
        *[("bullet", x) for x in clarifications(d, 1)],
        *[("bullet", "Excludes " + x) for x in offered(d)[1]],
        *[
            ("bullet", "Excludes " + x.lower())
            for x in r.sample(STANDARD_EXCLUSIONS, 5)
        ],
    ]
    for alt in d["alternates"]:
        blocks.append(
            (
                "bullet",
                f"Alternate: {alt['description']}, add "
                f"{money(alt['amount'], 1)} (not included in total price)",
            )
        )
    blocks += [
        ("gap", 12),
        ("para", f"Sincerely, {who['person']}, Project Estimator, {d['firm']}"),
    ]
    notes = dict(
        price_location="One 'TOTAL PRICE' after a long scope list.",
        line_prices="No. Many scope bullets share one total.",
        not_prices=f"Labor rates (${base:.2f} regular, overtime, double time), "
        "drawing and addendum dates, working hours",
        watch_for="Scope bullets mix the bidder's items with general notes. "
        "Exclusions are 'Excludes ...' notes after the price.",
    )
    return blocks, notes


def tax_rate(d):
    """The sales tax rate the GC adds to this bid, as printed text.

    Empty when the bid has no GC tax adder, which means its price includes tax.
    The rate is derived from the adder, so the document and the GC adjustments
    sheet always agree.
    """
    tax = float(d.get("tax") or 0)
    total = float(d["total"] or 0)
    if not tax or not total:
        return ""
    return f"{round(tax / total * 100, 2):g}%"


def tax_sentence(tax):
    if tax:
        return f"If job is taxable, add {tax} sales tax. Add 1.5% for bond if required."
    return "Price includes all applicable sales and use taxes. Add 1.5% for bond if required."


def structured_parts(d, r):
    rows = priced_lines(d)
    groups = sections(rows)
    alternates = d["alternates"]
    alt_total = round(float(d["total"]) + sum(a["amount"] for a in alternates), 2)
    # Kept so the random sequence, and every later choice, stays as before.
    r.choice(["6.25%", "7%", "5.3%"])
    tax = tax_rate(d)
    notes = dict(
        price_location="TOTAL at the end of the quote table. Section subtotals "
        "appear above it.",
        line_prices="Yes",
        not_prices=(f"Sales tax rate ({tax}, not added), " if tax else "")
        + "bond 1.5% if required (not added), quote number, validity days"
        + (", 'Total with add alternates'" if alternates else ""),
        watch_for="Section subtotals are part of the total, not extra. "
        + (
            "The 'Total with add alternates' row is not the bid total. "
            if alternates
            else ""
        )
        + ("The price excludes sales tax. The GC adds it. " if tax else "")
        + "Rows marked Included or Excluded have no price.",
    )
    return rows, groups, alternates, alt_total, tax, notes


def blocks_pdf(path, d, blocks, title):
    p = Pdf(
        path,
        title,
        footer=lambda q: (
            q.c.setFont("Helvetica", 7),
            q.c.drawRightString(q.R, 40, f"Page {q.page}"),
        ),
    )
    for kind, value in blocks:
        if kind == "title":
            p.line(value.upper(), "Helvetica-Bold", 15, lead=19)
        elif kind == "small":
            p.line(value, "Helvetica", 8)
        elif kind == "head":
            p.gap(4)
            p.line(value, "Helvetica-Bold", 9.5, lead=14)
        elif kind == "para":
            p.para(value, size=9)
        elif kind == "bullet":
            p.para("•  " + value, size=8.5, x=62, indent=72)
        elif kind == "item":
            p.para(value, size=8.5, x=62, indent=76)
        elif kind == "gap":
            p.gap(value)
        elif kind == "page":
            p.finish()
            p.c.showPage()
            p.start()
        elif kind == "total":
            label, amount = value
            base = p.line(label, "Helvetica-Bold", 11, lead=16)
            p.c.setFont("Helvetica-Bold", 11)
            p.c.drawString(p.L + 150, base, amount)
    p.save()


def blocks_docx(path, blocks):
    doc = Document()
    for kind, value in blocks:
        if kind == "title":
            doc.add_heading(value.upper(), 1)
        elif kind == "head":
            doc.add_paragraph().add_run(value).bold = True
        elif kind in ("para", "small", "item"):
            doc.add_paragraph(value)
        elif kind == "bullet":
            doc.add_paragraph(value, style="List Bullet")
        elif kind == "page":
            doc.add_page_break()
        elif kind == "total":
            doc.add_paragraph().add_run(f"{value[0]}   {value[1]}").bold = True
    doc.save(path)


def prose(path, d, maker, name):
    r = rng(name, d["project"], d["code"], d["trade"], d["firm"])
    blocks, notes = maker(d, r)
    if path.suffix == ".docx":
        blocks_docx(path, blocks)
    else:
        blocks_pdf(path, d, blocks, f"Proposal {d['trade']} {d['firm']}")
    return notes, [float(d["total"])]


def structured_pdf(path, d):
    r = rng("structured", d["project"], d["code"], d["trade"], d["firm"])
    who = contact(d["firm"])
    _, groups, alternates, alt_total, tax, notes = structured_parts(d, r)
    p = Pdf(path, f"Quotation {d['firm']}")
    p.line(d["firm"].upper(), "Helvetica-Bold", 15, lead=19)
    p.line(f"{who['street']}, {who['city']}  |  PHONE {who['phone']}", "Helvetica", 8)
    p.gap(6)
    p.line("QUOTATION", "Helvetica-Bold", 13, center=True, lead=18)
    half = (p.R - p.L) / 2
    p.row(
        [half, half], [f"Quote Number: {r.randint(30000, 39999)}", "Date: 01/14/2026"]
    )
    p.row([half, half], [f"Customer: {GC_NAME}", "Terms: Net 30 days"])
    p.row(
        [half, half], [f"Project Name: {d['project']}", f"Quoted By: {who['person']}"]
    )
    p.line(
        "** This quote is valid for 60 days. **",
        "Helvetica-Bold",
        8,
        center=True,
        lead=16,
    )
    widths = [222, 80, 90, 120]
    p.row(widths, ["DESCRIPTION", "QTY", "UNIT PRICE", "AMOUNT"], bold=True)
    required = []
    for name, group in groups:
        p.row([512], [name], bold=True)
        for desc, qty, rate, amount in group:
            if isinstance(amount, float):
                required.append(amount)
                shown = money(amount, r.choice([0, 1]))
            else:
                shown = amount
            p.row(
                widths, [desc, qty, money(rate, 1) if rate is not None else "", shown]
            )
        if len(groups) > 1:
            p.row(
                [392, 120], [f"{name} SUBTOTAL", money(subtotal(group), 1)], bold=True
            )
    p.row([392, 120], ["TOTAL", money(d["total"])], bold=True)
    required.append(float(d["total"]))
    if alternates:
        p.gap(6)
        for alt in alternates:
            p.row(
                [392, 120],
                [f"Add Alternate: {alt['description']}", money(alt["amount"], 1)],
            )
        p.row([392, 120], ["Total with add alternates", money(alt_total)], bold=True)
    p.gap(8)
    p.para(
        (
            f"If job is taxable, add {tax} sales tax to the above price."
            if tax
            else "Price includes all applicable sales and use taxes."
        )
        + " Add 1.5% for payment and performance bond if required.",
        "Helvetica-Bold",
        8.5,
    )
    p.gap(4)
    p.line("CONDITIONS:", "Helvetica-Bold", 9)
    for text in numbered(
        clarifications(d, 1)
        + excluded_text(d)
        + [
            "Omissions and quantity errors are subject to correction.",
            "We do not include sales tax." if tax else "Sales tax is included.",
            "All orders are subject to credit approval.",
        ],
        "number",
    ):
        p.para(text, size=8.5, x=62, indent=76)
    p.gap(10)
    p.line(f"Respectfully submitted, {who['person']}  -  {d['firm']}")
    p.line(
        "Accepted By: ____________________  Company: ____________________  Date: ________"
    )
    p.save()
    return notes, required


def structured_docx(path, d):
    r = rng("structured", d["project"], d["code"], d["trade"], d["firm"])
    who = contact(d["firm"])
    _, groups, alternates, alt_total, tax, notes = structured_parts(d, r)
    doc = Document()
    doc.add_heading(d["firm"].upper(), 1)
    doc.add_paragraph(f"{who['street']}, {who['city']} | {who['phone']}")
    info = doc.add_table(rows=3, cols=4)
    info.style = "Table Grid"
    for i, (a, b, c, e) in enumerate(
        [
            ("Quote No.", str(r.randint(30000, 39999)), "Date", "January 14, 2026"),
            ("To", GC_NAME, "Project", d["project"]),
            ("Quote Type", d["trade"], "Validity", "60 days"),
        ]
    ):
        for j, text in enumerate((a, b, c, e)):
            info.cell(i, j).text = text
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for j, text in enumerate(["Bid Item", "Qty", "Unit Price", "Amount"]):
        table.cell(0, j).text = text
    required = []

    def add(cells, merge=False):
        row = table.add_row()
        if merge:
            merged = row.cells[0].merge(row.cells[2])
            merged.text = cells[0]
            row.cells[3].text = cells[-1]
        else:
            for j, text in enumerate(cells):
                row.cells[j].text = text

    for name, group in groups:
        row = table.add_row()
        row.cells[0].merge(row.cells[3]).text = name
        for desc, qty, rate, amount in group:
            if isinstance(amount, float):
                required.append(amount)
            add(
                [
                    desc,
                    qty,
                    money(rate, 1) if rate is not None else "",
                    money(amount, 1) if isinstance(amount, float) else amount,
                ]
            )
        if len(groups) > 1:
            add([f"{name} subtotal", money(subtotal(group), 1)], merge=True)
    add(["Base Bid total", money(d["total"])], merge=True)
    required.append(float(d["total"]))
    for alt in alternates:
        add(
            [f"Add Alternate: {alt['description']}", money(alt["amount"], 1)],
            merge=True,
        )
    if alternates:
        add(["Total with add alternates", money(alt_total)], merge=True)
    doc.add_paragraph(tax_sentence(tax))
    doc.add_paragraph().add_run("Clarifications").bold = True
    for text in clarifications(d, 1):
        doc.add_paragraph(text, style="List Bullet")
    doc.add_paragraph().add_run("Exclusions").bold = True
    for text in excluded_text(d) + [x for x in r.sample(STANDARD_EXCLUSIONS, 4)]:
        doc.add_paragraph(text, style="List Bullet")
    doc.add_paragraph(f"Submitted by {who['person']}, {d['firm']}")
    doc.add_paragraph("Accepted By: ______________________   Date: ____________")
    doc.save(path)
    return notes, required


def structured_xlsx(path, d):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    r = rng("structured", d["project"], d["code"], d["trade"], d["firm"])
    who = contact(d["firm"])
    _, groups, alternates, alt_total, tax, notes = structured_parts(d, r)
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for extra in ("Sheet2", "Sheet3"):
        wb.create_sheet(extra)

    def put(row, col, value, span=1, bold=False):
        ws.cell(row, col, value)
        if span > 1:
            ws.merge_cells(
                start_row=row, start_column=col, end_row=row, end_column=col + span - 1
            )
        if bold:
            ws.cell(row, col).font = Font(bold=True)

    put(2, 1, d["firm"], 4, True)
    put(3, 1, f"Proposal# {r.randint(110000, 119999)}", 2)
    put(3, 4, "Jan 14, 2026")
    put(4, 1, f"{who['street']}, {who['city']}", 4)
    put(5, 1, "Tel: " + who["phone"], 4)
    put(7, 1, "To")
    put(7, 2, GC_NAME, 3)
    put(8, 1, "Job")
    put(8, 2, d["project"], 3)
    put(10, 1, "SCOPE OF WORK", 5, True)
    put(11, 1, "Summary:", 2)
    row = 12
    for name, group in groups:
        put(row, 2, name, 3)
        ws.cell(row, 5, subtotal(group))
        row += 1
    put(row, 4, "BASE BID:", 1, True)
    ws.cell(row, 5, float(d["total"]))
    row += 2
    for col, text in enumerate(
        ["DESCRIPTION", "QTY.", "UOM", "UNIT COST", "TOTAL COST"], 1
    ):
        put(row, col, text, 1, True)
    required = []
    for name, group in groups:
        row += 1
        put(row, 1, name, 5, True)
        for desc, qty, rate, amount in group:
            row += 1
            ws.cell(row, 1, desc)
            parts = qty.split(" ", 1)
            if parts and parts[0]:
                try:
                    ws.cell(row, 2, float(parts[0]))
                except ValueError:
                    ws.cell(row, 2, parts[0])
                ws.cell(row, 3, parts[1] if len(parts) > 1 else "")
            if rate is not None:
                ws.cell(row, 4, rate)
            ws.cell(row, 5, amount)
            if isinstance(amount, float):
                required.append(amount)
    row += 1
    put(row, 1, "Total for All Work", 4, True)
    ws.cell(row, 5, float(d["total"]))
    required.append(float(d["total"]))
    for alt in alternates:
        row += 1
        put(row, 1, f"Add Alternate: {alt['description']}", 4)
        ws.cell(row, 5, float(alt["amount"]))
    if alternates:
        row += 1
        put(row, 1, "Total with add alternates", 4)
        ws.cell(row, 5, alt_total)
    row += 2
    put(row, 1, tax_sentence(tax), 5)
    row += 1
    put(row, 1, "NOTES:", 5, True)
    for text in clarifications(d, 1):
        row += 1
        put(row, 1, "*" + text, 5)
    row += 1
    put(row, 1, "EXCLUSIONS:", 5, True)
    excl = ["NO " + x.upper() for x in offered(d)[1]] + [
        "NO " + x.upper() for x in r.sample(STANDARD_EXCLUSIONS, 6)
    ]
    for k in range(0, len(excl), 2):
        row += 1
        ws.cell(row, 1, "*" + excl[k])
        if k + 1 < len(excl):
            put(row, 3, "*" + excl[k + 1], 3)
    row += 2
    put(row, 1, "Proposal Submitted by:", 2)
    put(row, 3, d["firm"], 3)
    for col, width in zip("ABCDE", (52, 10, 8, 14, 16)):
        ws.column_dimensions[col].width = width
    wb.save(path)
    notes = dict(
        notes,
        price_location="'BASE BID' in the summary block at the top "
        "and 'Total for All Work' below the line items. Text rows use merged "
        "cells; two sheets are empty.",
    )
    return notes, required


def informal_pdf(path, d):
    r = rng("informal", d["project"], d["code"], d["trade"], d["firm"])
    who = contact(d["firm"])
    rows = priced_lines(d)
    p = Pdf(path, f"Estimate {d['firm']}")
    c = p.c
    # Layered header text, as in estimate tools that export shadowed titles. It
    # reads back as duplicated fragments.
    for text, dx in ((d["firm"][: max(4, len(d["firm"]) // 2)], 0), (d["firm"], 0)):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(p.L + dx, 740, text)
    for text in ("ESTIMA", "ESTIMATE", "TE"):
        c.setFont("Helvetica-Bold", 18)
        c.drawString(430 + (52 if text == "TE" else 0), 740, text)
    p.y = 726
    p.line(f"{who['street']}, {who['city']}", "Helvetica", 8.5)
    p.line(f"{who['phone']}  |  {who['email']}", "Helvetica", 8.5)
    p.gap(8)
    half = (p.R - p.L) / 2
    p.row([half, half], [f"ADDRESS: {GC_NAME}", f"ESTIMATE # {r.randint(1000, 9999)}"])
    p.row([half, half], [f"PROJECT: {d['project']}", "DATE 01/14/2026"])
    p.gap(8)
    widths = [262, 70, 80, 100]
    p.row(widths, ["DESCRIPTION", "QTY", "RATE", "AMOUNT"], bold=True)
    required = []
    for desc, qty, rate, amount in rows:
        if isinstance(amount, float):
            required.append(amount)
        p.row(
            widths,
            [
                desc,
                qty,
                f"{rate:,.2f}" if rate is not None else "",
                f"{amount:,.2f}" if isinstance(amount, float) else amount,
            ],
        )
    p.row([412, 100], ["TOTAL", f"USD ${float(d['total']):,.2f}"], bold=True)
    required.append(float(d["total"]))
    p.gap(8)
    p.line("PROJECT DETAILS", "Helvetica-Bold", 9)
    for text in (
        clarifications(d, 1)
        + ["Excludes-"]
        + ["*" + x for x in offered(d)[1]]
        + ["*Permits and fees", "*Anything not listed above"]
    ):
        p.para(text, size=8.5)
    for alt in d["alternates"]:
        p.para(
            f"Option: {alt['description']} - add ${alt['amount']:,.2f} (not in total)",
            size=8.5,
        )
    p.gap(6)
    p.para(
        "Estimate good through 02/14/2025. Prices subject to change after that.", size=8
    )
    p.gap(14)
    p.line("Accepted By ______________________    Accepted Date ____________")
    p.line(f"Make checks payable to {d['firm']}", "Helvetica", 8)
    p.save()
    notes = dict(
        price_location="TOTAL row under the estimate table.",
        line_prices="Yes",
        not_prices="Estimate number, phone number, dates",
        watch_for="Header text is layered, so it reads back as duplicated fragments "
        "('ESTIMA ESTIMATE TE'). The validity date has the wrong year (2025).",
    )
    return notes, required


def render(style, path, d):
    """Draw the bid in a style. Returns (notes, amounts that must be readable)."""
    pdf = path.suffix == ".pdf"
    if style == BID_FORM:
        return bid_form(path, d)
    if style == VAGUE:
        return vague_docx(path, d) if path.suffix == ".docx" else vague_pdf(path, d)
    if style == FORMAL:
        return prose(path, d, formal_blocks, "formal")
    if style == TECHNICAL:
        return prose(path, d, technical_blocks, "technical")
    if style == STRUCTURED:
        if pdf:
            return structured_pdf(path, d)
        if path.suffix == ".docx":
            return structured_docx(path, d)
        return structured_xlsx(path, d)
    if style == INFORMAL:
        return informal_pdf(path, d)
    raise ValueError(f"No renderer for the {style} style.")


def amounts(text):
    """Every number in the text, with thousands separators removed."""
    found = set()
    for token in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            found.add(round(float(token.replace(",", "")), 2))
        except ValueError:
            continue
    return found
