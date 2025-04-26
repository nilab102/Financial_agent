import sqlite3
import datetime
from decimal import Decimal
import os

# Import the functions to be tested
from utility_functions.utilities  import (
    _execute_sql, # Keep helper if needed
    # Budgeting Functions
    list_current_budgets,
    view_budget_details,
    view_budgeted_amount,
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
        print("\n--- Testing Budgeting Functions ---")

        # --- Test Data ---
        # Assuming current date falls within FY 2025 based on sample data
        test_status = 'Approved'
        test_budget_id = 1 # Annual Corporate Budget 2025
        test_dept_budget_id = 2 # Finance Department Budget 2025
        test_account_id = 40 # Sales Revenue (used in sample BudgetItems)
        test_period_id = 33 # Jan 2025 Period (used in sample BudgetItems)


        # == 1. Test list_current_budgets ==
        print(f"\n1. Testing list_current_budgets (Status: {test_status})...")
        current_budgets = list_current_budgets(conn, status=test_status)

        if current_budgets is not None and isinstance(current_budgets, list):
            print(f"   PASS: Retrieved list of {len(current_budgets)} '{test_status}' budgets for current FY.")
            if len(current_budgets) > 0:
                 if isinstance(current_budgets[0], (dict, sqlite3.Row)):
                      print(f"      PASS: List contains dict/Row objects.")
                      sample_budget = current_budgets[0]
                      print(f"      Sample Budget: ID={sample_budget['BudgetID']}, Name={sample_budget['BudgetName']}, "
                            f"Dept={sample_budget.get('DepartmentName', 'N/A')}")
                 else:
                      print(f"      FAIL: List elements are not dict/Row, type: {type(current_budgets[0])}")
            else:
                 print(f"      WARN: Budget list is empty for status '{test_status}' in current FY (check sample data/current date).")
        elif current_budgets is None:
             print("   FAIL: list_current_budgets returned None (check DB errors or FY logic).")
        else:
             print(f"   FAIL: Expected a list for budgets, got {type(current_budgets)}.")


        # == 2. Test view_budget_details ==
        print(f"\n2. Testing view_budget_details (Budget ID: {test_budget_id})...")
        budget_details = view_budget_details(conn, test_budget_id)

        if budget_details and isinstance(budget_details, (dict, sqlite3.Row)):
             if budget_details['BudgetID'] == test_budget_id:
                 print("   PASS: Retrieved details for budget.")
                 print(f"      - Name: {budget_details['BudgetName']}, Status: {budget_details['Status']}, FY: {budget_details['FiscalYearStart']} - {budget_details['FiscalYearEnd']}")
                 print(f"      - Created By: {budget_details['CreatedByName']}, Approved By: {budget_details.get('ApprovedByName', 'N/A')}")
             else:
                 print(f"   FAIL: Retrieved details, but BudgetID mismatch (Got {budget_details['BudgetID']}).")
        elif budget_details is None:
             print(f"   FAIL: view_budget_details returned None for BudgetID {test_budget_id}.")
        else:
             print(f"   FAIL: Expected dict/Row, got {type(budget_details)}.")

        # Test with a Department budget
        print(f"   Testing view_budget_details (Dept Budget ID: {test_dept_budget_id})...")
        dept_budget_details = view_budget_details(conn, test_dept_budget_id)
        if dept_budget_details and dept_budget_details.get('DepartmentName'):
             print("   PASS: Retrieved details for department budget and it includes DepartmentName.")
             print(f"      - Dept Name: {dept_budget_details['DepartmentName']}")
        elif dept_budget_details:
             print("   WARN: Retrieved department budget details, but DepartmentName is missing.")
        else:
             print(f"   FAIL: Could not retrieve details for Dept Budget ID {test_dept_budget_id}.")


        # == 3. Test view_budgeted_amount ==
        print(f"\n3. Testing view_budgeted_amount (Budget: {test_budget_id}, Account: {test_account_id}, Period: {test_period_id})...")
        budgeted_amount = view_budgeted_amount(conn, test_budget_id, test_account_id, test_period_id)

        # Based on sample data: Budget 1, Account 40 (Sales Rev), Period 33 (Jan 25) = 500000.00
        expected_sample_amount = Decimal('500000.00')

        if budgeted_amount is not None and isinstance(budgeted_amount, Decimal):
             print(f"   PASS: Function returned a Decimal value.")
             print(f"      Budgeted Amount Retrieved: {budgeted_amount:.2f}")
             if abs(budgeted_amount - expected_sample_amount) < Decimal('0.01'):
                 print(f"      PASS: Retrieved amount matches expected sample amount ({expected_sample_amount:.2f}).")
             else:
                 print(f"      WARN: Retrieved amount ({budgeted_amount:.2f}) differs from expected sample amount ({expected_sample_amount:.2f}). Check IDs/Sample Data.")
        elif budgeted_amount is None:
             print("   FAIL: view_budgeted_amount returned None (check IDs or if item exists).")
        else:
             print(f"   FAIL: Expected Decimal, got {type(budgeted_amount)}.")

        # Test non-existent combination
        print(f"   Testing non-existent combination (Budget: {test_budget_id}, Account: 999, Period: {test_period_id})...")
        non_existent_amount = view_budgeted_amount(conn, test_budget_id, 999, test_period_id)
        if non_existent_amount is None:
            print("   PASS: Correctly returned None for non-existent budget item.")
        else:
            print(f"   FAIL: Incorrectly returned a value ({non_existent_amount}) for non-existent budget item.")


        print("\n--- Budgeting Function Tests Complete ---")

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