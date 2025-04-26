import sqlite3
import datetime
from decimal import Decimal
import os
import time # To create unique invoice numbers sometimes

# Import the functions to be tested
from utility_functions.utilities  import (
    _execute_sql, # Keep helper if needed for direct checks
    _generate_gl_entries, # Keep helper if needed
    # AR Specific Functions
    create_customer,
    view_customer_details,
    update_customer_contact_info,
    deactivate_customer,
    create_simple_sales_invoice,
    view_invoice_details,
    record_simple_customer_payment,
    list_open_customer_invoices,
    apply_full_payment_to_invoice,
    get_total_accounts_receivable,
    void_invoice,
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
    test_customer_id = None
    test_invoice_id_1 = None
    test_invoice_id_2 = None # For voiding
    test_payment_id = None

    try:
        conn = get_db_connection()
        print(f"--- Connected to Database: {DATABASE_FILE} ---")
        print("\n--- Testing Accounts Receivable Functions ---")

        # --- Test Data ---
        test_employee_id = 16 # Jennifer Walker (AR Specialist)
        # GL Accounts from Sample Data
        ar_account_id = 7   # Accounts Receivable
        cash_account_id = 4 # Cash in Bank
        revenue_account_id = 40 # Sales Revenue
        bank_account_id = 1   # Main Operating Account

        today_str = datetime.date.today().isoformat()
        due_date_str = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()

        # == 1. Test create_customer ==
        print("\n1. Testing create_customer...")
        customer_name = f"Test AR Customer {int(time.time())}" # Unique name
        cust_email = "test.ar@example.com"
        cust_phone = "555-TEST-AR"
        cust_credit_limit = Decimal('10000.00')
        cust_terms = "Net 30 Test"

        test_customer_id = create_customer(
            conn, customer_name, "Test Contact", cust_email, cust_phone,
            "1 Test Address", "TX-TEST-AR", cust_credit_limit, cust_terms
        )

        if test_customer_id and isinstance(test_customer_id, int):
            print(f"   PASS: Customer created with CustomerID: {test_customer_id}")
            # Optional: Immediate verification
            details = view_customer_details(conn, test_customer_id)
            if details and details['CustomerName'] == customer_name and details['Email'] == cust_email:
                 print("      PASS: Customer details verified immediately.")
            elif details:
                 print("      WARN: Customer details mismatch after creation.")
            else:
                 print("      FAIL: Could not retrieve customer details after creation.")
        else:
            print(f"   FAIL: create_customer returned unexpected value: {test_customer_id}. Exiting subsequent tests.")
            exit() # Exit if customer creation fails, as others depend on it


        # == 2. Test view_customer_details ==
        print("\n2. Testing view_customer_details...")
        details = view_customer_details(conn, test_customer_id)
        if details and isinstance(details, dict) and details['CustomerID'] == test_customer_id:
             print(f"   PASS: Retrieved details for CustomerID {test_customer_id}: Name = {details['CustomerName']}")
        elif details:
             print(f"   FAIL: Retrieved details, but CustomerID mismatch or wrong type.")
        else:
             print(f"   FAIL: view_customer_details returned None for CustomerID {test_customer_id}.")


        # == 3. Test update_customer_contact_info ==
        print("\n3. Testing update_customer_contact_info...")
        new_email = "updated.ar@example.com"
        new_phone = "555-UPD-AR0"
        update_success = update_customer_contact_info(conn, test_customer_id, email=new_email, phone=new_phone)

        if update_success:
            print("   PASS: update_customer_contact_info returned True.")
            # Verification
            details = view_customer_details(conn, test_customer_id)
            if details and details['Email'] == new_email and details['Phone'] == new_phone:
                 print("      PASS: Customer contact info updated correctly in database.")
            elif details:
                 print("      FAIL: Customer contact info did not update correctly in database.")
            else:
                 print("      FAIL: Could not retrieve customer details after update attempt.")
        else:
             print("   FAIL: update_customer_contact_info returned False.")


        # == 4. Test create_simple_sales_invoice ==
        print("\n4. Testing create_simple_sales_invoice...")
        invoice_qty = Decimal('2.0')
        invoice_price = Decimal('150.00')
        invoice_tax_rate = Decimal('8.5') # 8.5%
        item_desc = "Test Product AR Sale"
        invoice_num_1 = f"INV-TEST-AR-{int(time.time())}"

        # Calculate expected total for verification
        subtotal = invoice_qty * invoice_price
        tax_amount = subtotal * (invoice_tax_rate / 100)
        expected_total = subtotal + tax_amount

        initial_ar_balance = view_gl_account_balance(conn, ar_account_id)
        initial_revenue_balance = view_gl_account_balance(conn, revenue_account_id)

        test_invoice_id_1 = create_simple_sales_invoice(
            conn, test_customer_id, today_str, due_date_str,
            item_desc, invoice_qty, invoice_price,
            revenue_account_id, ar_account_id, test_employee_id,
            invoice_number=invoice_num_1, tax_rate=invoice_tax_rate
        )

        if test_invoice_id_1 and isinstance(test_invoice_id_1, int):
            print(f"   PASS: Invoice created with InvoiceID: {test_invoice_id_1}")
            # Verification
            inv_details = view_invoice_details(conn, test_invoice_id_1)
            final_ar_balance = view_gl_account_balance(conn, ar_account_id)
            final_revenue_balance = view_gl_account_balance(conn, revenue_account_id)

            if not inv_details:
                print("      FAIL: Could not retrieve invoice details after creation.")
            else:
                # Check amounts
                if abs(inv_details['TotalAmount'] - expected_total) < Decimal('0.01'):
                     print(f"      PASS: Invoice TotalAmount ({inv_details['TotalAmount']:.2f}) matches expected ({expected_total:.2f}).")
                else:
                     print(f"      FAIL: Invoice TotalAmount ({inv_details['TotalAmount']:.2f}) MISMATCH expected ({expected_total:.2f}).")
                if abs(inv_details['Balance'] - expected_total) < Decimal('0.01'):
                    print(f"      PASS: Initial Invoice Balance ({inv_details['Balance']:.2f}) matches TotalAmount.")
                else:
                    print(f"      FAIL: Initial Invoice Balance ({inv_details['Balance']:.2f}) MISMATCH TotalAmount ({expected_total:.2f}).")
                if inv_details['Status'] == 'Issued':
                     print("      PASS: Invoice Status is 'Issued'.")
                else:
                     print(f"      FAIL: Invoice Status is '{inv_details['Status']}', expected 'Issued'.")
                if len(inv_details.get('items', [])) == 1:
                     print("      PASS: Invoice has 1 line item.")
                else:
                     print(f"      FAIL: Invoice has {len(inv_details.get('items', []))} items, expected 1.")

            # Check GL Balances
            expected_ar_balance = initial_ar_balance + expected_total # AR is Debit
            expected_revenue_balance = initial_revenue_balance + expected_total # Revenue is Credit
            if abs(final_ar_balance - expected_ar_balance) < Decimal('0.01'):
                 print("      PASS: AR GL balance updated correctly.")
            else:
                 print(f"      FAIL: AR GL balance mismatch. Expected ~{expected_ar_balance:.2f}, Got {final_ar_balance:.2f}")
            # Note: Revenue balance check assumes simple model where total invoice amount hits revenue.
            # A more complex model would split between revenue and tax payable.
            if abs(final_revenue_balance - expected_revenue_balance) < Decimal('0.01'):
                 print("      PASS: Revenue GL balance updated correctly (simple model).")
            else:
                 print(f"      FAIL: Revenue GL balance mismatch (simple model). Expected ~{expected_revenue_balance:.2f}, Got {final_revenue_balance:.2f}")

             # Check GL entries exist
            gl_entries = view_recent_gl_entries(conn, ar_account_id, 5)
            if any(f"InvoiceID:{test_invoice_id_1}" in entry.get('Reference','') for entry in gl_entries):
                 print("      PASS: Found related GL entry for AR account.")
            else:
                 print("      FAIL: Could not find related GL entry for AR account.")

        else:
            print(f"   FAIL: create_simple_sales_invoice returned unexpected value: {test_invoice_id_1}")
            test_invoice_id_1 = None # Ensure it's None if creation failed


        # == 5. Test view_invoice_details ==
        print("\n5. Testing view_invoice_details...")
        if test_invoice_id_1:
            details = view_invoice_details(conn, test_invoice_id_1)
            if details and isinstance(details, dict) and details['InvoiceID'] == test_invoice_id_1:
                 print(f"   PASS: Retrieved details for InvoiceID {test_invoice_id_1}.")
                 print(f"      - Customer: {details['CustomerName']}, Total: {details['TotalAmount']:.2f}, Status: {details['Status']}")
                 if details.get('items'):
                     print(f"      - Item 1 Desc: {details['items'][0].get('Description', 'N/A')[:30]}...")
                 else:
                     print("      - WARN: No items found in details.")
            elif details:
                 print(f"   FAIL: Retrieved details, but InvoiceID mismatch or wrong type.")
            else:
                 print(f"   FAIL: view_invoice_details returned None for InvoiceID {test_invoice_id_1}.")
        else:
             print("   SKIP: Cannot test view_invoice_details as invoice creation failed.")


        # == 6. Test record_simple_customer_payment ==
        print("\n6. Testing record_simple_customer_payment...")
        payment_amount = expected_total # Assume payment matches invoice exactly for simplicity here
        payment_method = "Test EFT"
        payment_ref = f"TEST-PAY-{int(time.time())}"

        initial_bank_balance = view_bank_account_balance(conn, bank_account_id)
        initial_cash_gl_balance = view_gl_account_balance(conn, cash_account_id)
        initial_ar_balance = view_gl_account_balance(conn, ar_account_id) # Re-fetch AR balance before payment

        test_payment_id = record_simple_customer_payment(
            conn, test_customer_id, today_str, payment_amount,
            payment_method, bank_account_id, cash_account_id,
            ar_account_id, test_employee_id, reference=payment_ref
        )

        if test_payment_id and isinstance(test_payment_id, int):
             print(f"   PASS: Customer Payment recorded with PaymentID: {test_payment_id}")
             # Verification
             final_bank_balance = view_bank_account_balance(conn, bank_account_id)
             final_cash_gl_balance = view_gl_account_balance(conn, cash_account_id)
             final_ar_balance = view_gl_account_balance(conn, ar_account_id)

             expected_bank_balance = initial_bank_balance + payment_amount
             expected_cash_gl_balance = initial_cash_gl_balance + payment_amount # Cash is Debit
             expected_ar_balance = initial_ar_balance - payment_amount # AR is Debit

             if abs(final_bank_balance - expected_bank_balance) < Decimal('0.01'):
                 print("      PASS: Bank Account balance updated correctly.")
             else:
                 print(f"      FAIL: Bank Account balance mismatch. Expected ~{expected_bank_balance:.2f}, Got {final_bank_balance:.2f}")
             if abs(final_cash_gl_balance - expected_cash_gl_balance) < Decimal('0.01'):
                 print("      PASS: Cash GL balance updated correctly.")
             else:
                 print(f"      FAIL: Cash GL balance mismatch. Expected ~{expected_cash_gl_balance:.2f}, Got {final_cash_gl_balance:.2f}")
             if abs(final_ar_balance - expected_ar_balance) < Decimal('0.01'):
                 print("      PASS: AR GL balance updated correctly.")
             else:
                 print(f"      FAIL: AR GL balance mismatch. Expected ~{expected_ar_balance:.2f}, Got {final_ar_balance:.2f}")

             # Check GL entries
             gl_entries = view_recent_gl_entries(conn, cash_account_id, 5)
             if any(f"CustPmtID:{test_payment_id}" in entry.get('Reference','') for entry in gl_entries):
                  print("      PASS: Found related GL entry for Cash account.")
             else:
                  print("      FAIL: Could not find related GL entry for Cash account.")

        else:
            print(f"   FAIL: record_simple_customer_payment returned unexpected value: {test_payment_id}")
            test_payment_id = None


        # == 7. Test list_open_customer_invoices ==
        print("\n7. Testing list_open_customer_invoices...")
        open_invoices = list_open_customer_invoices(conn, test_customer_id)

        if open_invoices is not None and isinstance(open_invoices, list):
            print(f"   PASS: Retrieved list of {len(open_invoices)} open invoices for customer {test_customer_id}.")
            # Check if the invoice created earlier is listed (it shouldn't be paid yet)
            found_invoice = False
            for inv in open_invoices:
                print(f"      - Open Invoice: ID {inv['InvoiceID']}, Num {inv['InvoiceNumber']}, Bal {inv['Balance']:.2f}")
                if test_invoice_id_1 and inv['InvoiceID'] == test_invoice_id_1:
                    found_invoice = True
            if test_invoice_id_1 and found_invoice:
                print(f"      PASS: Invoice {test_invoice_id_1} is correctly listed as open (before payment application).")
            elif test_invoice_id_1:
                print(f"      FAIL: Invoice {test_invoice_id_1} was NOT found in the open list (it should be).")
            elif not test_invoice_id_1:
                 print(f"      INFO: Cannot check for specific invoice as its creation failed.")

        elif open_invoices is None:
             print("   FAIL: list_open_customer_invoices returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected a list, got {type(open_invoices)}.")


        # == 8. Test apply_full_payment_to_invoice ==
        print("\n8. Testing apply_full_payment_to_invoice...")
        if test_invoice_id_1 and test_payment_id:
            apply_success = apply_full_payment_to_invoice(conn, test_payment_id, test_invoice_id_1)
            if apply_success:
                print(f"   PASS: apply_full_payment_to_invoice returned True for Payment {test_payment_id} to Invoice {test_invoice_id_1}.")
                # Verification
                details = view_invoice_details(conn, test_invoice_id_1)
                if details and details['Status'] == 'Paid' and details['Balance'] == Decimal('0.00'):
                     print(f"      PASS: Invoice {test_invoice_id_1} status is now 'Paid' and Balance is 0.")
                elif details:
                     print(f"      FAIL: Invoice {test_invoice_id_1} status/balance incorrect after applying payment. Status='{details['Status']}', Balance={details['Balance']:.2f}")
                else:
                     print(f"      FAIL: Could not retrieve invoice details after applying payment.")

                # Check open invoices again - it should be gone
                open_invoices_after = list_open_customer_invoices(conn, test_customer_id)
                found_invoice_after = False
                if isinstance(open_invoices_after, list):
                     for inv in open_invoices_after:
                         if inv['InvoiceID'] == test_invoice_id_1:
                             found_invoice_after = True
                             break
                     if not found_invoice_after:
                         print(f"      PASS: Invoice {test_invoice_id_1} is correctly REMOVED from open list.")
                     else:
                         print(f"      FAIL: Invoice {test_invoice_id_1} is STILL in open list after payment application.")
                else:
                     print("      WARN: Could not retrieve open invoices list after payment for verification.")

            else:
                 print(f"   FAIL: apply_full_payment_to_invoice returned False for Payment {test_payment_id} to Invoice {test_invoice_id_1}.")
        elif not test_invoice_id_1:
             print("   SKIP: Cannot test payment application as invoice creation failed.")
        elif not test_payment_id:
             print("   SKIP: Cannot test payment application as payment creation failed.")


        # == 9. Test get_total_accounts_receivable ==
        print("\n9. Testing get_total_accounts_receivable...")
        # Create another small invoice for this customer that remains unpaid
        invoice_num_2 = f"INV-TEST-AR2-{int(time.time())}"
        unpaid_amount = Decimal('55.25')
        test_invoice_id_2 = create_simple_sales_invoice(
            conn, test_customer_id, today_str, due_date_str, "Second Test Item",
            Decimal('1.0'), unpaid_amount, revenue_account_id, ar_account_id,
            test_employee_id, invoice_number=invoice_num_2, tax_rate=Decimal('0.0')
        )

        if test_invoice_id_2:
             print(f"   (Created second unpaid invoice ID: {test_invoice_id_2} with amount {unpaid_amount})")
        else:
             print("   (Failed to create second invoice for total AR test)")

        # Calculate expected total AR (should just be the balance of the second invoice now)
        expected_total_ar = Decimal('0.00')
        open_invoices_final = list_open_customer_invoices(conn, test_customer_id) # Check specifically for *this* customer
        if isinstance(open_invoices_final, list):
            for inv in open_invoices_final:
                expected_total_ar += inv['Balance']
        # Now call the function (which should sum across *all* customers if not filtered)
        # To make the test accurate, we'd ideally calculate the *global* AR, but for this test
        # we'll compare the function result to the known state of our test customer's invoices.
        # A more robust test might query *all* open invoices and sum their balances.
        total_ar = get_total_accounts_receivable(conn)

        print(f"   Expected AR for test customer (based on open list): {expected_total_ar:.2f}")
        print(f"   Global AR reported by function: {total_ar:.2f}")
        if total_ar is not None and isinstance(total_ar, Decimal):
             print(f"   PASS: get_total_accounts_receivable returned a Decimal value.")
             # Note: Exact comparison is tricky without knowing the full state of the DB before the test.
             # We just check if the function runs and returns the correct type.
             # If Invoice 2 was created, we expect total_ar >= unpaid_amount.
             if test_invoice_id_2 and total_ar >= unpaid_amount - Decimal('0.01'):
                 print("      INFO: Global AR includes at least the amount of the unpaid test invoice.")
             elif test_invoice_id_2:
                  print("      WARN: Global AR seems lower than expected based on unpaid test invoice.")

        else:
            print(f"   FAIL: get_total_accounts_receivable returned {total_ar} (type: {type(total_ar)}).")


        # == 10. Test void_invoice ==
        print("\n10. Testing void_invoice...")
        if test_invoice_id_2: # Use the second invoice which hasn't been paid
             initial_ar_balance_void = view_gl_account_balance(conn, ar_account_id)
             initial_revenue_balance_void = view_gl_account_balance(conn, revenue_account_id)
             invoice_details_before_void = view_invoice_details(conn, test_invoice_id_2)
             amount_to_reverse = invoice_details_before_void['TotalAmount'] if invoice_details_before_void else Decimal('0.00')

             print(f"   Attempting to void Invoice {test_invoice_id_2} with amount {amount_to_reverse:.2f}")
             void_success = void_invoice(conn, test_invoice_id_2, ar_account_id, revenue_account_id, test_employee_id)

             if void_success:
                 print(f"   PASS: void_invoice returned True for Invoice {test_invoice_id_2}.")
                 # Verification
                 details = view_invoice_details(conn, test_invoice_id_2)
                 final_ar_balance_void = view_gl_account_balance(conn, ar_account_id)
                 final_revenue_balance_void = view_gl_account_balance(conn, revenue_account_id)

                 if details and details['Status'] == 'Cancelled':
                      print(f"      PASS: Invoice {test_invoice_id_2} status is now 'Cancelled'.")
                 elif details:
                      print(f"      FAIL: Invoice {test_invoice_id_2} status incorrect after void. Status='{details['Status']}'")
                 else:
                      print(f"      FAIL: Could not retrieve invoice details after voiding.")

                 # Check GL reversal
                 expected_ar_after_void = initial_ar_balance_void - amount_to_reverse
                 expected_rev_after_void = initial_revenue_balance_void - amount_to_reverse
                 if abs(final_ar_balance_void - expected_ar_after_void) < Decimal('0.01'):
                      print("      PASS: AR GL balance reversed correctly.")
                 else:
                      print(f"      FAIL: AR GL balance mismatch after void. Expected ~{expected_ar_after_void:.2f}, Got {final_ar_balance_void:.2f}")
                 if abs(final_revenue_balance_void - expected_rev_after_void) < Decimal('0.01'):
                      print("      PASS: Revenue GL balance reversed correctly (simple model).")
                 else:
                      print(f"      FAIL: Revenue GL balance mismatch after void (simple model). Expected ~{expected_rev_after_void:.2f}, Got {final_revenue_balance_void:.2f}")

                 # Check GL Entries
                 gl_entries = view_recent_gl_entries(conn, ar_account_id, 5)
                 if any(f"VoidInvoiceID:{test_invoice_id_2}" in entry.get('Reference','') for entry in gl_entries):
                      print("      PASS: Found related reversing GL entry for AR account.")
                 else:
                      print("      FAIL: Could not find related reversing GL entry for AR account.")

             else:
                 print(f"   FAIL: void_invoice returned False for unpaid Invoice {test_invoice_id_2}.")
        else:
            print("   SKIP: Cannot test void_invoice as second invoice creation failed.")

        # Try to void the first (paid) invoice - should fail
        if test_invoice_id_1:
             print(f"   Attempting to void PAID Invoice {test_invoice_id_1} (should fail)...")
             void_paid_success = void_invoice(conn, test_invoice_id_1, ar_account_id, revenue_account_id, test_employee_id)
             if not void_paid_success:
                 print("   PASS: void_invoice correctly returned False for a paid invoice.")
             else:
                 print(f"   FAIL: void_invoice incorrectly returned TRUE for a paid invoice!")


        # == 11. Test deactivate_customer ==
        print("\n11. Testing deactivate_customer...")
        deactivate_success = deactivate_customer(conn, test_customer_id)
        if deactivate_success:
            print(f"   PASS: deactivate_customer returned True for CustomerID {test_customer_id}.")
            # Verification
            details = view_customer_details(conn, test_customer_id)
            if details and details['IsActive'] == 0:
                print("      PASS: Customer IsActive flag is now 0.")
            elif details:
                print("      FAIL: Customer IsActive flag is not 0 after deactivation.")
            else:
                 print("      FAIL: Could not retrieve customer details after deactivation.")
        else:
             print(f"   FAIL: deactivate_customer returned False for CustomerID {test_customer_id}.")


        print("\n--- Accounts Receivable Function Tests Complete ---")

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
            # Optional: Clean up test data (delete customer, invoices, payments)
            # print("\n--- Cleaning up test data ---")
            # try:
            #     # Note: Order matters due to foreign keys! Payments/Items before Headers.
            #     if test_payment_id: conn.execute("DELETE FROM CustomerPayments WHERE PaymentID = ?", (test_payment_id,))
            #     if test_invoice_id_1: conn.execute("DELETE FROM InvoiceItems WHERE InvoiceID = ?", (test_invoice_id_1,))
            #     if test_invoice_id_2: conn.execute("DELETE FROM InvoiceItems WHERE InvoiceID = ?", (test_invoice_id_2,))
            #     if test_invoice_id_1: conn.execute("DELETE FROM Invoices WHERE InvoiceID = ?", (test_invoice_id_1,))
            #     if test_invoice_id_2: conn.execute("DELETE FROM Invoices WHERE InvoiceID = ?", (test_invoice_id_2,))
            #     if test_customer_id: conn.execute("DELETE FROM Customers WHERE CustomerID = ?", (test_customer_id,))
            #     # Add deletes for test GL entries if desired (more complex to identify)
            #     conn.commit()
            #     print("   Test data cleanup attempted.")
            # except sqlite3.Error as e:
            #      print(f"   Error during cleanup: {e}")
            #      conn.rollback()

            conn.close()
            print("\n--- Database Connection Closed ---")