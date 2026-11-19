import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from openpyxl import load_workbook

import core
import project as p


class ProjectSetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = patch.object(core, "RUNS", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def build(self, project):
        folder = self.root / p.generate(project, core.MODELS, False)
        return folder, core.read(folder / "run.json")

    def test_trade_tally_and_replay(self):
        project = p.school_demo()
        b = project["packages"][1]["bidders"][2]
        b.update(post_bid=1000, tax=200, sdi=100)
        folder, run = self.build(project)
        summary, coverage, tallies = p.results(run, {})
        electrical = [
            r for r in coverage if r["Package"] == "26.00" and r["Item ID"] == "I03"
        ]
        self.assertEqual([r["Confirm"] for r in electrical], p.STATES)
        self.assertEqual(electrical[2]["Allowance"], 43475)
        self.assertEqual(tallies["26.00"][3]["Rank"], "Unranked")
        row = tallies["26.00"][2]
        self.assertEqual(row["Total package value"], row["Submitted"] + 43475 + 1300)
        self.assertEqual(summary[1]["Review"], "Pending clarification")
        z, w = p.exports(folder, run, {}, summary, coverage, tallies)
        with ZipFile(BytesIO(z)) as archive:
            self.assertTrue(
                all(k.startswith(("gc/", "bids/")) for k in archive.namelist())
            )
            for code in ("03.30", "26.00", "32.90"):
                self.assertIn(f"gc/{code}/Award policy.txt", archive.namelist())
        wb = load_workbook(BytesIO(w), read_only=True)
        self.assertEqual(wb["Item Coverage"].max_row, 25)
        self.assertNotIn("Exposure", [row[1] for row in wb["26.00"].values])
        wb.close()
        for d in run["files"]:
            if not d["firm"] or d["package"] != "26.00":
                continue
            text = core.ingest.read(folder / d["file"])["text"]
            self.assertEqual("DAS testing" in text, d["firm"] != "Dune Construction")
            self.assertNotIn("Synthetic test document", text)
        self.assertIn(
            "Adjusted",
            p.results(
                run,
                {"26.00": dict(p.DEFAULT_POLICY, template="Warranty-adjusted cost")},
            )[2]["26.00"][0],
        )

    def test_tcjc_full_project(self):
        project = p.starter()
        folder, run = self.build(project)
        summary, coverage, tallies = p.results(run, {})
        self.assertEqual((len(tallies), len(summary)), (45, 47))
        self.assertEqual(list(tallies)[0], "01.35")
        self.assertAlmostEqual(
            sum(row["GC estimate"] for row in summary[:45]), 82180161.49903
        )
        self.assertEqual(summary[-1]["GC estimate"], 821801.61)
        self.assertEqual(summary[-2]["Review"], "Included")
        self.assertEqual(tallies["13.49"], [])
        self.assertEqual(tallies["99.10"], [])
        self.assertEqual(summary[44]["Package value"], 797907)
        self.assertIn("removed", summary[30]["Expected award"])
        self.assertEqual(
            {
                r["Confirm"]
                for r in coverage
                if r["Package"] == "26.00" and r["Item ID"] == "I03"
            },
            set(p.STATES),
        )
        zipped, workbook = p.exports(folder, run, {}, summary, coverage, tallies)
        with ZipFile(BytesIO(zipped)) as archive:
            self.assertIn("gc/13.49/Scope withdrawal.xlsx", archive.namelist())
            self.assertFalse(
                any(name.startswith("bids/13.49/") for name in archive.namelist())
            )
            self.assertIn("gc/Project estimate.xlsx", archive.namelist())
        wb = load_workbook(BytesIO(workbook), read_only=True)
        self.assertTrue(set(tallies).issubset(wb.sheetnames))
        self.assertEqual(wb["Estimate Summary"].max_row, 48)
        wb.close()

    def test_revisions_budget_and_allowance(self):
        s = core.preset("Revision and partial scope")
        s["bidders"][1].update(
            response="Budget", plug=60000, plug_basis="Surface preparation"
        )
        folder = self.root / core.generate(s, core.MODELS, False)
        docs = core.read(folder / "run.json")["files"]
        original, revision = [d for d in docs if d["firm"] == "Alder Works"]
        self.assertEqual(original["expected"]["doc_type"], "bid")
        text = core.ingest.read(folder / original["file"])["text"]
        self.assertIn("Submitted total USD", text)
        self.assertNotIn("supersedes", text)
        self.assertIn("2026-01-12", text)
        self.assertIn("supersedes", core.ingest.read(folder / revision["file"])["text"])
        budget = next(d for d in docs if d["firm"] == "Birch Assembly")
        self.assertEqual(budget["expected"]["doc_type"], "budget")
        allowance = next(d for d in docs if "allowances" in d["title"])
        evidence = core.ingest.read(folder / allowance["file"])["text"]
        self.assertIn("60000", evidence)
        self.assertIn("Surface preparation", evidence)
