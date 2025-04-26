import sqlite3
import datetime
from decimal import Decimal
import os

# Import the functions to be tested
from utility_functions.utilities  import (
    _execute_sql, # Keep helper if needed for direct checks
    # Tax Functions
    view_active_tax_rates,
    # Other functions if needed for setup/verification
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
        print("\n--- Testing Tax Functions ---")

        # == 1. Test view_active_tax_rates ==
        print("\n1. Testing view_active_tax_rates...")
        active_rates = view_active_tax_rates(conn)

        if active_rates is not None and isinstance(active_rates, list):
            print(f"   PASS: Retrieved list of {len(active_rates)} active tax rates.")
            if len(active_rates) > 0:
                # Check type of elements and print one
                if isinstance(active_rates[0], (dict, sqlite3.Row)):
                     print(f"      PASS: List contains dict/Row objects.")
                     sample_rate = active_rates[0]
                     print(f"      Sample Active Rate: ID={sample_rate['TaxRateID']}, "
                           f"Name={sample_rate['TaxName']}, Rate={sample_rate['Rate']:.2f}%")
                else:
                     print(f"      FAIL: List elements are not dict/Row, type: {type(active_rates[0])}")
            else:
                print("      WARN: Active tax rates list is empty (check sample data).")
        elif active_rates is None:
             print("   FAIL: view_active_tax_rates returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected a list for active rates, got {type(active_rates)}.")

        print("\n--- Tax Function Tests Complete ---")

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