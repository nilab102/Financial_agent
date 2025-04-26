import sqlite3
import datetime
from decimal import Decimal
import os
import traceback # Import for detailed error printing

# Import the functions to be tested FROM fm_functions
# Ensure fm_functions.py is in the same directory or Python path
try:
    from utility_functions.utilities import (
        _execute_sql, # Import helper if used in add_sample_login_log
        view_recent_system_logins,
        view_user_activity,
        view_record_change_history,
    )
except ImportError:
    print("ERROR: Could not import functions from fm_functions.py.")
    print("Ensure fm_functions.py is in the same directory or accessible via PYTHONPATH.")
    exit()


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

# --- Helper to Add Sample Login Audit Log ---
def add_sample_login_log(conn, user_id, ip_address="127.0.0.1"):
    """Adds a sample Login entry to AuditLogs WITHOUT the Description column."""
    print(f"   INFO: Adding sample 'Login' Audit Log entry for user {user_id}...")
    # --- FIX: Remove Description column ---
    sql = """
        INSERT INTO AuditLogs
        (TableName, RecordID, ActionType, OldValue, NewValue, ChangedBy, ChangeDate, IPAddress)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
    """
    # Remove the parameter corresponding to Description
    params = ("System", user_id, "Login", None, None, user_id, ip_address)
    # --- END FIX ---
    try:
        # Using _execute_sql helper imported from fm_functions
        _execute_sql(conn, sql, params, commit=True)
        print("      Sample login log added.")
        return True
    except sqlite3.Error as e:
        print(f"      Error adding sample login log: {e}")
        # Rollback might be needed if called within a larger transaction elsewhere,
        # but _execute_sql with commit=True should handle its own scope.
        # conn.rollback() # Generally not needed here if commit=True works/fails atomically
        return False
    except Exception as e:
        # Catch other potential errors like NameError if _execute_sql wasn't imported
         print(f"      Unexpected error adding sample login log: {e}")
         return False


# --- Test Execution ---
if __name__ == "__main__":
    conn = None
    try:
        conn = get_db_connection()
        print(f"--- Connected to Database: {DATABASE_FILE} ---")
        print("\n--- Testing Audit Functions ---")

        # --- Test Data ---
        test_limit = 5
        test_employee_id_ar = 16 # Jennifer Walker (AR Specialist - has sample logs)
        test_employee_id_ap = 17 # Daniel Hall (AP Specialist - has sample logs)
        test_employee_id_login = 2 # Jane Doe (CFO - for sample login)
        test_table_name = "Invoices"
        # Use an InvoiceID known to have entries in the sample AuditLogs
        test_record_id = 1 # INV-2025-0001 had update in sample logs
        # Or use one that likely had actions from other tests if needed
        # test_record_id = test_invoice_id_1 # If testing AR/AP before Audit

        # Add a sample login log for testing view_recent_system_logins
        login_added = add_sample_login_log(conn, test_employee_id_login)
        if not login_added:
             print("   WARN: Failed to add sample login log, test might be less effective.")


        # == 1. Test view_recent_system_logins ==
        print("\n1. Testing view_recent_system_logins...")
        recent_logins = view_recent_system_logins(conn, limit=test_limit)

        if recent_logins is not None and isinstance(recent_logins, list):
            print(f"   PASS: Retrieved list of {len(recent_logins)} recent system logins (max {test_limit}).")
            if len(recent_logins) > 0:
                 if isinstance(recent_logins[0], (dict, sqlite3.Row)):
                      print(f"      PASS: List contains dict/Row objects.")
                      sample_login = recent_logins[0]
                      # --- FIX: Remove reference to Description ---
                      print(f"      Most Recent Sample Login: User={sample_login.get('FirstName','N/A')} {sample_login.get('LastName','N/A')}, "
                            f"Time={sample_login.get('ChangeDate','N/A')}, IP={sample_login.get('IPAddress','N/A')}")
                      # --- END FIX ---
                 else:
                      print(f"      FAIL: List elements are not dict/Row, type: {type(recent_logins[0])}")
            else:
                 print("      WARN: Recent logins list is empty (check sample data/helper function).")
        elif recent_logins is None:
             print("   FAIL: view_recent_system_logins returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected a list for logins, got {type(recent_logins)}.")


        # == 2. Test view_user_activity ==
        print(f"\n2. Testing view_user_activity (Employee ID: {test_employee_id_ar})...")
        user_activity = view_user_activity(conn, test_employee_id_ar, limit=test_limit)

        if user_activity is not None and isinstance(user_activity, list):
            print(f"   PASS: Retrieved list of {len(user_activity)} activities for employee {test_employee_id_ar} (max {test_limit}).")
            if len(user_activity) > 0:
                 if isinstance(user_activity[0], (dict, sqlite3.Row)):
                      print(f"      PASS: List contains dict/Row objects.")
                      sample_activity = user_activity[0]
                      print(f"      Most Recent Sample Activity: Table={sample_activity.get('TableName','N/A')}, "
                            f"Record={sample_activity.get('RecordID','N/A')}, Action={sample_activity.get('ActionType','N/A')}, Time={sample_activity.get('ChangeDate','N/A')}")
                 else:
                      print(f"      FAIL: List elements are not dict/Row, type: {type(user_activity[0])}")
            else:
                 print(f"      WARN: User activity list is empty for employee {test_employee_id_ar} (check sample data or run previous tests first).")
        elif user_activity is None:
             print("   FAIL: view_user_activity returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected a list for user activity, got {type(user_activity)}.")


        # == 3. Test view_record_change_history ==
        print(f"\n3. Testing view_record_change_history (Table: {test_table_name}, Record ID: {test_record_id})...")
        change_history = view_record_change_history(conn, test_table_name, test_record_id)

        if change_history is not None and isinstance(change_history, list):
            print(f"   PASS: Retrieved list of {len(change_history)} change history entries for {test_table_name} ID {test_record_id}.")
            if len(change_history) > 0:
                 if isinstance(change_history[0], (dict, sqlite3.Row)):
                      print(f"      PASS: List contains dict/Row objects.")
                      sample_change = change_history[0] # Most recent change
                      print(f"      Most Recent Change: User={sample_change.get('FirstName','N/A')} {sample_change.get('LastName','N/A')}, "
                            f"Action={sample_change.get('ActionType','N/A')}, Time={sample_change.get('ChangeDate','N/A')}")
                      # Use .get() for safety in case keys are missing
                      print(f"         Old Value: {str(sample_change.get('OldValue', 'N/A'))[:50]}...")
                      print(f"         New Value: {str(sample_change.get('NewValue', 'N/A'))[:50]}...")
                 else:
                      print(f"      FAIL: List elements are not dict/Row, type: {type(change_history[0])}")
            else:
                 print(f"      WARN: Change history list is empty for {test_table_name} ID {test_record_id} (check sample data or run AR/AP tests first).")
        elif change_history is None:
             print("   FAIL: view_record_change_history returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected a list for change history, got {type(change_history)}.")


        print("\n--- Audit Function Tests Complete ---")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
    except sqlite3.Error as e:
        print(f"DATABASE ERROR: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"UNEXPECTED ERROR during testing: {e}")
        traceback.print_exc() # Print detailed traceback
    finally:
        if conn:
            # Optional: Clean up the sample login log if desired and if added
            # Note: Need to ensure 'login_added' is accessible or re-check
            # print("\n--- Cleaning up test data ---")
            # try:
            #     # Check if the log was actually added before trying to delete
            #     check_sql = "SELECT 1 FROM AuditLogs WHERE ActionType = 'Login' AND ChangedBy = ? LIMIT 1"
            #     log_exists = _execute_sql(conn, check_sql, (test_employee_id_login,), fetchone=True)
            #     if log_exists:
            #         print(f"   Deleting test 'Login' log for user {test_employee_id_login}")
            #         conn.execute("DELETE FROM AuditLogs WHERE ActionType = 'Login' AND ChangedBy = ?", (test_employee_id_login,))
            #         conn.commit()
            #         print("   Test login log entry deleted.")
            #     else:
            #          print("   No test login log found to delete.")
            # except sqlite3.Error as e:
            #     print(f"   Error during cleanup: {e}")
            #     conn.rollback()
            # except Exception as e:
            #      print(f"   Unexpected error during cleanup: {e}")


            conn.close()
            print("\n--- Database Connection Closed ---")