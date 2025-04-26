import sqlite3
import datetime
from decimal import Decimal, ROUND_HALF_UP # Import ROUND_HALF_UP for standard rounding
import os
import sys
import traceback # Import traceback for detailed error printing

# Add the project root to the Python path to find utility_functions
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import the functions to be tested
try:
    from utility_functions.utilities import (
        # Payroll Functions
        view_employee_payroll_info,
        calculate_gross_pay_hourly,
        calculate_gross_pay_salary,
        list_active_employees_for_payroll,
    )
    print("Successfully imported utility functions.")
except ImportError as e:
    print(f"Error importing utility functions: {e}")
    print(f"Looked in sys.path entries including: {project_root}")
    sys.exit(1)

# --- Database File Configuration ---
DATABASE_FILE = './database/financial_agent.db'
print(f"Looking for database at: {os.path.abspath(DATABASE_FILE)}")

# --- Database Connection ---
def get_db_connection():
    """Establishes database connection with Decimal support."""
    if not os.path.exists(DATABASE_FILE):
        raise FileNotFoundError(f"Database file '{os.path.abspath(DATABASE_FILE)}' not found. "
                              "Please ensure the path is correct and the SQL setup script has been run.")

    conn = sqlite3.connect(DATABASE_FILE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row # Access columns by name
    conn.execute("PRAGMA foreign_keys = ON;")

    sqlite3.register_adapter(Decimal, str)
    sqlite3.register_converter("DECIMAL", lambda b: Decimal(b.decode('utf-8')))
    sqlite3.register_converter("REAL", lambda b: Decimal(b.decode('utf-8')))

    print("Database connection established with Decimal support.")
    return conn

# --- Test Execution ---
if __name__ == "__main__":
    conn = None
    # Define expected IDs based on sample data
    HOURLY_USER_ID = 9          # James Thomas (Accountant, Hourly, Active)
    SALARY_USER_ID = 2          # Jane Doe (CFO, Salary, Active)
    # User 17 is ACTIVE in sample data, used for testing active hourly calculation
    ACTIVE_HOURLY_USER_ID_2 = 17 # Daniel Hall (AP Spec, Hourly, Active)
    INVALID_USER_ID = 999
    # NOTE: No user is marked 'Inactive' in the current Employees sample data.
    # Add one in schema.sql if testing inactive exclusion is needed.

    # Expected values based on sample data
    expected_hourly_rate_9 = Decimal('40.87')
    expected_hourly_rate_17 = Decimal('36.06') # Daniel Hall's rate
    expected_salary_2 = Decimal('200000.00') # Jane Doe's salary
    expected_salary_semi_monthly_2 = (expected_salary_2 / Decimal(24)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) # 8333.33
    expected_hourly_gross_40_user9 = (expected_hourly_rate_9 * Decimal(40)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) # 1634.80
    expected_hourly_gross_40_5OT_user9 = (expected_hourly_rate_9 * Decimal(40) + expected_hourly_rate_9 * Decimal(5) * Decimal(1.5)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) # 1941.33
    expected_hourly_gross_40_user17 = (expected_hourly_rate_17 * Decimal(40)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) # 1442.40

    # --- Expected Active Employee Count ---
    # Count employees with Status='Active' AND who have a record in EmployeePayrollInfo
    # In sample data: IDs 1-20 are Active and have payroll info.
    expected_active_count = 20


    try:
        conn = get_db_connection()
        print(f"--- Connected to Database: {os.path.abspath(DATABASE_FILE)} ---")

        print("\n--- Testing Payroll Functions ---")

        # == 1. Test view_employee_payroll_info ==
        print("\n1. Testing view_employee_payroll_info...")
        # Test Case 1.1: Valid Hourly Employee
        print("   Test 1.1: Fetching active hourly employee (ID 9)...")
        payroll_info_hourly = view_employee_payroll_info(conn, HOURLY_USER_ID)
        # Corrected Check: isinstance dict
        if payroll_info_hourly and isinstance(payroll_info_hourly, dict):
            print(f"      PASS: Retrieved payroll info for EmployeeID {HOURLY_USER_ID}.")
            assert payroll_info_hourly['EmployeeID'] == HOURLY_USER_ID, "EmployeeID mismatch"
            assert payroll_info_hourly['PayType'] == 'Hourly', "PayType mismatch"
            assert isinstance(payroll_info_hourly['HourlyRate'], Decimal), f"HourlyRate type mismatch ({type(payroll_info_hourly['HourlyRate'])})"
            assert payroll_info_hourly['HourlyRate'] == expected_hourly_rate_9, f"HourlyRate value mismatch (Got {payroll_info_hourly['HourlyRate']}, Expected {expected_hourly_rate_9})"
            assert payroll_info_hourly['EmployeeStatus'] == 'Active', f"EmployeeStatus mismatch (Got {payroll_info_hourly['EmployeeStatus']})"
            print(f"         Details: Name={payroll_info_hourly['FirstName']} {payroll_info_hourly['LastName']}, PayType={payroll_info_hourly['PayType']}, Rate={payroll_info_hourly['HourlyRate']:.2f}, Status={payroll_info_hourly['EmployeeStatus']}")
        else:
            print(f"      FAIL: Failed to retrieve or invalid format for EmployeeID {HOURLY_USER_ID}. Type: {type(payroll_info_hourly)}")

        # Test Case 1.2: Valid Salary Employee
        print("   Test 1.2: Fetching active salary employee (ID 2)...")
        payroll_info_salary = view_employee_payroll_info(conn, SALARY_USER_ID)
         # Corrected Check: isinstance dict
        if payroll_info_salary and isinstance(payroll_info_salary, dict):
            print(f"      PASS: Retrieved payroll info for EmployeeID {SALARY_USER_ID}.")
            assert payroll_info_salary['EmployeeID'] == SALARY_USER_ID, "EmployeeID mismatch"
            assert payroll_info_salary['PayType'] == 'Salary', "PayType mismatch"
            assert isinstance(payroll_info_salary['AnnualSalary'], Decimal), f"AnnualSalary type mismatch ({type(payroll_info_salary['AnnualSalary'])})"
            assert payroll_info_salary['AnnualSalary'] == expected_salary_2, f"AnnualSalary value mismatch (Got {payroll_info_salary['AnnualSalary']}, Expected {expected_salary_2})"
            assert payroll_info_salary['EmployeeStatus'] == 'Active', f"EmployeeStatus mismatch (Got {payroll_info_salary['EmployeeStatus']})"
            print(f"         Details: Name={payroll_info_salary['FirstName']} {payroll_info_salary['LastName']}, PayType={payroll_info_salary['PayType']}, Salary={payroll_info_salary['AnnualSalary']:.2f}, Status={payroll_info_salary['EmployeeStatus']}")
        else:
            print(f"      FAIL: Failed to retrieve or invalid format for EmployeeID {SALARY_USER_ID}. Type: {type(payroll_info_salary)}")

        # Test Case 1.3: Fetching another Active Employee (User 17 - was incorrectly labeled inactive before)
        print("   Test 1.3: Fetching active employee (ID 17)...")
        payroll_info_active_17 = view_employee_payroll_info(conn, ACTIVE_HOURLY_USER_ID_2)
         # Corrected Check: isinstance dict
        if payroll_info_active_17 and isinstance(payroll_info_active_17, dict):
            print(f"      PASS: Retrieved payroll info for active EmployeeID {ACTIVE_HOURLY_USER_ID_2}.")
            # Corrected check based on sample data
            assert payroll_info_active_17['EmployeeStatus'] == 'Active', f"EmployeeStatus should be 'Active' (Got {payroll_info_active_17['EmployeeStatus']})"
            print(f"         Details: Name={payroll_info_active_17['FirstName']} {payroll_info_active_17['LastName']}, Status={payroll_info_active_17['EmployeeStatus']}")
        else:
             print(f"      FAIL: Failed to retrieve or invalid format for active EmployeeID {ACTIVE_HOURLY_USER_ID_2}. Type: {type(payroll_info_active_17)}")

        # Test Case 1.4: Invalid UserID
        print("   Test 1.4: Fetching invalid EmployeeID...")
        payroll_info_invalid = view_employee_payroll_info(conn, INVALID_USER_ID)
        if payroll_info_invalid is None:
            print(f"      PASS: Correctly returned None for invalid EmployeeID {INVALID_USER_ID}.")
        else:
            print(f"      FAIL: Expected None for invalid EmployeeID, got {type(payroll_info_invalid)}.")


        # == 2. Test calculate_gross_pay_hourly ==
        print("\n2. Testing calculate_gross_pay_hourly...")
        # Test Case 2.1: Valid Hourly Employee, 40 hours
        print("   Test 2.1: Calculating gross pay for hourly employee (ID 9, 40 reg hours)...")
        try:
            gross_pay_h = calculate_gross_pay_hourly(conn, HOURLY_USER_ID, Decimal('40.00'))
            if gross_pay_h is not None and isinstance(gross_pay_h, Decimal):
                if gross_pay_h == expected_hourly_gross_40_user9:
                    print(f"      PASS: Calculated gross pay correctly: {gross_pay_h:.2f}")
                else:
                    print(f"      FAIL: Calculated gross pay {gross_pay_h:.2f} != Expected {expected_hourly_gross_40_user9:.2f}")
            else:
                print(f"      FAIL: Did not return a Decimal. Returned: {gross_pay_h} (Type: {type(gross_pay_h)})")
        except ValueError as e:
             print(f"      FAIL: Function raised unexpected ValueError: {e}")
        except Exception as e:
             print(f"      FAIL: Function raised unexpected Exception: {type(e).__name__}: {e}")

        # Test Case 2.1b: Valid Hourly Employee, 40 reg, 5 OT hours
        print("   Test 2.1b: Calculating gross pay for hourly employee (ID 9, 40 reg, 5 OT hours)...")
        try:
            gross_pay_h_ot = calculate_gross_pay_hourly(conn, HOURLY_USER_ID, Decimal('40.00'), Decimal('5.00'))
            if gross_pay_h_ot is not None and isinstance(gross_pay_h_ot, Decimal):
                if gross_pay_h_ot == expected_hourly_gross_40_5OT_user9:
                    print(f"      PASS: Calculated gross pay with OT correctly: {gross_pay_h_ot:.2f}")
                else:
                    print(f"      FAIL: Calculated OT gross pay {gross_pay_h_ot:.2f} != Expected {expected_hourly_gross_40_5OT_user9:.2f}")
            else:
                print(f"      FAIL: Did not return a Decimal. Returned: {gross_pay_h_ot} (Type: {type(gross_pay_h_ot)})")
        except ValueError as e:
             print(f"      FAIL: Function raised unexpected ValueError: {e}")
        except Exception as e:
             print(f"      FAIL: Function raised unexpected Exception: {type(e).__name__}: {e}")


        # Test Case 2.2: Valid Hourly Employee, 0 hours
        print("   Test 2.2: Calculating gross pay for hourly employee (ID 9, 0 hours)...")
        try:
            gross_pay_h_zero = calculate_gross_pay_hourly(conn, HOURLY_USER_ID, Decimal('0.00'))
            if gross_pay_h_zero is not None and isinstance(gross_pay_h_zero, Decimal) and gross_pay_h_zero == Decimal('0.00'):
                print(f"      PASS: Calculated zero gross pay correctly: {gross_pay_h_zero:.2f}")
            else:
                print(f"      FAIL: Did not return Decimal('0.00'). Returned: {gross_pay_h_zero} (Type: {type(gross_pay_h_zero)})")
        except ValueError as e:
             print(f"      FAIL: Function raised unexpected ValueError: {e}")
        except Exception as e:
             print(f"      FAIL: Function raised unexpected Exception: {type(e).__name__}: {e}")

        # Test Case 2.3: Try on Salaried Employee (Expect ValueError)
        print("   Test 2.3: Attempting calculation for salaried employee (ID 2)...")
        try:
            calculate_gross_pay_hourly(conn, SALARY_USER_ID, Decimal('40.00'))
            print("      FAIL: Expected ValueError for salaried employee, but none was raised.")
        except ValueError:
             print("      PASS: Correctly raised ValueError for salaried employee.")
        except Exception as e:
            print(f"      FAIL: Expected ValueError, but got different exception: {type(e).__name__}: {e}")

        # Test Case 2.4: Try on *Active* Hourly Employee (ID 17)
        print("   Test 2.4: Attempting calculation for active hourly employee (ID 17, 40 hours)...")
        try:
            gross_pay_h_active17 = calculate_gross_pay_hourly(conn, ACTIVE_HOURLY_USER_ID_2, Decimal('40.00'))
            if gross_pay_h_active17 == expected_hourly_gross_40_user17:
                 print(f"      PASS: Calculated gross pay for active hourly employee (ID 17) correctly: {gross_pay_h_active17:.2f}")
            else:
                 print(f"      FAIL: Incorrect gross pay for active hourly employee (ID 17). Got {gross_pay_h_active17}, Expected {expected_hourly_gross_40_user17}")

        except ValueError as e:
             print(f"      FAIL: Function raised unexpected ValueError for active hourly employee (ID 17): {e}")
        except Exception as e:
             print(f"      FAIL: Function raised unexpected Exception for active hourly employee (ID 17): {type(e).__name__}: {e}")

        # Test Case 2.5: Invalid Hours (Negative)
        print("   Test 2.5: Attempting calculation with negative hours...")
        try:
            calculate_gross_pay_hourly(conn, HOURLY_USER_ID, Decimal('-10.00'))
            print("      FAIL: Expected ValueError for negative hours, but none was raised.")
        except ValueError:
            print("      PASS: Correctly raised ValueError for negative hours.")
        except Exception as e:
            print(f"      FAIL: Expected ValueError, but got different exception: {type(e).__name__}: {e}")

        # Test Case 2.6: Invalid UserID (Expect ValueError)
        print("   Test 2.6: Attempting calculation for invalid EmployeeID...")
        try:
            calculate_gross_pay_hourly(conn, INVALID_USER_ID, Decimal('40.00'))
            print("      FAIL: Expected ValueError for invalid EmployeeID, but none was raised.")
        except ValueError:
            print("      PASS: Correctly raised ValueError for invalid EmployeeID.")
        except Exception as e:
            print(f"      FAIL: Expected ValueError, but got different exception: {type(e).__name__}: {e}")


        # == 3. Test calculate_gross_pay_salary ==
        print("\n3. Testing calculate_gross_pay_salary...")
        # Test Case 3.1: Valid Salaried Employee
        print("   Test 3.1: Calculating gross pay for salaried employee (ID 2)...")
        try:
            gross_pay_s = calculate_gross_pay_salary(conn, SALARY_USER_ID)
            if gross_pay_s is not None and isinstance(gross_pay_s, Decimal):
                if gross_pay_s == expected_salary_semi_monthly_2:
                    print(f"      PASS: Calculated gross pay correctly: {gross_pay_s:.2f}")
                else:
                    print(f"      FAIL: Calculated gross pay {gross_pay_s:.2f} != Expected {expected_salary_semi_monthly_2:.2f}")
            else:
                print(f"      FAIL: Did not return a Decimal. Returned: {gross_pay_s} (Type: {type(gross_pay_s)})")
        except ValueError as e:
             print(f"      FAIL: Function raised unexpected ValueError: {e}")
        except Exception as e:
             print(f"      FAIL: Function raised unexpected Exception: {type(e).__name__}: {e}")

        # Test Case 3.2: Try on Hourly Employee (Expect ValueError)
        print("   Test 3.2: Attempting calculation for hourly employee (ID 9)...")
        try:
            calculate_gross_pay_salary(conn, HOURLY_USER_ID)
            print("      FAIL: Expected ValueError for hourly employee, but none was raised.")
        except ValueError:
             print("      PASS: Correctly raised ValueError for hourly employee.")
        except Exception as e:
            print(f"      FAIL: Expected ValueError, but got different exception: {type(e).__name__}: {e}")

        # Test Case 3.3: Try on Active Hourly Employee (ID 17 - Expect ValueError as it's hourly)
        print("   Test 3.3: Attempting calculation for active hourly employee (ID 17)...")
        try:
            calculate_gross_pay_salary(conn, ACTIVE_HOURLY_USER_ID_2)
            print(f"      FAIL: Expected ValueError for active hourly employee (ID {ACTIVE_HOURLY_USER_ID_2}), but none was raised.")
        except ValueError:
             print(f"      PASS: Correctly raised ValueError for active hourly employee (ID {ACTIVE_HOURLY_USER_ID_2}).")
        except Exception as e:
            print(f"      FAIL: Expected ValueError, but got different exception for active hourly employee: {type(e).__name__}: {e}")

        # Test Case 3.4: Invalid UserID (Expect ValueError)
        print("   Test 3.4: Attempting calculation for invalid EmployeeID...")
        try:
            calculate_gross_pay_salary(conn, INVALID_USER_ID)
            print("      FAIL: Expected ValueError for invalid EmployeeID, but none was raised.")
        except ValueError:
            print("      PASS: Correctly raised ValueError for invalid EmployeeID.")
        except Exception as e:
            print(f"      FAIL: Expected ValueError, but got different exception: {type(e).__name__}: {e}")


        # == 4. Test list_active_employees_for_payroll ==
        print("\n4. Testing list_active_employees_for_payroll...")
        active_employees = list_active_employees_for_payroll(conn)

        if active_employees is not None and isinstance(active_employees, list):
             # Corrected expected count
            print(f"   PASS: Retrieved list of {len(active_employees)} active employees.")
            if len(active_employees) == expected_active_count:
                 print(f"      PASS: Correct number of active employees ({expected_active_count}) returned.")
            else:
                 print(f"      FAIL: Expected {expected_active_count} active employees, but got {len(active_employees)}. Check sample data and function logic.") # Changed WARN to FAIL

            if len(active_employees) > 0:
                # Check type of elements and data types within
                sample_emp = active_employees[0]
                 # Corrected Check: isinstance dict
                if isinstance(sample_emp, dict):
                    print(f"      PASS: List contains dict objects.")
                    print(f"         Sample Active Employee: EmployeeID={sample_emp.get('EmployeeID')}, Name={sample_emp.get('FirstName')} {sample_emp.get('LastName')}, PayType={sample_emp.get('PayType')}")

                    # Check if monetary fields are Decimals
                    type_checks_ok = True
                    hourly_rate_key = 'HourlyRate'
                    salary_key = 'AnnualSalary'

                    for emp_check in active_employees[:5]:
                        if emp_check['PayType'] == 'Hourly' and emp_check.get(hourly_rate_key) is not None and not isinstance(emp_check[hourly_rate_key], Decimal):
                            print(f"      FAIL: {hourly_rate_key} is not Decimal for EmployeeID {emp_check.get('EmployeeID')}, type: {type(emp_check.get(hourly_rate_key))}")
                            type_checks_ok = False
                            break
                        if emp_check['PayType'] == 'Salary' and emp_check.get(salary_key) is not None and not isinstance(emp_check[salary_key], Decimal):
                            print(f"      FAIL: {salary_key} is not Decimal for EmployeeID {emp_check.get('EmployeeID')}, type: {type(emp_check.get(salary_key))}")
                            type_checks_ok = False
                            break
                    if type_checks_ok:
                         print("      PASS: Monetary fields appear to be correct Decimal types in samples.")

                    # Check if *any* inactive user is excluded (if sample data had one)
                    # Since sample data has no inactive users, this check is currently moot.
                    # If you add an inactive user to schema.sql, re-enable a check like this:
                    # inactive_test_id = YOUR_INACTIVE_EMPLOYEE_ID
                    # found_inactive = any(emp['EmployeeID'] == inactive_test_id for emp in active_employees)
                    # if not found_inactive:
                    #     print(f"      PASS: Inactive employee (EmployeeID {inactive_test_id}) correctly excluded (assuming one exists in data).")
                    # else:
                    #     print(f"      FAIL: Inactive employee (EmployeeID {inactive_test_id}) was included in the list.")
                    print("      INFO: Skipping check for inactive employee exclusion as none exist in current sample data.")

                else:
                     print(f"      FAIL: List elements are not dict, type: {type(sample_emp)}")
            else:
                 print("      WARN: Active employees list is empty (check sample data setup).")

        elif active_employees is None:
            print("   FAIL: list_active_employees_for_payroll returned None (check DB errors).")
        else:
            print(f"   FAIL: Expected a list for active employees, got {type(active_employees)}.")


        print("\n--- Payroll Function Tests Complete ---")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
    except sqlite3.Error as e:
        print(f"DATABASE ERROR during testing: {type(e).__name__}: {e}")
        traceback.print_exc()
        if conn:
            try:
                conn.rollback() # Attempt rollback on DB error
                print("   Attempted to rollback transaction.")
            except sqlite3.Error as rb_err:
                print(f"   Rollback failed: {rb_err}")
    except AssertionError as e:
         print(f"\nASSERTION FAILED: {e}")
         traceback.print_exc()
    except Exception as e:
        print(f"\nUNEXPECTED ERROR during testing: {type(e).__name__}: {e}")
        traceback.print_exc()
        if conn:
            try:
                conn.rollback()
                print("   Attempted to rollback transaction due to unexpected error.")
            except sqlite3.Error as rb_err:
                print(f"   Rollback failed: {rb_err}")
    finally:
        if conn:
            conn.close()
            print("\n--- Database Connection Closed ---")