import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from hardware_diagnostics import diagnose_hardware, driver_lookup


class HardwareDiagnosticsTests(unittest.TestCase):
    def test_missing_inventory_is_not_no_devices_proof(self):
        with tempfile.TemporaryDirectory() as raw:
            report = diagnose_hardware(system="Linux", sys_root=Path(raw))
        self.assertTrue(report["issues"])
        self.assertFalse(report["physicalOutputsArmed"])
        self.assertEqual(report["qualification"], "hardware-tests-required")

    def test_composite_usb_binding_and_rescan_removal(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            bus = root / "bus/usb/devices"
            device = bus / "1-2"
            device.mkdir(parents=True)
            (device / "idVendor").write_text("1234")
            (device / "idProduct").write_text("abcd")
            (device / "product").write_text("<script>device</script>")
            (device / "serial").write_text("private-serial")
            interface = bus / "1-2:1.0"
            interface.mkdir()
            (interface / "bInterfaceClass").write_text("01")
            driver = root / "drivers/snd-usb-audio"
            driver.mkdir(parents=True)
            (interface / "driver").symlink_to(driver)
            report = diagnose_hardware(system="Linux", sys_root=root)
            item = report["devices"][0]
            self.assertEqual(item["driver"], "snd-usb-audio")
            self.assertEqual(item["hardwareId"], "USB:1234:ABCD")
            self.assertFalse(item["qualified"])
            self.assertNotIn("private-serial", json.dumps(report))
            (device / "idVendor").unlink()
            self.assertEqual(diagnose_hardware(system="Linux", sys_root=root)["devices"], [])

    def test_windows_problem_and_serial_redaction(self):
        row = {"Name": "Interface", "PNPDeviceID": r"USB\VID_1234&PID_ABCD\secret", "Service": "usbaudio2", "ConfigManagerErrorCode": 28}
        with patch("hardware_diagnostics._command_json", return_value=row):
            report = diagnose_hardware(system="Windows")
        self.assertEqual(report["devices"][0]["diagnosis"], "os-reported-problem")
        self.assertNotIn("secret", json.dumps(report))

    def test_mac_nested_inventory_does_not_claim_binding(self):
        tree = {"SPUSBDataType": [{"_items": [{"_name": "Audio", "vendor_id": "0x1234 (Vendor)", "product_id": "0xabcd", "serial_num": "secret"}]}]}
        with patch("hardware_diagnostics._command_json", return_value=tree):
            report = diagnose_hardware(system="Darwin")
        self.assertEqual(report["devices"][0]["diagnosis"], "driver-status-unknown")
        self.assertNotIn("secret", json.dumps(report))

    def test_failed_or_malformed_native_probe_is_diagnostic(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("probe", 20), ValueError()):
            with self.subTest(error=type(error).__name__), patch("hardware_diagnostics._command_json", side_effect=error):
                report = diagnose_hardware(system="Windows")
                self.assertTrue(report["issues"])
                self.assertEqual(report["devices"], [])

    def test_lookup_is_encoded_id_only(self):
        links = driver_lookup("Windows", "USB:1234:abcd")
        url = urlparse(links[1]["url"])
        self.assertEqual(url.hostname, "www.catalog.update.microsoft.com")
        self.assertEqual(parse_qs(url.query)["q"], [r"USB\VID_1234&PID_ABCD"])
        self.assertEqual(len(driver_lookup("Windows", "USB:1234:abcd; private data")), 1)
        self.assertEqual(driver_lookup("Other", "USB:1234:abcd"), [])

    def test_unknown_os_does_not_run_commands(self):
        with patch("hardware_diagnostics._command_json") as command:
            self.assertTrue(diagnose_hardware(system="Other")["issues"])
            command.assert_not_called()
