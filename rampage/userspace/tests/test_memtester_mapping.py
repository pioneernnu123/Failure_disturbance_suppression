# //LZU CHANGE
import contextlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


USERSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(USERSPACE))

# Keep these tests runnable on Windows, where RAMpage's Linux-only fcntl and
# kernel device cannot be imported.
tester_package = types.ModuleType("tester")
tester_package.__path__ = []
scanner_module = types.ModuleType("tester.scanner_baseclass")


class ScannerBaseclass:
    def __init__(self, reporting):
        self.reporting = reporting

    @staticmethod
    def register(scanner_class):
        pass


scanner_module.ScannerBaseclass = ScannerBaseclass
sys.modules["tester"] = tester_package
sys.modules["tester.scanner_baseclass"] = scanner_module

physmem_module = types.ModuleType("physmem")
physmem_module.PAGE_SIZE = 4096
sys.modules["physmem"] = physmem_module
sys.modules["frame"] = types.ModuleType("frame")


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, USERSPACE / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wrapper_module = load_module("mapping_wrapper_test", "tester/memtester_wrapper.py")
scheduler_module = load_module("mapping_scheduler_test", "scheduling/slow/slow_scheduler.py")

from injection_state import write_injection_type


class Device:
    def __init__(self):
        self.file = tempfile.TemporaryFile()
        self.poisoned = []

    def dev(self):
        return self.file

    def mmap(self, length):
        return contextlib.nullcontext(None)

    def mark_pfn_bad(self, pfn):
        self.poisoned.append(pfn)


class Frame:
    def __init__(self, pfn, page_index=None):
        self.request = types.SimpleNamespace(requested_pfn=pfn)
        self.pfn = pfn if page_index is not None else 0
        self.vma_offset_of_first_byte = (
            page_index * 4096 if page_index is not None else 0
        )
        self.allocation_cost_jiffies = 1
        self.actual_source = 2
        self.page_index = page_index

    def is_claimed(self):
        return self.page_index is not None


class Status:
    def __init__(self, pfn):
        self.pfn = pfn
        self.num_errors = 0
        self.last_failed_test = 0
        self.last_successful_test = 0


class Reporter:
    def __init__(self):
        self.bad = []
        self.good = []

    def report_bad_frame(self, pfn):
        self.bad.append(pfn)

    def report_good_frame(self, pfn):
        self.good.append(pfn)


class Timestamping:
    def timestamp(self):
        return 12345

    def seconds_to_timestamp(self, seconds):
        return seconds * 100


class MappingTests(unittest.TestCase):
    def test_wrapper_passes_same_device_fd_and_reads_exact_page_results(self):
        device = Device()
        with tempfile.TemporaryDirectory() as directory:
            state_path = str(Path(directory) / "injection_type")
            log_path = str(Path(directory) / "memtester.log")
            with mock.patch.object(wrapper_module, "MEMTESTER_LOG_PATH", log_path):
                wrapper = wrapper_module.MemtesterWrapper(
                    None, "-i 1", 1, state_path, device
                )
                write_injection_type(4, state_path)
                seen = []

                def fake_run(command, *, stdout, stderr, check, pass_fds):
                    seen.append((command, pass_fds))
                    result_fd = int(command[command.index("-R") + 1])
                    os.write(
                        result_fd,
                        b"RAMPAGE_RESULT_V1 3\nBAD 1\nBAD 2\nEND\n",
                    )
                    return types.SimpleNamespace(returncode=4)

                with mock.patch.object(wrapper_module.os, "sysconf", return_value=4096, create=True):
                    with mock.patch.object(wrapper_module.subprocess, "run", side_effect=fake_run):
                        bad_offsets = wrapper.test(
                            None, 0, 3 * 4096,
                            [100 * 4096, 101 * 4096, 102 * 4096],
                        )

            self.assertEqual(bad_offsets, [4096, 8192])
            command, passed_fds = seen[0]
            self.assertEqual(command[command.index("-c") + 1], "4")
            self.assertEqual(command[-2:], ["12288B", "1"])
            self.assertEqual(int(command[command.index("-F") + 1]), device.file.fileno())
            self.assertEqual(set(passed_fds), {
                device.file.fileno(), int(command[command.index("-R") + 1])
            })
            self.assertIn("page=1 PFN=0x65", Path(log_path).read_text())
        device.file.close()

    def test_incomplete_result_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "complete RAMpage result"):
            wrapper_module.MemtesterWrapper._parse_result(
                "RAMPAGE_RESULT_V1 2\nBAD 0 0\n", 2
            )

    def test_memtester_launch_failure_is_not_a_bad_page(self):
        device = Device()
        with tempfile.TemporaryDirectory() as directory:
            state_path = str(Path(directory) / "injection_type")
            log_path = str(Path(directory) / "memtester.log")
            with mock.patch.object(wrapper_module, "MEMTESTER_LOG_PATH", log_path):
                wrapper = wrapper_module.MemtesterWrapper(
                    None, "-i 0", 0, state_path, device
                )
                with mock.patch.object(wrapper_module.os, "sysconf", return_value=4096, create=True):
                    with mock.patch.object(
                        wrapper_module.subprocess, "run",
                        return_value=types.SimpleNamespace(returncode=1),
                    ):
                        with self.assertRaisesRegex(RuntimeError, "complete RAMpage result"):
                            wrapper.test(None, 0, 4096, [100 * 4096])
        device.file.close()

    def test_scheduler_uses_mapping_offsets_and_poisons_failed_pages(self):
        device = Device()
        reporter = Reporter()
        statuses = {pfn: Status(pfn) for pfn in (100, 101, 102)}
        observed = []

        class TestAlgorithm:
            def test(self, region, offset, length, physaddr):
                observed.append((length, physaddr))
                return [0, 4096]

        scheduler = scheduler_module.SlowScheduler(
            device, [TestAlgorithm()], statuses, None, None,
            Timestamping(), reporter, 0,
        )
        scheduler._claim_pfns = lambda pfns, sources: [
            Frame(100, 1), Frame(101), Frame(102, 0)
        ]
        tested = scheduler.test_frames_and_record_result(
            list(statuses.values()), 2
        )

        self.assertEqual(tested, 2)
        self.assertEqual(observed, [(8192, [102 * 4096, 100 * 4096])])
        self.assertEqual(device.poisoned, [100, 102])
        self.assertCountEqual(reporter.bad, [100, 102])
        self.assertEqual(statuses[100].num_errors, 1)
        self.assertEqual(statuses[102].num_errors, 1)
        device.file.close()

    def test_scheduler_rejects_mapping_gap_before_running_tester(self):
        device = Device()
        statuses = {pfn: Status(pfn) for pfn in (100, 101)}
        scheduler = scheduler_module.SlowScheduler(
            device, [], statuses, None, None, Timestamping(), Reporter(), 0
        )
        scheduler._claim_pfns = lambda pfns, sources: [
            Frame(100, 0), Frame(101, 2)
        ]
        with self.assertRaisesRegex(RuntimeError, "missing page offsets"):
            scheduler.test_frames_and_record_result(list(statuses.values()), 2)
        self.assertEqual(device.poisoned, [])
        device.file.close()

if __name__ == "__main__":
    unittest.main()
