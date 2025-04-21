import sqlite3
import datetime
from decimal import Decimal

# --- Database Connection (Assume this is established elsewhere) ---
# Example:
# def get_db_connection():
#     conn = sqlite3.connect('financial_management.db')
#     conn.row_factory = sqlite3.Row # Optional: Access columns by name
#     conn.execute("PRAGMA foreign_keys = ON;")
#     # Enable decimal adapter/converter if needed
#     sqlite3.register_adapter(Decimal, str)
#     sqlite3.register_converter("DECIMAL", lambda b: Decimal(b.decode('utf-8')))
#     return conn
#
# conn = get_db_connection()
# --- Helper Functions ---

def _execute_sql(conn, sql, params=(), fetchone=False, fetchall=False, commit=False):
    """Helper function to execute SQL queries."""
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        if fetchone:
            result = cursor.fetchone()
            return dict(result) if result else None
        elif fetchall:
            results = cursor.fetchall()
            return [dict(row) for row in results]
        elif commit:
            conn.commit()
            return cursor.lastrowid # Return last inserted row ID if applicable
        return cursor # Or return cursor for other operations
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        print(f"SQL: {sql}")
        print(f"Params: {params}")
        conn.rollback() # Rollback on error if part of a transaction
        raise # Re-raise the exception
    finally:
        # Cursor closing is implicitly handled when 'with conn:' is used,
        # but explicit closing is fine too if not using 'with'.
        pass

def _generate_gl_entries(conn, entries, created_by_employee_id, entry_type=None, reference=None):
    """
    Generates multiple balanced GL entries.
    'entries' should be a list of tuples:
    [(account_id, debit_amount, credit_amount, description), ...]
    """
    ledger_entry_ids = []
    total_debit = Decimal('0.00')
    total_credit = Decimal('0.00')

    base_sql = """
        INSERT INTO GeneralLedger
        (EntryDate, Description, AccountID, DebitAmount, CreditAmount, EntryType, Reference, CreatedBy, CreationDate)
        VALUES (DATE('now'), ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """

    for account_id, debit, credit, desc in entries:
        debit = Decimal(debit)
        credit = Decimal(credit)
        total_debit += debit
        total_credit += credit
        params = (desc, account_id, str(debit), str(credit), entry_type, reference, created_by_employee_id)
        last_id = _execute_sql(conn, base_sql, params, commit=False) # Commit happens later
        ledger_entry_ids.append(last_id) # Note: lastrowid not reliable in transactions before commit

    # Basic balance check
    if total_debit != total_credit:
        raise ValueError(f"GL entries are unbalanced. Debits: {total_debit}, Credits: {total_credit}")

    # Note: Returning ledger_entry_ids might not be reliable with implicit commits.
    # It's better to commit outside this function after all related operations.

# --- Function Implementations ---

# =============================================
# Bookkeeping & Recording Functions
# =============================================

def record_simple_cash_receipt(conn: sqlite3.Connection, transaction_date: str, amount: Decimal, description: str, bank_account_id: int, cash_account_id: int, income_account_id: int, created_by_employee_id: int, reference: str = None):
    """
    Logs cash received not tied to a customer payment (e.g., bank interest).
    Creates a CashTransaction and corresponding GeneralLedger entries.

    Args:
        conn: Database connection object.
        transaction_date: Date of the transaction (YYYY-MM-DD).
        amount: Amount received (positive Decimal).
        description: Description of the receipt.
        bank_account_id: The BankAccountID where the cash was deposited.
        cash_account_id: The ChartOfAccounts AccountID for the cash account linked to the bank account.
        income_account_id: The ChartOfAccounts AccountID for the income recognition.
        created_by_employee_id: EmployeeID of the user recording the transaction.
        reference: Optional reference text.

    Returns:
        int: The ID of the created CashTransaction, or None on failure.
    """
    if amount <= 0:
        raise ValueError("Amount must be positive for a cash receipt.")

    amount_str = str(amount)
    reference = reference or f"Cash Receipt {transaction_date}"

    try:
        conn.execute("BEGIN")

        # 1. Create Cash Transaction
        ct_sql = """
            INSERT INTO CashTransactions
            (TransactionDate, BankAccountID, TransactionType, Amount, Description, Reference, RelatedAccountID, CreatedBy, CreationDate)
            VALUES (?, ?, 'Deposit', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        cursor = conn.cursor()
        cursor.execute(ct_sql, (transaction_date, bank_account_id, amount_str, description, reference, income_account_id, created_by_employee_id))
        cash_transaction_id = cursor.lastrowid

        # 2. Update Bank Account Balance
        bal_sql = "UPDATE BankAccounts SET CurrentBalance = CurrentBalance + ? WHERE BankAccountID = ?"
        conn.execute(bal_sql, (amount_str, bank_account_id))

        # 3. Generate General Ledger Entries
        gl_entries = [
            # Debit Cash
            (cash_account_id, amount, Decimal('0.00'), f"Cash Receipt: {description}"),
            # Credit Income
            (income_account_id, Decimal('0.00'), amount, f"Cash Receipt: {description}")
        ]
        _generate_gl_entries(conn, gl_entries, created_by_employee_id, entry_type='CashReceipt', reference=f"CashTransID:{cash_transaction_id}")

        conn.commit()
        return cash_transaction_id
    except Exception as e:
        print(f"Error in record_simple_cash_receipt: {e}")
        conn.rollback()
        return None

def record_simple_cash_disbursement(conn: sqlite3.Connection, transaction_date: str, amount: Decimal, description: str, bank_account_id: int, cash_account_id: int, expense_account_id: int, created_by_employee_id: int, reference: str = None):
    """
    Logs cash paid out not tied to a vendor bill (e.g., minor cash purchase).
    Creates a CashTransaction and corresponding GeneralLedger entries.

    Args:
        conn: Database connection object.
        transaction_date: Date of the transaction (YYYY-MM-DD).
        amount: Amount paid (positive Decimal).
        description: Description of the disbursement.
        bank_account_id: The BankAccountID from which cash was withdrawn.
        cash_account_id: The ChartOfAccounts AccountID for the cash account linked to the bank account.
        expense_account_id: The ChartOfAccounts AccountID for the expense recognition.
        created_by_employee_id: EmployeeID of the user recording the transaction.
        reference: Optional reference text.

    Returns:
        int: The ID of the created CashTransaction, or None on failure.
    """
    if amount <= 0:
        raise ValueError("Amount must be positive for a cash disbursement.")

    amount_str = str(amount)
    # Store negative amount for withdrawal in CashTransactions if schema implied Amount is signed based on type
    # But current schema seems to store positive amount and rely on TransactionType
    reference = reference or f"Cash Disbursement {transaction_date}"

    try:
        conn.execute("BEGIN")

        # 1. Create Cash Transaction
        ct_sql = """
            INSERT INTO CashTransactions
            (TransactionDate, BankAccountID, TransactionType, Amount, Description, Reference, RelatedAccountID, CreatedBy, CreationDate)
            VALUES (?, ?, 'Withdrawal', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        cursor = conn.cursor()
        cursor.execute(ct_sql, (transaction_date, bank_account_id, amount_str, description, reference, expense_account_id, created_by_employee_id))
        cash_transaction_id = cursor.lastrowid

        # 2. Update Bank Account Balance
        bal_sql = "UPDATE BankAccounts SET CurrentBalance = CurrentBalance - ? WHERE BankAccountID = ?"
        conn.execute(bal_sql, (amount_str, bank_account_id))

        # 3. Generate General Ledger Entries
        gl_entries = [
            # Debit Expense
            (expense_account_id, amount, Decimal('0.00'), f"Cash Disbursement: {description}"),
            # Credit Cash
            (cash_account_id, Decimal('0.00'), amount, f"Cash Disbursement: {description}")
        ]
        _generate_gl_entries(conn, gl_entries, created_by_employee_id, entry_type='CashDisbursement', reference=f"CashTransID:{cash_transaction_id}")

        conn.commit()
        return cash_transaction_id
    except Exception as e:
        print(f"Error in record_simple_cash_disbursement: {e}")
        conn.rollback()
        return None

def view_recent_gl_entries(conn: sqlite3.Connection, account_id: int, limit: int = 10):
    """
    Displays the latest general ledger transactions posted to a specific account.

    Args:
        conn: Database connection object.
        account_id: The ChartOfAccounts AccountID to query.
        limit: The maximum number of entries to retrieve.

    Returns:
        list: A list of dictionaries representing the GL entries, or None on failure.
    """
    sql = """
        SELECT gl.*, coa.AccountName
        FROM GeneralLedger gl
        JOIN ChartOfAccounts coa ON gl.AccountID = coa.AccountID
        WHERE gl.AccountID = ?
        ORDER BY gl.EntryDate DESC, gl.LedgerEntryID DESC
        LIMIT ?
    """
    return _execute_sql(conn, sql, (account_id, limit), fetchall=True)

def post_simple_manual_journal_entry(conn: sqlite3.Connection, entry_date: str, description: str, debit_account_id: int, credit_account_id: int, amount: Decimal, created_by_employee_id: int, reference: str = None):
    """
    Records a basic, balanced two-line journal entry for adjustments or corrections.

    Args:
        conn: Database connection object.
        entry_date: Date of the journal entry (YYYY-MM-DD).
        description: Description for the entry.
        debit_account_id: The AccountID to be debited.
        credit_account_id: The AccountID to be credited.
        amount: The amount for the debit and credit (positive Decimal).
        created_by_employee_id: EmployeeID of the user posting the entry.
        reference: Optional reference text (e.g., adjustment reason).

    Returns:
        bool: True on success, False on failure.
    """
    if amount <= 0:
        raise ValueError("Amount must be positive for a journal entry.")
    if debit_account_id == credit_account_id:
         raise ValueError("Debit and Credit accounts cannot be the same.")

    reference = reference or f"Manual Journal Entry {entry_date}"

    try:
        conn.execute("BEGIN")

        # Generate General Ledger Entries
        gl_entries = [
            # Debit
            (debit_account_id, amount, Decimal('0.00'), description),
            # Credit
            (credit_account_id, Decimal('0.00'), amount, description)
        ]
        # Use a unique identifier for the journal batch if needed, here using reference
        _generate_gl_entries(conn, gl_entries, created_by_employee_id, entry_type='ManualJournal', reference=reference)

        conn.commit()
        return True
    except Exception as e:
        print(f"Error in post_simple_manual_journal_entry: {e}")
        conn.rollback()
        return False
    
def view_bank_account_balance(conn: sqlite3.Connection, bank_account_id: int):
    """
    Retrieves the current recorded balance for a specific company bank account.

    Args:
        conn: Database connection object.
        bank_account_id: The BankAccountID to query.

    Returns:
        Decimal: The current balance as a Decimal, or Decimal('0.00') if not found or NULL.
    """
    sql = "SELECT CurrentBalance FROM BankAccounts WHERE BankAccountID = ?"
    result = _execute_sql(conn, sql, (bank_account_id,), fetchone=True)
    # --- FIX: Ensure Decimal return type ---
    if result and result['CurrentBalance'] is not None:
        try:
            # Explicitly convert the fetched value to Decimal
            return Decimal(result['CurrentBalance'])
        except Exception as e:
            print(f"Error converting bank balance to Decimal for BankAccountID {bank_account_id}: {e}. Value: {result['CurrentBalance']}")
            # Decide how to handle conversion errors, maybe return None or raise
            return Decimal('0.00') # Or return None / raise error
    else:
        # Return Decimal(0) if account not found or balance is NULL
        return Decimal('0.00')


    """
    Retrieves the current recorded balance for a specific company bank account.

    Args:
        conn: Database connection object.
        bank_account_id: The BankAccountID to query.

    Returns:
        Decimal: The current balance, or None if the account is not found or on error.
    """
    sql = "SELECT CurrentBalance FROM BankAccounts WHERE BankAccountID = ?"
    result = _execute_sql(conn, sql, (bank_account_id,), fetchone=True)
    return result['CurrentBalance'] if result else None

def view_gl_account_balance(conn: sqlite3.Connection, account_id: int):
    """
    Calculates the current balance for a specific GL account by summing ledger entries.
    NOTE: This function calculates the balance on the fly. It does not use a
          potentially stale 'CurrentBalance' field in ChartOfAccounts.

    Args:
        conn: Database connection object.
        account_id: The ChartOfAccounts AccountID to query.

    Returns:
        Decimal: The calculated balance (Debit positive, Credit negative based on BalanceType),
                 or Decimal('0.00') if no entries or account not found.
    """
    coa_sql = "SELECT BalanceType FROM ChartOfAccounts WHERE AccountID = ?"
    coa_info = _execute_sql(conn, coa_sql, (account_id,), fetchone=True)

    if not coa_info:
        print(f"Warning: AccountID {account_id} not found in ChartOfAccounts.")
        return Decimal('0.00')

    balance_type = coa_info['BalanceType']

    gl_sql = """
        SELECT SUM(DebitAmount) as TotalDebit, SUM(CreditAmount) as TotalCredit
        FROM GeneralLedger
        WHERE AccountID = ?
    """
    result = _execute_sql(conn, gl_sql, (account_id,), fetchone=True)

    # --- FIX: Explicitly convert SUM results to Decimal ---
    try:
        total_debit = Decimal(result['TotalDebit']) if result and result['TotalDebit'] is not None else Decimal('0.00')
        total_credit = Decimal(result['TotalCredit']) if result and result['TotalCredit'] is not None else Decimal('0.00')
    except Exception as e:
        print(f"Error converting GL SUM results to Decimal for AccountID {account_id}: {e}. Values: D={result.get('TotalDebit', 'N/A')}, C={result.get('TotalCredit', 'N/A')}")
        return Decimal('0.00') # Or handle error differently
    # --- END FIX ---


    if balance_type == 'Debit':
        return total_debit - total_credit
    elif balance_type == 'Credit':
        return total_credit - total_debit
    else:
        print(f"Warning: Unknown BalanceType '{balance_type}' for AccountID {account_id}.")
        return total_debit - total_credit # Default to debit balance convention
def record_bank_transfer(conn: sqlite3.Connection, transaction_date: str, amount: Decimal, source_bank_account_id: int, source_cash_account_id: int, target_bank_account_id: int, target_cash_account_id: int, description: str, created_by_employee_id: int, reference: str = None):
    """
    Logs money moved electronically between two company bank accounts.

    Args:
        conn: Database connection object.
        transaction_date: Date of the transfer (YYYY-MM-DD).
        amount: Amount transferred (positive Decimal).
        source_bank_account_id: BankAccountID money is transferred FROM.
        source_cash_account_id: ChartOfAccountsID for the source cash account.
        target_bank_account_id: BankAccountID money is transferred TO.
        target_cash_account_id: ChartOfAccountsID for the target cash account.
        description: Description of the transfer.
        created_by_employee_id: EmployeeID recording the transfer.
        reference: Optional reference text.

    Returns:
        tuple: (source_cash_transaction_id, target_cash_transaction_id) or None on failure.
    """
    if amount <= 0:
        raise ValueError("Amount must be positive for a transfer.")
    if source_bank_account_id == target_bank_account_id:
         raise ValueError("Source and Target bank accounts cannot be the same.")
    if source_cash_account_id == target_cash_account_id:
         raise ValueError("Source and Target cash GL accounts cannot be the same.")

    amount_str = str(amount)
    reference = reference or f"Bank Transfer {transaction_date}"

    try:
        conn.execute("BEGIN")

        # 1. Create Cash Transaction (Withdrawal from Source)
        ct_sql_out = """
            INSERT INTO CashTransactions
            (TransactionDate, BankAccountID, TransactionType, Amount, Description, Reference, RelatedAccountID, CreatedBy, CreationDate)
            VALUES (?, ?, 'Transfer', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        cursor = conn.cursor()
        cursor.execute(ct_sql_out, (transaction_date, source_bank_account_id, amount_str, f"Transfer Out to Bank {target_bank_account_id}: {description}", reference, target_cash_account_id, created_by_employee_id))
        source_cash_transaction_id = cursor.lastrowid

        # 2. Update Source Bank Account Balance
        bal_sql_out = "UPDATE BankAccounts SET CurrentBalance = CurrentBalance - ? WHERE BankAccountID = ?"
        conn.execute(bal_sql_out, (amount_str, source_bank_account_id))

        # 3. Create Cash Transaction (Deposit to Target)
        ct_sql_in = """
            INSERT INTO CashTransactions
            (TransactionDate, BankAccountID, TransactionType, Amount, Description, Reference, RelatedAccountID, CreatedBy, CreationDate)
            VALUES (?, ?, 'Transfer', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        cursor.execute(ct_sql_in, (transaction_date, target_bank_account_id, amount_str, f"Transfer In from Bank {source_bank_account_id}: {description}", reference, source_cash_account_id, created_by_employee_id))
        target_cash_transaction_id = cursor.lastrowid

        # 4. Update Target Bank Account Balance
        bal_sql_in = "UPDATE BankAccounts SET CurrentBalance = CurrentBalance + ? WHERE BankAccountID = ?"
        conn.execute(bal_sql_in, (amount_str, target_bank_account_id))

        # 5. Generate General Ledger Entries
        gl_entries = [
            # Debit Target Cash Account
            (target_cash_account_id, amount, Decimal('0.00'), f"Bank Transfer: {description}"),
            # Credit Source Cash Account
            (source_cash_account_id, Decimal('0.00'), amount, f"Bank Transfer: {description}")
        ]
        # Link GL to both cash transactions if possible in Reference
        gl_ref = f"Transfer IDs:{source_cash_transaction_id},{target_cash_transaction_id}"
        _generate_gl_entries(conn, gl_entries, created_by_employee_id, entry_type='BankTransfer', reference=gl_ref)

        conn.commit()
        return (source_cash_transaction_id, target_cash_transaction_id)
    except Exception as e:
        print(f"Error in record_bank_transfer: {e}")
        conn.rollback()
        return None

# =============================================
# Accounts Receivable Functions
# =============================================

def create_customer(conn: sqlite3.Connection, customer_name: str, contact_person: str = None, email: str = None, phone: str = None, address: str = None, tax_id: str = None, credit_limit: Decimal = None, payment_terms: str = None):
    """
    Adds a new customer record with basic details.

    Args:
        conn: Database connection object.
        customer_name: Name of the customer (required).
        contact_person: Contact person's name.
        email: Customer email address.
        phone: Customer phone number.
        address: Customer address.
        tax_id: Customer Tax ID.
        credit_limit: Customer credit limit.
        payment_terms: Customer payment terms (e.g., "Net 30").

    Returns:
        int: The ID of the newly created customer, or None on failure.
    """
    sql = """
        INSERT INTO Customers
        (CustomerName, ContactPerson, Email, Phone, Address, TaxID, CreditLimit, PaymentTerms, IsActive)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """
    params = (customer_name, contact_person, email, phone, address, tax_id, str(credit_limit) if credit_limit else None, payment_terms)
    try:
        return _execute_sql(conn, sql, params, commit=True)
    except sqlite3.IntegrityError as e:
         print(f"Error creating customer (likely duplicate name or constraint violation): {e}")
         return None
    except Exception as e:
        print(f"Error in create_customer: {e}")
        return None


def view_customer_details(conn: sqlite3.Connection, customer_id: int):
    """
    Retrieves and displays information for a specific customer.

    Args:
        conn: Database connection object.
        customer_id: The ID of the customer to retrieve.

    Returns:
        dict: A dictionary containing customer details, or None if not found.
    """
    sql = "SELECT * FROM Customers WHERE CustomerID = ?"
    return _execute_sql(conn, sql, (customer_id,), fetchone=True)

def update_customer_contact_info(conn: sqlite3.Connection, customer_id: int, contact_person: str = None, email: str = None, phone: str = None):
    """
    Modifies the contact details (email, phone, contact person) for an existing customer.

    Args:
        conn: Database connection object.
        customer_id: The ID of the customer to update.
        contact_person: The new contact person name.
        email: The new email address.
        phone: The new phone number.

    Returns:
        bool: True on success, False on failure or if customer not found.
    """
    updates = []
    params = []
    if contact_person is not None:
        updates.append("ContactPerson = ?")
        params.append(contact_person)
    if email is not None:
        updates.append("Email = ?")
        params.append(email)
    if phone is not None:
        updates.append("Phone = ?")
        params.append(phone)

    if not updates:
        print("No update information provided.")
        return False

    sql = f"UPDATE Customers SET {', '.join(updates)} WHERE CustomerID = ?"
    params.append(customer_id)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        updated_rows = cursor.rowcount
        conn.commit()
        return updated_rows > 0
    except Exception as e:
        print(f"Error in update_customer_contact_info: {e}")
        conn.rollback()
        return False

def deactivate_customer(conn: sqlite3.Connection, customer_id: int):
    """
    Marks an existing customer as inactive.

    Args:
        conn: Database connection object.
        customer_id: The ID of the customer to deactivate.

    Returns:
        bool: True on success, False on failure or if customer not found.
    """
    sql = "UPDATE Customers SET IsActive = 0 WHERE CustomerID = ?"
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (customer_id,))
        updated_rows = cursor.rowcount
        conn.commit()
        return updated_rows > 0
    except Exception as e:
        print(f"Error in deactivate_customer: {e}")
        conn.rollback()
        return False

def create_simple_sales_invoice(conn: sqlite3.Connection, customer_id: int, invoice_date: str, due_date: str, item_description: str, quantity: Decimal, unit_price: Decimal, revenue_account_id: int, ar_account_id: int, created_by_employee_id: int, invoice_number: str = None, tax_rate: Decimal = Decimal('0.00')):
    """
    Generates a basic invoice with one line item and posts GL entries.
    NOTE: Assumes AR Account ID is provided. Calculates totals manually.

    Args:
        conn: Database connection object.
        customer_id: The ID of the customer being invoiced.
        invoice_date: Date of the invoice (YYYY-MM-DD).
        due_date: Date the invoice payment is due (YYYY-MM-DD).
        item_description: Description of the single item sold.
        quantity: Quantity of the item.
        unit_price: Price per unit.
        revenue_account_id: The ChartOfAccounts ID for the revenue.
        ar_account_id: The ChartOfAccounts ID for Accounts Receivable.
        created_by_employee_id: EmployeeID creating the invoice.
        invoice_number: Optional specific invoice number (must be unique if provided).
        tax_rate: The tax rate percentage (e.g., 5.0 for 5%).

    Returns:
        int: The ID of the newly created invoice, or None on failure.
    """
    if quantity <= 0 or unit_price < 0 or tax_rate < 0:
        raise ValueError("Quantity must be positive, unit price and tax rate cannot be negative.")

    # Calculations
    line_subtotal = quantity * unit_price
    tax_amount = line_subtotal * (tax_rate / Decimal(100))
    line_total = line_subtotal + tax_amount
    total_amount = line_total # For a single item invoice

    if invoice_number is None:
        # Basic sequential numbering (prone to race conditions without locking)
        # In a real app, use a sequence or more robust method
        cur = conn.cursor()
        cur.execute("SELECT MAX(CAST(SUBSTR(InvoiceNumber, 5) AS INTEGER)) FROM Invoices WHERE InvoiceNumber LIKE 'INV-%'")
        max_num = cur.fetchone()[0]
        next_num = (max_num or 0) + 1
        invoice_number = f"INV-{next_num:04d}"

    try:
        conn.execute("BEGIN")

        # 1. Create Invoice Header
        inv_sql = """
            INSERT INTO Invoices
            (InvoiceNumber, CustomerID, InvoiceDate, DueDate, TotalAmount, PaidAmount, Balance, Status, CreatedBy, CreationDate)
            VALUES (?, ?, ?, ?, ?, 0.00, ?, 'Issued', ?, CURRENT_TIMESTAMP)
        """
        cursor = conn.cursor()
        # Calculate initial balance
        initial_balance = total_amount
        cursor.execute(inv_sql, (invoice_number, customer_id, invoice_date, due_date, str(total_amount), str(initial_balance), created_by_employee_id))
        invoice_id = cursor.lastrowid

        # 2. Create Invoice Item
        item_sql = """
            INSERT INTO InvoiceItems
            (InvoiceID, Description, Quantity, UnitPrice, TaxRate, TaxAmount, LineTotal, AccountID)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn.execute(item_sql, (invoice_id, item_description, str(quantity), str(unit_price), str(tax_rate), str(tax_amount), str(line_total), revenue_account_id))

        # 3. Generate General Ledger Entries
        #   Debit Accounts Receivable
        #   Credit Revenue (and optionally Tax Payable if tracked separately)
        #   For simplicity here, crediting Revenue for the full amount.
        #   A more complex setup would credit Revenue (subtotal) and Tax Payable (tax_amount).
        gl_entries = [
            # Debit AR
            (ar_account_id, total_amount, Decimal('0.00'), f"Invoice {invoice_number}"),
            # Credit Revenue
            (revenue_account_id, Decimal('0.00'), total_amount, f"Invoice {invoice_number} - {item_description}")
            # TODO: Optionally split credit between Revenue and a Tax Payable account if needed
        ]
        _generate_gl_entries(conn, gl_entries, created_by_employee_id, entry_type='SalesInvoice', reference=f"InvoiceID:{invoice_id}")

        conn.commit()
        return invoice_id
    except sqlite3.IntegrityError as e:
         print(f"Error creating invoice (likely duplicate InvoiceNumber {invoice_number}): {e}")
         conn.rollback()
         return None
    except Exception as e:
        print(f"Error in create_simple_sales_invoice: {e}")
        conn.rollback()
        return None

def view_invoice_details(conn: sqlite3.Connection, invoice_id: int):
    """
    Displays the full details of a specific customer invoice, including line items.

    Args:
        conn: Database connection object.
        invoice_id: The ID of the invoice to retrieve.

    Returns:
        dict: A dictionary containing invoice header details and a list of items, or None if not found.
    """
    header_sql = """
        SELECT i.*, c.CustomerName
        FROM Invoices i
        JOIN Customers c ON i.CustomerID = c.CustomerID
        WHERE i.InvoiceID = ?
    """
    items_sql = "SELECT * FROM InvoiceItems WHERE InvoiceID = ?"

    invoice_data = _execute_sql(conn, header_sql, (invoice_id,), fetchone=True)
    if not invoice_data:
        return None

    items_data = _execute_sql(conn, items_sql, (invoice_id,), fetchall=True)
    invoice_data['items'] = items_data
    return invoice_data

def record_simple_customer_payment(conn: sqlite3.Connection, customer_id: int, payment_date: str, amount: Decimal, payment_method: str, bank_account_id: int, cash_account_id: int, ar_account_id: int, created_by_employee_id: int, reference: str = None):
    """
    Logs a payment received from a customer (initial recording, allocation separate).
    Creates CustomerPayments record and posts GL entry (Dr Cash, Cr AR).

    Args:
        conn: Database connection object.
        customer_id: ID of the paying customer.
        payment_date: Date payment was received (YYYY-MM-DD).
        amount: Amount received (positive Decimal).
        payment_method: Method (e.g., 'Check', 'EFT', 'Cash').
        bank_account_id: BankAccountID where payment was deposited.
        cash_account_id: The ChartOfAccounts ID for the cash account.
        ar_account_id: The ChartOfAccounts ID for Accounts Receivable.
        created_by_employee_id: EmployeeID recording the payment.
        reference: Optional payment reference (e.g., Check number).

    Returns:
        int: The ID of the created CustomerPayment, or None on failure.
    """
    if amount <= 0:
        raise ValueError("Payment amount must be positive.")

    amount_str = str(amount)

    try:
        conn.execute("BEGIN")

        # 1. Create Customer Payment Record
        pay_sql = """
            INSERT INTO CustomerPayments
            (CustomerID, PaymentDate, Amount, PaymentMethod, Reference, BankAccountID, CreatedBy, CreationDate)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        cursor = conn.cursor()
        cursor.execute(pay_sql, (customer_id, payment_date, amount_str, payment_method, reference, bank_account_id, created_by_employee_id))
        payment_id = cursor.lastrowid

        # 2. Update Bank Account Balance (Increase)
        bal_sql = "UPDATE BankAccounts SET CurrentBalance = CurrentBalance + ? WHERE BankAccountID = ?"
        conn.execute(bal_sql, (amount_str, bank_account_id))

        # 3. Generate General Ledger Entries
        gl_entries = [
            # Debit Cash
            (cash_account_id, amount, Decimal('0.00'), f"Customer Payment {reference or payment_id}"),
            # Credit Accounts Receivable
            (ar_account_id, Decimal('0.00'), amount, f"Customer Payment {reference or payment_id}")
        ]
        _generate_gl_entries(conn, gl_entries, created_by_employee_id, entry_type='CustomerPayment', reference=f"CustPmtID:{payment_id}")

        conn.commit()
        return payment_id
    except Exception as e:
        print(f"Error in record_simple_customer_payment: {e}")
        conn.rollback()
        return None

def list_open_customer_invoices(conn: sqlite3.Connection, customer_id: int):
    """
    Shows all invoices for a specific customer that are not yet fully paid.

    Args:
        conn: Database connection object.
        customer_id: The ID of the customer.

    Returns:
        list: A list of dictionaries representing open invoices, or None on failure.
    """
    sql = """
        SELECT InvoiceID, InvoiceNumber, InvoiceDate, DueDate, TotalAmount, PaidAmount, Balance, Status
        FROM Invoices
        WHERE CustomerID = ?
        AND Status IN ('Issued', 'Overdue') -- Assuming 'Partially Paid' isn't a status, use Balance > 0
        AND Balance > 0.00
        ORDER BY DueDate ASC
    """
    # Alternative if 'Partially Paid' status exists:
    # sql = """
    #     SELECT InvoiceID, InvoiceNumber, InvoiceDate, DueDate, TotalAmount, PaidAmount, Balance, Status
    #     FROM Invoices
    #     WHERE CustomerID = ?
    #     AND Status IN ('Issued', 'Partially Paid', 'Overdue')
    #     ORDER BY DueDate ASC
    # """
    return _execute_sql(conn, sql, (customer_id,), fetchall=True)

def apply_full_payment_to_invoice(conn: sqlite3.Connection, payment_id: int, invoice_id: int):
    """
    Allocates a single customer payment to fully pay off one specific invoice.
    NOTE: Simplified version. Assumes payment amount >= invoice balance.
          Does not handle partial payments or allocation tables. Updates invoice directly.

    Args:
        conn: Database connection object.
        payment_id: The ID of the CustomerPayments record.
        invoice_id: The ID of the Invoice to be paid.

    Returns:
        bool: True on success, False on failure (e.g., invoice not found, already paid, payment insufficient).
    """
    try:
        conn.execute("BEGIN")

        # 1. Get Payment Amount
        payment_sql = "SELECT Amount FROM CustomerPayments WHERE PaymentID = ?"
        payment_info = _execute_sql(conn, payment_sql, (payment_id,), fetchone=True)
        if not payment_info:
            print(f"Error: PaymentID {payment_id} not found.")
            conn.rollback()
            return False
        payment_amount = Decimal(payment_info['Amount'])

        # 2. Get Invoice Balance and Status
        invoice_sql = "SELECT Balance, Status, TotalAmount FROM Invoices WHERE InvoiceID = ?"
        invoice_info = _execute_sql(conn, invoice_sql, (invoice_id,), fetchone=True)
        if not invoice_info:
            print(f"Error: InvoiceID {invoice_id} not found.")
            conn.rollback()
            return False

        invoice_balance = Decimal(invoice_info['Balance'] or '0.00') # Handle potential NULL
        invoice_status = invoice_info['Status']
        invoice_total = Decimal(invoice_info['TotalAmount'])

        if invoice_status == 'Paid' or invoice_balance <= 0:
            print(f"Info: InvoiceID {invoice_id} is already paid or has zero balance.")
            # Depending on requirements, might still proceed if payment amount matches total and status isn't 'Paid'
            conn.rollback() # Treat as non-actionable / potential error state
            return False

        # 3. Check if payment is sufficient (for this simplified 'full payment' function)
        if payment_amount < invoice_balance:
            print(f"Error: Payment amount {payment_amount} is less than invoice balance {invoice_balance}.")
            # In a real system, this might trigger a partial payment update.
            conn.rollback()
            return False

        # 4. Update Invoice: Set PaidAmount = TotalAmount, Balance = 0, Status = 'Paid'
        #    Note: Assumes the payment fully covers the remaining balance.
        update_sql = """
            UPDATE Invoices
            SET PaidAmount = TotalAmount,
                Balance = 0.00,
                Status = 'Paid'
            WHERE InvoiceID = ?
        """
        cursor = conn.cursor()
        cursor.execute(update_sql, (invoice_id,))
        updated_rows = cursor.rowcount

        # 5. Optionally: Link payment and invoice (e.g., update a note field or an allocation table if it existed)
        # Example: Add note to payment
        # note_sql = "UPDATE CustomerPayments SET Notes = Notes || ? WHERE PaymentID = ?"
        # conn.execute(note_sql, (f'\nApplied to InvoiceID {invoice_id}', payment_id))

        conn.commit()
        return updated_rows > 0

    except Exception as e:
        print(f"Error in apply_full_payment_to_invoice: {e}")
        conn.rollback()
        return False

def get_total_accounts_receivable(conn: sqlite3.Connection):
    """
    Calculates the total amount currently owed by all customers (sum of positive balances).

    Args:
        conn: Database connection object.

    Returns:
        Decimal: The total outstanding AR balance, or Decimal('0.00') on failure/no open invoices.
    """
    # Sum the 'Balance' column directly, assuming it's accurately maintained
    sql = """
        SELECT SUM(Balance) as TotalAR
        FROM Invoices
        WHERE Status NOT IN ('Paid', 'Cancelled', 'Draft')
        AND Balance > 0.00
    """
    # If Balance column isn't reliable:
    # sql = """
    #     SELECT SUM(TotalAmount - PaidAmount) as TotalAR
    #     FROM Invoices
    #     WHERE Status NOT IN ('Paid', 'Cancelled', 'Draft')
    #     AND (TotalAmount - PaidAmount) > 0.00
    # """
    result = _execute_sql(conn, sql, fetchone=True)
    return result['TotalAR'] if result and result['TotalAR'] else Decimal('0.00')


def void_invoice(conn: sqlite3.Connection, invoice_id: int, ar_account_id: int, revenue_account_id: int, void_by_employee_id: int):
    """
    Marks an existing invoice as Void and reverses its GL impact.
    Only possible if the invoice has not been paid at all.

    Args:
        conn: Database connection object.
        invoice_id: The ID of the invoice to void.
        ar_account_id: The ChartOfAccounts ID for Accounts Receivable used in the original entry.
        revenue_account_id: The ChartOfAccounts ID for Revenue used in the original entry.
        void_by_employee_id: EmployeeID performing the void action.

    Returns:
        bool: True on success, False on failure (e.g., invoice not found, already paid, error).
    """
    try:
        conn.execute("BEGIN")

        # 1. Check Invoice Status and Paid Amount
        check_sql = "SELECT PaidAmount, Status, TotalAmount FROM Invoices WHERE InvoiceID = ?"
        invoice_info = _execute_sql(conn, check_sql, (invoice_id,), fetchone=True)

        if not invoice_info:
            print(f"Error: InvoiceID {invoice_id} not found.")
            conn.rollback()
            return False

        paid_amount = Decimal(invoice_info['PaidAmount'] or '0.00')
        status = invoice_info['Status']
        total_amount = Decimal(invoice_info['TotalAmount'])

        if paid_amount > 0:
            print(f"Error: Cannot void InvoiceID {invoice_id} because it has payments recorded (PaidAmount: {paid_amount}). Consider a credit note.")
            conn.rollback()
            return False
        if status == 'Paid' or status == 'Cancelled': # Should be redundant if paid_amount > 0 check works
             print(f"Error: Cannot void InvoiceID {invoice_id} with status '{status}'.")
             conn.rollback()
             return False

        # 2. Update Invoice Status to 'Cancelled' (or 'Void' if preferred)
        update_sql = "UPDATE Invoices SET Status = 'Cancelled', Balance = 0.00 WHERE InvoiceID = ?"
        cursor = conn.cursor()
        cursor.execute(update_sql, (invoice_id,))
        updated_rows = cursor.rowcount

        if updated_rows == 0:
             # Should not happen if check_sql found the record, but good practice
             print(f"Error: Failed to update status for InvoiceID {invoice_id}.")
             conn.rollback()
             return False

        # 3. Generate Reversing General Ledger Entries (if original GL was posted)
        #    Credit Accounts Receivable
        #    Debit Revenue
        #    Assumes original entry was Dr AR / Cr Revenue for total_amount
        if total_amount > 0: # Only reverse if there was an amount
            gl_entries = [
                # Credit AR (Reverse original Debit)
                (ar_account_id, Decimal('0.00'), total_amount, f"Void InvoiceID {invoice_id}"),
                # Debit Revenue (Reverse original Credit)
                (revenue_account_id, total_amount, Decimal('0.00'), f"Void InvoiceID {invoice_id}")
            ]
            _generate_gl_entries(conn, gl_entries, void_by_employee_id, entry_type='InvoiceVoid', reference=f"VoidInvoiceID:{invoice_id}")

        conn.commit()
        return True

    except Exception as e:
        print(f"Error in void_invoice: {e}")
        conn.rollback()
        return False


# =============================================
# Accounts Payable Functions
# =============================================

def create_vendor(conn: sqlite3.Connection, vendor_name: str, contact_person: str = None, email: str = None, phone: str = None, address: str = None, tax_id: str = None, payment_terms: str = None):
    """
    Adds a new vendor record with basic details.

    Args:
        conn: Database connection object.
        vendor_name: Name of the vendor (required).
        contact_person: Contact person's name.
        email: Vendor email address.
        phone: Vendor phone number.
        address: Vendor address.
        tax_id: Vendor Tax ID.
        payment_terms: Vendor payment terms (e.g., "Net 30").

    Returns:
        int: The ID of the newly created vendor, or None on failure.
    """
    sql = """
        INSERT INTO Vendors
        (VendorName, ContactPerson, Email, Phone, Address, TaxID, PaymentTerms, IsActive)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """
    params = (vendor_name, contact_person, email, phone, address, tax_id, payment_terms)
    try:
        return _execute_sql(conn, sql, params, commit=True)
    except sqlite3.IntegrityError as e:
         print(f"Error creating vendor (likely duplicate name or constraint violation): {e}")
         return None
    except Exception as e:
        print(f"Error in create_vendor: {e}")
        return None


def view_vendor_details(conn: sqlite3.Connection, vendor_id: int):
    """
    Retrieves and displays information for a specific vendor.

    Args:
        conn: Database connection object.
        vendor_id: The ID of the vendor to retrieve.

    Returns:
        dict: A dictionary containing vendor details, or None if not found.
    """
    sql = "SELECT * FROM Vendors WHERE VendorID = ?"
    return _execute_sql(conn, sql, (vendor_id,), fetchone=True)

def update_vendor_contact_info(conn: sqlite3.Connection, vendor_id: int, contact_person: str = None, email: str = None, phone: str = None, address: str = None):
    """
    Modifies the contact details (email, phone, contact person, address) for an existing vendor.

    Args:
        conn: Database connection object.
        vendor_id: The ID of the vendor to update.
        contact_person: The new contact person name.
        email: The new email address.
        phone: The new phone number.
        address: The new address.

    Returns:
        bool: True on success, False on failure or if vendor not found.
    """
    updates = []
    params = []
    if contact_person is not None:
        updates.append("ContactPerson = ?")
        params.append(contact_person)
    if email is not None:
        updates.append("Email = ?")
        params.append(email)
    if phone is not None:
        updates.append("Phone = ?")
        params.append(phone)
    if address is not None:
        updates.append("Address = ?")
        params.append(address)

    if not updates:
        print("No update information provided.")
        return False

    sql = f"UPDATE Vendors SET {', '.join(updates)} WHERE VendorID = ?"
    params.append(vendor_id)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        updated_rows = cursor.rowcount
        conn.commit()
        return updated_rows > 0
    except Exception as e:
        print(f"Error in update_vendor_contact_info: {e}")
        conn.rollback()
        return False

def deactivate_vendor(conn: sqlite3.Connection, vendor_id: int):
    """
    Marks an existing vendor as inactive.

    Args:
        conn: Database connection object.
        vendor_id: The ID of the vendor to deactivate.

    Returns:
        bool: True on success, False on failure or if vendor not found.
    """
    sql = "UPDATE Vendors SET IsActive = 0 WHERE VendorID = ?"
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (vendor_id,))
        updated_rows = cursor.rowcount
        conn.commit()
        return updated_rows > 0
    except Exception as e:
        print(f"Error in deactivate_vendor: {e}")
        conn.rollback()
        return False

def enter_simple_vendor_bill(conn: sqlite3.Connection, vendor_id: int, bill_number: str, bill_date: str, due_date: str, item_description: str, quantity: Decimal, unit_price: Decimal, expense_account_id: int, ap_account_id: int, created_by_employee_id: int, tax_rate: Decimal = Decimal('0.00')):
    """
    Records a basic bill received from a vendor with one line item and posts GL.
    NOTE: Assumes AP Account ID is provided. Uses generated columns for BillItems totals.

    Args:
        conn: Database connection object.
        vendor_id: The ID of the vendor.
        bill_number: The vendor's bill number (must be unique).
        bill_date: Date on the bill (YYYY-MM-DD).
        due_date: Date the bill payment is due (YYYY-MM-DD).
        item_description: Description of the single item purchased.
        quantity: Quantity of the item.
        unit_price: Price per unit.
        expense_account_id: The ChartOfAccounts ID for the expense.
        ap_account_id: The ChartOfAccounts ID for Accounts Payable.
        created_by_employee_id: EmployeeID entering the bill.
        tax_rate: The tax rate percentage applied by the vendor (e.g., 5.0 for 5%).

    Returns:
        int: The ID of the newly created bill, or None on failure.
    """
    if quantity <= 0 or unit_price < 0 or tax_rate < 0:
        raise ValueError("Quantity must be positive, unit price and tax rate cannot be negative.")

    # Calculate total amount for the Bill header (since BillItems totals are generated)
    line_subtotal = quantity * unit_price
    tax_amount = line_subtotal * (tax_rate / Decimal(100))
    total_amount = line_subtotal + tax_amount

    try:
        conn.execute("BEGIN")

        # 1. Create Bill Header
        # Note: Balance is a GENERATED column, so we don't insert it.
        bill_sql = """
            INSERT INTO Bills
            (BillNumber, VendorID, BillDate, DueDate, TotalAmount, PaidAmount, Status, CreatedBy, CreationDate)
            VALUES (?, ?, ?, ?, ?, 0.00, 'Received', ?, CURRENT_TIMESTAMP)
        """
        cursor = conn.cursor()
        cursor.execute(bill_sql, (bill_number, vendor_id, bill_date, due_date, str(total_amount), created_by_employee_id))
        bill_id = cursor.lastrowid

        # 2. Create Bill Item
        # Note: TaxAmount and LineTotal are GENERATED columns, so we don't insert them.
        item_sql = """
            INSERT INTO BillItems
            (BillID, Description, Quantity, UnitPrice, TaxRate, AccountID)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        conn.execute(item_sql, (bill_id, item_description, str(quantity), str(unit_price), str(tax_rate), expense_account_id))

        # 3. Generate General Ledger Entries
        #    Debit Expense (or Asset)
        #    Credit Accounts Payable
        #    For simplicity, debiting Expense for the full amount.
        #    A more complex setup might debit Expense (subtotal) and a "VAT Input" Asset (tax_amount).
        gl_entries = [
             # Debit Expense Account
            (expense_account_id, total_amount, Decimal('0.00'), f"Vendor Bill {bill_number}"),
            # Credit Accounts Payable
            (ap_account_id, Decimal('0.00'), total_amount, f"Vendor Bill {bill_number}")
            # TODO: Optionally split debit if tax is tracked separately (e.g., Dr Expense, Dr Tax Asset, Cr AP)
        ]
        _generate_gl_entries(conn, gl_entries, created_by_employee_id, entry_type='VendorBill', reference=f"BillID:{bill_id}")

        conn.commit()
        return bill_id
    except sqlite3.IntegrityError as e:
         print(f"Error entering bill (likely duplicate BillNumber {bill_number}): {e}")
         conn.rollback()
         return None
    except Exception as e:
        print(f"Error in enter_simple_vendor_bill: {e}")
        conn.rollback()
        return None


def view_bill_details(conn: sqlite3.Connection, bill_id: int):
    """
    Displays the full details of a specific vendor bill, including line items.

    Args:
        conn: Database connection object.
        bill_id: The ID of the bill to retrieve.

    Returns:
        dict: A dictionary containing bill header details and a list of items, or None if not found.
    """
    header_sql = """
        SELECT b.*, v.VendorName
        FROM Bills b
        JOIN Vendors v ON b.VendorID = v.VendorID
        WHERE b.BillID = ?
    """
    # Query generated columns too
    items_sql = "SELECT BillItemID, BillID, Description, Quantity, UnitPrice, TaxRate, TaxAmount, LineTotal, AccountID FROM BillItems WHERE BillID = ?"

    bill_data = _execute_sql(conn, header_sql, (bill_id,), fetchone=True)
    if not bill_data:
        return None

    items_data = _execute_sql(conn, items_sql, (bill_id,), fetchall=True)
    bill_data['items'] = items_data
    return bill_data

def record_simple_vendor_payment(conn: sqlite3.Connection, vendor_id: int, payment_date: str, amount: Decimal, payment_method: str, bank_account_id: int, cash_account_id: int, ap_account_id: int, created_by_employee_id: int, reference: str = None):
    """
    Logs a payment made to a vendor (initial recording, allocation separate).
    Creates VendorPayments record and posts GL entry (Dr AP, Cr Cash).

    Args:
        conn: Database connection object.
        vendor_id: ID of the paid vendor.
        payment_date: Date payment was made (YYYY-MM-DD).
        amount: Amount paid (positive Decimal).
        payment_method: Method (e.g., 'Check', 'EFT', 'Wire').
        bank_account_id: BankAccountID from which payment was made.
        cash_account_id: The ChartOfAccounts ID for the cash account.
        ap_account_id: The ChartOfAccounts ID for Accounts Payable.
        created_by_employee_id: EmployeeID recording the payment.
        reference: Optional payment reference (e.g., Check number, EFT ID).

    Returns:
        int: The ID of the created VendorPayment, or None on failure.
    """
    if amount <= 0:
        raise ValueError("Payment amount must be positive.")

    amount_str = str(amount)

    try:
        conn.execute("BEGIN")

        # 1. Create Vendor Payment Record
        pay_sql = """
            INSERT INTO VendorPayments
            (VendorID, PaymentDate, Amount, PaymentMethod, Reference, BankAccountID, CreatedBy, CreationDate)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        cursor = conn.cursor()
        cursor.execute(pay_sql, (vendor_id, payment_date, amount_str, payment_method, reference, bank_account_id, created_by_employee_id))
        payment_id = cursor.lastrowid

        # 2. Update Bank Account Balance (Decrease)
        bal_sql = "UPDATE BankAccounts SET CurrentBalance = CurrentBalance - ? WHERE BankAccountID = ?"
        conn.execute(bal_sql, (amount_str, bank_account_id))

        # 3. Generate General Ledger Entries
        gl_entries = [
            # Debit Accounts Payable
            (ap_account_id, amount, Decimal('0.00'), f"Vendor Payment {reference or payment_id}"),
            # Credit Cash
            (cash_account_id, Decimal('0.00'), amount, f"Vendor Payment {reference or payment_id}")
        ]
        _generate_gl_entries(conn, gl_entries, created_by_employee_id, entry_type='VendorPayment', reference=f"VendPmtID:{payment_id}")

        conn.commit()
        return payment_id
    except Exception as e:
        print(f"Error in record_simple_vendor_payment: {e}")
        conn.rollback()
        return None

def list_open_vendor_bills(conn: sqlite3.Connection, vendor_id: int):
    """
    Shows all bills for a specific vendor that are not yet fully paid.

    Args:
        conn: Database connection object.
        vendor_id: The ID of the vendor.

    Returns:
        list: A list of dictionaries representing open bills, or None on failure.
    """
    # Uses the generated Balance column
    sql = """
        SELECT BillID, BillNumber, BillDate, DueDate, TotalAmount, PaidAmount, Balance, Status
        FROM Bills
        WHERE VendorID = ?
        AND Status NOT IN ('Paid', 'Cancelled', 'Draft')
        AND Balance > 0.00
        ORDER BY DueDate ASC
    """
    return _execute_sql(conn, sql, (vendor_id,), fetchall=True)


def apply_full_payment_to_bill(conn: sqlite3.Connection, payment_id: int, bill_id: int):
    """
    Allocates a single vendor payment to fully pay off one specific bill.
    NOTE: Simplified version. Assumes payment amount >= bill balance.
          Does not handle partial payments or allocation tables. Updates bill directly.

    Args:
        conn: Database connection object.
        payment_id: The ID of the VendorPayments record.
        bill_id: The ID of the Bill to be paid.

    Returns:
        bool: True on success, False on failure (e.g., bill not found, already paid, payment insufficient).
    """
    try:
        conn.execute("BEGIN")

        # 1. Get Payment Amount
        payment_sql = "SELECT Amount FROM VendorPayments WHERE PaymentID = ?"
        payment_info = _execute_sql(conn, payment_sql, (payment_id,), fetchone=True)
        if not payment_info:
            print(f"Error: PaymentID {payment_id} not found.")
            conn.rollback()
            return False
        payment_amount = Decimal(payment_info['Amount'])

        # 2. Get Bill Balance and Status (Balance is generated)
        bill_sql = "SELECT Balance, Status, TotalAmount FROM Bills WHERE BillID = ?"
        bill_info = _execute_sql(conn, bill_sql, (bill_id,), fetchone=True)
        if not bill_info:
            print(f"Error: BillID {bill_id} not found.")
            conn.rollback()
            return False

        bill_balance = Decimal(bill_info['Balance'] or '0.00')
        bill_status = bill_info['Status']
        bill_total = Decimal(bill_info['TotalAmount'])

        if bill_status == 'Paid' or bill_balance <= 0:
            print(f"Info: BillID {bill_id} is already paid or has zero balance.")
            conn.rollback() # Treat as non-actionable / potential error state
            return False

        # 3. Check if payment is sufficient
        if payment_amount < bill_balance:
            print(f"Error: Payment amount {payment_amount} is less than bill balance {bill_balance}.")
            conn.rollback()
            return False

        # 4. Update Bill: Set PaidAmount = TotalAmount, Status = 'Paid'
        #    The 'Balance' column will update automatically since it's generated.
        update_sql = """
            UPDATE Bills
            SET PaidAmount = TotalAmount,
                Status = 'Paid'
            WHERE BillID = ?
        """
        cursor = conn.cursor()
        cursor.execute(update_sql, (bill_id,))
        updated_rows = cursor.rowcount

        # 5. Optionally link payment and bill
        # note_sql = "UPDATE VendorPayments SET Notes = Notes || ? WHERE PaymentID = ?"
        # conn.execute(note_sql, (f'\nApplied to BillID {bill_id}', payment_id))

        conn.commit()
        return updated_rows > 0

    except Exception as e:
        print(f"Error in apply_full_payment_to_bill: {e}")
        conn.rollback()
        return False

def get_total_accounts_payable(conn: sqlite3.Connection):
    """
    Calculates the total amount currently owed to all vendors (sum of positive balances).

    Args:
        conn: Database connection object.

    Returns:
        Decimal: The total outstanding AP balance, or Decimal('0.00') on failure/no open bills.
    """
    # Use the generated Balance column
    sql = """
        SELECT SUM(Balance) as TotalAP
        FROM Bills
        WHERE Status NOT IN ('Paid', 'Cancelled', 'Draft')
        AND Balance > 0.00
    """
    result = _execute_sql(conn, sql, fetchone=True)
    return result['TotalAP'] if result and result['TotalAP'] else Decimal('0.00')

def void_bill(conn: sqlite3.Connection, bill_id: int, ap_account_id: int, expense_account_id: int, void_by_employee_id: int):
    """
    Marks an existing vendor bill as Cancelled and reverses its GL impact.
    Only possible if the bill has not been paid at all.

    Args:
        conn: Database connection object.
        bill_id: The ID of the bill to void.
        ap_account_id: The ChartOfAccounts ID for Accounts Payable used in the original entry.
        expense_account_id: The ChartOfAccounts ID for the Expense used in the original entry.
                            (NOTE: Simplified, assumes single expense line item for reversal)
        void_by_employee_id: EmployeeID performing the void action.

    Returns:
        bool: True on success, False on failure (e.g., bill not found, already paid, error).
    """
    try:
        conn.execute("BEGIN")

        # 1. Check Bill Status and Paid Amount
        check_sql = "SELECT PaidAmount, Status, TotalAmount FROM Bills WHERE BillID = ?"
        bill_info = _execute_sql(conn, check_sql, (bill_id,), fetchone=True)

        if not bill_info:
            print(f"Error: BillID {bill_id} not found.")
            conn.rollback()
            return False

        paid_amount = Decimal(bill_info['PaidAmount'] or '0.00')
        status = bill_info['Status']
        total_amount = Decimal(bill_info['TotalAmount'])

        if paid_amount > 0:
            print(f"Error: Cannot void BillID {bill_id} because payments are recorded (PaidAmount: {paid_amount}).")
            conn.rollback()
            return False
        if status == 'Paid' or status == 'Cancelled':
             print(f"Error: Cannot void BillID {bill_id} with status '{status}'.")
             conn.rollback()
             return False

        # 2. Update Bill Status to 'Cancelled'
        #    The generated Balance column should effectively become zero as TotalAmount - PaidAmount (0)
        update_sql = "UPDATE Bills SET Status = 'Cancelled' WHERE BillID = ?" # Keep PaidAmount = 0
        cursor = conn.cursor()
        cursor.execute(update_sql, (bill_id,))
        updated_rows = cursor.rowcount

        if updated_rows == 0:
             print(f"Error: Failed to update status for BillID {bill_id}.")
             conn.rollback()
             return False

        # 3. Generate Reversing General Ledger Entries (if original GL was posted)
        #    Debit Accounts Payable
        #    Credit Expense Account(s)
        #    NOTE: This assumes the original entry was Dr Expense / Cr AP for total_amount.
        #          If multiple BillItems existed hitting different expense accounts,
        #          this reversal needs to be more complex, looking up BillItems.
        #          For simplicity, we use the provided single expense_account_id.
        if total_amount > 0:
            gl_entries = [
                # Debit AP (Reverse original Credit)
                (ap_account_id, total_amount, Decimal('0.00'), f"Void BillID {bill_id}"),
                # Credit Expense (Reverse original Debit)
                (expense_account_id, Decimal('0.00'), total_amount, f"Void BillID {bill_id}")
            ]
            _generate_gl_entries(conn, gl_entries, void_by_employee_id, entry_type='BillVoid', reference=f"VoidBillID:{bill_id}")

        conn.commit()
        return True

    except Exception as e:
        print(f"Error in void_bill: {e}")
        conn.rollback()
        return False

# =============================================
# Payroll Functions (Skipped due to missing schema)
# =============================================
# view_employee_payroll_info - Requires EmployeesPayrollInfo table
# calculate_gross_pay_hourly - Requires EmployeesPayrollInfo table
# calculate_gross_pay_salary - Requires EmployeesPayrollInfo table
# list_active_employees - Requires EmployeesPayrollInfo table

# =============================================
# Reporting & Master Data Functions
# =============================================

def view_chart_of_accounts_list(conn: sqlite3.Connection, include_inactive=False):
    """
    Displays the list of financial accounts used by the company.

    Args:
        conn: Database connection object.
        include_inactive: If True, includes inactive accounts. Defaults to False.

    Returns:
        list: A list of dictionaries representing accounts, or None on failure.
    """
    sql = "SELECT AccountID, AccountNumber, AccountName, AccountType, ParentAccountID, Description, IsActive, BalanceType FROM ChartOfAccounts"
    if not include_inactive:
        sql += " WHERE IsActive = 1"
    sql += " ORDER BY AccountNumber ASC"
    return _execute_sql(conn, sql, fetchall=True)

def add_new_gl_account(conn: sqlite3.Connection, account_number: str, account_name: str, account_type: str, balance_type: str, parent_account_id: int = None, description: str = None):
    """
    Creates a new account in the Chart of Accounts.

    Args:
        conn: Database connection object.
        account_number: The unique account number (required).
        account_name: The name of the account (required).
        account_type: Type ('Asset', 'Liability', 'Equity', 'Revenue', 'Expense').
        balance_type: Normal balance ('Debit', 'Credit').
        parent_account_id: Optional ID of the parent account for hierarchical structure.
        description: Optional description for the account.

    Returns:
        int: The ID of the newly created account, or None on failure.
    """
    sql = """
        INSERT INTO ChartOfAccounts
        (AccountNumber, AccountName, AccountType, ParentAccountID, Description, IsActive, BalanceType)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """
    params = (account_number, account_name, account_type, parent_account_id, description, balance_type)
    try:
        # Check constraints manually before insert as safeguard
        if account_type not in ('Asset', 'Liability', 'Equity', 'Revenue', 'Expense'):
            raise ValueError(f"Invalid AccountType: {account_type}")
        if balance_type not in ('Debit', 'Credit'):
             raise ValueError(f"Invalid BalanceType: {balance_type}")

        return _execute_sql(conn, sql, params, commit=True)
    except sqlite3.IntegrityError as e:
         print(f"Error adding GL account (likely duplicate AccountNumber {account_number} or invalid ParentAccountID): {e}")
         conn.rollback() # Ensure rollback if commit=True failed midway
         return None
    except ValueError as e:
        print(f"Validation Error: {e}")
        conn.rollback()
        return None
    except Exception as e:
        print(f"Error in add_new_gl_account: {e}")
        conn.rollback()
        return None

def view_account_details(conn: sqlite3.Connection, account_id: int):
    """
    Retrieves details for a specific General Ledger account.

    Args:
        conn: Database connection object.
        account_id: The ID of the account to retrieve.

    Returns:
        dict: A dictionary containing account details, or None if not found.
    """
    sql = "SELECT * FROM ChartOfAccounts WHERE AccountID = ?"
    return _execute_sql(conn, sql, (account_id,), fetchone=True)

def generate_trial_balance(conn: sqlite3.Connection, report_date: str = None):
    """
    Creates a list of all active GL accounts and their calculated balances
    as of a specific date (or current if date is None) to ensure debits equal credits.

    Args:
        conn: Database connection object.
        report_date: The date (YYYY-MM-DD) to calculate balances up to (inclusive).
                     If None, uses all entries.

    Returns:
        dict: A dictionary containing 'accounts' (list of dicts with account info & balances)
              and 'totals' (dict with total debits and credits), or None on failure.
              Returns {'accounts': [], 'totals': {'debit': 0, 'credit': 0}} if no accounts.
    """
    accounts_sql = """
        SELECT AccountID, AccountNumber, AccountName, BalanceType
        FROM ChartOfAccounts
        WHERE IsActive = 1
        ORDER BY AccountNumber
    """
    active_accounts = _execute_sql(conn, accounts_sql, fetchall=True)

    if active_accounts is None: # Indicates an error occurred
        return None
    if not active_accounts:
        return {'accounts': [], 'totals': {'debit': Decimal('0.00'), 'credit': Decimal('0.00')}}

    trial_balance_accounts = []
    total_debits = Decimal('0.00')
    total_credits = Decimal('0.00')

    gl_sql_base = """
        SELECT SUM(DebitAmount) as TotalDebit, SUM(CreditAmount) as TotalCredit
        FROM GeneralLedger
        WHERE AccountID = ?
    """
    gl_params_base = []

    if report_date:
        gl_sql_base += " AND EntryDate <= ?"
        gl_params_base.append(report_date)

    try:
        for account in active_accounts:
            account_id = account['AccountID']
            balance_type = account['BalanceType']
            gl_params = tuple([account_id] + gl_params_base)

            balance_result = _execute_sql(conn, gl_sql_base, gl_params, fetchone=True)

            debit_sum = balance_result['TotalDebit'] if balance_result and balance_result['TotalDebit'] else Decimal('0.00')
            credit_sum = balance_result['TotalCredit'] if balance_result and balance_result['TotalCredit'] else Decimal('0.00')

            balance = Decimal('0.00')
            debit_balance = Decimal('0.00')
            credit_balance = Decimal('0.00')

            if balance_type == 'Debit':
                balance = debit_sum - credit_sum
            elif balance_type == 'Credit':
                balance = credit_sum - debit_sum
            else: # Should not happen
                 balance = debit_sum - credit_sum # Default convention

            if balance > 0:
                if balance_type == 'Debit':
                    debit_balance = balance
                    total_debits += balance
                else: # Credit balance type
                    credit_balance = balance
                    total_credits += balance
            elif balance < 0:
                 # Contra-balance situation
                if balance_type == 'Debit':
                    credit_balance = -balance # Show as positive credit
                    total_credits += -balance
                else: # Credit balance type
                    debit_balance = -balance # Show as positive debit
                    total_debits += -balance
            # If balance is zero, both debit_balance and credit_balance remain 0

            trial_balance_accounts.append({
                'AccountID': account_id,
                'AccountNumber': account['AccountNumber'],
                'AccountName': account['AccountName'],
                'Debit': debit_balance,
                'Credit': credit_balance
            })

        return {
            'accounts': trial_balance_accounts,
            'totals': {
                'debit': total_debits,
                'credit': total_credits
            }
        }
    except Exception as e:
        print(f"Error generating trial balance: {e}")
        return None

# =============================================
# Fixed Assets Functions (Simplified)
# =============================================

def record_fixed_asset_purchase(conn: sqlite3.Connection, asset_name: str, purchase_date: str, purchase_cost: Decimal, useful_life_years: int, depreciation_method: str, asset_account_id: int, cash_or_ap_account_id: int, created_by_employee_id: int):
    """
    Logs the acquisition of a new fixed asset and posts the initial GL entry.
    NOTE: Does not create FixedAssets table entries as it's missing from schema.
          Only performs the GL posting part. Assumes payment decreases cash/increases AP.

    Args:
        conn: Database connection object.
        asset_name: Description of the asset.
        purchase_date: Date of purchase (YYYY-MM-DD).
        purchase_cost: Cost of the asset (positive Decimal).
        useful_life_years: Estimated useful life (required for future depreciation calc, not used here).
        depreciation_method: e.g., 'Straight-line' (not used here).
        asset_account_id: The ChartOfAccounts ID for the fixed asset category.
        cash_or_ap_account_id: The ChartOfAccounts ID for Cash (if paid cash) or AP (if purchased on credit).
        created_by_employee_id: EmployeeID recording the purchase.

    Returns:
        bool: True on success, False on failure.
    """
    if purchase_cost <= 0:
        raise ValueError("Purchase cost must be positive.")

    try:
        conn.execute("BEGIN")

        # Generate General Ledger Entries for acquisition
        # Debit Fixed Asset Account
        # Credit Cash or Accounts Payable
        gl_entries = [
            (asset_account_id, purchase_cost, Decimal('0.00'), f"Purchase Asset: {asset_name}"),
            (cash_or_ap_account_id, Decimal('0.00'), purchase_cost, f"Purchase Asset: {asset_name}")
        ]
        _generate_gl_entries(conn, gl_entries, created_by_employee_id, entry_type='AssetPurchase', reference=f"Asset:{asset_name}")

        # TODO: Insert into a 'FixedAssets' table here if it existed.
        # Example:
        # fa_sql = "INSERT INTO FixedAssets (AssetName, PurchaseDate, PurchaseCost, ...) VALUES (?, ?, ?, ...)"
        # conn.execute(fa_sql, (asset_name, purchase_date, str(purchase_cost), ...))

        conn.commit()
        return True
    except Exception as e:
        print(f"Error in record_fixed_asset_purchase: {e}")
        conn.rollback()
        return False

# view_active_fixed_assets_list - Requires FixedAssets table

# =============================================
# Inventory Functions (Skipped due to missing schema)
# =============================================
# check_stock_level_for_item - Requires StockMovements, InventoryItems tables
# view_inventory_item_details - Requires InventoryItems, Products tables

# =============================================
# Tax Functions
# =============================================

def view_active_tax_rates(conn: sqlite3.Connection):
    """
    Displays the list of tax rates currently marked as active.

    Args:
        conn: Database connection object.

    Returns:
        list: A list of dictionaries representing active tax rates, or None on failure.
    """
    # Note: Schema doesn't have EffectiveDate/EndDate, only IsActive
    sql = "SELECT TaxRateID, TaxName, Rate, Description FROM TaxRates WHERE IsActive = 1 ORDER BY TaxName"
    return _execute_sql(conn, sql, fetchall=True)

# =============================================
# Profit & Loss Functions (Calculated from GL)
# =============================================

def calculate_total_revenue_for_period(conn: sqlite3.Connection, start_date: str, end_date: str):
    """
    Calculates the total revenue recorded within a specific date range based on GL entries.

    Args:
        conn: Database connection object.
        start_date: Start date of the period (YYYY-MM-DD).
        end_date: End date of the period (YYYY-MM-DD).

    Returns:
        Decimal: The total revenue (Credits - Debits for Revenue accounts), or Decimal('0.00').
    """
    sql = """
        SELECT SUM(gl.CreditAmount) - SUM(gl.DebitAmount) as TotalRevenue
        FROM GeneralLedger gl
        JOIN ChartOfAccounts coa ON gl.AccountID = coa.AccountID
        WHERE coa.AccountType = 'Revenue'
        AND gl.EntryDate BETWEEN ? AND ?
    """
    result = _execute_sql(conn, sql, (start_date, end_date), fetchone=True)
    return result['TotalRevenue'] if result and result['TotalRevenue'] else Decimal('0.00')

def calculate_total_expenses_for_period(conn: sqlite3.Connection, start_date: str, end_date: str):
    """
    Calculates the total expenses recorded within a specific date range based on GL entries.

    Args:
        conn: Database connection object.
        start_date: Start date of the period (YYYY-MM-DD).
        end_date: End date of the period (YYYY-MM-DD).

    Returns:
        Decimal: The total expenses (Debits - Credits for Expense accounts), or Decimal('0.00').
    """
    sql = """
        SELECT SUM(gl.DebitAmount) - SUM(gl.CreditAmount) as TotalExpenses
        FROM GeneralLedger gl
        JOIN ChartOfAccounts coa ON gl.AccountID = coa.AccountID
        WHERE coa.AccountType = 'Expense'
        AND gl.EntryDate BETWEEN ? AND ?
    """
    result = _execute_sql(conn, sql, (start_date, end_date), fetchone=True)
    return result['TotalExpenses'] if result and result['TotalExpenses'] else Decimal('0.00')

# =============================================
# Cash Flow Functions (Calculated from CashTransactions)
# =============================================

def calculate_net_cash_change_for_period(conn: sqlite3.Connection, start_date: str, end_date: str):
    """
    Determines the net increase or decrease in cash across all bank accounts
    for a given period by summing CashTransactions.

    Args:
        conn: Database connection object.
        start_date: Start date of the period (YYYY-MM-DD).
        end_date: End date of the period (YYYY-MM-DD).

    Returns:
        Decimal: The net change in cash (Deposits - Withdrawals), or Decimal('0.00').
    """
    # Assumes Amount is always positive, TransactionType determines flow
    sql = """
        SELECT
            SUM(CASE WHEN TransactionType = 'Deposit' THEN Amount ELSE 0 END) -
            SUM(CASE WHEN TransactionType = 'Withdrawal' THEN Amount ELSE 0 END)
            -- Transfers net out to zero in this calculation if using Amount directly
            -- If Amount was signed, it would be simpler: SUM(Amount)
            as NetCashChange
        FROM CashTransactions
        WHERE TransactionDate BETWEEN ? AND ?
        -- Exclude transfers if they shouldn't affect net change from operations/investing/financing
        -- AND TransactionType != 'Transfer'
        -- Or handle transfers carefully if one side is internal cash, other external
    """
    result = _execute_sql(conn, sql, (start_date, end_date), fetchone=True)
    return result['NetCashChange'] if result and result['NetCashChange'] else Decimal('0.00')

# =============================================
# Audit Functions (Assuming AuditLogs table is populated)
# =============================================

def view_recent_system_logins(conn: sqlite3.Connection, limit: int = 20):
    """
    Shows the most recent login activities recorded in the audit log.
    NOTE: Assumes 'Login' action type exists and ChangedBy links to Employees.

    Args:
        conn: Database connection object.
        limit: The maximum number of login events to show.

    Returns:
        list: List of dictionaries representing login events, or None on failure.
    """
    sql = """
        SELECT a.LogID, a.ChangeDate, a.IPAddress, a.Description, -- Added Description assuming it might hold success/failure
               e.EmployeeID, e.FirstName, e.LastName, e.Email
        FROM AuditLogs a
        LEFT JOIN Employees e ON a.ChangedBy = e.EmployeeID
        WHERE a.ActionType = 'Login' -- Assuming 'Login' is used for ActionType
        ORDER BY a.ChangeDate DESC
        LIMIT ?
    """
    # If 'Login' isn't an ActionType, adjust WHERE clause accordingly
    # (e.g., WHERE TableName = 'System' AND ActionType = 'Authenticate')
    return _execute_sql(conn, sql, (limit,), fetchall=True)


def view_user_activity(conn: sqlite3.Connection, employee_id: int, limit: int = 50):
    """
    Lists the recent actions performed by a specific employee recorded in the audit log.

    Args:
        conn: Database connection object.
        employee_id: The EmployeeID of the user.
        limit: The maximum number of log entries to show.

    Returns:
        list: List of dictionaries representing audit log entries for the user, or None on failure.
    """
    sql = """
        SELECT LogID, TableName, RecordID, ActionType, OldValue, NewValue, ChangeDate, IPAddress
        FROM AuditLogs
        WHERE ChangedBy = ?
        ORDER BY ChangeDate DESC
        LIMIT ?
    """
    return _execute_sql(conn, sql, (employee_id, limit), fetchall=True)

def view_record_change_history(conn: sqlite3.Connection, table_name: str, record_id: int):
    """
    Displays the history of changes recorded for a specific entity (e.g., a vendor or invoice).

    Args:
        conn: Database connection object.
        table_name: The name of the table (e.g., 'Vendors', 'Invoices').
        record_id: The primary key ID of the record in that table.

    Returns:
        list: List of dictionaries representing change history, or None on failure.
    """
    sql = """
        SELECT a.LogID, a.ActionType, a.OldValue, a.NewValue, a.ChangeDate, a.IPAddress,
               e.EmployeeID, e.FirstName, e.LastName
        FROM AuditLogs a
        LEFT JOIN Employees e ON a.ChangedBy = e.EmployeeID
        WHERE a.TableName = ? AND a.RecordID = ?
        ORDER BY a.ChangeDate DESC
    """
    return _execute_sql(conn, sql, (table_name, record_id), fetchall=True)


# =============================================
# Budgeting Functions
# =============================================

def list_current_budgets(conn: sqlite3.Connection, status: str = 'Approved'):
    """
    Displays a list of budgets for the current fiscal year with a specific status.

    Args:
        conn: Database connection object.
        status: The status to filter by (e.g., 'Approved', 'Draft'). Defaults to 'Approved'.

    Returns:
        list: List of dictionaries representing budgets, or None on failure.
              Returns empty list if no matching budgets.
    """
    # Find current fiscal year (assuming only one is open or based on current date)
    # This logic might need refinement based on business rules
    today = datetime.date.today().isoformat()
    fy_sql = "SELECT FiscalYearID FROM FiscalYears WHERE ? BETWEEN StartDate AND EndDate AND IsClosed = 0 LIMIT 1"
    fy_result = _execute_sql(conn, fy_sql, (today,), fetchone=True)

    if not fy_result:
        print("Warning: No active fiscal year found for today's date.")
        # Optionally try to find the latest non-closed year
        fy_sql_fallback = "SELECT FiscalYearID FROM FiscalYears WHERE IsClosed = 0 ORDER BY EndDate DESC LIMIT 1"
        fy_result = _execute_sql(conn, fy_sql_fallback, fetchone=True)
        if not fy_result:
             print("Error: No open fiscal year found.")
             return None # Or return empty list?
        # return []

    current_fiscal_year_id = fy_result['FiscalYearID']

    # List budgets for that year and status
    budget_sql = """
        SELECT b.BudgetID, b.BudgetName, b.Description, b.Status, b.CreationDate, b.ApprovalDate,
               fy.StartDate as FiscalYearStart, fy.EndDate as FiscalYearEnd,
               d.DepartmentName,
               creator.FirstName || ' ' || creator.LastName as CreatedByName,
               approver.FirstName || ' ' || approver.LastName as ApprovedByName
        FROM Budgets b
        JOIN FiscalYears fy ON b.FiscalYearID = fy.FiscalYearID
        LEFT JOIN Departments d ON b.DepartmentID = d.DepartmentID
        LEFT JOIN Employees creator ON b.CreatedBy = creator.EmployeeID
        LEFT JOIN Employees approver ON b.ApprovedBy = approver.EmployeeID
        WHERE b.FiscalYearID = ? AND b.Status = ?
        ORDER BY b.BudgetName
    """
    return _execute_sql(conn, budget_sql, (current_fiscal_year_id, status), fetchall=True)

def view_budget_details(conn: sqlite3.Connection, budget_id: int):
    """
    Shows the header information for a specific budget.

    Args:
        conn: Database connection object.
        budget_id: The ID of the budget to view.

    Returns:
        dict: Dictionary with budget header details, or None if not found.
    """
    budget_sql = """
        SELECT b.BudgetID, b.BudgetName, b.Description, b.Status, b.CreationDate, b.ApprovalDate,
               fy.StartDate as FiscalYearStart, fy.EndDate as FiscalYearEnd, fy.FiscalYearID,
               d.DepartmentName, d.DepartmentID,
               creator.FirstName || ' ' || creator.LastName as CreatedByName, creator.EmployeeID as CreatedByID,
               approver.FirstName || ' ' || approver.LastName as ApprovedByName, approver.EmployeeID as ApprovedByID
        FROM Budgets b
        JOIN FiscalYears fy ON b.FiscalYearID = fy.FiscalYearID
        LEFT JOIN Departments d ON b.DepartmentID = d.DepartmentID
        LEFT JOIN Employees creator ON b.CreatedBy = creator.EmployeeID
        LEFT JOIN Employees approver ON b.ApprovedBy = approver.EmployeeID
        WHERE b.BudgetID = ?
    """
    return _execute_sql(conn, budget_sql, (budget_id,), fetchone=True)

def view_budgeted_amount(conn: sqlite3.Connection, budget_id: int, account_id: int, period_id: int):
    """
    Retrieves the budgeted amount for a specific account in a specific period within a budget.

    Args:
        conn: Database connection object.
        budget_id: The ID of the budget.
        account_id: The ChartOfAccounts ID.
        period_id: The FiscalPeriods ID.

    Returns:
        Decimal: The PlannedAmount for the budget item, or None if not found or on error.
    """
    sql = """
        SELECT PlannedAmount
        FROM BudgetItems
        WHERE BudgetID = ? AND AccountID = ? AND PeriodID = ?
    """
    result = _execute_sql(conn, sql, (budget_id, account_id, period_id), fetchone=True)
    # Ensure Decimal conversion if needed based on connection setup
    return result['PlannedAmount'] if result else None


# =============================================
# Financial Reporting Functions
# =============================================

def list_recent_reports(conn: sqlite3.Connection, limit: int = 5):
    """
    Show a list of the most recently generated financial reports.

    Args:
        conn: Database connection object.
        limit: The maximum number of reports to list.

    Returns:
        list: List of dictionaries representing recent reports, or None on failure.
    """
    sql = """
        SELECT fr.ReportID, fr.ReportName, fr.ReportType, fr.GenerationDate, fr.Description,
               e.FirstName || ' ' || e.LastName as GeneratedByName
        FROM FinancialReports fr
        JOIN Employees e ON fr.GeneratedBy = e.EmployeeID
        ORDER BY fr.GenerationDate DESC
        LIMIT ?
    """
    return _execute_sql(conn, sql, (limit,), fetchall=True)

def view_report_metadata(conn: sqlite3.Connection, report_id: int):
    """
    Display the details about a specific generated report (type, period, generator, etc.).
    Does not retrieve the actual report data blob/file.

    Args:
        conn: Database connection object.
        report_id: The ID of the report to view.

    Returns:
        dict: Dictionary containing report metadata, or None if not found.
    """
    sql = """
        SELECT fr.ReportID, fr.ReportName, fr.ReportType, fr.GenerationDate, fr.Parameters, fr.Description,
               fy.StartDate as FiscalYearStart, fy.EndDate as FiscalYearEnd,
               fp.PeriodNumber as FiscalPeriod, fp.StartDate as PeriodStart, fp.EndDate as PeriodEnd,
               e.FirstName || ' ' || e.LastName as GeneratedByName, e.EmployeeID as GeneratedByID
        FROM FinancialReports fr
        LEFT JOIN FiscalYears fy ON fr.FiscalYearID = fy.FiscalYearID
        LEFT JOIN FiscalPeriods fp ON fr.PeriodID = fp.PeriodID
        JOIN Employees e ON fr.GeneratedBy = e.EmployeeID
        WHERE fr.ReportID = ?
    """
    # Note: Parameters field assumed to be TEXT, might need JSON parsing if stored as JSON
    return _execute_sql(conn, sql, (report_id,), fetchone=True)