"""Small Linux durability primitives for same-directory publication boundaries."""
from __future__ import annotations
import os
from pathlib import Path


def fsync_directory(path: Path) -> None:
    path=Path(path)
    flags=os.O_RDONLY|getattr(os,"O_DIRECTORY",0)
    fd=os.open(path,flags)
    try:os.fsync(fd)
    finally:os.close(fd)


def publish_hardlink(source: Path, target: Path) -> None:
    """Create a non-replacing hard-link publication and durably commit its directory entry.

    If the directory sync fails, remove the just-created target best-effort and
    never report publication success. The source remains available for retry.
    """
    source=Path(source);target=Path(target);os.link(source,target)
    try:fsync_directory(target.parent)
    except BaseException:
        try:target.unlink()
        except OSError:pass
        try:fsync_directory(target.parent)
        except OSError:pass
        raise


def unlink_and_sync(path: Path) -> bool:
    """Remove one path and durably commit the directory update when possible."""
    path=Path(path)
    try:path.unlink()
    except FileNotFoundError:return True
    except OSError:return False
    try:fsync_directory(path.parent)
    except OSError:return False
    return True
