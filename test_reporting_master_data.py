import sqlite3
import datetime
from decimal import Decimal
import os
import time # For unique IDs

# Import the functions to be tested
from utility_functions.utilities  import (
    _execute_sql, # Keep helper if needed for direct checks
    # Reporting & Master Data Functions
    view_chart_of_accounts_list,
    add_new_gl_account,
    view_account_details,
    generate_trial_balance,
    # Need other functions only if they are prerequisites or for verification
)

DATABASE_FILE = './database/financial_agent.db'# Adjust path if needed

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
    # Use variables to store IDs created during the test
    new_account_id = None
    new_account_number = f"9999-TEST-{int(time.time())}" # Unique test account number

    try:
        conn = get_db_connection()
        print(f"--- Connected to Database: {DATABASE_FILE} ---")
        print("\n--- Testing Reporting & Master Data Functions ---")

        # --- Test Data ---
        # Use IDs from the sample data provided in the SQL script if needed
        existing_account_id = 4 # Cash in Bank (known active account)
        parent_account_id = 45 # Expenses (Parent for new test expense)


        # == 1. Test view_chart_of_accounts_list ==
        print("\n1. Testing view_chart_of_accounts_list...")
        # Test fetching only active accounts (default)
        active_accounts = view_chart_of_accounts_list(conn)
        if active_accounts is not None and isinstance(active_accounts, list):
            print(f"   PASS: Retrieved list of {len(active_accounts)} active accounts.")
            if len(active_accounts) > 0:
                # Check type of elements and print one
                if isinstance(active_accounts[0], (dict, sqlite3.Row)):
                     print(f"      PASS: List contains dict/Row objects.")
                     print(f"      Sample Active Account: ID={active_accounts[0]['AccountID']}, "
                           f"Num={active_accounts[0]['AccountNumber']}, Name={active_accounts[0]['AccountName']}")
                else:
                     print(f"      FAIL: List elements are not dict/Row, type: {type(active_accounts[0])}")
            else:
                print("      WARN: Active account list is empty (check sample data).")
        elif active_accounts is None:
             print("   FAIL: view_chart_of_accounts_list (active) returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected a list for active accounts, got {type(active_accounts)}.")

        # Test fetching all accounts (including inactive)
        all_accounts = view_chart_of_accounts_list(conn, include_inactive=True)
        if all_accounts is not None and isinstance(all_accounts, list):
             print(f"   PASS: Retrieved list of {len(all_accounts)} total accounts (active & inactive).")
             # Optionally compare counts if you know inactive accounts exist
             # if len(all_accounts) > len(active_accounts):
             #     print("      PASS: All accounts list is longer than active accounts list.")
             # elif len(all_accounts) == len(active_accounts):
             #      print("      INFO: No inactive accounts found or tested.")
             # else:
             #      print("      FAIL: All accounts list is unexpectedly shorter than active list.")
        elif all_accounts is None:
             print("   FAIL: view_chart_of_accounts_list (all) returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected a list for all accounts, got {type(all_accounts)}.")


        # == 2. Test add_new_gl_account ==
        print("\n2. Testing add_new_gl_account...")
        account_name = "Test Temporary Expense Account"
        account_type = "Expense"
        balance_type = "Debit"
        description = "Account added during testing"

        # Attempt to add the new account
        new_account_id = add_new_gl_account(
            conn, new_account_number, account_name, account_type,
            balance_type, parent_account_id, description
        )

        if new_account_id and isinstance(new_account_id, int):
            print(f"   PASS: add_new_gl_account returned new AccountID: {new_account_id}")
            # Verification: Immediately try to view the added account
            details = view_account_details(conn, new_account_id)
            if details:
                print("      PASS: Successfully retrieved details for the new account.")
                if (details['AccountNumber'] == new_account_number and
                    details['AccountName'] == account_name and
                    details['AccountType'] == account_type and
                    details['BalanceType'] == balance_type and
                    details['ParentAccountID'] == parent_account_id and
                    details['IsActive'] == 1):
                    print("      PASS: Details of the new account match the input.")
                else:
                    print("      FAIL: Details of the new account DO NOT match input.")
                    print("      Expected:", new_account_number, account_name, account_type, balance_type, parent_account_id, 1)
                    print("      Got:", details['AccountNumber'], details['AccountName'], details['AccountType'], details['BalanceType'], details['ParentAccountID'], details['IsActive'])
            else:
                print(f"      FAIL: Could not retrieve details for the newly added AccountID {new_account_id} immediately after creation.")
        else:
            print(f"   FAIL: add_new_gl_account did not return a valid integer ID. Returned: {new_account_id}")

        # Test failure case: Adding duplicate account number
        print(f"   Attempting to add duplicate account number '{new_account_number}' (should fail)...")
        duplicate_id = add_new_gl_account(
            conn, new_account_number, "Duplicate Test Name", "Expense", "Debit"
        )
        if duplicate_id is None:
            print("   PASS: add_new_gl_account correctly returned None for duplicate account number.")
        else:
            print(f"   FAIL: add_new_gl_account INCORRECTLY returned an ID ({duplicate_id}) for a duplicate account number!")
            # Attempt to clean up the accidentally created duplicate if possible
            if isinstance(duplicate_id, int):
                 try:
                     print(f"      Attempting to clean up duplicate account ID: {duplicate_id}")
                     conn.execute("DELETE FROM ChartOfAccounts WHERE AccountID = ?", (duplicate_id,))
                     conn.commit()
                 except sqlite3.Error as e:
                     print(f"      Error cleaning up duplicate: {e}")
                     conn.rollback()


        # == 3. Test view_account_details ==
        print("\n3. Testing view_account_details...")
        # Test with an existing account
        print(f"   Fetching details for existing AccountID: {existing_account_id}")
        details_existing = view_account_details(conn, existing_account_id)
        if details_existing and isinstance(details_existing, (dict, sqlite3.Row)):
             if details_existing['AccountID'] == existing_account_id:
                 print("   PASS: Retrieved details for existing account.")
                 print(f"      - Num: {details_existing['AccountNumber']}, Name: {details_existing['AccountName']}, Type: {details_existing['AccountType']}")
             else:
                 print(f"   FAIL: Retrieved details, but AccountID mismatch (Got {details_existing['AccountID']}).")
        elif details_existing is None:
             print(f"   FAIL: view_account_details returned None for existing AccountID {existing_account_id}.")
        else:
             print(f"   FAIL: Expected dict/Row for existing account, got {type(details_existing)}.")

        # Test with the newly added account (if successful)
        if new_account_id:
             print(f"   Fetching details for newly added AccountID: {new_account_id}")
             details_new = view_account_details(conn, new_account_id)
             if details_new and isinstance(details_new, (dict, sqlite3.Row)):
                  if details_new['AccountID'] == new_account_id:
                      print("   PASS: Retrieved details for newly added account.")
                  else:
                      print(f"   FAIL: Retrieved details, but AccountID mismatch (Got {details_new['AccountID']}).")
             elif details_new is None:
                  print(f"   FAIL: view_account_details returned None for newly added AccountID {new_account_id}.")
             else:
                  print(f"   FAIL: Expected dict/Row for new account, got {type(details_new)}.")
        else:
             print("   SKIP: Cannot test viewing newly added account as its creation failed.")

        # Test with a non-existent account
        non_existent_id = 999999
        print(f"   Fetching details for non-existent AccountID: {non_existent_id}")
        details_non_existent = view_account_details(conn, non_existent_id)
        if details_non_existent is None:
             print(f"   PASS: view_account_details correctly returned None for non-existent AccountID {non_existent_id}.")
        else:
             print(f"   FAIL: view_account_details returned a value ({details_non_existent}) for a non-existent AccountID!")


        # == 4. Test generate_trial_balance ==
        print("\n4. Testing generate_trial_balance...")
        # Generate TB for current state (end of today)
        report_date_str = datetime.date.today().isoformat()
        print(f"   Generating Trial Balance as of: {report_date_str}")
        trial_balance_data = generate_trial_balance(conn, report_date_str)

        if trial_balance_data and isinstance(trial_balance_data, dict):
             print("   PASS: generate_trial_balance returned a dictionary.")
             if 'accounts' in trial_balance_data and 'totals' in trial_balance_data:
                 print("      PASS: Dictionary contains 'accounts' and 'totals' keys.")
                 accounts_list = trial_balance_data['accounts']
                 totals_dict = trial_balance_data['totals']

                 if isinstance(accounts_list, list):
                     print(f"      PASS: 'accounts' key contains a list ({len(accounts_list)} accounts found).")
                     if len(accounts_list) > 0 and isinstance(accounts_list[0], dict):
                         print(f"      Sample TB Line: Acc={accounts_list[0].get('AccountNumber', 'N/A')}, "
                               f"Name={accounts_list[0].get('AccountName', 'N/A')[:20]}..., "
                               f"Debit={accounts_list[0].get('Debit', 0):.2f}, "
                               f"Credit={accounts_list[0].get('Credit', 0):.2f}")
                     elif len(accounts_list) == 0:
                         print("      INFO: Trial balance account list is empty.")
                     else:
                          print(f"      FAIL: 'accounts' list elements are not dictionaries (type: {type(accounts_list[0])}).")

                 else:
                     print(f"      FAIL: 'accounts' key does not contain a list (type: {type(accounts_list)}).")

                 if isinstance(totals_dict, dict) and 'debit' in totals_dict and 'credit' in totals_dict:
                      print("      PASS: 'totals' dictionary contains 'debit' and 'credit' keys.")
                      total_debits = totals_dict['debit']
                      total_credits = totals_dict['credit']
                      if isinstance(total_debits, Decimal) and isinstance(total_credits, Decimal):
                           print(f"      PASS: Totals are Decimal objects.")
                           print(f"      Total Debits : {total_debits:.2f}")
                           print(f"      Total Credits: {total_credits:.2f}")
                           # *** THE MOST IMPORTANT CHECK ***
                           if abs(total_debits - total_credits) < Decimal('0.01'):
                               print("      PASS: Total Debits EQUAL Total Credits (Trial Balance is balanced).")
                           else:
                               print(f"      FAIL: Total Debits DO NOT EQUAL Total Credits! Difference: {(total_debits - total_credits):.2f}")
                      else:
                           print(f"      FAIL: Total debit/credit values are not Decimal objects (Types: D={type(total_debits)}, C={type(total_credits)}).")
                 else:
                      print(f"      FAIL: 'totals' dictionary is malformed or missing keys.")

             else:
                  print("      FAIL: Dictionary is missing 'accounts' or 'totals' key.")
        elif trial_balance_data is None:
            print("   FAIL: generate_trial_balance returned None (check DB errors or function logic).")
        else:
            print(f"   FAIL: generate_trial_balance returned unexpected type: {type(trial_balance_data)}")


        print("\n--- Reporting & Master Data Function Tests Complete ---")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
    except sqlite3.Error as e:
        print(f"DATABASE ERROR: {e}")
        if conn:
            conn.rollback() # Rollback any pending transaction on DB error
    except Exception as e:
        print(f"UNEXPECTED ERROR during testing: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback for unexpected errors
    finally:
        if conn:
            # Optional: Clean up test data
            if new_account_id:
                 print("\n--- Cleaning up test data ---")
                 try:
                     print(f"   Deleting test GL account ID: {new_account_id}")
                     # Ensure no transactions were posted to it (would violate FK if GL entries existed)
                     # A safer cleanup might first check GeneralLedger or just mark as inactive
                     conn.execute("DELETE FROM ChartOfAccounts WHERE AccountID = ?", (new_account_id,))
                     conn.commit()
                     print("   Test GL account deleted.")
                 except sqlite3.Error as e:
                      print(f"   Error during cleanup: {e}")
                      print("   (Maybe transactions were posted to it? Or other FK issues?)")
                      conn.rollback()

            conn.close()
            print("\n--- Database Connection Closed ---")