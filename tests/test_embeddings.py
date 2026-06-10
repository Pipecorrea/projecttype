"""Tests de similitud coseno (Nivel 2)."""

from __future__ import annotations

import unittest

import numpy as np

from proyecttype.embeddings import cosine_top2, cosine_top2_batch


class TestCosineSimilarity(unittest.TestCase):
    def test_cosine_top2(self) -> None:
        matrix = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.8, 0.6, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype=np.float32,
        )
        query = np.array([0.9, 0.1, 0.0], dtype=np.float32)
        sim1, sim2, idx1, idx2 = cosine_top2(query, matrix)
        self.assertEqual(idx1, 0)
        self.assertGreater(sim1, sim2)

    def test_cosine_top2_batch(self) -> None:
        matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        queries = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        sim1, sim2, idx1, idx2 = cosine_top2_batch(queries, matrix)
        self.assertEqual(int(idx1[0]), 0)
        self.assertEqual(int(idx1[1]), 1)


if __name__ == "__main__":
    unittest.main()
