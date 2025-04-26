import sqlite3
import datetime
from decimal import Decimal
import os
import time # For unique IDs

# Import the functions to be tested
from utility_functions.utilities  import (
    _execute_sql, # Keep helper if needed for direct checks
    _generate_gl_entries, # Keep helper if needed
    # AP Specific Functions
    create_vendor,
    view_vendor_details,
    update_vendor_contact_info,
    deactivate_vendor,
    enter_simple_vendor_bill,
    view_bill_details,
    record_simple_vendor_payment,
    list_open_vendor_bills,
    apply_full_payment_to_bill,
    get_total_accounts_payable,
    void_bill,
    # Helper view functions needed for verification
    view_bank_account_balance,
    view_gl_account_balance,
    view_recent_gl_entries
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
    # Use variables to store IDs created during the test for subsequent steps
    test_vendor_id = None
    test_bill_id_1 = None
    test_bill_id_2 = None # For voiding/total AP test
    test_payment_id = None

    try:
        conn = get_db_connection()
        print(f"--- Connected to Database: {DATABASE_FILE} ---")
        print("\n--- Testing Accounts Payable Functions ---")

        # --- Test Data ---
        test_employee_id = 17 # Daniel Hall (AP Specialist)
        # GL Accounts from Sample Data
        ap_account_id = 23      # Accounts Payable
        cash_account_id = 4     # Cash in Bank
        expense_account_id = 53 # Office Supplies Expense (Example)
        bank_account_id = 1       # Main Operating Account

        today_str = datetime.date.today().isoformat()
        due_date_str = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()

        # == 1. Test create_vendor ==
        print("\n1. Testing create_vendor...")
        vendor_name = f"Test AP Vendor {int(time.time())}" # Unique name
        vend_email = "test.ap@supplier.com"
        vend_phone = "555-TEST-AP"
        vend_terms = "Net 15 Test"

        test_vendor_id = create_vendor(
            conn, vendor_name, "Supplier Contact", vend_email, vend_phone,
            "1 Supply Address", "TX-TEST-AP", vend_terms
        )

        if test_vendor_id and isinstance(test_vendor_id, int):
            print(f"   PASS: Vendor created with VendorID: {test_vendor_id}")
            # Optional: Immediate verification
            details = view_vendor_details(conn, test_vendor_id)
            if details and details['VendorName'] == vendor_name and details['Email'] == vend_email:
                 print("      PASS: Vendor details verified immediately.")
            elif details:
                 print("      WARN: Vendor details mismatch after creation.")
            else:
                 print("      FAIL: Could not retrieve vendor details after creation.")
        else:
            print(f"   FAIL: create_vendor returned unexpected value: {test_vendor_id}. Exiting subsequent tests.")
            exit() # Exit if vendor creation fails


        # == 2. Test view_vendor_details ==
        print("\n2. Testing view_vendor_details...")
        details = view_vendor_details(conn, test_vendor_id)
        if details and isinstance(details, dict) and details['VendorID'] == test_vendor_id:
             print(f"   PASS: Retrieved details for VendorID {test_vendor_id}: Name = {details['VendorName']}")
        elif details:
             print(f"   FAIL: Retrieved details, but VendorID mismatch or wrong type.")
        else:
             print(f"   FAIL: view_vendor_details returned None for VendorID {test_vendor_id}.")


        # == 3. Test update_vendor_contact_info ==
        print("\n3. Testing update_vendor_contact_info...")
        new_contact = "Updated Contact Person"
        new_vend_phone = "555-UPD-AP0"
        update_success = update_vendor_contact_info(conn, test_vendor_id, contact_person=new_contact, phone=new_vend_phone)

        if update_success:
            print("   PASS: update_vendor_contact_info returned True.")
            # Verification
            details = view_vendor_details(conn, test_vendor_id)
            if details and details['ContactPerson'] == new_contact and details['Phone'] == new_vend_phone:
                 print("      PASS: Vendor contact info updated correctly in database.")
            elif details:
                 print("      FAIL: Vendor contact info did not update correctly in database.")
            else:
                 print("      FAIL: Could not retrieve vendor details after update attempt.")
        else:
             print("   FAIL: update_vendor_contact_info returned False.")


        # == 4. Test enter_simple_vendor_bill ==
        print("\n4. Testing enter_simple_vendor_bill...")
        bill_qty = Decimal('5.0')
        bill_price = Decimal('25.50')
        bill_tax_rate = Decimal('0.0') # No tax for simplicity here
        item_desc = "Test AP Supplies Purchase"
        bill_num_1 = f"BILL-TEST-AP-{int(time.time())}"

        # Calculate expected total for verification
        subtotal = bill_qty * bill_price
        tax_amount = subtotal * (bill_tax_rate / 100)
        expected_total = subtotal + tax_amount

        initial_ap_balance = view_gl_account_balance(conn, ap_account_id)
        initial_expense_balance = view_gl_account_balance(conn, expense_account_id)

        test_bill_id_1 = enter_simple_vendor_bill(
            conn, test_vendor_id, bill_num_1, today_str, due_date_str,
            item_desc, bill_qty, bill_price,
            expense_account_id, ap_account_id, test_employee_id,
            tax_rate=bill_tax_rate
        )

        if test_bill_id_1 and isinstance(test_bill_id_1, int):
            print(f"   PASS: Bill entered with BillID: {test_bill_id_1}")
            # Verification
            bill_details = view_bill_details(conn, test_bill_id_1)
            final_ap_balance = view_gl_account_balance(conn, ap_account_id)
            final_expense_balance = view_gl_account_balance(conn, expense_account_id)

            if not bill_details:
                print("      FAIL: Could not retrieve bill details after creation.")
            else:
                # Check amounts
                if abs(bill_details['TotalAmount'] - expected_total) < Decimal('0.01'):
                     print(f"      PASS: Bill TotalAmount ({bill_details['TotalAmount']:.2f}) matches expected ({expected_total:.2f}).")
                else:
                     print(f"      FAIL: Bill TotalAmount ({bill_details['TotalAmount']:.2f}) MISMATCH expected ({expected_total:.2f}).")
                # Check generated Balance column
                if abs(bill_details['Balance'] - expected_total) < Decimal('0.01'):
                    print(f"      PASS: Initial Bill Balance ({bill_details['Balance']:.2f}) matches TotalAmount.")
                else:
                    print(f"      FAIL: Initial Bill Balance ({bill_details['Balance']:.2f}) MISMATCH TotalAmount ({expected_total:.2f}).")
                if bill_details['Status'] == 'Received':
                     print("      PASS: Bill Status is 'Received'.")
                else:
                     print(f"      FAIL: Bill Status is '{bill_details['Status']}', expected 'Received'.")
                if len(bill_details.get('items', [])) == 1:
                     print("      PASS: Bill has 1 line item.")
                else:
                     print(f"      FAIL: Bill has {len(bill_details.get('items', []))} items, expected 1.")

            # Check GL Balances
            expected_ap_balance = initial_ap_balance + expected_total # AP is Credit
            expected_expense_balance = initial_expense_balance + expected_total # Expense is Debit
            if abs(final_ap_balance - expected_ap_balance) < Decimal('0.01'):
                 print("      PASS: AP GL balance updated correctly.")
            else:
                 print(f"      FAIL: AP GL balance mismatch. Expected ~{expected_ap_balance:.2f}, Got {final_ap_balance:.2f}")
            if abs(final_expense_balance - expected_expense_balance) < Decimal('0.01'):
                 print("      PASS: Expense GL balance updated correctly.")
            else:
                 print(f"      FAIL: Expense GL balance mismatch. Expected ~{expected_expense_balance:.2f}, Got {final_expense_balance:.2f}")

             # Check GL entries exist
            gl_entries = view_recent_gl_entries(conn, ap_account_id, 5)
            if any(f"BillID:{test_bill_id_1}" in entry.get('Reference','') for entry in gl_entries):
                 print("      PASS: Found related GL entry for AP account.")
            else:
                 print("      FAIL: Could not find related GL entry for AP account.")

        else:
            print(f"   FAIL: enter_simple_vendor_bill returned unexpected value: {test_bill_id_1}")
            test_bill_id_1 = None # Ensure it's None if creation failed


        # == 5. Test view_bill_details ==
        print("\n5. Testing view_bill_details...")
        if test_bill_id_1:
            details = view_bill_details(conn, test_bill_id_1)
            if details and isinstance(details, dict) and details['BillID'] == test_bill_id_1:
                 print(f"   PASS: Retrieved details for BillID {test_bill_id_1}.")
                 print(f"      - Vendor: {details['VendorName']}, Total: {details['TotalAmount']:.2f}, Status: {details['Status']}")
                 if details.get('items'):
                     item = details['items'][0]
                     print(f"      - Item 1 Desc: {item.get('Description', 'N/A')[:30]}..., Qty: {item.get('Quantity')}, Price: {item.get('UnitPrice')}")
                     # Check generated columns in item view
                     calc_line_total = Decimal(item.get('Quantity',0)) * Decimal(item.get('UnitPrice',0)) * (1 + Decimal(item.get('TaxRate',0)) / 100)
                     if abs(Decimal(item.get('LineTotal', -1)) - calc_line_total) < Decimal('0.01'):
                         print(f"      - Item 1 LineTotal ({item.get('LineTotal'):.2f}) matches calculation.")
                     else:
                         print(f"      - WARN: Item 1 LineTotal ({item.get('LineTotal'):.2f}) MISMATCH calculation ({calc_line_total:.2f}).")
                 else:
                     print("      - WARN: No items found in details.")
            elif details:
                 print(f"   FAIL: Retrieved details, but BillID mismatch or wrong type.")
            else:
                 print(f"   FAIL: view_bill_details returned None for BillID {test_bill_id_1}.")
        else:
             print("   SKIP: Cannot test view_bill_details as bill entry failed.")


        # == 6. Test record_simple_vendor_payment ==
        print("\n6. Testing record_simple_vendor_payment...")
        payment_amount = expected_total # Assume payment matches bill exactly for simplicity
        payment_method = "Test Check 123"
        payment_ref = f"TEST-VPay-{int(time.time())}"

        initial_bank_balance = view_bank_account_balance(conn, bank_account_id)
        initial_cash_gl_balance = view_gl_account_balance(conn, cash_account_id)
        initial_ap_balance = view_gl_account_balance(conn, ap_account_id) # Re-fetch AP balance before payment

        test_payment_id = record_simple_vendor_payment(
            conn, test_vendor_id, today_str, payment_amount,
            payment_method, bank_account_id, cash_account_id,
            ap_account_id, test_employee_id, reference=payment_ref
        )

        if test_payment_id and isinstance(test_payment_id, int):
             print(f"   PASS: Vendor Payment recorded with PaymentID: {test_payment_id}")
             # Verification
             final_bank_balance = view_bank_account_balance(conn, bank_account_id)
             final_cash_gl_balance = view_gl_account_balance(conn, cash_account_id)
             final_ap_balance = view_gl_account_balance(conn, ap_account_id)

             expected_bank_balance = initial_bank_balance - payment_amount
             expected_cash_gl_balance = initial_cash_gl_balance - payment_amount # Cash is Debit, decreases with Credit
             expected_ap_balance = initial_ap_balance - payment_amount # AP is Credit, decreases with Debit

             if abs(final_bank_balance - expected_bank_balance) < Decimal('0.01'):
                 print("      PASS: Bank Account balance updated correctly.")
             else:
                 print(f"      FAIL: Bank Account balance mismatch. Expected ~{expected_bank_balance:.2f}, Got {final_bank_balance:.2f}")
             if abs(final_cash_gl_balance - expected_cash_gl_balance) < Decimal('0.01'):
                 print("      PASS: Cash GL balance updated correctly.")
             else:
                 print(f"      FAIL: Cash GL balance mismatch. Expected ~{expected_cash_gl_balance:.2f}, Got {final_cash_gl_balance:.2f}")
             if abs(final_ap_balance - expected_ap_balance) < Decimal('0.01'):
                 print("      PASS: AP GL balance updated correctly.")
             else:
                 print(f"      FAIL: AP GL balance mismatch. Expected ~{expected_ap_balance:.2f}, Got {final_ap_balance:.2f}")

             # Check GL entries
             gl_entries = view_recent_gl_entries(conn, ap_account_id, 5) # Check AP side
             if any(f"VendPmtID:{test_payment_id}" in entry.get('Reference','') for entry in gl_entries):
                  print("      PASS: Found related GL entry for AP account.")
             else:
                  print("      FAIL: Could not find related GL entry for AP account.")

        else:
            print(f"   FAIL: record_simple_vendor_payment returned unexpected value: {test_payment_id}")
            test_payment_id = None


        # == 7. Test list_open_vendor_bills ==
        print("\n7. Testing list_open_vendor_bills...")
        open_bills = list_open_vendor_bills(conn, test_vendor_id)

        if open_bills is not None and isinstance(open_bills, list):
            print(f"   PASS: Retrieved list of {len(open_bills)} open bills for vendor {test_vendor_id}.")
            # Check if the bill entered earlier is listed (it shouldn't be paid yet)
            found_bill = False
            for bill in open_bills:
                print(f"      - Open Bill: ID {bill['BillID']}, Num {bill['BillNumber']}, Bal {bill['Balance']:.2f}")
                if test_bill_id_1 and bill['BillID'] == test_bill_id_1:
                    found_bill = True
            if test_bill_id_1 and found_bill:
                print(f"      PASS: Bill {test_bill_id_1} is correctly listed as open (before payment application).")
            elif test_bill_id_1:
                print(f"      FAIL: Bill {test_bill_id_1} was NOT found in the open list (it should be).")
            elif not test_bill_id_1:
                 print(f"      INFO: Cannot check for specific bill as its entry failed.")

        elif open_bills is None:
             print("   FAIL: list_open_vendor_bills returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected a list, got {type(open_bills)}.")


        # == 8. Test apply_full_payment_to_bill ==
        print("\n8. Testing apply_full_payment_to_bill...")
        if test_bill_id_1 and test_payment_id:
            apply_success = apply_full_payment_to_bill(conn, test_payment_id, test_bill_id_1)
            if apply_success:
                print(f"   PASS: apply_full_payment_to_bill returned True for Payment {test_payment_id} to Bill {test_bill_id_1}.")
                # Verification
                details = view_bill_details(conn, test_bill_id_1)
                if details and details['Status'] == 'Paid' and abs(details['Balance']) < Decimal('0.01'): # Use abs() for float safety
                     print(f"      PASS: Bill {test_bill_id_1} status is now 'Paid' and Balance is 0.")
                elif details:
                     print(f"      FAIL: Bill {test_bill_id_1} status/balance incorrect after applying payment. Status='{details['Status']}', Balance={details['Balance']:.2f}")
                else:
                     print(f"      FAIL: Could not retrieve bill details after applying payment.")

                # Check open bills again - it should be gone
                open_bills_after = list_open_vendor_bills(conn, test_vendor_id)
                found_bill_after = False
                if isinstance(open_bills_after, list):
                     for bill in open_bills_after:
                         if bill['BillID'] == test_bill_id_1:
                             found_bill_after = True
                             break
                     if not found_bill_after:
                         print(f"      PASS: Bill {test_bill_id_1} is correctly REMOVED from open list.")
                     else:
                         print(f"      FAIL: Bill {test_bill_id_1} is STILL in open list after payment application.")
                else:
                     print("      WARN: Could not retrieve open bills list after payment for verification.")

            else:
                 print(f"   FAIL: apply_full_payment_to_bill returned False for Payment {test_payment_id} to Bill {test_bill_id_1}.")
        elif not test_bill_id_1:
             print("   SKIP: Cannot test payment application as bill entry failed.")
        elif not test_payment_id:
             print("   SKIP: Cannot test payment application as payment recording failed.")


        # == 9. Test get_total_accounts_payable ==
        print("\n9. Testing get_total_accounts_payable...")
        # Create another small bill for this vendor that remains unpaid
        bill_num_2 = f"BILL-TEST-AP2-{int(time.time())}"
        unpaid_amount = Decimal('78.90')
        test_bill_id_2 = enter_simple_vendor_bill(
            conn, test_vendor_id, bill_num_2, today_str, due_date_str, "Second Test AP Item",
            Decimal('1.0'), unpaid_amount, expense_account_id, ap_account_id,
            test_employee_id, tax_rate=Decimal('0.0')
        )

        if test_bill_id_2:
             print(f"   (Created second unpaid bill ID: {test_bill_id_2} with amount {unpaid_amount})")
        else:
             print("   (Failed to create second bill for total AP test)")

        # Calculate expected total AP based *only* on open bills for our test vendor
        expected_total_ap_test_vendor = Decimal('0.00')
        open_bills_final = list_open_vendor_bills(conn, test_vendor_id)
        if isinstance(open_bills_final, list):
            for bill in open_bills_final:
                expected_total_ap_test_vendor += bill['Balance']

        # Get the global total AP from the function
        total_ap = get_total_accounts_payable(conn)

        print(f"   Expected AP for test vendor (based on open list): {expected_total_ap_test_vendor:.2f}")
        print(f"   Global AP reported by function: {total_ap:.2f}")
        if total_ap is not None and isinstance(total_ap, Decimal):
             print(f"   PASS: get_total_accounts_payable returned a Decimal value.")
             # Check if global AP includes at least our test vendor's unpaid amount
             if test_bill_id_2 and total_ap >= expected_total_ap_test_vendor - Decimal('0.01'):
                 print("      INFO: Global AP includes at least the amount of the unpaid test vendor's bills.")
             elif test_bill_id_2:
                  print("      WARN: Global AP seems lower than expected based on unpaid test vendor's bills.")
        else:
            print(f"   FAIL: get_total_accounts_payable returned {total_ap} (type: {type(total_ap)}).")


        # == 10. Test void_bill ==
        print("\n10. Testing void_bill...")
        if test_bill_id_2: # Use the second bill which hasn't been paid
             initial_ap_balance_void = view_gl_account_balance(conn, ap_account_id)
             initial_expense_balance_void = view_gl_account_balance(conn, expense_account_id)
             bill_details_before_void = view_bill_details(conn, test_bill_id_2)
             amount_to_reverse = bill_details_before_void['TotalAmount'] if bill_details_before_void else Decimal('0.00')

             print(f"   Attempting to void Bill {test_bill_id_2} with amount {amount_to_reverse:.2f}")
             void_success = void_bill(conn, test_bill_id_2, ap_account_id, expense_account_id, test_employee_id)

             if void_success:
                 print(f"   PASS: void_bill returned True for Bill {test_bill_id_2}.")
                 # Verification
                 details = view_bill_details(conn, test_bill_id_2)
                 final_ap_balance_void = view_gl_account_balance(conn, ap_account_id)
                 final_expense_balance_void = view_gl_account_balance(conn, expense_account_id)

                 if details and details['Status'] == 'Cancelled':
                      print(f"      PASS: Bill {test_bill_id_2} status is now 'Cancelled'.")
                 elif details:
                      print(f"      FAIL: Bill {test_bill_id_2} status incorrect after void. Status='{details['Status']}'")
                 else:
                      print(f"      FAIL: Could not retrieve bill details after voiding.")

                 # Check GL reversal
                 expected_ap_after_void = initial_ap_balance_void - amount_to_reverse # Debit decreases AP(Credit)
                 expected_exp_after_void = initial_expense_balance_void - amount_to_reverse # Credit decreases Expense(Debit)
                 if abs(final_ap_balance_void - expected_ap_after_void) < Decimal('0.01'):
                      print("      PASS: AP GL balance reversed correctly.")
                 else:
                      print(f"      FAIL: AP GL balance mismatch after void. Expected ~{expected_ap_after_void:.2f}, Got {final_ap_balance_void:.2f}")
                 if abs(final_expense_balance_void - expected_exp_after_void) < Decimal('0.01'):
                      print("      PASS: Expense GL balance reversed correctly.")
                 else:
                      print(f"      FAIL: Expense GL balance mismatch after void. Expected ~{expected_exp_after_void:.2f}, Got {final_expense_balance_void:.2f}")

                 # Check GL Entries
                 gl_entries = view_recent_gl_entries(conn, ap_account_id, 5)
                 if any(f"VoidBillID:{test_bill_id_2}" in entry.get('Reference','') for entry in gl_entries):
                      print("      PASS: Found related reversing GL entry for AP account.")
                 else:
                      print("      FAIL: Could not find related reversing GL entry for AP account.")

             else:
                 print(f"   FAIL: void_bill returned False for unpaid Bill {test_bill_id_2}.")
        else:
            print("   SKIP: Cannot test void_bill as second bill entry failed.")

        # Try to void the first (paid) bill - should fail
        if test_bill_id_1:
             print(f"   Attempting to void PAID Bill {test_bill_id_1} (should fail)...")
             void_paid_success = void_bill(conn, test_bill_id_1, ap_account_id, expense_account_id, test_employee_id)
             if not void_paid_success:
                 print("   PASS: void_bill correctly returned False for a paid bill.")
             else:
                 print(f"   FAIL: void_bill incorrectly returned TRUE for a paid bill!")


        # == 11. Test deactivate_vendor ==
        print("\n11. Testing deactivate_vendor...")
        deactivate_success = deactivate_vendor(conn, test_vendor_id)
        if deactivate_success:
            print(f"   PASS: deactivate_vendor returned True for VendorID {test_vendor_id}.")
            # Verification
            details = view_vendor_details(conn, test_vendor_id)
            if details and details['IsActive'] == 0:
                print("      PASS: Vendor IsActive flag is now 0.")
            elif details:
                print("      FAIL: Vendor IsActive flag is not 0 after deactivation.")
            else:
                 print("      FAIL: Could not retrieve vendor details after deactivation.")
        else:
             print(f"   FAIL: deactivate_vendor returned False for VendorID {test_vendor_id}.")


        print("\n--- Accounts Payable Function Tests Complete ---")

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
            # Optional: Clean up test data (delete vendor, bills, payments)
            # print("\n--- Cleaning up test data ---")
            # try:
            #     # Note: Order matters due to foreign keys! Payments/Items before Headers.
            #     if test_payment_id: conn.execute("DELETE FROM VendorPayments WHERE PaymentID = ?", (test_payment_id,))
            #     if test_bill_id_1: conn.execute("DELETE FROM BillItems WHERE BillID = ?", (test_bill_id_1,))
            #     if test_bill_id_2: conn.execute("DELETE FROM BillItems WHERE BillID = ?", (test_bill_id_2,))
            #     if test_bill_id_1: conn.execute("DELETE FROM Bills WHERE BillID = ?", (test_bill_id_1,))
            #     if test_bill_id_2: conn.execute("DELETE FROM Bills WHERE BillID = ?", (test_bill_id_2,))
            #     if test_vendor_id: conn.execute("DELETE FROM Vendors WHERE VendorID = ?", (test_vendor_id,))
            #     # Add deletes for test GL entries if desired
            #     conn.commit()
            #     print("   Test data cleanup attempted.")
            # except sqlite3.Error as e:
            #      print(f"   Error during cleanup: {e}")
            #      conn.rollback()

            conn.close()
            print("\n--- Database Connection Closed ---")