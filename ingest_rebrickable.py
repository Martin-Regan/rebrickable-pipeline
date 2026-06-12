"""Ingest themes, colors, sets, and minifigs from Rebrickable API into Snowflake RAW layer."""

import json
import os
import time

import requests
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["REBRICKABLE_API_KEY"]
BASE_URL = "https://rebrickable.com/api/v3/lego"

ENDPOINTS = {
    "colors": {"table": "RAW_COLORS", "key_field": "id"},
    "themes": {"table": "RAW_THEMES", "key_field": "id"},
    "sets": {"table": "RAW_SETS", "key_field": "set_num"},
    "minifigs": {"table": "RAW_MINIFIGS", "key_field": "set_num"},
}

SCHEMA = "TIL_PORTFOLIO_PROJECTS.MR_REBRICKABLE"


def fetch_all_pages(endpoint: str) -> list[dict]:
    """Fetch all pages from a paginated Rebrickable endpoint."""
    results = []
    url = f"{BASE_URL}/{endpoint}/"
    params = {"key": API_KEY, "page_size": 1000, "page": 1}

    while url:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        print(f"  {endpoint}: fetched page, total so far {len(results)}/{data['count']}")
        url = data.get("next")
        params = {}  # next URL embeds query params
        if url:
            time.sleep(1)  # respect rate limit

    return results


def load_to_snowflake(conn, table: str, key_field: str, records: list[dict]) -> int:
    """MERGE records into the target table using a stable key for idempotency."""
    cur = conn.cursor()
    staging = f"{table}__STAGING"

    cur.execute(
        f"CREATE OR REPLACE TEMPORARY TABLE {SCHEMA}.{staging} "
        f"(RECORD_KEY VARCHAR(100), RAW_JSON VARIANT)"
    )

    batch_size = 500
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        values_clause = ", ".join(["(%s, %s)"] * len(batch))
        sql = (
            f"INSERT INTO {SCHEMA}.{staging} (RECORD_KEY, RAW_JSON) "
            f"SELECT column1, PARSE_JSON(column2) FROM VALUES {values_clause}"
        )
        params = []
        for r in batch:
            params.append(str(r[key_field]))
            params.append(json.dumps(r))
        cur.execute(sql, params)

    cur.execute(f"""
        MERGE INTO {SCHEMA}.{table} AS tgt
        USING {SCHEMA}.{staging} AS src
            ON tgt.RECORD_KEY = src.RECORD_KEY
        WHEN MATCHED THEN UPDATE SET
            tgt.RAW_JSON = src.RAW_JSON,
            tgt.LOADED_AT = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (RECORD_KEY, RAW_JSON, LOADED_AT)
            VALUES (src.RECORD_KEY, src.RAW_JSON, CURRENT_TIMESTAMP())
    """)

    merge_result = cur.fetchone()
    print(f"    MERGE: {merge_result[0]} inserted, {merge_result[1]} updated")

    conn.commit()
    cur.close()
    return len(records)


def main():
    conn = snowflake.connector.connect(connection_name="tiluk-core")
    conn.cursor().execute("USE WAREHOUSE DATASCHOOL_WH")
    conn.cursor().execute("USE DATABASE TIL_PORTFOLIO_PROJECTS")
    conn.cursor().execute("USE SCHEMA MR_REBRICKABLE")

    for endpoint, cfg in ENDPOINTS.items():
        print(f"Fetching {endpoint}...")
        records = fetch_all_pages(endpoint)
        n = load_to_snowflake(conn, cfg["table"], cfg["key_field"], records)
        print(f"  -> {cfg['table']}: loaded {n} records")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
