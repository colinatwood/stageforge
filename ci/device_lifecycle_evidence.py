"""Run the native lifecycle check and bind evidence to source and executable."""
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
    "documentType": "org.upp.device-lifecycle-smoke",
    "schemaVersion": 1,
    "host": {"os": platform.system(), "release": platform.release(), "architecture": platform.machine()},
    "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "githubRunId": os.environ.get("GITHUB_RUN_ID"),
    "binarySha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    "sourceSha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((root / "native").glob("*")) if p.is_file()},
    "physicalOutputsArmed": False,
    "physicalHardwareQualified": False,
    "audioStreamingQualified": False,
    "physicalHotplugQualified": False,
    "status": "failed",
}
try:
    run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30, check=True)
    report["nativeChecks"] = json.loads(run.stdout)
    report["status"] = "passed"
finally:
    Path("device-lifecycle-evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
