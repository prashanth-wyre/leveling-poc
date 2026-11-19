import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core
from ranking import rank_bids


def policy(template):
    return dict(
        template=template,
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


class SimulatorTests(unittest.TestCase):
    def test_award_changes(self):
        scenario = core.preset("Roofing stress test")
        rows, winner = core.evaluate(scenario, policy(core.POLICIES[0]))
        self.assertEqual(winner, "Alder Works")
        rows, winner = core.evaluate(scenario, policy(core.POLICIES[1]))
        self.assertEqual(winner, "Birch Assembly")
        self.assertEqual([r["Adjusted"] for r in rows[:2]], [510000, 507000])
        self.assertEqual(
            [r["Status"] for r in rows[2:]],
            ["Clarify price", "Clarify price", "Unrelated scope", "Regret"],
        )

    def test_policy_ranks_and_ties(self):
        scenario = core.preset("Roofing stress test")
        for template, expected in [(core.POLICIES[0], [1, 2]), (core.POLICIES[1], [2, 1])]:
            rows, _ = core.evaluate(scenario, policy(template))
            rank_bids(rows, template)
            self.assertEqual([r["Rank"] for r in rows], expected + ["Unranked"] * 4)
        rows = [{"Status": "Eligible", "Score": n} for n in (100, 75, 100)]
        rank_bids(rows, "Weighted best value")
        self.assertEqual([r["Rank"] for r in rows], [1, 3, 1])
        rank_bids(rows, "Split or combined packages")
        self.assertTrue(all(r["Rank"] == "By package" for r in rows))

    def test_split(self):
        rows, winner = core.evaluate(
            core.preset("Split award"), policy("Split or combined packages")
        )
        self.assertIn("480,000", winner)

    def test_no_award(self):
        for name in ("All regrets", "All unrelated"):
            self.assertEqual(
                core.evaluate(core.preset(name), policy(core.POLICIES[0]))[1],
                "No award",
            )

    def test_renders_documents(self):
        import pymupdf

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(core, "RUNS", Path(tmp)),
        ):
            d = core.RUNS / core.generate(
                core.preset("Document extraction stress"), core.MODELS, False
            )
            run = core.read(d / "run.json")
            self.assertEqual(len(run["files"]), 9)
            book = next(
                d / x["file"] for x in run["files"] if x["firm"] == "Alder Works"
            )
            self.assertGreater(core.load_workbook(book).active.max_row, 400)
            scan = next(
                d / x["file"] for x in run["files"] if x["firm"] == "Cedar Group"
            )
            with pymupdf.open(scan) as doc:
                self.assertFalse(doc[0].get_text().strip())
                self.assertTrue(doc[0].get_images())
