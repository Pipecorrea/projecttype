"""Tests PT-23: split dev/holdout del golden expost."""

from __future__ import annotations

import unittest

from projecttype.golden_split import TAG_DEV, TAG_HOLDOUT, assign_dev_holdout_tags, split_summary


def _caso(caso_id: str, subsector: str) -> dict:
    return {
        "caso_id": caso_id,
        "input": {"Codigo BIP": caso_id},
        "esperado": {"tipo_proyecto": "X"},
        "tags": ["expost", f"subsector:{subsector}"],
    }


class TestGoldenSplit(unittest.TestCase):
    def test_split_is_deterministic(self) -> None:
        casos = [_caso(f"expost-{i:04d}", "Sub A") for i in range(20)]
        a = assign_dev_holdout_tags(casos, holdout_ratio=0.2, seed=42)
        b = assign_dev_holdout_tags(casos, holdout_ratio=0.2, seed=42)
        self.assertEqual(
            [c["tags"] for c in a],
            [c["tags"] for c in b],
        )

    def test_split_preserves_expost_and_subsector_tags(self) -> None:
        casos = [_caso("expost-1", "Educacion Basica y Media")]
        tagged = assign_dev_holdout_tags(casos, holdout_ratio=0.2, seed=7)
        tags = tagged[0]["tags"]
        self.assertIn("expost", tags)
        self.assertIn("subsector:Educacion Basica y Media", tags)
        self.assertTrue(TAG_DEV in tags or TAG_HOLDOUT in tags)

    def test_split_stratified_ratio_approximate(self) -> None:
        casos = []
        for sub in ("A", "B", "C", "D"):
            casos.extend(_caso(f"expost-{sub}-{i}", sub) for i in range(25))
        tagged = assign_dev_holdout_tags(casos, holdout_ratio=0.2, seed=99)
        summary = split_summary(tagged)
        self.assertEqual(summary["dev"] + summary["holdout"], 100)
        self.assertGreaterEqual(summary["holdout"], 15)
        self.assertLessEqual(summary["holdout"], 25)
        self.assertEqual(summary["subsectores_dev"], 4)
        self.assertEqual(summary["subsectores_holdout"], 4)

    def test_single_case_goes_to_dev(self) -> None:
        tagged = assign_dev_holdout_tags([_caso("expost-1", "Unico")], seed=1)
        self.assertIn(TAG_DEV, tagged[0]["tags"])
        self.assertNotIn(TAG_HOLDOUT, tagged[0]["tags"])


if __name__ == "__main__":
    unittest.main()
