"""PT-19: API HITL (TestClient) — health, cola, item, veredicto, manual, catálogo, config."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import polars as pl
from fastapi.testclient import TestClient

from projecttype.api.main import create_app

_TIPO_ID = "ENERGIA.ALUMBRADO_PUBLICO.ALUMBRADO_PUBLICO"


def _seed_store(base: Path) -> None:
    """CONSULTAS_EBI (5 proyectos ENERGIA/ALUMBRADO PUBLICO) + enr para 2 de ellos."""
    from sni_commons.contracts import ENR_TIPO_PROYECTO_CONTRACT
    from sni_commons.store import BipDataStore

    ebi = pl.DataFrame(
        {
            "EBI_CODIGO": ["100", "200", "300", "400", "500"],
            "SOL_CLAVE": ["1"] * 5,
            "EBI_NOMBRE": [f"Alumbrado sector {i}" for i in range(1, 6)],
            "SEC_CLAVE": ["5"] * 5,   # ENERGIA
            "SBS_CLAVE": ["1088"] * 5,  # ALUMBRADO PUBLICO
            "EBI_DESCRIPCION": ["Reposición luminarias"] * 5,
            "EBI_JUSTIFICACION": ["Seguridad vial"] * 5,
        }
    )
    store = BipDataStore(base)
    store.upsert_dataframe(
        "CONSULTAS_EBI", ebi, key_cols=["EBI_CODIGO", "SOL_CLAVE"], writer="test"
    )
    # Solo 100 y 200 clasificados (propuestas del sistema); 300/400/500 pendientes.
    enr = pl.DataFrame(
        {
            "EBI_CODIGO": ["100", "200"],
            "tipo_final_id": [_TIPO_ID, _TIPO_ID],
            "tipo_final_nombre": ["ALUMBRADO PUBLICO", "ALUMBRADO PUBLICO"],
            "score_final": [0.95, 0.55],
            "nivel_final": [1, 3],
            "nivel_asignacion": ["L1", "L3"],
            "confianza": [0.95, 0.55],
            "evidencia_resumen": ["keyword: alumbrado", "L3: obra de iluminación"],
            "modelo": ["n/a", "gemini-2.5-flash"],
            "prompt_version": ["p1", "p1"],
            "taxonomy_hash": ["t1", "t1"],
            "enricher_version": ["projecttype@test", "projecttype@test"],
        }
    )
    ENR_TIPO_PROYECTO_CONTRACT.validate(enr.columns, source="test")
    store.upsert_dataframe(
        "enr_tipo_proyecto", enr, key_cols=["EBI_CODIGO"], writer="projecttype/test"
    )


def _write_l3_cache(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "codigo_bip": "200",
                "model": "gemini-2.5-flash",
                "prompt_version": "p1",
                "l3_estado": "asignado",
                "l3_tipo_id": _TIPO_ID,
                "l3_razonamiento": "Análisis: obra de iluminación pública nocturna.",
                "l3_tipos_secundarios_nombres": "SEÑALETICA",
            }
        )
        + "\n",
        encoding="utf-8",
    )


class TestApiHitl(unittest.TestCase):
    def _client(self, base: Path, tmp: Path) -> TestClient:
        cache = tmp / "l3_cache.jsonl"
        _write_l3_cache(cache)
        app = create_app(
            data_dir=base,
            verdicts_path=tmp / "veredictos.jsonl",
            l3_cache_path=cache,
            load_snapshot=True,
        )
        return TestClient(app)

    def test_health_and_catalogo(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "store"
            base.mkdir()
            _seed_store(base)
            client = self._client(base, Path(d))
            h = client.get("/api/health")
            self.assertEqual(h.status_code, 200)
            self.assertTrue(h.json()["snapshot_loaded"])
            self.assertEqual(h.json()["total_clasificados"], 2)
            cat = client.get("/api/catalogo/arbol").json()
            self.assertEqual(cat["n_tipos"], 326)
            self.assertGreater(len(cat["sectores"]), 0)

    def test_summary_and_queue(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "store"
            base.mkdir()
            _seed_store(base)
            client = self._client(base, Path(d))
            s = client.get("/api/review/summary").json()
            self.assertEqual(s["total_clasificados"], 2)
            self.assertEqual(s["pendientes"], 2)
            self.assertEqual(s["por_origen"].get("l1"), 1)
            self.assertEqual(s["por_origen"].get("l3"), 1)
            # Cola ordenada por confianza asc: el L3 (0.55) va primero.
            q = client.get("/api/review/queue").json()
            self.assertEqual(q["total"], 2)
            self.assertEqual(q["items"][0]["ebi_codigo"], "200")
            self.assertEqual(q["items"][0]["subsector"], "ALUMBRADO PUBLICO")
            # Filtro por origen.
            q_l1 = client.get("/api/review/queue", params={"origen": "l1"}).json()
            self.assertEqual(q_l1["total"], 1)
            self.assertEqual(q_l1["items"][0]["ebi_codigo"], "100")

    def test_item_includes_cot(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "store"
            base.mkdir()
            _seed_store(base)
            client = self._client(base, Path(d))
            it = client.get("/api/review/item/200").json()
            self.assertEqual(it["origen"], "l3")
            self.assertIn("iluminación", it["cot"])
            self.assertIn("SEÑALETICA", it["tipos_secundarios"])
            self.assertEqual(client.get("/api/review/item/999").status_code, 404)

    def test_save_verdict_persists(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "store"
            base.mkdir()
            _seed_store(base)
            tmp = Path(d)
            client = self._client(base, tmp)
            r = client.post(
                "/api/review/item/200/verdict",
                json={"veredicto": "aceptado", "revisor": "felipe"},
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["tipo_final_id"], _TIPO_ID)
            # Persistió en el JSONL.
            lines = (tmp / "veredictos.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["revisor"], "felipe")
            # Se refleja en summary.
            s = client.get("/api/review/summary").json()
            self.assertEqual(s["revisados"], 1)
            self.assertEqual(s["por_veredicto"].get("aceptado"), 1)

    def test_manual_subsectores_y_pendientes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "store"
            base.mkdir()
            _seed_store(base)
            client = self._client(base, Path(d))
            subs = client.get("/api/manual/subsectores").json()
            energia = [s for s in subs["items"] if s["subsector"] == "ALUMBRADO PUBLICO"]
            self.assertEqual(len(energia), 1)
            self.assertEqual(energia[0]["n_clasificados"], 2)
            self.assertEqual(energia[0]["n_pendientes"], 3)
            self.assertEqual(energia[0]["n_tipos"], 1)
            # Pendientes de ese subsector: 300/400/500.
            pend = client.get(
                "/api/manual/pendientes", params={"subsector": "ALUMBRADO PUBLICO"}
            ).json()
            self.assertEqual(pend["total"], 3)
            self.assertEqual({p["ebi_codigo"] for p in pend["items"]}, {"300", "400", "500"})

    def test_manual_clasificar(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "store"
            base.mkdir()
            _seed_store(base)
            client = self._client(base, Path(d))
            r = client.post(
                "/api/manual/clasificar/300",
                json={"veredicto": "corregido", "tipo_final_id": _TIPO_ID, "revisor": "ana"},
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["tipo_final_nombre"], "ALUMBRADO PUBLICO")
            self.assertEqual(r.json()["origen"], "manual")
            # 300 ya no aparece como pendiente.
            pend = client.get(
                "/api/manual/pendientes", params={"subsector": "ALUMBRADO PUBLICO"}
            ).json()
            self.assertEqual(pend["total"], 2)
            # El badge de cobertura refleja el veredicto humano (2 sistema + 1 manual).
            subs = client.get("/api/manual/subsectores").json()
            energia = [s for s in subs["items"] if s["subsector"] == "ALUMBRADO PUBLICO"][0]
            self.assertEqual(energia["n_clasificados"], 3)
            self.assertEqual(energia["n_pendientes"], 2)


class TestApiConfig(unittest.TestCase):
    def _client(self) -> TestClient:
        return TestClient(create_app(load_snapshot=True, data_dir=None))

    def test_list_and_read_prompts(self) -> None:
        client = self._client()
        files = client.get("/api/config/files").json()
        kinds = {f["kind"]: f["writable"] for f in files}
        self.assertTrue(kinds["l3"])
        self.assertFalse(kinds["taxonomia"])
        l3 = client.get("/api/config/file/l3").json()
        self.assertGreater(len(l3["content"]), 50)

    def test_write_taxonomia_rejected(self) -> None:
        client = self._client()
        r = client.put("/api/config/file/taxonomia", json={"content": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("solo lectura", r.json()["detail"])

    def test_write_prompt_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "l3.yaml"
            target.write_text("original: true\n", encoding="utf-8")
            from projecttype.review import config_files

            with (
                patch.dict(config_files._PATHS, {"l3": target}),
                patch.object(config_files, "VERSIONS_PATH", Path(d) / "versions.json"),
                patch.object(config_files, "_git_write_through", return_value=True),
            ):
                client = self._client()
                r = client.put("/api/config/file/l3", json={"content": "nuevo: 1\n"})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["content"], "nuevo: 1\n")
                self.assertTrue(r.json()["writable"])
            self.assertEqual(target.read_text(encoding="utf-8"), "nuevo: 1\n")


if __name__ == "__main__":
    unittest.main()
