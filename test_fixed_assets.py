import sqlite3
import datetime
from decimal import Decimal
import os
import time
INVENTORY_ASSET_ACCT_ID = 8   # Example: '1140', 'Inventory'
COGS_ACCT_ID = 46             # Example: '5100', 'Cost of Goods Sold'
EQUIPMENT_ASSET_ACCT_ID = 13  # Example: '1213', 'Equipment'
ACCUM_DEPR_EQUIP_ACCT_ID = 16 # Example: '1215', 'Accumulated Depreciation' (May need specific ones per asset type)
DEPR_EXPENSE_ACCT_ID = 50     # Example: '5500', 'Depreciation Expense'
AP_ACCT_ID = 23               # Example: '2110', 'Accounts Payable'
CASH_ACCT_ID = 4              # Example: '1111', 'Cash in Bank'
# Import necessary functions from fm_functions
try:
    from utility_functions.utilities import (
        _execute_sql, # If needed for direct checks
        _generate_gl_entries, # If needed
        record_fixed_asset_purchase_with_fa_table,
        view_active_fixed_assets_list,
        view_gl_account_balance, # For verification
    )
except ImportError:
    print("ERROR: Could not import functions/constants from fm_functions.py.")
    exit()
except NameError:
     print("ERROR: Ensure Account ID constants (e.g., EQUIPMENT_ASSET_ACCT_ID) are defined in fm_functions.py.")
     exit()

DATABASE_FILE = './database/financial_agent.db'# Adjust path if needed

# --- Database Connection ---
def get_db_connection():
    """Establishes database connection with Decimal support."""
    if not os.path.exists(DATABASE_FILE):
        raise FileNotFoundError(f"Database file '{DATABASE_FILE}' not found.")
    conn = sqlite3.connect(DATABASE_FILE, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    sqlite3.register_adapter(Decimal, str)
    sqlite3.register_converter("DECIMAL", lambda b: Decimal(b.decode('utf-8')))
    return conn

# --- Test Execution ---
if __name__ == "__main__":
    conn = None
    test_asset_id = None
    try:
        conn = get_db_connection()
        print(f"--- Connected to Database: {DATABASE_FILE} ---")
        print("\n--- Testing Fixed Assets Functions ---")

        # --- Test Data ---
        test_employee_id = 6 # Sarah Miller (Controller)
        asset_name = f"Test Machine {int(time.time())}"
        asset_tag = f"TEST-ASSET-{int(time.time())}"
        purchase_date = datetime.date.today().isoformat()
        depr_start_date = (datetime.date.today().replace(day=1) + datetime.timedelta(days=32)).replace(day=1).isoformat() # Start next month
        purchase_cost = Decimal('15000.00')
        salvage_value = Decimal('1500.00')
        useful_life = 5 # Years
        depr_method = 'Straight-line'
        # Assume purchase on account (AP)
        cash_or_ap_acct = AP_ACCT_ID

        # == 1. Test record_fixed_asset_purchase_with_fa_table ==
        print(f"\n1. Testing record_fixed_asset_purchase_with_fa_table...")
        initial_asset_acct_balance = view_gl_account_balance(conn, EQUIPMENT_ASSET_ACCT_ID)
        initial_ap_acct_balance = view_gl_account_balance(conn, AP_ACCT_ID)

        test_asset_id = record_fixed_asset_purchase_with_fa_table(
            conn, asset_name, purchase_date, purchase_cost, useful_life,
            depr_method, depr_start_date, EQUIPMENT_ASSET_ACCT_ID,
            ACCUM_DEPR_EQUIP_ACCT_ID, DEPR_EXPENSE_ACCT_ID, cash_or_ap_acct,
            test_employee_id, asset_tag=asset_tag, salvage_value=salvage_value
        )

        if test_asset_id and isinstance(test_asset_id, int):
            print(f"   PASS: Fixed Asset recorded with AssetID: {test_asset_id}")
            # Verification - Check FixedAssets table
            asset_details = _execute_sql(conn, "SELECT * FROM FixedAssets WHERE AssetID = ?", (test_asset_id,), fetchone=True)
            if asset_details and asset_details['AssetName'] == asset_name and abs(Decimal(asset_details['PurchaseCost']) - purchase_cost) < Decimal('0.01'):
                print("      PASS: Asset details verified in FixedAssets table.")
                print(f"         -> Cost: {asset_details['PurchaseCost']}, AccumDepr: {asset_details['AccumulatedDepreciation']}, CurrentValue: {asset_details['CurrentValue']}")
            elif asset_details:
                print("      FAIL: Asset details mismatch in FixedAssets table.")
            else:
                print("      FAIL: Could not retrieve asset details from FixedAssets table.")

            # Verification - Check GL balances
            final_asset_acct_balance = view_gl_account_balance(conn, EQUIPMENT_ASSET_ACCT_ID)
            final_ap_acct_balance = view_gl_account_balance(conn, AP_ACCT_ID)

            expected_asset_acct_balance = initial_asset_acct_balance + purchase_cost # Asset is Debit
            expected_ap_acct_balance = initial_ap_acct_balance + purchase_cost    # AP is Credit

            if abs(final_asset_acct_balance - expected_asset_acct_balance) < Decimal('0.01'):
                 print("      PASS: Asset GL Account balance updated correctly.")
            else:
                 print(f"      FAIL: Asset GL Account balance mismatch. Expected ~{expected_asset_acct_balance:.2f}, Got {final_asset_acct_balance:.2f}")
            if abs(final_ap_acct_balance - expected_ap_acct_balance) < Decimal('0.01'):
                 print("      PASS: AP GL Account balance updated correctly.")
            else:
                 print(f"      FAIL: AP GL Account balance mismatch. Expected ~{expected_ap_acct_balance:.2f}, Got {final_ap_acct_balance:.2f}")

        else:
            print(f"   FAIL: record_fixed_asset_purchase returned unexpected value: {test_asset_id}")


        # == 2. Test view_active_fixed_assets_list ==
        print("\n2. Testing view_active_fixed_assets_list...")
        active_assets = view_active_fixed_assets_list(conn)

        if active_assets is not None and isinstance(active_assets, list):
            print(f"   PASS: Retrieved list of {len(active_assets)} active fixed assets.")
            found_test_asset = False
            if len(active_assets) > 0:
                 if isinstance(active_assets[0], (dict, sqlite3.Row)):
                      print(f"      PASS: List contains dict/Row objects.")
                      sample_asset = active_assets[0]
                      print(f"      Sample Active Asset: ID={sample_asset['AssetID']}, Name={sample_asset['AssetName']}, "
                            f"Cost={sample_asset['PurchaseCost']}, Value={sample_asset['CurrentValue']}")
                      # Check if our newly added asset is in the list
                      for asset in active_assets:
                          if asset['AssetID'] == test_asset_id:
                              found_test_asset = True
                              break
                      if test_asset_id and found_test_asset:
                           print(f"      PASS: Newly added asset (ID: {test_asset_id}) found in the active list.")
                      elif test_asset_id:
                           print(f"      FAIL: Newly added asset (ID: {test_asset_id}) *NOT* found in the active list.")

                 else:
                      print(f"      FAIL: List elements are not dict/Row, type: {type(active_assets[0])}")
            else:
                 print("      WARN: Active fixed assets list is empty.")

            # Test filtering (using the ID we expect our test asset to have)
            print(f"   Testing view_active_fixed_assets_list filtering by AccountID: {EQUIPMENT_ASSET_ACCT_ID}")
            filtered_assets = view_active_fixed_assets_list(conn, asset_account_id=EQUIPMENT_ASSET_ACCT_ID)
            if filtered_assets is not None and isinstance(filtered_assets, list):
                 print(f"      PASS: Retrieved list of {len(filtered_assets)} active assets for account {EQUIPMENT_ASSET_ACCT_ID}.")
                 found_filtered = False
                 all_match_filter = True
                 for asset in filtered_assets:
                      # Need to requery the asset account ID if not returned by view function
                      details = _execute_sql(conn, "SELECT AssetAccountID FROM FixedAssets WHERE AssetID = ?", (asset['AssetID'],), fetchone=True)
                      if details and details['AssetAccountID'] != EQUIPMENT_ASSET_ACCT_ID:
                          all_match_filter = False
                      if asset['AssetID'] == test_asset_id:
                          found_filtered = True
                 if test_asset_id and found_filtered:
                      print(f"      PASS: Test asset ID {test_asset_id} found in filtered list.")
                 elif test_asset_id:
                      print(f"      WARN: Test asset ID {test_asset_id} not found in filtered list.")
                 if all_match_filter:
                      print(f"      PASS: All assets in filtered list belong to account {EQUIPMENT_ASSET_ACCT_ID}.")
                 else:
                      print(f"      FAIL: Filtered list contains assets from other accounts!")
            else:
                 print("      FAIL: Filtered asset list retrieval failed.")


        elif active_assets is None:
             print("   FAIL: view_active_fixed_assets_list returned None (check DB errors).")
        else:
             print(f"   FAIL: Expected a list for active assets, got {type(active_assets)}.")


        print("\n--- Fixed Assets Function Tests Complete ---")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
    except sqlite3.Error as e:
        print(f"DATABASE ERROR: {e}")
        if conn: conn.rollback()
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            # Optional: Cleanup test asset
            if test_asset_id:
                 print("\n--- Cleaning up test data ---")
                 try:
                     print(f"   Deleting test fixed asset ID: {test_asset_id}")
                     # Need to delete related GL entries first (more complex) or handle FK constraints
                     # Simpler: Just delete from FixedAssets, assuming no dependent GL needed for other tests
                     conn.execute("DELETE FROM FixedAssets WHERE AssetID = ?", (test_asset_id,))
                     # Attempt to delete related GL (might fail if needed elsewhere)
                     # conn.execute("DELETE FROM GeneralLedger WHERE Reference = ?", (f"FixedAssetID:{test_asset_id}",))
                     conn.commit()
                     print("   Test fixed asset deleted.")
                 except sqlite3.Error as e:
                      print(f"   Error during cleanup: {e}")
                      conn.rollback()

            conn.close()
            print("\n--- Database Connection Closed ---")