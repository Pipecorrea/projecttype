"""Tests PT-17: conversor expost → golden."""

from __future__ import annotations

import unittest

from scripts.convert_expost_to_golden import canonical_tipo, normalize_bip


class TestConvertExpost(unittest.TestCase):
    def test_normalize_bip_quita_dv(self) -> None:
        self.assertEqual(normalize_bip("30039296-0"), "30039296")

    def test_canonical_tipo_aliases(self) -> None:
        self.assertEqual(
            canonical_tipo("Gimnasio Estandar"),
            "GIMNASIO ESTANDARD",
        )
        self.assertEqual(
            canonical_tipo("Biblioteca Municipal"),
            "Biblioteca Municipal",
        )


if __name__ == "__main__":
    unittest.main()
