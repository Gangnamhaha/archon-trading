import py_compile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIR_NAMES = {".git", "__pycache__", ".venv", "venv"}


def _iter_python_files():
    for file_path in ROOT.rglob("*.py"):
        if any(part in EXCLUDED_DIR_NAMES for part in file_path.parts):
            continue
        yield file_path


class CompileSmokeTests(unittest.TestCase):
    def test_all_python_files_compile(self):
        for file_path in _iter_python_files():
            with self.subTest(file=str(file_path)):
                py_compile.compile(str(file_path), doraise=True)


if __name__ == "__main__":
    unittest.main()
