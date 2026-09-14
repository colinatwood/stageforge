"""Run the native execution-fence smoke and bind evidence to exact source/binary."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
binary = Path(sys.argv[1]).resolve()
run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30, check=True)
checks = json.loads(run.stdout)
report = {
    "documentType": "org.upp.device-execution-fence-smoke",
    "schemaVersion": 1,
    "host": {"os": platform.system(), "release": platform.release(), "architecture": platform.machine()},
    "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "githubRunId": os.environ.get("GITHUB_RUN_ID"),
    "binarySha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    "nativeChecks": checks,
    "syntheticFenceQualified": checks.get("syntheticFenceQualified") is True,
    "silentRearmPrevented": checks.get("silentRearmPrevented") is True,
    "nativeSoftwareFenceQualified": (
        platform.system() == "Darwin"
        and checks.get("coreMidiFenceQualified") is True
        and checks.get("coreAudioFenceQualified") is True
    ),
    "physicalOutputsArmed": False,
    "physicalHardwareQualified": False,
    "audioStreamingQualified": False,
    "physicalHotplugQualified": False,
    "status": "passed",
}
Path("device-fence-evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
