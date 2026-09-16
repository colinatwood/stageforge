import subprocess
import unittest
from pathlib import Path


class MarkersPanelTests(unittest.TestCase):
    def test_marker_dom_workflow(self):
        subprocess.run(["node", str(Path(__file__).with_name("markers_panel_test.js"))], check=True)


if __name__ == "__main__":
    unittest.main()
