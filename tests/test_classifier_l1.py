"""Tests básicos del clasificador Nivel 1."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from proyecttype import ClassifierL1, EstadoClasificacion
from proyecttype.paths import DEFAULT_TAXONOMY

TAXONOMY = DEFAULT_TAXONOMY


class TestClassifierL1(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.clf = ClassifierL1.from_yaml(TAXONOMY)

    def test_biblioteca_asignada(self) -> None:
        result = self.clf.classify_row(
            sector="CULTURA Y PATRIMONIO",
            subsector="CULTURA",
            nombre="REPOSICION BIBLIOTECA MUNICIPAL TEODORO SCHMIDT",
            descripcion="CONSTRUCCION DE UN EDIFICIO PARA BIBLIOTECA COMUNAL",
        )
        self.assertEqual(result.estado, EstadoClasificacion.ASIGNADO)
        self.assertEqual(result.tipo_nombre, "BIBLIOTECA")
        self.assertGreaterEqual(result.score, 4)

    def test_sin_taxonomia(self) -> None:
        result = self.clf.classify_row(sector="SECTOR INEXISTENTE", subsector="X")
        self.assertEqual(result.estado, EstadoClasificacion.SIN_TAXONOMIA)

    def test_alias_deportes_recreativo(self) -> None:
        result = self.clf.classify_row(
            sector="DEPORTES",
            subsector="DEPORTE RECREATIVO",
            nombre="CONSTRUCCION CANCHA DE FUTBOL CARPETA SINTETICA",
        )
        self.assertIn(
            result.estado,
            (EstadoClasificacion.ASIGNADO, EstadoClasificacion.AMBIGUO),
        )
        self.assertEqual(result.subsector_resuelto, "RECREATIVO")

    def test_jardin_infantil_y_sala_cuna_compuesto(self) -> None:
        result = self.clf.classify_row(
            sector="EDUCACION",
            subsector="EDUCACION PREBASICA",
            nombre="CONSTRUCCION JARDIN INFANTIL SECTOR PURINGUE RICO, MARIQUINA",
            descripcion="capacidad para 20 lactantes en nivel sala cuna y 24 parvulos en nivel medio",
        )
        self.assertEqual(result.estado, EstadoClasificacion.ASIGNADO)
        self.assertEqual(result.tipo_nombre, "JARDIN INFANTIL Y SALA CUNA")

    def test_jardin_infantil_solo_sin_sala_cuna(self) -> None:
        result = self.clf.classify_row(
            sector="EDUCACION",
            subsector="EDUCACION PREBASICA",
            nombre="CONSTRUCCION JARDIN INFANTIL MUNICIPAL",
            descripcion="establecimiento para infantes en edad preescolar",
        )
        self.assertEqual(result.tipo_nombre, "JARDIN INFANTIL")

    def test_agua_potable_apr_sistema_rural(self) -> None:
        result = self.clf.classify_row(
            sector="RECURSOS HIDRICOS",
            subsector="AGUA POTABLE",
            nombre="MEJORAMIENTO SISTEMA APR COMUNIDAD EL ALMENDRO",
        )
        self.assertEqual(result.estado, EstadoClasificacion.ASIGNADO)
        self.assertEqual(result.tipo_nombre, "SISTEMA AGUA POTABLE RURAL")

    def test_agua_potable_excluye_riego(self) -> None:
        result = self.clf.classify_row(
            sector="RECURSOS HIDRICOS",
            subsector="AGUA POTABLE",
            nombre="SISTEMA DE RIEGO COMUNIDAD AGRICOLA",
        )
        self.assertEqual(result.estado, EstadoClasificacion.SIN_MATCH)

    def test_agua_potable_mixto_alcantarillado_ambiguo(self) -> None:
        """Exclusión penaliza pero no bloquea si hay señales fuertes de agua potable."""
        result = self.clf.classify_row(
            sector="RECURSOS HIDRICOS",
            subsector="AGUA POTABLE",
            nombre="MEJORAMIENTO RED AGUA POTABLE Y ALCANTARILLADO",
        )
        self.assertIn(
            result.estado,
            (EstadoClasificacion.AMBIGUO, EstadoClasificacion.ASIGNADO),
        )

    def test_salud_bc_cesfam(self) -> None:
        result = self.clf.classify_row(
            sector="SALUD",
            subsector="BAJA COMPLEJIDAD",
            nombre="CONSTRUCCION CESFAM LOS ALAMOS",
        )
        self.assertEqual(result.estado, EstadoClasificacion.ASIGNADO)
        self.assertEqual(result.tipo_nombre, "CENTRO DE SALUD FAMILIAR (CESFAM)")

    def test_justicia_cdp(self) -> None:
        result = self.clf.classify_row(
            sector="JUSTICIA",
            subsector="REHABILITACION ADULTOS",
            nombre="AMPLIACION CDP VALDIVIA",
        )
        self.assertEqual(result.estado, EstadoClasificacion.ASIGNADO)
        self.assertEqual(result.tipo_nombre, "CENTRO DE DETENCION PREVENTIVA (CDP)")

    def test_sala_cuna_no_por_lactancia_sola(self) -> None:
        result = self.clf.classify_row(
            sector="EDUCACION",
            subsector="EDUCACION PREBASICA",
            nombre="PROGRAMA SALA DE LACTANCIA MUNICIPAL",
        )
        self.assertNotEqual(result.tipo_nombre, "SALA CUNA")

    def test_resolve_transporte_urbano(self) -> None:
        tipos = self.clf.taxonomia.tipos_para(
            "TRANSPORTE", "TRANSPORTE URBANO,VIALIDAD PEATONAL"
        )
        self.assertGreater(len(tipos), 0)


if __name__ == "__main__":
    unittest.main()
