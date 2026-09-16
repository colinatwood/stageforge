"""Recover this engine's fixed-format PCM spool into a separate WAV."""
import os
import stat
import struct
import tempfile
import uuid
import wave
from pathlib import Path
from durable_filesystem import publish_hardlink,unlink_and_sync


def recover_partial(root: Path, name: str) -> dict:
    root = Path(root)
    if Path(name).name != name or not name.endswith(".partial.wav"):
        raise ValueError("recovery requires a partial WAV basename")
    source = root / name
    if source.is_symlink():
        raise ValueError("recovery does not accept symbolic links")
    temporary = None
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as original:
        before = os.fstat(original.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("recovery requires a regular file")
        header = original.read(44)
        if len(header) != 44:
            raise ValueError("partial recording has no complete WAV header")
        riff, _, wav, fmt, fmt_size, encoding, channels, rate, byte_rate, align, bits, data, _ = struct.unpack("<4sI4s4sIHHIIHH4sI", header)
        if (riff, wav, fmt, fmt_size, encoding, channels, rate, byte_rate, align, bits, data) != (b"RIFF", b"WAVE", b"fmt ", 16, 1, 2, 192000, 1536000, 8, 32, b"data"):
            raise ValueError("unsupported partial recording format")
        payload = before.st_size - 44
        frames, discarded = divmod(payload, align)
        if frames < 1 or frames * align > 0xFFFFFFFF - 36:
            raise ValueError("partial recording has no recoverable frames or exceeds WAV limit")
        fd, raw = tempfile.mkstemp(prefix=".recovery-", suffix=".tmp", dir=root)
        os.close(fd)
        temporary = Path(raw)
        target = root / ("recovered-" + uuid.uuid4().hex + ".wav")
        try:
            with wave.open(str(temporary), "wb") as output:
                output.setnchannels(channels); output.setsampwidth(4); output.setframerate(rate)
                remaining = frames * align
                while remaining:
                    chunk = original.read(min(65536, remaining))
                    if not chunk:
                        raise ValueError("partial recording changed during recovery")
                    output.writeframesraw(chunk); remaining -= len(chunk)
            after = os.fstat(original.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError("partial recording changed during recovery")
            with temporary.open("rb") as completed:
                os.fsync(completed.fileno())
            publish_hardlink(temporary,target)  # Publication name is durable before success.
        finally:
            cleanup_pending=not unlink_and_sync(temporary) if temporary is not None else False
    return {"state": "recovered", "path": str(target), "source": name,
            "frames": frames, "discardedTrailingBytes": discarded,
            "sourcePreserved": True, "continuityVerified": False,
            "directoryDurable": True, "temporaryCleanupPending": cleanup_pending,
            "physicalInputArmed": False, "physicalOutputsArmed": False}
