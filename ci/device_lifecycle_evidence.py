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
    "schemaVersion": 2,
    "host": {"os": platform.system(), "release": platform.release(), "architecture": platform.machine()},
    "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "githubRunId": os.environ.get("GITHUB_RUN_ID"),
    "binarySha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    "sourceSha256": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
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
    if len(sys.argv) > 2:
        events_binary = Path(sys.argv[2]).resolve()
        report["eventsBinarySha256"] = hashlib.sha256(events_binary.read_bytes()).hexdigest()
        events = subprocess.run([str(events_binary)], capture_output=True, text=True, timeout=45, check=True)
        report["deviceEvents"] = json.loads(events.stdout)
    report["status"] = "passed"
except subprocess.CalledProcessError as error:
    report["error"] = {"exitCode": error.returncode, "stderr": error.stderr[-4000:]}
    raise
except subprocess.TimeoutExpired:
    report["error"] = {"reason": "native executable timed out"}
    raise
finally:
    Path("device-lifecycle-evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
