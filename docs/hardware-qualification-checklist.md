# StageForge hardware qualification checklist

The developer-alpha software gate is automated in CI. These items remain
separate and must be marked qualified only on a real Linux host or VM with the
corresponding devices.

## Software-only preparation

1. Build Release and run `ctest --test-dir build --output-on-failure`.
2. Run `scripts/release-check.py`.
3. Optionally run `sudo scripts/virtual-audio-check.sh` for ALSA loopback.

Loopback is evidence for software routing only; it does not qualify physical
audio, clock, latency, or device permissions.

## Clean-host package and service

- Install with `scripts/install-linux.sh` on a clean Ubuntu host or VM.
- Confirm sysusers/tmpfiles provision the service user and state directory.
- Run `systemctl daemon-reload`, then explicitly enable and start the service.
- Record `systemctl status stageforge` and `journalctl -u stageforge`.
- Verify reinstall preserves state and uninstall preserves documented state.

## Device access

- ALSA playback/capture, negotiated format, recovery, and sustained run.
- MIDI enumeration, input, disconnect, and reconnect.
- UWB and Bluetooth LE ISO permissions, framing, non-blocking behavior, and
  device-loss recovery.
- Art-Net and sACN output on an isolated test network.

## Evidence rules

Do not claim physical, audible, latency, clock, or hardware-permission
qualification from WSL, mocks, CI, or ALSA loopback alone. Record the host,
kernel, device identifiers, commands, logs, and pass/fail result.
