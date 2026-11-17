#!/usr/bin/env python3
"""
MiniCPU-8 full validation -- exit status 0 only if everything passes.

    python3 validate.py

Checks
    1. unit + integration test suite (tests/)
    2. both demonstration programs (assemble, run, verify, save traces)
    3. final report PDF is present
"""

import io
import sys
import unittest
from pathlib import Path

import run_demo

ROOT = Path(__file__).resolve().parent


def check_tests():
    stream = io.StringIO()
    tests_dir = str(ROOT / "tests")
    suite = unittest.defaultTestLoader.discover(tests_dir,
                                                top_level_dir=tests_dir)
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    ok = result.wasSuccessful()
    if not ok:
        print(stream.getvalue())
    detail = "%d tests run, %d failures, %d errors, %d skipped" % (
        result.testsRun, len(result.failures), len(result.errors),
        len(result.skipped))
    return ok, detail


def check_demos():
    print("-" * 78)
    ok = run_demo.main(["--quiet"]) == 0
    print("-" * 78)
    return ok, "Program A = 64, Program B = 120, traces in output/"


def check_report():
    pdf = ROOT / "docs" / "CPU_Design_Report.pdf"
    return pdf.is_file() and pdf.stat().st_size > 0, str(pdf.relative_to(ROOT))


def main():
    checks = (("Test suite", check_tests),
              ("Demonstrations", check_demos),
              ("Final report", check_report))
    results = []
    for name, check in checks:
        ok, detail = check()
        results.append(ok)
        print("[%s] %-15s %s" % ("PASS" if ok else "FAIL", name, detail))
    if all(results):
        print("[PASS] MiniCPU-8 validation complete.")
        return 0
    print("[FAIL] Validation failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
