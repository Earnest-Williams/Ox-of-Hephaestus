"""Single-host, process-lifetime exclusive Ox supervisor lease.

The three-crew and five-crew supervisors use the *same* .ox-state lock
before authenticating or sending any world commands. The OS releases the
lock after a process crash. Never unlink its stable inode on release.

This is a local POSIX advisory process lease, not a distributed consensus
fence or permission in Evennia. Multi-host deployment will require a
world-enforced generation token or another distributed fencing mechanism.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import stat


class SupervisorAlreadyRunning(RuntimeError):
    """Another Ox controller already owns the shared ship process lease."""


class SupervisorLease:
    """Acquire one shared lock across *both* supervisor entry points."""

    def __init__(self, path: Path, *, owner: str) -> None:
        if not isinstance(owner, str) or not owner or len(owner) > 80:
            raise ValueError("A bounded supervisor owner name is required")
        self.path = Path(path)
        self.owner = owner
        self._fd: int | None = None
        self.epoch: int | None = None

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self) -> int:
        if self._fd is not None:
            raise RuntimeError("Supervisor lease already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PermissionError("Supervisor lock must be a regular file")
            if info.st_mode & 0o077:
                raise PermissionError("Supervisor lock file is too broadly accessible")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SupervisorAlreadyRunning(
                    "Another three-crew or five-crew supervisor owns this ship"
                ) from None
            # Metadata is solely operator diagnostics, not distributed fencing.
            # Incrementing the epoch under lock makes restarts inspectable.
            size = os.fstat(fd).st_size
            if size > 4096:
                raise ValueError("Supervisor lease metadata is oversized")
            raw = os.pread(fd, size, 0)
            previous = json.loads(raw) if raw else {}
            previous_epoch = previous.get("epoch", 0)
            if (isinstance(previous_epoch, bool)
                    or not isinstance(previous_epoch, int)
                    or not 0 <= previous_epoch < 2**63 - 1):
                raise ValueError("Invalid supervisor lease epoch")
            self.epoch = previous_epoch + 1
            record = json.dumps(
                {"epoch": self.epoch, "owner": self.owner, "pid": os.getpid()},
                sort_keys=True,
            ).encode("utf-8")
            os.ftruncate(fd, 0)
            os.pwrite(fd, record, 0)
            os.fsync(fd)
            self._fd = fd
            return self.epoch
        except BaseException:
            os.close(fd)
            raise

    def assert_held(self) -> None:
        if self._fd is None:
            raise PermissionError("Supervisor has not acquired the ship lease")
        if not stat.S_ISREG(os.fstat(self._fd).st_mode):
            raise PermissionError("Supervisor lease descriptor invalid")

    def release(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        # Preserve the inode to avoid a new controller locking a different
        # path while an existing supervisor holds an unlinked old inode.

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, _type, _value, _traceback):
        self.release()
