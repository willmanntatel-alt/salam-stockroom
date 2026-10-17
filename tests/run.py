"""Compile the real Salam code, then exercise its public CLI. No pip packages."""
import csv
import io
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
SUFFIX = ".exe" if os.name == "nt" else ""
APP = BUILD / ("stockroom" + SUFFIX)
HEADER = "sku,on_hand,reserved,inbound,weekly_demand,lead_days,cover_days,safety_stock,pack_size,unit_cost_minor"


def compile_all():
    compiler = os.environ.get("SALAM") or shutil.which("salam")
    if not compiler:
        raise SystemExit("Set SALAM to the Salam 0.5.5 executable, or put it on PATH.")
    BUILD.mkdir(exist_ok=True)
    sources = [*(ROOT / "tests").glob("*.salam"), ROOT / "src/main.salam"]
    for source in sorted(sources):
        target = APP if source.name == "main.salam" else BUILD / (source.stem + SUFFIX)
        result = subprocess.run([compiler, "build", str(source.relative_to(ROOT)), f"--output=build/{target.name}"], cwd=ROOT, capture_output=True, timeout=120)
        (BUILD / f"{source.stem}-build.log").write_bytes(result.stdout + result.stderr)
        if result.returncode:
            sys.stderr.buffer.write(result.stdout + result.stderr)
            raise SystemExit(result.returncode)
        if source.name != "main.salam":
            subprocess.run([str(target)], cwd=ROOT, check=True, timeout=20)


class StockroomCLI(unittest.TestCase):
    def run_csv(self, content, *args):
        with tempfile.TemporaryDirectory(prefix="stockroom-") as directory:
            path = Path(directory) / "inventory.csv"
            path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
            return subprocess.run([str(APP), str(path), *args], capture_output=True, timeout=10)

    def parsed(self, content, *args):
        result = self.run_csv(content, "--csv", *args)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return list(csv.DictReader(io.StringIO(result.stdout.decode("utf-8"))))

    def test_example_budget_priority(self):
        result = subprocess.run([str(APP), "examples/inventory.csv", "--csv", "--budget-minor", "5000"], cwd=ROOT, capture_output=True, check=True)
        rows = list(csv.DictReader(io.StringIO(result.stdout.decode())))
        self.assertEqual([int(r["allocated"]) for r in rows], [0, 18, 0, 0])
        self.assertEqual(sum(int(r["cost_minor"]) for r in rows), 4500)

    def test_bom_crlf_unicode_and_quoting(self):
        content = "\ufeff" + HEADER + '\r\n"蓝色, \"\"背包\"\"",0,0,0,7,7,14,0,6,105\r\n'
        rows = self.parsed(content)
        self.assertEqual(rows[0]["sku"], '蓝色, "背包"')
        self.assertEqual(rows[0]["wanted"], "18")

    def test_zero_budget(self):
        rows = self.parsed(HEADER + "\nA,0,0,0,1,1,14,0,1,10", "--budget-minor", "0")
        self.assertEqual(rows[0]["allocated"], "0")

    def test_inbound_and_zero_demand(self):
        rows = self.parsed(HEADER + "\nA,0,0,100,7,7,14,0,1,1\nB,0,0,0,0,7,14,0,1,1")
        self.assertEqual([r["wanted"] for r in rows], ["0", "0"])

    def test_header_order_and_data_errors(self):
        bad_rows = [
            "A,1,2,0,1,1,2,0,1,100",  # reserved > on hand
            "A,1,0,0,1,1,2,0,0,100",  # zero pack
            "A,1,0,0,1,1,2,0,1,0",  # zero cost
            "A,-1,0,0,1,1,2,0,1,100",
            "A,1,0,0,1.5,1,2,0,1,100",
            "A,1,0,0,1,7,2,0,1,100",  # target before lead time
            "A,1000001,0,0,1,1,2,0,1,100",
            "A,1,0,0,1,367,367,0,1,100",
            ",1,0,0,1,1,2,0,1,100",
            "A,1,0,0,1,1,2,0,1",
            '"A"junk,1,0,0,1,1,2,0,1,100',
            '"A,1,0,0,1,1,2,0,1,100',
        ]
        for row in bad_rows:
            with self.subTest(row=row):
                result = self.run_csv(HEADER + "\n" + row)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertTrue(result.stderr.startswith(b"stockroom: "))
        result = self.run_csv(HEADER.replace("on_hand", "stock") + "\nA,1,0,0,1,1,2,0,1,100")
        self.assertEqual(result.returncode, 2)

    def test_duplicate_trimmed_sku(self):
        result = self.run_csv(HEADER + "\nA,1,0,0,1,1,2,0,1,100\n A ,1,0,0,1,1,2,0,1,100")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"duplicate SKU", result.stderr)

    def test_invalid_encoding_nul_and_field_limit(self):
        for bad in [HEADER.encode() + b"\n\xff,0,0,0,1,1,2,0,1,1", HEADER.encode() + b"\0", HEADER + "\n" + "x" * 300, "x" * (2097152 + 1)]:
            with self.subTest(size=len(bad)):
                self.assertEqual(self.run_csv(bad).returncode, 2)

    def test_formula_cell_is_neutralized(self):
        for sku in ["=1+1", "+SUM(1)", "-2+3", "@SUM(1)"]:
            rows = self.parsed(HEADER + "\n" + sku + ",0,0,0,1,1,14,0,1,1")
            self.assertEqual(rows[0]["sku"], "'" + sku)

    def test_row_limit(self):
        body = "\n".join(f"S{i},0,0,0,1,1,2,0,1,1" for i in range(1001))
        self.assertEqual(self.run_csv(HEADER + "\n" + body).returncode, 2)

    def test_cli_errors_and_help(self):
        for args in [[], ["--unknown"], ["no-file.csv"], ["examples/inventory.csv", "--budget-minor"], ["examples/inventory.csv", "--budget-minor", "-1"], ["examples/inventory.csv", "--budget-minor", "1000000000001"]]:
            self.assertEqual(subprocess.run([str(APP), *args], cwd=ROOT, capture_output=True).returncode, 2)
        result = subprocess.run([str(APP), "--help"], capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"Usage:", result.stdout)

    def test_deterministic_properties_against_integer_oracle(self):
        rng = random.Random(20261018)
        for _ in range(12):
            entries = []
            for i in range(20):
                on_hand = rng.randrange(101)
                lead = rng.randrange(31)
                entries.append([f"S{i}", on_hand, rng.randrange(on_hand + 1), rng.randrange(21), rng.randrange(51), lead, lead + rng.randrange(31), rng.randrange(11), rng.randrange(1, 13), rng.randrange(1, 10001)])
            content = HEADER + "\n" + "\n".join(",".join(map(str, e)) for e in entries)
            cap = rng.randrange(100000)
            actual = self.parsed(content, "--budget-minor", str(cap))
            remaining = cap
            expected = []
            for e in entries:
                sku, hand, reserved, inbound, demand, lead, cover, safety, pack, cost = e
                available = hand - reserved
                position = available + inbound
                reorder = (demand * lead + 6) // 7 + safety
                target = (demand * cover + 6) // 7 + safety
                wanted = ((target - position + pack - 1) // pack) * pack if position <= reorder and target > position else 0
                priority = (2 if available < (demand * lead + 6) // 7 else 1) if wanted else 0
                expected.append(dict(wanted=wanted, priority=priority, allocated=0, cost_minor=0))
            for priority in [2, 1]:
                for e, ex in zip(entries, expected):
                    if ex["priority"] == priority:
                        units = min(ex["wanted"], remaining // (e[8] * e[9]) * e[8])
                        ex.update(allocated=units, cost_minor=units * e[9])
                        remaining -= ex["cost_minor"]
            for row, ex in zip(actual, expected):
                for key, value in ex.items():
                    self.assertEqual(int(row[key]), value)
            self.assertLessEqual(sum(int(r["cost_minor"]) for r in actual), cap)


if __name__ == "__main__":
    compile_all()
    unittest.main(verbosity=2)
