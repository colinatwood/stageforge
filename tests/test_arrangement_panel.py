import subprocess
import unittest
from pathlib import Path


class ArrangementPanelTests(unittest.TestCase):
    def test_pointer_keyboard_and_snap_workflow(self):
        subprocess.run(["node", str(Path(__file__).with_name("arrangement_panel_test.js"))], check=True)


if __name__ == "__main__":
    unittest.main()
