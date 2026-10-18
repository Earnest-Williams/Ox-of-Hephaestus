"""Cross-process exclusivity, failure handling and crash recovery for Ox lease."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

from ox_ai.runtime.supervisor_lease import SupervisorAlreadyRunning, SupervisorLease


class SupervisorLeaseTests(unittest.TestCase):
    def test_three_and_five_crew_cannot_run_together(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "supervisor.lock"
            old = SupervisorLease(path, owner="CrewWatchSupervisor")
            new = SupervisorLease(path, owner="FiveCrewSupervisor")
            self.assertEqual(old.acquire(), 1)
            with self.assertRaises(SupervisorAlreadyRunning):
                new.acquire()
            script = (
                "from ox_ai.runtime.supervisor_lease import SupervisorLease,SupervisorAlreadyRunning;"
                "from pathlib import Path;"
                f"l=SupervisorLease(Path({str(path)!r}),owner='FiveCrewSupervisor');"
                "\ntry:\n l.acquire()\nexcept SupervisorAlreadyRunning:\n print('LOCK_DENIED')"
                "\nelse:\n raise SystemExit('Unexpected second controller')"
            )
            child = subprocess.run([sys.executable, "-c", script],
                                   capture_output=True, text=True, timeout=10)
            self.assertEqual(child.returncode, 0, child.stderr)
            self.assertIn("LOCK_DENIED", child.stdout)
            old.assert_held()
            old.release()
            self.assertTrue(path.exists(), "Stable lock inode must never be unlinked")
            self.assertEqual(new.acquire(), 2)
            new.release()
            self.assertEqual(json.loads(path.read_text())["epoch"], 2)

    def test_process_crash_releases_os_lock(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "supervisor.lock"
            # os._exit intentionally skips cleanup, proving kernel-managed
            # lock release instead of stale PID-file expiry logic.
            script = (
                "from ox_ai.runtime.supervisor_lease import SupervisorLease;"
                "from pathlib import Path; import os;"
                f"SupervisorLease(Path({str(path)!r}),owner='crashed').acquire();"
                "os._exit(0)"
            )
            child = subprocess.run([sys.executable, "-c", script],
                                   capture_output=True, text=True, timeout=10)
            self.assertEqual(child.returncode, 0, child.stderr)
            with SupervisorLease(path, owner="replacement") as lease:
                self.assertEqual(lease.epoch, 2)
                lease.assert_held()

    def test_symlink_and_insecure_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real = root / "real"
            real.write_text("")
            symlink = root / "fake"
            symlink.symlink_to(real)
            with self.assertRaises(OSError):
                SupervisorLease(symlink, owner="controller").acquire()
            path = root / "supervisor.lock"
            path.write_text("")
            os.chmod(path, 0o666)
            with self.assertRaises(PermissionError):
                SupervisorLease(path, owner="controller").acquire()

    def test_double_open_and_missing_owner(self):
        with tempfile.TemporaryDirectory() as td:
            lease = SupervisorLease(Path(td) / "lock", owner="ship")
            with self.assertRaises(PermissionError):
                lease.assert_held()
            lease.acquire()
            with self.assertRaises(RuntimeError):
                lease.acquire()
            lease.release()
            lease.release()

if __name__ == "__main__":
    unittest.main()
