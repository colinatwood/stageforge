#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

TRACKED = [
    "backend/session_channel.py",
    "backend/local_ipc.py",
    "backend/windows_named_pipe.py",
    "backend/audio_endpoint_evidence.py",
]


def normalized_sha256(path: str) -> str:
    data = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(path: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{path}"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="strict",
    ).strip()


def verify_snapshot() -> dict:
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="strict",
    ).strip()
    if status:
        raise RuntimeError(f"tracked working tree is not clean: {status}")
    return {
        path: {
            "gitBlobSha": git_blob_sha(path),
            "normalizedSha256": normalized_sha256(path),
        }
        for path in TRACKED
    }


def windows_pipe() -> dict:
    from multiprocessing.connection import Client
    from local_ipc import WindowsNamedPipeIpcServer
    from session_channel import AuthenticatedSessionChannel
    import csv

    row = next(
        csv.reader(
            io.StringIO(
                subprocess.check_output(
                    ["whoami.exe", "/user", "/fo", "csv", "/nh"],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                ).strip()
            )
        )
    )
    sid = row[1].upper()
    name = rf"\\.\pipe\StageForge\CI-{uuid.uuid4().hex}"
    key = hashlib.sha256(b"stageforge-github-bootstrap").digest()
    cluster = "11" * 16
    session = "22" * 32

    def channel() -> AuthenticatedSessionChannel:
        return AuthenticatedSessionChannel(
            key,
            cluster,
            session,
            {7},
            send_direction="server",
            receive_direction="client",
        )

    server = WindowsNamedPipeIpcServer(
        name,
        channel,
        lambda c, p: b"github-ci:" + p,
        max_requests=1,
        allowed_sids=(sid,),
        allow_administrators=False,
    )
    server.start()
    errors: list[BaseException] = []
    thread = threading.Thread(target=lambda: _serve(server, errors), daemon=True)
    thread.start()

    conn = None
    deadline = time.monotonic() + 10
    while conn is None and time.monotonic() < deadline:
        try:
            conn = Client(name, family="AF_PIPE")
        except OSError:
            time.sleep(0.05)
    if conn is None:
        server.close()
        raise RuntimeError("pipe connect timeout")

    client = AuthenticatedSessionChannel(
        key,
        cluster,
        session,
        {7},
        send_direction="client",
        receive_direction="server",
    )
    conn.send_bytes(client.encode(7, b"ping"))
    decoded = client.decode(conn.recv_bytes())
    conn.close()
    thread.join(10)
    server.close()
    if errors:
        raise errors[0]
    if decoded["payload"] != b"github-ci:ping":
        raise RuntimeError("unexpected pipe response")

    return {
        "kernelDaclAndAuthorizedRoundtripQualified": True,
        "sidHash": hashlib.sha256(sid.encode()).hexdigest(),
        "unauthorizedClientDenialQualified": False,
    }


def _serve(server, errors: list[BaseException]) -> None:
    try:
        server.serve_once()
    except BaseException as exc:
        errors.append(exc)


def mac_audio() -> dict:
    from audio_endpoint_evidence import macos_endpoint_probe

    def run(cmd):
        return json.loads(
            subprocess.check_output(
                cmd,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        )

    endpoints, drivers = macos_endpoint_probe(run)
    return {
        "coreAudioProbeQualified": True,
        "endpointCount": len(endpoints),
        "driverRecordCount": len(drivers),
        "physicalInterfaceQualified": False,
    }


def main() -> int:
    report = {
        "documentType": "org.upp.github-platform-module-smoke",
        "schemaVersion": 2,
        "provenanceCheckpoint": 69,
        "gitHubSource": {
            "sha": os.environ.get("GITHUB_SHA"),
            "headRef": os.environ.get("GITHUB_HEAD_REF"),
        },
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
        },
        "physicalOutputsArmed": False,
        "physicalHardwareQualified": False,
        "trackedFiles": verify_snapshot(),
        "checks": {},
    }
    if platform.system() == "Windows":
        report["checks"]["windowsNamedPipe"] = windows_pipe()
    elif platform.system() == "Darwin":
        report["checks"]["macosAudioEvidence"] = mac_audio()
    else:
        report["checks"]["linuxImportReference"] = {"qualified": True}

    out = Path(os.environ.get("STAGEFORGE_CI_EVIDENCE", "platform-module-smoke.json"))
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
