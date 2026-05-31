"""Tests de tipos compuestos."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from proyecttype.composite import (
    CompositeIndex,
    components_match_text,
    parse_tipo_components,
)
from proyecttype import ClassifierL1, Taxonomia
from proyecttype.paths import DEFAULT_TAXONOMY
from proyecttype.scorer import EstadoClasificacion
from proyecttype.text_utils import normalize_tipo_name


class TestCompositeParsing(unittest.TestCase):
    def test_jardin_y_sala_cuna(self) -> None:
        siblings = frozenset(
            {
                normalize_tipo_name("JARDIN INFANTIL"),
                normalize_tipo_name("SALA CUNA"),
                normalize_tipo_name("JARDIN INFANTIL Y SALA CUNA"),
            }
        )
        parts = parse_tipo_components("JARDIN INFANTIL Y SALA CUNA", siblings)
        self.assertEqual(parts.and_parts, ("jardin infantil", "sala cuna"))
        self.assertTrue(
            components_match_text(
                parts,
                "construccion jardin infantil con modulo sala cuna para lactantes",
            )
        )

    def test_red_alcantarillado_y_planta(self) -> None:
        siblings = frozenset(
            {
                normalize_tipo_name("RED DE ALCANTARILLADO"),
                normalize_tipo_name("PLANTA TRATAMIENTO AGUAS SERVIDAS"),
                normalize_tipo_name("RED DE ALCANTARILLADO Y PLANTA TRATAMIENTO AGUAS SERVIDAS"),
            }
        )
        parts = parse_tipo_components(
            "RED DE ALCANTARILLADO Y PLANTA TRATAMIENTO AGUAS SERVIDAS", siblings
        )
        self.assertEqual(len(parts.and_parts), 2)
        self.assertTrue(
            components_match_text(
                parts,
                "construccion red de alcantarillado y planta de tratamiento de aguas servidas",
            )
        )

    def test_casetas_slash_jerarquico(self) -> None:
        siblings = frozenset(
            {
                normalize_tipo_name("CASETAS SANITARIAS/ALCANTARILLADO"),
                normalize_tipo_name("CASETAS SANITARIAS/ALCANTARILLADO/PLANTA DE TRATAMIENTO"),
            }
        )
        parts = parse_tipo_components(
            "CASETAS SANITARIAS/ALCANTARILLADO/PLANTA DE TRATAMIENTO", siblings
        )
        self.assertEqual(len(parts.and_parts), 3)

    def test_colegio_basica_media_no_se_parte(self) -> None:
        siblings = frozenset(
            {
                normalize_tipo_name("COLEGIO BASICA/MEDIA CIENTIFICO HUMANISTA"),
                normalize_tipo_name("ESCUELA BASICA"),
            }
        )
        parts = parse_tipo_components("COLEGIO BASICA/MEDIA CIENTIFICO HUMANISTA", siblings)
        self.assertEqual(len(parts.and_parts), 1)

    def test_escuela_basica_mas_kinder_y_o_prekinder(self) -> None:
        siblings = frozenset(
            {
                normalize_tipo_name("ESCUELA BASICA"),
                normalize_tipo_name("ESCUELA BASICA MAS KINDER Y/O PREKINDER"),
            }
        )
        parts = parse_tipo_components("ESCUELA BASICA MAS KINDER Y/O PREKINDER", siblings)
        self.assertEqual(parts.and_parts, ("escuela basica",))
        self.assertEqual(parts.or_groups, (("kinder", "prekinder"),))


class TestCompositeIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tax = Taxonomia.from_yaml(DEFAULT_TAXONOMY)
        cls.clf = ClassifierL1.from_yaml(DEFAULT_TAXONOMY)

    def test_index_detecta_relaciones(self) -> None:
        tipos = self.tax.tipos_para("EDUCACION", "EDUCACION PREBASICA")
        index = CompositeIndex.from_tipos(tipos)
        self.assertGreater(len(index.relations), 0)
        ji_relation = next(
            r for r in index.relations if "JARDIN INFANTIL Y SALA CUNA" in r.composite.nombre
        )
        subset_names = {t.nombre for t in ji_relation.subsets}
        self.assertIn("JARDIN INFANTIL", subset_names)
        self.assertIn("SALA CUNA", subset_names)

    def test_red_alcantarillado_compuesto(self) -> None:
        result = self.clf.classify_row(
            sector="RECURSOS HIDRICOS",
            subsector="EVACUACION DISPOSICION FINAL AGUAS SERVIDAS",
            nombre="CONSTRUCCION RED DE ALCANTARILLADO Y PTAS",
            descripcion="incluye red de alcantarillado y planta de tratamiento de aguas servidas",
        )
        self.assertEqual(
            result.tipo_nombre,
            "RED DE ALCANTARILLADO Y PLANTA TRATAMIENTO AGUAS SERVIDAS",
        )


if __name__ == "__main__":
    unittest.main()
