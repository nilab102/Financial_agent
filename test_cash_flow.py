import sqlite3
import datetime
from decimal import Decimal
import os

# Import the functions to be tested
from utility_functions.utilities  import (
    _execute_sql, # Keep helper if needed
    # Cash Flow Functions
    calculate_net_cash_change_for_period,
    # Other functions if needed
)

DATABASE_FILE = './database/financial_agent.db'

# --- Database Connection ---
def get_db_connection():
    """Establishes database connection with Decimal support."""
    if not os.path.exists(DATABASE_FILE):
        raise FileNotFoundError(f"Database file '{DATABASE_FILE}' not found. "
                              "Please run the SQL script first.")

    conn = sqlite3.connect(DATABASE_FILE, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row # Access columns by name
    conn.execute("PRAGMA foreign_keys = ON;")

    # Register adapter/converter for Decimal
    sqlite3.register_adapter(Decimal, str)
    sqlite3.register_converter("DECIMAL", lambda b: Decimal(b.decode('utf-8')))

    return conn

# --- Test Execution ---
if __name__ == "__main__":
    conn = None
    try:
        conn = get_db_connection()
        print(f"--- Connected to Database: {DATABASE_FILE} ---")
        print("\n--- Testing Cash Flow Functions ---")

        # --- Test Data ---
        # Use a period with sample CashTransactions data (e.g., March 2025 from sample data)
        start_date_str = "2025-03-01"
        end_date_str = "2025-03-31"
        print(f"--- Testing Period: {start_date_str} to {end_date_str} ---")


        # == 1. Test calculate_net_cash_change_for_period ==
        print("\n1. Testing calculate_net_cash_change_for_period...")
        net_cash_change = calculate_net_cash_change_for_period(conn, start_date_str, end_date_str)

        if net_cash_change is not None and isinstance(net_cash_change, Decimal):
            print(f"   PASS: Function returned a Decimal value.")
            print(f"      Net Cash Change Calculated for Period: {net_cash_change:.2f}")
            # Note: Exact verification requires manually summing Deposits - Withdrawals
            # from sample CashTransactions data for March 2025.
            # This test primarily confirms the function runs and returns the correct type.
            print("      (Manual verification recommended based on sample data)")
        elif net_cash_change is None:
             print("   FAIL: calculate_net_cash_change_for_period returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected Decimal, got {type(net_cash_change)}.")


        print("\n--- Cash Flow Function Tests Complete ---")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
    except sqlite3.Error as e:
        print(f"DATABASE ERROR: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"UNEXPECTED ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("\n--- Database Connection Closed ---")