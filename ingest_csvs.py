"""Download inventory CSVs from Rebrickable and load into Snowflake."""

import csv
import gzip
import io
import os

import requests
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

SCHEMA = "TIL_PORTFOLIO_PROJECTS.MR_REBRICKABLE"

CSVS = {
    "inventories": {
        "url": "https://cdn.rebrickable.com/media/downloads/inventories.csv.gz",
        "table": "RAW_INVENTORIES",
        "columns": ["INVENTORY_ID", "VERSION", "SET_NUM"],
    },
    "inventory_minifigs": {
        "url": "https://cdn.rebrickable.com/media/downloads/inventory_minifigs.csv.gz",
        "table": "RAW_INVENTORY_MINIFIGS",
        "columns": ["INVENTORY_ID", "FIG_NUM", "QUANTITY"],
    },
}


def download_csv(url: str) -> list[list[str]]:
    print(f"  Downloading {url}...")
    resp = requests.get(url)
    resp.raise_for_status()
    raw = gzip.decompress(resp.content).decode("utf-8")
    reader = csv.reader(io.StringIO(raw))
    header = next(reader)
    print(f"  Columns: {header}")
    return [row for row in reader]


def load_csv(conn, table: str, columns: list[str], rows: list[list[str]]) -> int:
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {SCHEMA}.{table}")

    batch_size = 5000
    col_list = ", ".join(columns)
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        placeholders = ", ".join(["(%s, %s, %s)"] * len(batch))
        sql = f"INSERT INTO {SCHEMA}.{table} ({col_list}) VALUES {placeholders}"
        params = []
        for row in batch:
            params.extend(row[:3])
        cur.execute(sql, params)

    conn.commit()
    cur.close()
    return len(rows)


def main():
    conn = snowflake.connector.connect(connection_name="tiluk-core")
    conn.cursor().execute("USE WAREHOUSE DATASCHOOL_WH")
    conn.cursor().execute("USE DATABASE TIL_PORTFOLIO_PROJECTS")
    conn.cursor().execute("USE SCHEMA MR_REBRICKABLE")

    for name, cfg in CSVS.items():
        print(f"Processing {name}...")
        rows = download_csv(cfg["url"])
        n = load_csv(conn, cfg["table"], cfg["columns"], rows)
        print(f"  -> {cfg['table']}: loaded {n} rows")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
