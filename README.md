# Salam Stockroom

A local inventory and pack-aware replenishment planner built with the
[Salam Programming Language](https://github.com/SalamLang/Salam).

Import a stock worksheet, review which SKUs need replenishment, and allocate a
fixed purchasing budget in whole packs. The app reads files and prints reports;
it never places an order or changes inventory. All examples use fictional data.

## Run

Install the official [Salam 0.5.5 compiler](https://github.com/SalamLang/Salam/releases/tag/v0.5.5).
Use the release archive for your OS, verify its `.sha256` file, and extract it.
No database, API key, paid service, or Python package is needed.

From the project directory, on Linux or macOS:

```sh
export SALAM=/path/to/salam
export SALAM_STD=/path/to/std
mkdir -p build
"$SALAM" build src/main.salam --output=build/stockroom
./build/stockroom examples/inventory.csv --budget-minor 5000
./build/stockroom examples/inventory.csv --csv
```

On Windows PowerShell:

```powershell
$env:SALAM = 'C:/Tools/salam-windows/salam.exe'
$env:SALAM_STD = 'C:/Tools/salam-windows/std'
New-Item -ItemType Directory build -Force | Out-Null
& $env:SALAM build src/main.salam --output=build/stockroom.exe
./build/stockroom.exe examples/inventory.csv --budget-minor 5000
```

If this compiler cannot resolve an absolute standard-library path containing
non-ASCII characters on Windows, use an ASCII installation path or a relative
`SALAM_STD` path from this project directory. Do not disable TLS checks or
change system security settings. The official x64 compiler release includes
its compilation toolchain; this project does not download a compiler at run time.

`--help` prints usage. Default output is text; `--csv` prints CSV. Missing or
invalid arguments/data exit 2 and print an error to stderr. Redirect stdout
yourself if you want a report file, taking care not to overwrite the input.

## Input

The header must match this order exactly:

```csv
sku,on_hand,reserved,inbound,weekly_demand,lead_days,cover_days,safety_stock,pack_size,unit_cost_minor
PHONE-CASE,10,2,0,7,7,14,2,6,105
```

- Enter whole units and nonnegative decimal integers. No decimal prices,
  scientific notation, or negative quantities.
- Use **one currency with 100 minor units**. `105` is 1.05; a budget of `5000`
  is 50.00. Currency conversion is not performed.
- `weekly_demand` is your explicit estimate, `lead_days` the delivery lead
  time, and `cover_days` the target coverage window (at least lead time).
- Reserved stock is subtracted, inbound stock counted once. A triggered order
  rounds up to whole packs. Urgent rows are allocated first; ties keep input order.
- Omitting a budget means unlimited. A zero budget means buy zero units.

With the fictional example and budget 50.00, the urgent USB-CABLE gets 18 units
costing 45.00. Only 5.00 remains, which cannot buy the next PHONE-CASE pack at
6.30. The report leaves that amount unspent instead of buying a partial pack.

Read [the design and limits](docs/design.md) before using a plan. Inbound
arrival dates, supplier minimum order values, taxes, and demand uncertainty are
not modeled. This tool does not guarantee stock availability or optimal spend.

## Verify

Python 3.10+ is only used to drive the tests:

```sh
# SALAM and SALAM_STD as above
python3 tests/run.py
```

On Windows use `python tests/run.py`. The harness compiles the production app
and four Salam test executables, then tests actual CLI behavior. It also checks
240 deterministic randomized stock rows against a Python integer oracle.
Build logs and executables stay in ignored `build/`. The Linux GitHub workflow
uses the pinned official release and verifies its published checksum; a CI
file's presence alone is not evidence of a successful CI run.

Development history contains separate working increments: numeric/domain
foundation, strict import, replenishment/budget engine, reports/CLI, encoding
and regression checks, and reproducible documentation/CI.

## License and disclosure

GPL-3.0-only; see [LICENSE](LICENSE).

AI assistance: OpenAI Codex is used for implementation and verification.
The author does not claim personal manual testing by anyone else. This was
prepared for [Salam's community reward](https://github.com/SalamLang/Salam/issues/1713);
preparing or publishing it does not establish acceptance or payment.
