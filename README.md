# FinSAC Climate Pipeline

Python ETL pipeline that processes country Excel submissions and seeds the Cloudflare D1 database powering the climate risk dashboard.

## How it works

```
submissions/*.xlsx
      ↓
batch_run.py  (runs pipeline for each file)
      ↓
data/dashboard.db  (local SQLite)
      ↓
export_d1.py  (generates SQL seed file)
      ↓
wrangler d1 execute  (seeds Cloudflare D1)
      ↓
Hono / Cloudflare Workers backend ✅
```

## Automated (GitHub Actions)

Every time a `.xlsx` file is pushed to `submissions/`, GitHub Actions runs the full pipeline automatically. No manual steps needed.

See [`.github/workflows/pipeline.yml`](.github/workflows/pipeline.yml).

## Run locally

```bash
# Install dependencies
pip install -r requirements.txt

# Process all submissions
python batch_run.py

# Export to D1 SQL
python export_d1.py

# Seed D1 (requires wrangler + Cloudflare credentials)
wrangler d1 execute climate_dashboard --file=data/seed_d1.sql --remote
```

## Adding a new country submission

1. Drop the `{Country}_MP.xlsx` file into `submissions/`
2. Commit and push to `main`
3. GitHub Actions runs automatically

## Folder structure

```
.github/workflows/pipeline.yml   ← GitHub Actions
config/                          ← YAML config (indicators, validation rules, weights)
stages/                          ← ETL stage modules
submissions/                     ← Drop Excel files here
data/                            ← Generated DB + SQL (gitignored)
logs/                            ← Pipeline logs (gitignored)
models.py                        ← Data models
database.py                      ← SQLite schema & queries
pipeline.py                      ← Single-file orchestrator
batch_run.py                     ← Batch runner (all files in submissions/)
export_d1.py                     ← SQLite → D1 SQL exporter
requirements.txt
```

## GitHub Secrets required

Set these in **Settings → Secrets → Actions** on this repo:

| Secret | Value |
|---|---|
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token with D1 edit permission |
| `CLOUDFLARE_ACCOUNT_ID` | Your Cloudflare account ID |

## Excel template format (FinSAC 9-sheet)

| Sheet | Content |
|---|---|
| `00_README` | Instructions (ignored) |
| `01_Submission_Metadata` | Country code, round, analyst info |
| `02_Ref_Country` | Country reference list |
| `03_Ref_Indicator` | Indicator definitions |
| `04_Ref_Region` | Region reference list |
| `05_Ref_Sector_NACE` | NACE sector hierarchy |
| `06_Data_National` | National-level data |
| `07_Data_Regional` | Regional-level data |
| `08_Data_Sectoral` | Sectoral-level data |

## Layer 5 scoring (national level)

| Score | Formula |
|---|---|
| Physical Risk | AVG(flood, drought, wildfire, landslide, vulnerability) |
| Transition Risk | weighted_avg(GHG×0.4, energy×0.3, coal×0.2, renewables×0.1) → min-max norm |
| Financial Vulnerability | weighted_avg(debt×0.3, fiscal×0.2, CA×0.2, FX×0.2, doll×0.1) → min-max norm |
| **CCR Score** | **0.35×Physical + 0.40×Transition + 0.25×Financial** |
