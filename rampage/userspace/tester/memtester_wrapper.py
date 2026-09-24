
# LZU DSLAB CHANGE

'''
LZU DSLAB CHANGE
Add this .py file to adapt to the RAMpage based 
on memtester which is a open source tool using 
to test for faulty memory subsystem.
It is implemented on EulixOS for RISC-V64.
'''
from tester.scanner_baseclass import ScannerBaseclass
# //LZU CHANGE
import os
import subprocess
import tempfile
import time  # 引入时间模块，用于在日志中打时间戳
# //LZU CHANGE
from injection_state import (
    DEFAULT_INJECTION_STATE_PATH,
    INJECTION_TYPE_NAMES,
    read_injection_type,
    validate_injection_type,
    write_injection_type,
)

# //LZU CHANGE
MEMTESTER_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "memtester_execution_details.log",
)

class MemtesterWrapper(ScannerBaseclass):
    @staticmethod
    def name():
        return "memtester (external tool)"

    @staticmethod
    def shortname():
        return "memtester"

    # //LZU CHANGE
    def __init__(self, reporting, extra_args="", injection_type=None,
                 injection_state_path=DEFAULT_INJECTION_STATE_PATH,
                 physmem_device=None):
        super().__init__(reporting)

        if isinstance(extra_args, str):
            self.extra_args = extra_args.split()
        else:
            self.extra_args = extra_args

        # //LZU CHANGE
        self.injection_type = validate_injection_type(
            0 if injection_type is None else injection_type
        )
        self.injection_state_path = injection_state_path
        self.physmem_device = physmem_device
        write_injection_type(self.injection_type, self.injection_state_path)

    # //LZU CHANGE
    @staticmethod
    def _parse_result(report_text, page_count):
        lines = report_text.splitlines()
        if (len(lines) < 2 or
                lines[0] != "RAMPAGE_RESULT_V1 %d" % page_count or
                lines[-1] != "END"):
            raise RuntimeError("memtester did not return a complete RAMpage result")

        bad_pages = set()
        for line in lines[1:-1]:
            parts = line.split()
            if (len(parts) != 2 or parts[0] != "BAD" or
                    not parts[1].isdigit()):
                raise RuntimeError("invalid RAMpage result line: %r" % line)
            page_index = int(parts[1])
            if page_index >= page_count or page_index in bad_pages:
                raise RuntimeError("invalid RAMpage bad-page index: %d" % page_index)
            bad_pages.add(page_index)

        return sorted(bad_pages)

    # //LZU CHANGE
    def test(self, region, offset, length, physaddr):
        if self.physmem_device is None or not physaddr or length % len(physaddr):
            raise RuntimeError("memtester needs the claimed RAMpage mapping")
        page_size = length // len(physaddr)
        if page_size != os.sysconf("SC_PAGE_SIZE"):
            raise RuntimeError("RAMpage and memtester page sizes do not match")

        # //LZU CHANGE
        self.injection_type = read_injection_type(
            self.injection_state_path,
            self.injection_type,
        )
        injection_type_name = INJECTION_TYPE_NAMES[self.injection_type]

        # //LZU CHANGE
        print("当前错误类型：%s" % injection_type_name)

        # //LZU CHANGE
        with tempfile.TemporaryFile(mode="w+t") as result_file:
            mapped_fd = self.physmem_device.dev().fileno()
            result_fd = result_file.fileno()
            cmd = ["/usr/local/bin/memtester"] + self.extra_args
            # The same open /dev/phys_mem session is inherited by memtester.
            # The explicit -c follows any legacy -c in --memtester-args.
            cmd += ["-F", str(mapped_fd), "-R", str(result_fd),
                    "-c", str(self.injection_type), "%dB" % length, "1"]

            print(
                "开始执行 memtester：%s" % " ".join(cmd),
                flush=True
            )
            print(
                "memtester 详细日志：%s" % MEMTESTER_LOG_PATH,
                flush=True
            )

            with open(MEMTESTER_LOG_PATH, "a") as log_file:
                # //LZU CHANGE
                header = f"\n{'='*20} Run at {time.strftime('%Y-%m-%d %H:%M:%S')} {'='*20}\n"
                header += "Injection type: %d (%s)\n" % (
                    self.injection_type,
                    injection_type_name,
                )
                header += "Claimed PFNs: %s\n" % ", ".join(
                    "0x%x" % (address // page_size) for address in physaddr
                )
                header += f"Command: {' '.join(cmd)}\n"
                log_file.write(header)
                log_file.flush() # 确保头信息先写入硬盘

                # //LZU CHANGE
                completed = subprocess.run(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=False,
                    pass_fds=(mapped_fd, result_fd),
                )
                result_file.seek(0)
                bad_pages = self._parse_result(
                    result_file.read(), len(physaddr)
                )
                if (completed.returncode not in (0, 2, 4, 6) or
                        bool(bad_pages) != bool(completed.returncode)):
                    raise RuntimeError(
                        "memtester exited with inconsistent result %d; see %s"
                        % (completed.returncode, MEMTESTER_LOG_PATH)
                    )

                # //LZU CHANGE
                for page_index in bad_pages:
                    log_file.write(
                        "Mapped failure: page=%d PFN=0x%x\n"
                        % (page_index, physaddr[page_index] // page_size)
                    )

        # //LZU CHANGE
        return [offset + page_index * page_size for page_index in bad_pages]

ScannerBaseclass.register(MemtesterWrapper)
