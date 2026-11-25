import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

import core
import project as p
import styles

POLICY = dict(
    template=core.POLICIES[0],
    low=0.05,
    high=10,
    min_years=0,
    probability=0.1,
    repair=100000,
    event_year=5,
    event_coverage="Labor and materials",
    weight=70,
    window=3,
    budget=550000,
    deadline=60,
)


class StyleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(core, "RUNS", Path(tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def build(self, project):
        folder = core.RUNS / p.generate(project, core.MODELS, False)
        run = core.read(folder / "run.json")
        return folder, run, p.results(run, {})

    def styled_demo(self):
        project = p.school_demo()
        project["proposal_styles"] = "Realistic mix"
        electrical = project["packages"][1]["bidders"]
        electrical[0].update(format="docx", style=styles.VAGUE)
        electrical[1].update(format="pdf", style=styles.VAGUE)
        electrical[2].update(format="pdf", style=styles.BID_FORM)
        return project

    def test_standard_output_is_unchanged(self):
        folder, run, (summary, coverage, tallies) = self.build(p.school_demo())
        self.assertFalse(any("style" in d for d in run["files"]))
        _, workbook = p.exports(folder, run, {}, summary, coverage, tallies)
        wb = load_workbook(BytesIO(workbook), read_only=True)
        self.assertNotIn("Extraction notes", wb.sheetnames)
        wb.close()

    def test_styles_keep_the_answers(self):
        _, _, (standard, _, _) = self.build(p.school_demo())
        folder, run, (summary, coverage, tallies) = self.build(self.styled_demo())
        self.assertEqual(
            [(r["Expected award"], r["Package value"]) for r in summary],
            [(r["Expected award"], r["Package value"]) for r in standard],
        )
        docs = {
            d["firm"]: d
            for d in run["files"]
            if d["package"] == "26.00" and d["kind"] == "bid"
        }
        for firm, style in [
            ("Alder Works", styles.VAGUE),
            ("Birch Assembly", styles.VAGUE),
            ("Cedar Group", styles.BID_FORM),
        ]:
            d = docs[firm]
            self.assertEqual(d["style"], style)
            text = core.ingest.read(folder / d["file"])["text"]
            self.assertIn(firm, text)
            self.assertIn(d["expected"]["stated_total"], styles.amounts(text))
        # The bid form's filled values read apart from their labels.
        form = core.ingest.read(folder / docs["Cedar Group"]["file"])["text"]
        self.assertGreater(form.index("Cedar Group"), form.index("MATERIAL BREAKOUT"))
        self.assertIn("EXCLUDED", form)
        # A lump-sum style reports its items as included in the lump sum.
        vague = [
            r
            for r in coverage
            if r["Package"] == "26.00" and r["Firm"] == "Alder Works"
        ]
        self.assertTrue(
            all(
                (r["Confirm"], r["Included in"], r["Value"])
                == ("Included", "Lump sum", None)
                for r in vague
            )
        )
        _, workbook = p.exports(folder, run, {}, summary, coverage, tallies)
        wb = load_workbook(BytesIO(workbook), read_only=True)
        rows = list(wb["Extraction notes"].values)
        wb.close()
        self.assertEqual(len(rows) - 1, sum(1 for d in run["files"] if d.get("style")))

    def test_mix_is_repeatable(self):
        _, first, _ = self.build(self.styled_demo())
        _, second, _ = self.build(self.styled_demo())
        self.assertEqual(
            [(d["file"], d.get("style")) for d in first["files"]],
            [(d["file"], d.get("style")) for d in second["files"]],
        )

    def test_style_needs_a_matching_format(self):
        s = core.preset("Roofing stress test")
        s["bidders"][1].update(format="xlsx", style=styles.BID_FORM)
        with self.assertRaisesRegex(ValueError, "needs a pdf document"):
            core.validate(s)
        s["bidders"][1]["style"] = "Fancy"
        with self.assertRaisesRegex(ValueError, "Unknown proposal style"):
            core.validate(s)

    def test_every_style_and_format(self):
        base = core.preset("Roofing stress test")
        _, standard_award = core.evaluate(base, POLICY)
        for style, formats in styles.FORMATS.items():
            for fmt in formats:
                with self.subTest(style=style, format=fmt):
                    s = core.preset("Roofing stress test")
                    s["proposal_styles"] = "Realistic mix"
                    s["bidders"][0].update(format=fmt, style=style)
                    s["bidders"][0]["alternates"] = [
                        {"description": "Upgrade membrane", "amount": 42000}
                    ]
                    folder = core.RUNS / core.generate(s, core.MODELS, False)
                    run = core.read(folder / "run.json")
                    doc = next(d for d in run["files"] if d["firm"] == "Alder Works")
                    self.assertEqual(doc.get("style", styles.STANDARD), style)
                    text = core.ingest.read(folder / doc["file"])["text"]
                    self.assertIn("Alder Works", text)
                    self.assertIn(500000.0, styles.amounts(text))
                    self.assertIn(42000.0, styles.amounts(text))
                    self.assertEqual(
                        core.evaluate(run["scenario"], POLICY)[1], standard_award
                    )

    def test_tax_wording_follows_the_gc_tax_adder(self):
        # Only a bid the GC adds sales tax to may say its price excludes tax,
        # and the printed rate must match the adder.
        for style, formats in [
            (styles.STRUCTURED, ["pdf", "docx", "xlsx"]),
            (styles.FORMAL, ["pdf"]),
        ]:
            for fmt in formats:
                for tax in (0.0, 26500.0):
                    with self.subTest(style=style, format=fmt, tax=tax):
                        s = core.preset("Roofing stress test")
                        s["proposal_styles"] = "Realistic mix"
                        s["bidders"][0].update(format=fmt, style=style, tax=tax)
                        folder = core.RUNS / core.generate(s, core.MODELS, False)
                        run = core.read(folder / "run.json")
                        doc = next(
                            d for d in run["files"] if d["firm"] == "Alder Works"
                        )
                        text = " ".join(
                            core.ingest.read(folder / doc["file"])["text"].split()
                        )
                        if tax:
                            self.assertIn("5.3%", text)
                            self.assertIn("sales tax", text)
                            self.assertNotIn("includes all applicable sales", text)
                            self.assertNotIn("tax included", text)
                        else:
                            self.assertNotIn("If job is taxable", text)
                            self.assertNotIn("tax excluded", text)
                            self.assertNotIn("We do not include sales tax", text)

    def test_mix_scans_only_its_own_informal_picks(self):
        s = dict(name="P", trade="Roofing", proposal_styles="Realistic mix")
        b = dict(firm="X", format="pdf", style=styles.INFORMAL)
        self.assertFalse(styles.scanned(s, b, styles.INFORMAL))
        self.assertFalse(styles.scanned(s, dict(b, style="Auto"), styles.FORMAL))
        picks = [
            styles.scanned(s, dict(b, firm=f"Firm {i}", style="Auto"), styles.INFORMAL)
            for i in range(200)
        ]
        self.assertTrue(10 < sum(picks) < 110)

    def test_single_trade_revision_on_bid_form(self):
        s = core.preset("Revision and partial scope")
        s["proposal_styles"] = "Realistic mix"
        s["bidders"][0].update(format="pdf", style=styles.BID_FORM)
        s["bidders"][1].update(format="pdf", style=styles.VAGUE)
        folder = core.RUNS / core.generate(s, core.MODELS, False)
        docs = core.read(folder / "run.json")["files"]
        original, revision = [d for d in docs if d["firm"] == "Alder Works"]
        self.assertNotIn("style", original)
        text = core.ingest.read(folder / revision["file"])["text"]
        self.assertIn("supersedes", text)
        self.assertIn("Complete roof assembly", text)
        partial = next(d for d in docs if d["firm"] == "Birch Assembly")
        text = core.ingest.read(folder / partial["file"])["text"]
        self.assertIn("We decline the remaining scope.", text)
        self.assertIn("Membrane materials", text)


if __name__ == "__main__":
    unittest.main()
