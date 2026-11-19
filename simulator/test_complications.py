from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile

import complications as c
import core
import project as p
from openpyxl import load_workbook


class ComplicationTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        run_dir = patch.object(core, "RUNS", Path(tmp.name))
        run_dir.start()
        self.addCleanup(run_dir.stop)

    def generate(self, settings, draft=None):
        project = draft or p.starter()
        project["complications"] = settings
        folder = core.RUNS / p.generate(project, {}, False)
        return folder, core.read(folder / "run.json")

    def test_individual_exports(self):
        for name, cfg in c.OPTIONS.items():
            with self.subTest(scenario=name):
                folder, run = self.generate({name: cfg})
                summary, coverage, tallies = p.results(run, {})
                checks = c.checks(run, summary, tallies)
                z, w = p.exports(folder, run, {}, summary, coverage, tallies)
                wb = load_workbook(BytesIO(w), read_only=True)
                self.assertEqual(wb["Scenario checks"].max_row, len(checks) + 1)
                wb.close()
                with ZipFile(BytesIO(z)) as archive:
                    self.assertFalse(
                        any("answer" in f.lower() for f in archive.namelist())
                    )
                code = cfg.get("package", cfg.get("earthwork"))
                bidder = run["packages"][code]["bidders"][0]
                docs = [
                    core.ingest.read(folder / d["file"])["text"]
                    for d in run["files"]
                    if d["package"] == code and d["firm"] == bidder["firm"]
                ]
                expected = {
                    c.SHARED: "BF-01",
                    c.AMBIG: "Included",
                    c.PARTIAL: "Excluded",
                    c.COST: "Submitted total",
                    c.ALT: "ALT-DAS",
                    c.WARRANTY: "Motor coverage: 5",
                    c.HISTORY: "ER-01",
                }
                self.assertIn(expected[name], " ".join(docs))

    def test_policy_replay_and_commitments(self):
        draft = p.starter()
        earth = next(pkg for pkg in draft["packages"] if pkg["code"] == "31.00")
        earth["bidders"][0]["years"] = 1
        earth["bidders"][1]["post_bid"] = 500000
        earth["bidders"][2]["years"] = 1
        cfg = deepcopy(c.OPTIONS)
        cfg[c.SHARED]["exception_firm"] = earth["bidders"][1]["firm"]
        cfg[c.ALT]["disposition"] = "Accepted"
        folder, run = self.generate(cfg, draft)
        before = {d["file"]: (folder / d["file"]).read_bytes() for d in run["files"]}
        summary, _, tallies = p.results(run, {})
        checks = c.checks(run, summary, tallies)
        self.assertIn("1 carrier", checks[0]["Answer"])
        base = sum(row["Package value"] or 0 for row in summary)
        self.assertIn(
            f"{base + 821801.61 + 157670 + 12000 + 12000 - 50000:,.2f}",
            checks[-1]["Answer"],
        )
        summary, _, tallies = p.results(
            run, {"31.00": dict(p.DEFAULT_POLICY, min_years=2)}
        )
        checks = c.checks(run, summary, tallies)
        self.assertIn("0 carriers", checks[0]["Answer"])
        self.assertEqual(checks[-1]["Result"], "Needs clarification")
        self.assertTrue(
            all((folder / key).read_bytes() == data for key, data in before.items())
        )

    def test_clarification_and_validation(self):
        cfg = deepcopy(c.OPTIONS)
        cfg[c.AMBIG]["statement"] = "x65000"
        cfg[c.PARTIAL]["disposition"] = "Needs clarification"
        cfg[c.HISTORY]["later_price"] = "Unstated"
        cfg[c.WARRANTY]["motor_offer"] = "Silent"
        _folder, run = self.generate(cfg)
        summary, _coverage, tallies = p.results(
            run, {"12.20": dict(p.DEFAULT_POLICY, template="Warranty-adjusted cost")}
        )
        self.assertIsNone(tallies["12.20"][0]["Adjusted"])
        self.assertEqual(tallies["09.67"][0]["Status"], "Clarify scope")
        self.assertEqual(tallies["32.90"][0]["Status"], "Clarify scope")
        self.assertEqual(
            c.checks(run, summary, tallies)[-1]["Result"], "Needs clarification"
        )
        cfg[c.AMBIG]["item"] = "absent"
        with self.assertRaisesRegex(ValueError, "Missing item"):
            c.compile_draft(dict(p.starter(), complications=cfg))
