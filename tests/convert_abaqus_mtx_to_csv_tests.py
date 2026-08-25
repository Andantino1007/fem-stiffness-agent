import csv
import tempfile
import unittest
from pathlib import Path

from scripts.abaqus.convert_abaqus_mtx_to_csv import convert


class ConvertAbaqusMtxTests(unittest.TestCase):
    def convert_lines(self, lines: str) -> list[list[float]]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "matrix.mtx"
            output = root / "matrix.csv"
            source.write_text(lines, encoding="utf-8")
            convert(source, output)
            with output.open(newline="", encoding="utf-8") as handle:
                return [[float(value) for value in row] for row in csv.reader(handle)]

    def test_full_symmetric_coordinate_matrix_is_not_doubled(self) -> None:
        matrix = self.convert_lines("1 1 10\n1 2 3\n2 1 3\n2 2 20\n")

        self.assertEqual(matrix[0][0], 10.0)
        self.assertEqual(matrix[0][1], 3.0)
        self.assertEqual(matrix[1][0], 3.0)
        self.assertEqual(matrix[1][1], 20.0)

    def test_triangular_coordinate_matrix_is_completed(self) -> None:
        matrix = self.convert_lines("1 1 10\n1 2 3\n2 2 20\n")

        self.assertEqual(matrix[0][1], 3.0)
        self.assertEqual(matrix[1][0], 3.0)

    def test_inconsistent_symmetric_entries_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "inconsistent symmetric entries"):
            self.convert_lines("1 2 3\n2 1 4\n")


if __name__ == "__main__":
    unittest.main()
