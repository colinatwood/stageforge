"""Read-only PnP inventory. Discovery and driver lookup never imply qualification."""
from __future__ import annotations

import json
import platform
import re
import subprocess
from pathlib import Path
from urllib.parse import urlencode
from driver_compatibility import assess_driver, load_catalog
from audio_endpoint_evidence import windows_endpoint_probe, macos_endpoint_probe

SOURCES = {
    "Linux": "https://docs.kernel.org/sound/alsa-configuration.html",
    "Windows": "https://learn.microsoft.com/en-us/windows-hardware/drivers/audio/usb-2-0-audio-drivers",
    "Darwin": "https://support.apple.com/guide/audio-midi-setup/welcome/mac",
}


def driver_lookup(system, hardware_id):
    """Only a validated VID/PID is sent in user-opened internet searches."""
    if system not in SOURCES:
        return []
    links = [{"label": "Official OS audio guidance", "url": SOURCES[system]}]
    match = re.fullmatch(r"USB:([0-9a-fA-F]{4}):([0-9a-fA-F]{4})", hardware_id or "")
    if match:
        vid, pid = (v.upper() for v in match.groups())
        if system == "Windows":
            url = "https://www.catalog.update.microsoft.com/Search.aspx?" + urlencode({"q": f"USB\\VID_{vid}&PID_{pid}"})
            label = "Find hardware ID in Microsoft Update Catalog"
        else:
            domain = "kernel.org" if system == "Linux" else "support.apple.com"
            url = "https://www.google.com/search?" + urlencode({"q": f"site:{domain} USB {vid} {pid} driver"})
            label = "Search official support by hardware ID"
        links.append({"label": label, "url": url})
    return links


def _read(path):
    try:
        return path.read_text(errors="replace").strip()[:256]
    except OSError:
        return ""


def _device(system, identity, name, hardware_id, binding, problem=None):
    if problem:
        state, action = "os-reported-problem", "Inspect the OS device error before opening a stream."
    elif binding:
        state, action = "driver-bound-unverified", "Verify application access, supported formats and loopback timing."
    else:
        state, action = "driver-status-unknown", "Check the OS device manager and official driver guidance."
    return {"id": identity, "name": str(name or identity)[:256], "hardwareId": hardware_id,
            "driver": binding or None, "diagnosis": state, "osProblem": problem,
            "nextAction": action, "qualified": False, "driverLookup": driver_lookup(system, hardware_id)}


def _linux(root):
    bus = root / "bus/usb/devices"
    if not bus.is_dir():
        return [], ["USB sysfs inventory is unavailable; this is not proof that hardware is absent."]
    devices = []
    for node in sorted(bus.iterdir()):
        vid, pid = _read(node / "idVendor"), _read(node / "idProduct")
        if not re.fullmatch("[0-9a-fA-F]{4}", vid) or not re.fullmatch("[0-9a-fA-F]{4}", pid):
            continue
        interfaces = sorted(bus.glob(node.name + ":*"))
        drivers = sorted({p.joinpath("driver").resolve().name for p in interfaces if p.joinpath("driver").is_symlink() and p.joinpath("driver").exists()})
        item = _device("Linux", "usb:" + node.name, _read(node / "product"),
                       f"USB:{vid.upper()}:{pid.upper()}", ", ".join(drivers))
        item["interfaceClasses"] = sorted({_read(p / "bInterfaceClass") for p in interfaces} - {""})
        item["identityScope"] = "connection-port; not a durable controller-mapping identity"
        devices.append(item)
    return devices, []


def _command_json(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=True)
    return json.loads(result.stdout)


def _windows():
    # Fixed read-only command; no device strings or HTTP parameters enter PowerShell.
    rows = _command_json(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "@(Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPDeviceID -like 'USB*'} | Select-Object Name,PNPDeviceID,Service,ConfigManagerErrorCode) | ConvertTo-Json -Compress"])
    if rows is None:
        rows = []
    if isinstance(rows, dict):
        rows = [rows]
    devices = []
    for i, row in enumerate(rows):
        match = re.search(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", row.get("PNPDeviceID") or "", re.I)
        hid = "USB:" + ":".join(v.upper() for v in match.groups()) if match else None
        # Do not export the PNP instance suffix: it can contain a serial number.
        devices.append(_device("Windows", f"usb-snapshot:{i}", row.get("Name"), hid,
                               row.get("Service"), row.get("ConfigManagerErrorCode")))
    return devices, []


def _mac():
    tree = _command_json(["system_profiler", "SPUSBDataType", "-json", "-detailLevel", "mini"])
    devices = []
    def visit(rows):
        for row in rows:
            vid = re.match(r"0x([0-9a-fA-F]{4})", row.get("vendor_id", ""))
            pid = re.match(r"0x([0-9a-fA-F]{4})", row.get("product_id", ""))
            if vid and pid:
                devices.append(_device("Darwin", f"usb-snapshot:{len(devices)}", row.get("_name"),
                                       f"USB:{vid[1].upper()}:{pid[1].upper()}", None))
            visit(row.get("_items", []))
    visit(tree.get("SPUSBDataType", []))
    return devices, ["USB inventory does not expose audio-driver binding; verify in Audio MIDI Setup."]


def diagnose_hardware(*, system=None, sys_root=Path("/sys"), catalog_path=None):
    system = system or platform.system()
    try:
        if system == "Linux":
            devices, issues = _linux(sys_root)
        elif system == "Windows":
            devices, issues = _windows()
        elif system == "Darwin":
            devices, issues = _mac()
        else:
            devices, issues = [], ["No inventory adapter for this OS."]
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError) as exc:
        devices, issues = [], [f"Inventory unavailable ({type(exc).__name__}); use the OS device manager."]
    release, architecture = platform.release(), platform.machine()
    default_catalog = Path(__file__).resolve().parents[1] / "packaging/driver-catalog.json"
    catalog = load_catalog(catalog_path or default_catalog)
    for device in devices:
        device["driverCompatibility"] = assess_driver(device, system, release, architecture, catalog)

    audio_endpoints, audio_drivers, endpoint_issues = [], [], []
    try:
        if system == "Windows":
            audio_endpoints, audio_drivers = windows_endpoint_probe(_command_json)
        elif system == "Darwin":
            audio_endpoints, audio_drivers = macos_endpoint_probe(_command_json)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError) as exc:
        endpoint_issues.append(f"Audio endpoint evidence unavailable ({type(exc).__name__}); use the OS audio device tools.")

    all_issues = list(issues) + endpoint_issues
    return {"documentType": "org.upp.hardware-diagnostics", "schemaVersion": 1,
            "host": {"os": system, "release": release, "architecture": architecture},
            "scope": "USB PnP inventory plus read-only OS audio endpoint/driver evidence; network/RF hardware requires separate adapters",
            "devices": devices, "audioEndpoints": audio_endpoints, "audioDrivers": audio_drivers,
            "endpointIssues": endpoint_issues, "issues": all_issues,
            "scanStatus": "partial-or-unavailable" if all_issues else "complete",
            "qualification": "hardware-tests-required", "physicalOutputsArmed": False,
            "lookupMode": "user-opened-online-search; results and compatibility require review",
            "officialGuidance": driver_lookup(system, None)}
