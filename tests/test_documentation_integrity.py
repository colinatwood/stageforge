import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationIntegrityTests(unittest.TestCase):
    def test_reference_board_links_to_existing_guidance(self):
        board = (ROOT / "docs" / "open-source-hardware-reference-board.md").read_text(
            encoding="utf-8"
        )
        links = re.findall(r"\]\(([^)]+\.md)\)", board)
        self.assertGreaterEqual(len(links), 4)
        for link in links:
            self.assertTrue((ROOT / "docs" / link).is_file(), link)

    def test_readme_lists_each_interoperability_guide(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guides = sorted((ROOT / "docs").glob("*-interoperability.md"))
        self.assertGreaterEqual(len(guides), 10)
        for guide in guides:
            self.assertIn(guide.name, readme, guide.name)


if __name__ == "__main__":
    unittest.main()
