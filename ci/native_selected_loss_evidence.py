"""Selected software endpoint removal/recreation, not physical hotplug qualification."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
binary = Path(sys.argv[1]).resolve()
report = {
    "documentType": "org.upp.native-selected-loss-smoke", "schemaVersion": 1,
    "host": {"os": platform.system(), "release": platform.release(), "architecture": platform.machine()},
    "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "githubRunId": os.environ.get("GITHUB_RUN_ID"),
    "binarySha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    "sourceSha256": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((root / "native").glob("*")) if p.is_file()},
    "physicalHardwareQualified": False, "audibleOutputQualified": False,
    "physicalCaptureQualified": False, "fullEngineIntegrated": False, "status": "failed",
}
try:
    result = subprocess.run([str(binary)], capture_output=True, text=True, check=True, timeout=30)
    checks = json.loads(result.stdout)
    report["nativeChecks"] = checks
    if checks.get("audioSamplesStored") is not False:
        raise RuntimeError("capture test must not store samples")
    if platform.system() == "Darwin":
        for key in ["softwareFixtureAvailable", "selectedRemovalStopsNativeIo", "recreationRequiresExplicitRearm",
                    "injectedIdentityDowngradeStopsNativeIo", "restoredAssuranceRequiresExplicitRearm"]:
            if checks.get(key) is not True:
                raise RuntimeError(f"missing selected loss check: {key}")
        if checks["playbackCallbacks"] < 24 or checks["captureCallbacks"] < 24:
            raise RuntimeError("insufficient native callback evidence")
    elif any(checks[key] for key in ["softwareFixtureAvailable", "selectedRemovalStopsNativeIo", "recreationRequiresExplicitRearm", "playbackCallbacks", "captureCallbacks",
                                    "injectedIdentityDowngradeStopsNativeIo", "restoredAssuranceRequiresExplicitRearm"]):
        raise RuntimeError("unexpected selected-loss claim on unsupported OS")
    report["status"] = "passed"
except Exception as error:
    report["error"] = str(error)
    if isinstance(error, subprocess.CalledProcessError):
        report["stderr"] = error.stderr[-8000:]
    raise
finally:
    Path("native-selected-loss-evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
