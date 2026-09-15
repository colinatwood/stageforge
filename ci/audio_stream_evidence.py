"""Evidence for a lifecycle contract and manually driven software Audio Unit.

Not device-clocked audio, WASAPI I/O or physical stream qualification.
"""
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
    "documentType": "org.upp.audio-stream-lifecycle-smoke",
    "schemaVersion": 1,
    "host": {"os": platform.system(), "release": platform.release(), "architecture": platform.machine()},
    "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "githubRunId": os.environ.get("GITHUB_RUN_ID"),
    "binarySha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    "sourceSha256": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((root / "native").glob("*")) if p.is_file()},
    "physicalOutputsArmed": False,
    "audioStreamingQualified": False,
    "deviceClockQualified": False,
    "physicalHardwareQualified": False,
    "status": "failed",
}
try:
    run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30, check=True)
    checks = json.loads(run.stdout)
    report["nativeChecks"] = checks
    required = ["lifecycleContractPassed", "staleGenerationRejected", "pendingStopPreserved",
                "implicitRecoveryRejected", "unimplementedConversionRejected",
                "singleExplicitRearmRecoversNativeRevocation", "oldConsumerRevokedOnRearm"]
    if platform.system() == "Darwin":
        required += ["softwareRendererAvailable", "nativeUnitStarted", "nativeUnitStopped", "samplesVerified",
                     "fencedRenderSilent", "restartVerified", "manualRender"]
        if checks.get("callbackCount") != 18 or checks.get("renderedFrames") != 4608:
            raise RuntimeError("Unexpected manual callback/frame accounting")
    if not all(checks.get(key) is True for key in required):
        raise RuntimeError("Required native check missing")
    report["status"] = "passed"
except subprocess.CalledProcessError as error:
    report["error"] = {"exitCode": error.returncode, "stderr": error.stderr[-4000:]}
    raise
finally:
    Path("audio-stream-lifecycle-evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
