from src.database.manager import DatabaseManager


def main():

    db = DatabaseManager()

    print("Checking database...")

    print("Orders table:", db.table_exists("orders"))

    result = db.execute(
        "SELECT COUNT(*) AS total FROM orders"
    )

    print(result)


if __name__ == "__main__":
    main()