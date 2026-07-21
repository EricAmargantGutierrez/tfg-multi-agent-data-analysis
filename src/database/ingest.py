"""
Database ingestion module.

Responsibilities:
1. Load the Superstore CSV dataset.
2. Validate its contents.
3. Normalize the data.
4. Create the SQLite database.
5. Verify the import.
"""

from pathlib import Path
import sqlite3

import pandas as pd

from src.core.paths import DATA_DIR

# ============================================================================
# Configuration
# ============================================================================

EXPECTED_ROWS = 9994

REQUIRED_COLUMNS = [
    "Row ID",
    "Order ID",
    "Order Date",
    "Ship Date",
    "Ship Mode",
    "Customer ID",
    "Customer Name",
    "Segment",
    "Country",
    "City",
    "State",
    "Postal Code",
    "Region",
    "Product ID",
    "Category",
    "Sub-Category",
    "Product Name",
    "Sales",
    "Quantity",
    "Discount",
    "Profit",
]


# ============================================================================
# Loading
# ============================================================================

def load_dataset(csv_path: Path) -> pd.DataFrame:
    print(f"\nLoading dataset:\n{csv_path}\n")
    return pd.read_csv(csv_path)


# ============================================================================
# Validation
# ============================================================================

def validate_dataset(df: pd.DataFrame) -> None:

    print("=" * 60)
    print("DATASET VALIDATION")
    print("=" * 60)

    rows = len(df)

    if rows != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} rows but found {rows}"
        )

    print(f"Rows: {rows}")
    print(f"Columns: {len(df.columns)}")

    missing_columns = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    print("Required columns found")

    missing_values = int(df.isna().sum().sum())
    print(f"Missing values: {missing_values}")

    duplicate_rows = int(df.duplicated().sum())
    print(f"Duplicate rows: {duplicate_rows}")


# ============================================================================
# Normalization
# ============================================================================

def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:

    print("\nNormalizing dataset...")

    column_mapping = {
        "Row ID": "row_id",
        "Order ID": "order_id",
        "Order Date": "order_date",
        "Ship Date": "ship_date",
        "Ship Mode": "ship_mode",
        "Customer ID": "customer_id",
        "Customer Name": "customer_name",
        "Segment": "segment",
        "Country": "country",
        "City": "city",
        "State": "state",
        "Postal Code": "postal_code",
        "Region": "region",
        "Product ID": "product_id",
        "Category": "category",
        "Sub-Category": "sub_category",
        "Product Name": "product_name",
        "Sales": "sales",
        "Quantity": "quantity",
        "Discount": "discount",
        "Profit": "profit",
    }

    df = df.rename(columns=column_mapping)

    df["order_date"] = pd.to_datetime(df["order_date"])
    df["ship_date"] = pd.to_datetime(df["ship_date"])

    print("Column names normalized")
    print("Dates converted")

    return df


# ============================================================================
# SQLite
# ============================================================================

def create_database(df: pd.DataFrame, db_path: Path):

    print("\nCreating SQLite database...")

    conn = sqlite3.connect(db_path)

    df.to_sql(
        "orders",
        conn,
        if_exists="replace",
        index=False,
    )

    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM orders")

    rows = cursor.fetchone()[0]

    conn.close()

    print(f"Database created")
    print(f"Imported rows: {rows}")


# ============================================================================
# Main
# ============================================================================

def main():

    csv_path = DATA_DIR / "superstore.csv"
    db_path = DATA_DIR / "superstore.db"

    df = load_dataset(csv_path)

    validate_dataset(df)

    df = normalize_dataset(df)

    create_database(df, db_path)

    print("\n" + "=" * 60)
    print("INGESTION COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(f"Database saved to:\n{db_path}")


if __name__ == "__main__":
    main()