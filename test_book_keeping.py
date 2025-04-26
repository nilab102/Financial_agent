import sqlite3
import datetime
from decimal import Decimal
import os

# Import the functions to be tested (assuming they are in fm_functions.py)
from utility_functions.utilities import (
    _execute_sql,
    _generate_gl_entries,
    record_simple_cash_receipt,
    record_simple_cash_disbursement,
    view_recent_gl_entries,
    post_simple_manual_journal_entry,
    view_bank_account_balance,
    view_gl_account_balance,
    record_bank_transfer
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
    conn = None # Initialize connection variable
    try:
        conn = get_db_connection()
        print(f"--- Connected to Database: {DATABASE_FILE} ---")
        print("\n--- Testing Bookkeeping & Recording Functions ---")

        # --- Test Data ---
        # Use IDs from the sample data provided in the SQL script
        test_employee_id = 9  # James Thomas (Accountant)
        test_bank_account_id_1 = 1 # Main Operating Account
        test_bank_account_id_2 = 2 # Payroll Account
        test_cash_gl_account_id_1 = 4 # Cash in Bank (linked conceptually to Bank 1)
        # Assuming Cash on Hand (ID 5) is conceptually linked to Bank 2 for transfer test
        test_cash_gl_account_id_2 = 5 # Cash on Hand
        test_interest_income_account_id = 43 # Interest Revenue
        test_office_supplies_expense_account_id = 53 # Office Supplies Expense
        test_prepaid_expense_account_id = 9 # Prepaid Expenses
        test_ap_account_id = 23 # Accounts Payable
        test_ar_account_id = 7  # Accounts Receivable

        today_str = datetime.date.today().isoformat()

        # == 1. Test record_simple_cash_receipt ==
        print("\n1. Testing record_simple_cash_receipt...")
        receipt_amount = Decimal('150.75')
        receipt_desc = "Received Bank Interest"
        initial_bank_balance = view_bank_account_balance(conn, test_bank_account_id_1)
        initial_cash_gl_balance = view_gl_account_balance(conn, test_cash_gl_account_id_1)
        initial_income_gl_balance = view_gl_account_balance(conn, test_interest_income_account_id)

        receipt_trans_id = record_simple_cash_receipt(
            conn, today_str, receipt_amount, receipt_desc,
            test_bank_account_id_1, test_cash_gl_account_id_1,
            test_interest_income_account_id, test_employee_id,
            reference="TEST-RCPT-001"
        )

        if receipt_trans_id:
            print(f"   PASS: Cash Receipt recorded with TransactionID: {receipt_trans_id}")
            # Verification
            final_bank_balance = view_bank_account_balance(conn, test_bank_account_id_1)
            final_cash_gl_balance = view_gl_account_balance(conn, test_cash_gl_account_id_1)
            final_income_gl_balance = view_gl_account_balance(conn, test_interest_income_account_id)

            # Check balances (handle potential None for initial balances if account was empty)
            expected_bank_balance = (initial_bank_balance or Decimal(0)) + receipt_amount
            expected_cash_gl_balance = (initial_cash_gl_balance or Decimal(0)) + receipt_amount
            expected_income_gl_balance = (initial_income_gl_balance or Decimal(0)) + receipt_amount # Income is credit balance

            if abs(final_bank_balance - expected_bank_balance) < Decimal('0.01'):
                 print("      PASS: Bank Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Bank Balance mismatch. Expected ~{expected_bank_balance}, Got {final_bank_balance}")

            if abs(final_cash_gl_balance - expected_cash_gl_balance) < Decimal('0.01'):
                 print("      PASS: Cash GL Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Cash GL Balance mismatch. Expected ~{expected_cash_gl_balance}, Got {final_cash_gl_balance}")

            if abs(final_income_gl_balance - expected_income_gl_balance) < Decimal('0.01'):
                 print("      PASS: Income GL Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Income GL Balance mismatch. Expected ~{expected_income_gl_balance}, Got {final_income_gl_balance}")

            # Check GL entries (basic check for existence)
            gl_entries = view_recent_gl_entries(conn, test_cash_gl_account_id_1, 5)
            if any(f"CashTransID:{receipt_trans_id}" in entry.get('Reference','') for entry in gl_entries):
                 print("      PASS: Found related GL entry for Cash account.")
            else:
                 print("      FAIL: Could not find related GL entry for Cash account.")

        else:
            print("   FAIL: record_simple_cash_receipt returned None.")

        # == 2. Test record_simple_cash_disbursement ==
        print("\n2. Testing record_simple_cash_disbursement...")
        disburse_amount = Decimal('45.50')
        disburse_desc = "Purchased Office Supplies (Cash)"
        initial_bank_balance = view_bank_account_balance(conn, test_bank_account_id_1)
        initial_cash_gl_balance = view_gl_account_balance(conn, test_cash_gl_account_id_1)
        initial_expense_gl_balance = view_gl_account_balance(conn, test_office_supplies_expense_account_id)

        disburse_trans_id = record_simple_cash_disbursement(
            conn, today_str, disburse_amount, disburse_desc,
            test_bank_account_id_1, test_cash_gl_account_id_1,
            test_office_supplies_expense_account_id, test_employee_id,
            reference="TEST-DISB-001"
        )

        if disburse_trans_id:
            print(f"   PASS: Cash Disbursement recorded with TransactionID: {disburse_trans_id}")
             # Verification
            final_bank_balance = view_bank_account_balance(conn, test_bank_account_id_1)
            final_cash_gl_balance = view_gl_account_balance(conn, test_cash_gl_account_id_1)
            final_expense_gl_balance = view_gl_account_balance(conn, test_office_supplies_expense_account_id)

            expected_bank_balance = (initial_bank_balance or Decimal(0)) - disburse_amount
            expected_cash_gl_balance = (initial_cash_gl_balance or Decimal(0)) - disburse_amount
            expected_expense_gl_balance = (initial_expense_gl_balance or Decimal(0)) + disburse_amount # Expense is debit balance

            if abs(final_bank_balance - expected_bank_balance) < Decimal('0.01'):
                 print("      PASS: Bank Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Bank Balance mismatch. Expected ~{expected_bank_balance}, Got {final_bank_balance}")

            if abs(final_cash_gl_balance - expected_cash_gl_balance) < Decimal('0.01'):
                 print("      PASS: Cash GL Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Cash GL Balance mismatch. Expected ~{expected_cash_gl_balance}, Got {final_cash_gl_balance}")

            if abs(final_expense_gl_balance - expected_expense_gl_balance) < Decimal('0.01'):
                 print("      PASS: Expense GL Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Expense GL Balance mismatch. Expected ~{expected_expense_gl_balance}, Got {final_expense_gl_balance}")

            # Check GL entries (basic check for existence)
            gl_entries = view_recent_gl_entries(conn, test_office_supplies_expense_account_id, 5)
            if any(f"CashTransID:{disburse_trans_id}" in entry.get('Reference','') for entry in gl_entries):
                 print("      PASS: Found related GL entry for Expense account.")
            else:
                 print("      FAIL: Could not find related GL entry for Expense account.")

        else:
            print("   FAIL: record_simple_cash_disbursement returned None.")

        # == 3. Test view_recent_gl_entries ==
        print("\n3. Testing view_recent_gl_entries...")
        print(f"   Fetching recent entries for Cash Account (ID: {test_cash_gl_account_id_1}):")
        recent_entries = view_recent_gl_entries(conn, test_cash_gl_account_id_1, limit=5)
        if recent_entries is not None:
            if isinstance(recent_entries, list):
                print(f"   PASS: Received list of {len(recent_entries)} entries.")
                for entry in recent_entries:
                     # Use .get() for safety in case a key is missing unexpectedly
                     print(f"      - ID: {entry.get('LedgerEntryID')}, Date: {entry.get('EntryDate')}, "
                           f"Desc: {entry.get('Description', '')[:30]}..., "
                           f"Debit: {entry.get('DebitAmount', 0):.2f}, Credit: {entry.get('CreditAmount', 0):.2f}, "
                           f"Ref: {entry.get('Reference')}")
            else:
                print(f"   FAIL: Expected a list, but got {type(recent_entries)}.")
        else:
            print("   FAIL: view_recent_gl_entries returned None (check for DB errors).")

        # == 4. Test post_simple_manual_journal_entry ==
        print("\n4. Testing post_simple_manual_journal_entry...")
        journal_amount = Decimal('500.00')
        journal_desc = "Record Prepaid Insurance"
        journal_ref = "TEST-JE-001"
        initial_prepaid_balance = view_gl_account_balance(conn, test_prepaid_expense_account_id)
        initial_cash_balance = view_gl_account_balance(conn, test_cash_gl_account_id_1) # Assuming paid from Bank 1 cash

        success = post_simple_manual_journal_entry(
            conn, today_str, journal_desc,
            test_prepaid_expense_account_id, # Debit Prepaid Expense
            test_cash_gl_account_id_1,       # Credit Cash
            journal_amount, test_employee_id, reference=journal_ref
        )

        if success:
            print("   PASS: Manual Journal Entry posted successfully.")
            # Verification
            final_prepaid_balance = view_gl_account_balance(conn, test_prepaid_expense_account_id)
            final_cash_balance = view_gl_account_balance(conn, test_cash_gl_account_id_1)

            expected_prepaid_balance = (initial_prepaid_balance or Decimal(0)) + journal_amount # Prepaid is Asset (Debit)
            expected_cash_balance = (initial_cash_balance or Decimal(0)) - journal_amount    # Cash is Asset (Debit)

            if abs(final_prepaid_balance - expected_prepaid_balance) < Decimal('0.01'):
                 print("      PASS: Debit Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Debit Account Balance mismatch. Expected ~{expected_prepaid_balance}, Got {final_prepaid_balance}")

            if abs(final_cash_balance - expected_cash_balance) < Decimal('0.01'):
                 print("      PASS: Credit Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Credit Account Balance mismatch. Expected ~{expected_cash_balance}, Got {final_cash_balance}")

            # Check GL entries directly
            gl_sql = "SELECT * FROM GeneralLedger WHERE Reference = ? ORDER BY LedgerEntryID"
            gl_entries = _execute_sql(conn, gl_sql, (journal_ref,), fetchall=True)
            if len(gl_entries) == 2:
                 print("      PASS: Found 2 GL entries for the journal reference.")
                 # Basic check for debit/credit accounts
                 debit_ok = any(e['AccountID'] == test_prepaid_expense_account_id and e['DebitAmount'] == journal_amount for e in gl_entries)
                 credit_ok = any(e['AccountID'] == test_cash_gl_account_id_1 and e['CreditAmount'] == journal_amount for e in gl_entries)
                 if debit_ok and credit_ok:
                     print("      PASS: GL entries have correct accounts and amounts.")
                 else:
                     print("      FAIL: GL entries have incorrect accounts or amounts.")
            else:
                 print(f"      FAIL: Expected 2 GL entries, found {len(gl_entries)}.")

        else:
            print("   FAIL: post_simple_manual_journal_entry returned False.")

        # == 5. Test view_bank_account_balance ==
        print("\n5. Testing view_bank_account_balance...")
        bank_id_to_check = test_bank_account_id_1
        balance = view_bank_account_balance(conn, bank_id_to_check)
        if balance is not None:
             print(f"   PASS: Retrieved balance for Bank Account ID {bank_id_to_check}: {balance:.2f}")
             # Cross-check with direct query (optional but good)
             direct_balance_row = _execute_sql(conn, "SELECT CurrentBalance FROM BankAccounts WHERE BankAccountID = ?", (bank_id_to_check,), fetchone=True)
             direct_balance = direct_balance_row['CurrentBalance'] if direct_balance_row else None
             if direct_balance is not None and abs(balance - direct_balance) < Decimal('0.01'):
                 print("      PASS: Function balance matches direct query.")
             elif direct_balance is not None:
                 print(f"      WARN: Function balance {balance} differs slightly from direct query {direct_balance} (check precision).")
             else:
                 print(f"      FAIL: Could not get balance via direct query for verification.")

        else:
             print(f"   FAIL: view_bank_account_balance returned None for Bank Account ID {bank_id_to_check}.")

        # == 6. Test view_gl_account_balance ==
        print("\n6. Testing view_gl_account_balance...")
        # Test a Debit balance account (Cash)
        cash_bal = view_gl_account_balance(conn, test_cash_gl_account_id_1)
        print(f"   Balance for Cash GL Account (ID {test_cash_gl_account_id_1}, Debit Type): {cash_bal:.2f}")
        # Test a Credit balance account (AP)
        ap_bal = view_gl_account_balance(conn, test_ap_account_id)
        print(f"   Balance for AP GL Account (ID {test_ap_account_id}, Credit Type): {ap_bal:.2f}")
        # Test an account likely with zero balance (add one if needed)
        # zero_bal_account_id = 99 # Example - ensure this exists or is added
        # zero_bal = view_gl_account_balance(conn, zero_bal_account_id)
        # print(f"   Balance for Zero Balance Account (ID {zero_bal_account_id}): {zero_bal:.2f}")
        print("   PASS: Function executed (manual verification of results needed based on all prior transactions).")

        # == 7. Test record_bank_transfer ==
        print("\n7. Testing record_bank_transfer...")
        transfer_amount = Decimal('10000.00')
        transfer_desc = "Fund Payroll Account"
        transfer_ref = "TEST-XFER-001"

        initial_bank1_bal = view_bank_account_balance(conn, test_bank_account_id_1)
        initial_bank2_bal = view_bank_account_balance(conn, test_bank_account_id_2)
        initial_cash1_gl_bal = view_gl_account_balance(conn, test_cash_gl_account_id_1)
        initial_cash2_gl_bal = view_gl_account_balance(conn, test_cash_gl_account_id_2)

        transfer_ids = record_bank_transfer(
            conn, today_str, transfer_amount,
            test_bank_account_id_1, test_cash_gl_account_id_1, # Source
            test_bank_account_id_2, test_cash_gl_account_id_2, # Target
            transfer_desc, test_employee_id, reference=transfer_ref
        )

        if transfer_ids and len(transfer_ids) == 2:
            source_trans_id, target_trans_id = transfer_ids
            print(f"   PASS: Bank Transfer recorded. Source TransID: {source_trans_id}, Target TransID: {target_trans_id}")
            # Verification
            final_bank1_bal = view_bank_account_balance(conn, test_bank_account_id_1)
            final_bank2_bal = view_bank_account_balance(conn, test_bank_account_id_2)
            final_cash1_gl_bal = view_gl_account_balance(conn, test_cash_gl_account_id_1)
            final_cash2_gl_bal = view_gl_account_balance(conn, test_cash_gl_account_id_2)

            expected_bank1_bal = (initial_bank1_bal or Decimal(0)) - transfer_amount
            expected_bank2_bal = (initial_bank2_bal or Decimal(0)) + transfer_amount
            expected_cash1_gl_bal = (initial_cash1_gl_bal or Decimal(0)) - transfer_amount
            expected_cash2_gl_bal = (initial_cash2_gl_bal or Decimal(0)) + transfer_amount

            if abs(final_bank1_bal - expected_bank1_bal) < Decimal('0.01'):
                 print("      PASS: Source Bank Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Source Bank Balance mismatch. Expected ~{expected_bank1_bal}, Got {final_bank1_bal}")
            if abs(final_bank2_bal - expected_bank2_bal) < Decimal('0.01'):
                 print("      PASS: Target Bank Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Target Bank Balance mismatch. Expected ~{expected_bank2_bal}, Got {final_bank2_bal}")
            if abs(final_cash1_gl_bal - expected_cash1_gl_bal) < Decimal('0.01'):
                 print("      PASS: Source Cash GL Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Source Cash GL Balance mismatch. Expected ~{expected_cash1_gl_bal}, Got {final_cash1_gl_bal}")
            if abs(final_cash2_gl_bal - expected_cash2_gl_bal) < Decimal('0.01'):
                 print("      PASS: Target Cash GL Account Balance updated correctly.")
            else:
                 print(f"      FAIL: Target Cash GL Balance mismatch. Expected ~{expected_cash2_gl_bal}, Got {final_cash2_gl_bal}")

            # Check GL entries
            gl_ref_expected = f"Transfer IDs:{source_trans_id},{target_trans_id}"
            gl_sql = "SELECT * FROM GeneralLedger WHERE Reference = ? ORDER BY LedgerEntryID"
            gl_entries = _execute_sql(conn, gl_sql, (gl_ref_expected,), fetchall=True)
            if len(gl_entries) == 2:
                 print("      PASS: Found 2 GL entries for the transfer reference.")
                 debit_ok = any(e['AccountID'] == test_cash_gl_account_id_2 and e['DebitAmount'] == transfer_amount for e in gl_entries)
                 credit_ok = any(e['AccountID'] == test_cash_gl_account_id_1 and e['CreditAmount'] == transfer_amount for e in gl_entries)
                 if debit_ok and credit_ok:
                     print("      PASS: GL entries have correct accounts and amounts.")
                 else:
                     print("      FAIL: GL entries have incorrect accounts or amounts.")
            else:
                 print(f"      FAIL: Expected 2 GL entries for ref '{gl_ref_expected}', found {len(gl_entries)}.")

        else:
            print("   FAIL: record_bank_transfer did not return expected tuple of IDs.")


        print("\n--- Bookkeeping Function Tests Complete ---")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
    except sqlite3.Error as e:
        print(f"DATABASE ERROR: {e}")
        # Optionally rollback if a transaction was manually started:
        # if conn:
        #     conn.rollback()
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
    finally:
        if conn:
            conn.close()
            print("\n--- Database Connection Closed ---")