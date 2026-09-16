import subprocess
import unittest
from pathlib import Path


class AutomationPanelTests(unittest.TestCase):
    def test_automation_dom_workflow(self):
        subprocess.run(["node", str(Path(__file__).with_name("automation_panel_test.js"))], check=True)


if __name__ == "__main__":
    unittest.main()
