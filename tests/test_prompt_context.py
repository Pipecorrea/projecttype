"""Tests de contexto dinámico L3."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from proyecttype.prompt_context import (
    composite_relations_for_subsector,
    confusion_pairs_for_subsector,
    select_few_shot_examples,
)


class TestPromptContext(unittest.TestCase):
    def test_confusion_pairs_transporte(self) -> None:
        pairs = confusion_pairs_for_subsector(
            "TRANSPORTE URBANO, Y VIALIDAD PEATONAL",
            max_pairs=3,
        )
        self.assertGreater(len(pairs), 0)
        self.assertIn("tipo_a", pairs[0])

    def test_composite_relations_hidricos(self) -> None:
        rels = composite_relations_for_subsector(
            "RECURSOS HIDRICOS",
            "AGUAS LLUVIAS",
            max_relations=2,
        )
        self.assertGreater(len(rels), 0)

    def test_few_shot_selection_by_subsector(self) -> None:
        examples = select_few_shot_examples(
            "TRANSPORTE",
            "TRANSPORTE URBANO, Y VIALIDAD PEATONAL",
            max_examples=2,
        )
        self.assertGreater(len(examples), 0)
        ids = {ex["id"] for ex in examples}
        self.assertIn("transporte_vialidad_estructurante", ids)


if __name__ == "__main__":
    unittest.main()
