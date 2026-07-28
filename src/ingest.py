"""
src/ingest.py

CSV -> clean SQLite database.

Responsibilities:
1. Load the Superstore CSV dataset (with an encoding fallback chain).
2. Validate its contents (soft sanity checks, not a brittle exact count).
3. Normalize column names and dates.
4. Create the SQLite database.
5. Assert that a year-grouped date query actually returns real numbers
   before declaring success -- this is the check that would have caught
   the original 'strftime() silently returns NULL on M/D/YYYY strings'
   failure mode if it had ever been reintroduced.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

from src.core.paths import DATA_DIR

TABLE_NAME = "orders"

# A generous sanity range, not a brittle exact match -- the point is to
# catch "this obviously isn't the Superstore dataset" (wrong file, empty
# file, truncated download), not to break on a legitimate future refresh
# of the dataset that adds or removes a handful of rows.
MIN_EXPECTED_ROWS = 5_000
MAX_EXPECTED_ROWS = 50_000

REQUIRED_COLUMNS = [
    "Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode",
    "Customer ID", "Customer Name", "Segment", "Country", "City", "State",
    "Postal Code", "Region", "Product ID", "Category", "Sub-Category",
    "Product Name", "Sales", "Quantity", "Discount", "Profit",
]

COLUMN_MAPPING = {
    "Row ID": "row_id", "Order ID": "order_id", "Order Date": "order_date",
    "Ship Date": "ship_date", "Ship Mode": "ship_mode", "Customer ID": "customer_id",
    "Customer Name": "customer_name", "Segment": "segment", "Country": "country",
    "City": "city", "State": "state", "Postal Code": "postal_code", "Region": "region",
    "Product ID": "product_id", "Category": "category", "Sub-Category": "sub_category",
    "Product Name": "product_name", "Sales": "sales", "Quantity": "quantity",
    "Discount": "discount", "Profit": "profit",
}

DATE_COLUMNS = ["order_date", "ship_date"]


def load_dataset(csv_path: Path) -> pd.DataFrame:
    print(f"\nLoading dataset:\n{csv_path}\n")
    last_err = None
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            print(f"Read with encoding={encoding} ({len(df)} rows)")
            return df
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
    raise RuntimeError(f"Could not read {csv_path} with utf-8/latin-1/cp1252: {last_err}")


def validate_dataset(df: pd.DataFrame) -> None:
    print("=" * 60)
    print("DATASET VALIDATION")
    print("=" * 60)

    rows = len(df)
    if not (MIN_EXPECTED_ROWS <= rows <= MAX_EXPECTED_ROWS):
        raise ValueError(
            f"Row count {rows} is outside the expected sanity range "
            f"[{MIN_EXPECTED_ROWS}, {MAX_EXPECTED_ROWS}]. This usually means "
            "the wrong file was provided, or the download was truncated."
        )
    print(f"Rows: {rows} (within sanity range)")
    print(f"Columns: {len(df.columns)}")

    missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing columns: {missing_columns}")
    print("Required columns found")

    print(f"Missing values: {int(df.isna().sum().sum())}")
    print(f"Duplicate rows: {int(df.duplicated().sum())}")


def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    print("\nNormalizing dataset...")
    df = df.rename(columns=COLUMN_MAPPING)

    for col in DATE_COLUMNS:
        # Explicit format, not inference: the raw CSV uses M/D/YYYY, and
        # relying on pandas to infer that consistently across the whole
        # column is unnecessary risk when we know the exact format.
        parsed = pd.to_datetime(df[col], format="%m/%d/%Y", errors="coerce")
        still_bad = parsed.isna() & df[col].notna()
        if still_bad.any():
            parsed.loc[still_bad] = pd.to_datetime(df.loc[still_bad, col], errors="coerce")
        n_bad = int(parsed.isna().sum() - df[col].isna().sum())
        if n_bad > 0:
            print(f"WARNING: {n_bad} unparseable dates in '{col}'")
        df[col] = parsed.dt.strftime("%Y-%m-%d")

    print("Column names normalized")
    print("Dates converted to ISO (YYYY-MM-DD)")
    return df


def create_database(df: pd.DataFrame, db_path: Path) -> None:
    print("\nCreating SQLite database...")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
        for col in ("order_date", "region", "category", "sub_category", "customer_id"):
            if col in df.columns:
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{col} ON {TABLE_NAME}({col})")
        conn.commit()
        rows = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    finally:
        conn.close()

    print(f"Database created. Imported rows: {rows}")


def sanity_check(db_path: Path) -> None:
    """The check that matters most: assert dates are actually queryable."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            f"""
            SELECT strftime('%Y', order_date) AS yr, ROUND(SUM(sales), 2) AS total
            FROM {TABLE_NAME}
            WHERE order_date IS NOT NULL
            GROUP BY yr
            ORDER BY yr
            """
        ).fetchall()
    finally:
        conn.close()

    if not rows or all(r[0] is None for r in rows):
        raise AssertionError(
            "SANITY FAILED: strftime('%Y', order_date) returned no usable "
            "years. Dates were not normalized to ISO format correctly."
        )
    if any(r[1] is None or r[1] == 0 for r in rows):
        raise AssertionError(f"SANITY FAILED: a year bucket has NULL/zero sales: {rows}")

    print(f"\nsanity: sales by year -> {rows}")
    print("sanity OK: dates are ISO and queryable \u2714")


def main() -> None:
    csv_path = DATA_DIR / "superstore.csv"
    db_path = DATA_DIR / "superstore.db"

    if not csv_path.exists():
        print(f"ERROR: {csv_path} does not exist", file=sys.stderr)
        sys.exit(1)

    df = load_dataset(csv_path)
    validate_dataset(df)
    df = normalize_dataset(df)
    create_database(df, db_path)

    try:
        sanity_check(db_path)
    except AssertionError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("INGESTION COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(f"Database saved to:\n{db_path}")


if __name__ == "__main__":
    main()
