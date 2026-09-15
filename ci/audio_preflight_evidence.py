"""Run native audio preflight and bind evidence to exact source/binary.

This is deliberately preflight-only evidence. It does not start audio I/O or qualify
physical hardware.
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
    "documentType": "org.upp.audio-preflight-smoke",
    "schemaVersion": 1,
    "host": {"os": platform.system(), "release": platform.release(), "architecture": platform.machine()},
    "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "githubRunId": os.environ.get("GITHUB_RUN_ID"),
    "binarySha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    "sourceSha256": {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / "native").glob("*")) if p.is_file()
    },
    "preflightOnly": True,
    "configurationApplied": False,
    "physicalOutputsArmed": False,
    "audioStreamingQualified": False,
    "physicalHardwareQualified": False,
    "status": "failed",
}
try:
    run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30, check=True)
    checks = json.loads(run.stdout)
    report["nativeChecks"] = checks
    report["preflightContractQualified"] = all([
        checks.get("syntheticExactQualified") is True,
        checks.get("syntheticExplicitAdaptationQualified") is True,
        checks.get("implicitConversionRejected") is True,
        checks.get("missingEndpointRejected") is True,
        checks.get("missingPinnedEndpointRejected") is True,
    ])
    playback = checks.get("playback") or {}
    capture = checks.get("capture") or {}
    expected_pinned = int(playback.get("endpointPresent") is True) + int(capture.get("endpointPresent") is True)
    if checks.get("pinnedDefaultProbeCount") != expected_pinned:
        raise RuntimeError("Pinned endpoint readback evidence incomplete")
    report["playbackEndpointObserved"] = playback.get("endpointPresent") is True
    report["captureEndpointObserved"] = capture.get("endpointPresent") is True
    report["playbackProbeQualified"] = playback.get("exactHostPlanQualified") is True
    report["captureProbeQualified"] = capture.get("exactHostPlanQualified") is True
    report["liveEndpointPreflightObserved"] = (
        (playback.get("endpointPresent") is True and playback.get("preflightStatus") == "exact")
        or (capture.get("endpointPresent") is True and capture.get("preflightStatus") == "exact")
    )
    report["targetOsPreflightProbeQualified"] = (
        report["preflightContractQualified"]
        and report["playbackProbeQualified"]
        and report["captureProbeQualified"]
    )
    report["status"] = "passed" if report["targetOsPreflightProbeQualified"] else "failed"
finally:
    Path("audio-preflight-evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
if report["status"] != "passed":
    raise SystemExit(1)
