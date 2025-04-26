import sqlite3
import datetime
from decimal import Decimal
import os

# Import the functions to be tested
from utility_functions.utilities  import (
    _execute_sql, # Keep helper if needed
    # P&L Functions
    calculate_total_revenue_for_period,
    calculate_total_expenses_for_period,
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
        print("\n--- Testing Profit & Loss Functions ---")

        # --- Test Data ---
        # Use a period with sample GL data (e.g., March 2025 from sample data)
        start_date_str = "2025-03-01"
        end_date_str = "2025-03-31"
        print(f"--- Testing Period: {start_date_str} to {end_date_str} ---")


        # == 1. Test calculate_total_revenue_for_period ==
        print("\n1. Testing calculate_total_revenue_for_period...")
        total_revenue = calculate_total_revenue_for_period(conn, start_date_str, end_date_str)

        if total_revenue is not None and isinstance(total_revenue, Decimal):
            print(f"   PASS: Function returned a Decimal value.")
            print(f"      Total Revenue Calculated for Period: {total_revenue:.2f}")
            # Note: Exact verification requires manually summing all relevant sample GL entries.
            # This test primarily confirms the function runs and returns the correct type.
            if total_revenue >= 0: # Based on sample data, revenue should be positive
                print("      INFO: Calculated revenue is non-negative (basic check).")
            else:
                print("      WARN: Calculated revenue is negative.")
        elif total_revenue is None:
             print("   FAIL: calculate_total_revenue_for_period returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected Decimal, got {type(total_revenue)}.")


        # == 2. Test calculate_total_expenses_for_period ==
        print("\n2. Testing calculate_total_expenses_for_period...")
        total_expenses = calculate_total_expenses_for_period(conn, start_date_str, end_date_str)

        if total_expenses is not None and isinstance(total_expenses, Decimal):
            print(f"   PASS: Function returned a Decimal value.")
            print(f"      Total Expenses Calculated for Period: {total_expenses:.2f}")
            # Note: Exact verification requires manually summing all relevant sample GL entries.
            # This test primarily confirms the function runs and returns the correct type.
            if total_expenses >= 0: # Based on sample data, expenses should be positive
                print("      INFO: Calculated expenses are non-negative (basic check).")
            else:
                print("      WARN: Calculated expenses are negative.")
        elif total_expenses is None:
             print("   FAIL: calculate_total_expenses_for_period returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected Decimal, got {type(total_expenses)}.")

        # == 3. Calculate Net Income/Loss (Simple) ==
        print("\n3. Calculating Net Income/Loss (Revenue - Expenses)...")
        if isinstance(total_revenue, Decimal) and isinstance(total_expenses, Decimal):
            net_income_loss = total_revenue - total_expenses
            print(f"   Calculated Net Income/(Loss) for Period: {net_income_loss:.2f}")
            print("   (Manual verification recommended based on sample data)")
        else:
            print("   SKIP: Cannot calculate Net Income/Loss due to errors in previous steps.")


        print("\n--- Profit & Loss Function Tests Complete ---")

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