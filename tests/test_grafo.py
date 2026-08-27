import unittest

from patos_agro.grafo import adicionar_conexoes_sem_ciclo, cria_ciclo


class TestConexoesSemCiclo(unittest.TestCase):
    def test_rejeita_conexao_que_fecharia_ciclo(self):
        adjacencias = [set() for _ in range(6)]
        for primeiro, segundo in [(0, 1), (2, 3), (4, 5)]:
            adjacencias[primeiro].add(segundo)
            adjacencias[segundo].add(primeiro)

        quantidade = adicionar_conexoes_sem_ciclo(
            adjacencias,
            [(1, 2), (3, 4), (5, 0)],
        )

        self.assertEqual(quantidade, 2)
        self.assertNotIn(0, adjacencias[5])
        self.assertTrue(cria_ciclo(adjacencias, 5, 0))


if __name__ == "__main__":
    unittest.main()
