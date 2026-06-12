# Rebrickable Pipeline

A Python pipeline that ingests LEGO data from the [Rebrickable API](https://rebrickable.com/api/) into Snowflake, landing raw JSON in a RAW layer with clean modelled views on top.

## What it does

Pulls **all** records from four Rebrickable endpoints and loads them into Snowflake:

| Endpoint | Raw Table | Modelled View | Key |
|----------|-----------|---------------|-----|
| `/lego/colors/` | `RAW_COLORS` | `DIM_COLORS` | `id` |
| `/lego/themes/` | `RAW_THEMES` | `DIM_THEMES` | `id` |
| `/lego/sets/` | `RAW_SETS` | `DIM_SETS` | `set_num` |
| `/lego/minifigs/` | `RAW_MINIFIGS` | `DIM_MINIFIGS` | `set_num` |

### Key features

- **Paginated fetch** with `page_size=1000` and automatic next-page following
- **Rate-limit aware** -- 1 second sleep between API requests
- **Idempotent** -- uses `MERGE` on a stable key so re-runs never create duplicates
- **Raw JSON preserved** -- full API response stored as `VARIANT` for flexibility

## Setup

### Prerequisites

- Python 3.11+
- A Snowflake account with a configured connection in `~/.snowflake/connections.toml`
- A [Rebrickable API key](https://rebrickable.com/api/)

### Install

```bash
pip install -r requirements.txt
```

### Configure

Create a `.env` file (see `.env-example`):

```
REBRICKABLE_API_KEY=your_key_here
```

### Create Snowflake objects

Run `setup.sql` in your Snowflake worksheet to create the schema and tables, then run `models.sql` to create the views.

## Usage

```bash
python ingest_rebrickable.py
```

The script will authenticate to Snowflake (browser SSO), fetch all pages from each endpoint, and MERGE the data into the raw tables.

## Project structure

```
.
├── ingest_rebrickable.py   # Main ingestion script
├── setup.sql               # Schema + raw table DDL
├── models.sql              # Typed view definitions
├── requirements.txt        # Python dependencies
├── .env-example            # Required environment variables
└── .gitignore              # Files excluded from version control
```

## Architecture

```
Rebrickable API ──> ingest_rebrickable.py ──> Snowflake
                    (paginate + sleep)         │
                                               ├─ RAW_COLORS (VARIANT)
                                               ├─ RAW_THEMES (VARIANT)
                                               ├─ RAW_SETS (VARIANT)
                                               └─ RAW_MINIFIGS (VARIANT)
                                                       │
                                               ┌──────────────┐
                                               │  DIM views   │
                                               │  (typed SQL) │
                                               └──────────────┘
```
