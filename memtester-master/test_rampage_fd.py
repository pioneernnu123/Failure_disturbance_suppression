#!/usr/bin/env python3
# //LZU CHANGE
"""Smoke-test RAMpage's inherited-fd mode on a disposable file mapping."""

import os
from pathlib import Path
import subprocess
import tempfile


def run_case(binary, injection_type, expected_bad):
    page_size = os.sysconf("SC_PAGE_SIZE")
    page_count = 3
    with tempfile.TemporaryFile() as mapped, tempfile.TemporaryFile(mode="w+t") as result:
        mapped.truncate(page_count * page_size)
        command = [
            str(binary), "-F", str(mapped.fileno()),
            "-R", str(result.fileno()), "-i", "1",
            "-c", str(injection_type), "%dB" % (page_count * page_size), "1",
        ]
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            pass_fds=(mapped.fileno(), result.fileno()),
        )
        result.seek(0)
        lines = result.read().splitlines()
        expected = ["RAMPAGE_RESULT_V1 3"]
        if expected_bad:
            expected.append("BAD 1")
        expected.append("END")
        expected_codes = (2, 4, 6) if expected_bad else (0,)
        if lines != expected or completed.returncode not in expected_codes:
            raise AssertionError(
                "RAMpage fd test failed: command=%r rc=%d report=%r output=%s"
                % (command, completed.returncode, lines, completed.stdout[-2000:])
            )


if __name__ == "__main__":
    binary = Path(__file__).with_name("memtester").resolve()
    if not binary.is_file():
        raise SystemExit("Build memtester in this directory before running the test")
    run_case(binary, 0, False)
    for injection_type in range(1, 8):
        run_case(binary, injection_type, True)
    print("RAMpage inherited-fd smoke test: OK")
