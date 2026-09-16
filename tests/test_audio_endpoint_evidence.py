import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from audio_endpoint_evidence import windows_endpoint_probe, macos_endpoint_probe
from hardware_diagnostics import diagnose_hardware


class AudioEndpointEvidenceTests(unittest.TestCase):
    def test_windows_endpoint_and_signed_driver_evidence_redacts_instance_ids(self):
        payload = {
            "endpoints": [{
                "Status": "OK", "Class": "AudioEndpoint", "FriendlyName": "Speakers (Interface)",
                "InstanceId": r"SWD\MMDEVAPI\{private-endpoint-token}"
            }],
            "drivers": [{
                "DeviceName": "USB Audio Device", "DeviceID": r"USB\VID_1235&PID_8219\PRIVATE-SERIAL",
                "DriverProviderName": "Focusrite Audio Engineering, Ltd.", "DriverVersion": "4.150.0.432",
                "InfName": "oem42.inf", "IsSigned": True, "Signer": "Microsoft Windows Hardware Compatibility Publisher"
            }]
        }
        endpoints, drivers = windows_endpoint_probe(lambda command: payload)
        self.assertEqual(endpoints[0]["name"], "Speakers (Interface)")
        self.assertTrue(endpoints[0]["endpointIdentityHash"].startswith("sha256:"))
        self.assertNotIn("private-endpoint-token", json.dumps(endpoints))
        self.assertEqual(drivers[0]["hardwareId"], "USB:1235:8219")
        self.assertEqual(drivers[0]["version"], "4.150.0.432")
        self.assertTrue(drivers[0]["signed"])
        self.assertNotIn("PRIVATE-SERIAL", json.dumps(drivers))
        self.assertFalse(drivers[0]["qualified"])

    def test_windows_probe_command_is_fixed_read_only_inventory(self):
        seen = []
        def runner(command):
            seen.append(command)
            return {"endpoints": [], "drivers": []}
        windows_endpoint_probe(runner)
        joined = " ".join(seen[0])
        self.assertIn("Get-PnpDevice", joined)
        self.assertIn("Win32_PnPSignedDriver", joined)
        self.assertIn("ConvertTo-Json", joined)
        self.assertNotIn("Set-", joined)
        self.assertNotIn("Remove-", joined)

    def test_macos_coreaudio_evidence_hashes_uid_and_does_not_invent_package_semantics(self):
        payload = {"SPAudioDataType": [{
            "_name": "Example USB Interface",
            "coreaudio_device_uid": "private-coreaudio-device-uid",
            "coreaudio_device_manufacturer": "Example Audio",
            "coreaudio_device_transport": "USB",
            "coreaudio_device_input": "4",
            "coreaudio_device_output": "4",
        }]}
        endpoints, drivers = macos_endpoint_probe(lambda command: payload)
        self.assertEqual(endpoints[0]["manufacturer"], "Example Audio")
        self.assertEqual(endpoints[0]["transport"], "USB")
        self.assertTrue(endpoints[0]["endpointIdentityHash"].startswith("sha256:"))
        self.assertNotIn("private-coreaudio-device-uid", json.dumps(endpoints))
        self.assertEqual(drivers[0]["evidenceKind"], "coreaudio-device-present")
        self.assertEqual(drivers[0]["packageSemantics"], "not-applicable-no-windows-style-package-claim")
        self.assertIsNone(drivers[0]["version"])

    def test_diagnostics_keeps_usb_inventory_when_endpoint_probe_fails(self):
        usb_row = {"Name": "Interface", "PNPDeviceID": r"USB\VID_1234&PID_ABCD\secret", "Service": "usbaudio2", "ConfigManagerErrorCode": 0}
        with patch("hardware_diagnostics._command_json", side_effect=[usb_row, ValueError("bad endpoint payload")]):
            report = diagnose_hardware(system="Windows")
        self.assertEqual(report["devices"][0]["hardwareId"], "USB:1234:ABCD")
        self.assertEqual(report["audioEndpoints"], [])
        self.assertEqual(report["audioDrivers"], [])
        self.assertTrue(report["endpointIssues"])
        self.assertEqual(report["scanStatus"], "partial-or-unavailable")
        self.assertNotIn("secret", json.dumps(report))

    def test_windows_diagnostics_exposes_endpoint_and_driver_evidence_separately(self):
        usb_row = {"Name": "Interface", "PNPDeviceID": r"USB\VID_1234&PID_ABCD\secret", "Service": "usbaudio2", "ConfigManagerErrorCode": 0}
        evidence = {"endpoints": [{"Status":"OK","FriendlyName":"Speakers","InstanceId":"private-endpoint"}],
                    "drivers": [{"DeviceName":"Interface","DeviceID":r"USB\VID_1234&PID_ABCD\secret","DriverProviderName":"Vendor","DriverVersion":"1.2","InfName":"oem1.inf","IsSigned":True,"Signer":"Signer"}]}
        with patch("hardware_diagnostics._command_json", side_effect=[usb_row, evidence]):
            report = diagnose_hardware(system="Windows")
        self.assertEqual(len(report["devices"]), 1)
        self.assertEqual(len(report["audioEndpoints"]), 1)
        self.assertEqual(len(report["audioDrivers"]), 1)
        self.assertEqual(report["audioDrivers"][0]["hardwareId"], "USB:1234:ABCD")
        self.assertEqual(report["qualification"], "hardware-tests-required")
        self.assertFalse(report["physicalOutputsArmed"])


if __name__ == "__main__":
    unittest.main()
