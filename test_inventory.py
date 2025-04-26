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
        _add_sample_product_and_item, # Helper assumed added to fm_functions
        _add_sample_warehouse, # Helper assumed added to fm_functions
        record_inventory_movement,
        check_stock_level_for_item,
        view_inventory_item_details,
    )
except ImportError:
    print("ERROR: Could not import functions/constants from fm_functions.py.")
    exit()
except NameError:
     print("ERROR: Ensure Account ID constants (e.g., INVENTORY_ASSET_ACCT_ID) are defined in fm_functions.py.")
     exit()

DATABASE_FILE = './database/financial_agent.db'

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
    test_item_id = None
    test_warehouse_id = None
    movement_purchase_id = None
    movement_sale_id = None
    movement_adj_id = None

    try:
        conn = get_db_connection()
        print(f"--- Connected to Database: {DATABASE_FILE} ---")
        print("\n--- Testing Inventory Functions ---")

        # --- Test Setup ---
        print("--- Setting up test data (Product, Item, Warehouse) ---")
        # Create unique SKUs
        product_sku = f"PROD-TEST-{int(time.time())}"
        item_sku = f"ITEM-TEST-{int(time.time())}"
        warehouse_name = f"WH-TEST-{int(time.time())}"

        # Add sample Warehouse (using helper)
        test_warehouse_id = _add_sample_warehouse(conn, warehouse_name)
        if not test_warehouse_id:
             print("   FAIL: Could not create/find test warehouse. Exiting.")
             exit()

        # Add sample Product and InventoryItem (using helper)
        test_item_id = _add_sample_product_and_item(
            conn, product_sku, "Test Inventory Product", item_sku, "Test Inventory Item",
            Decimal('99.99'), Decimal('55.50'), # Sell Price, Cost
            INVENTORY_ASSET_ACCT_ID, COGS_ACCT_ID, uom='Unit'
        )
        if not test_item_id:
             print("   FAIL: Could not create/find test product/item. Exiting.")
             exit()

        print("--- Test data setup complete ---")

        # == 1. Test check_stock_level_for_item (Initial) ==
        print(f"\n1. Testing check_stock_level_for_item (Item ID: {test_item_id}, Initial)...")
        initial_stock = check_stock_level_for_item(conn, test_item_id)
        if initial_stock is not None and initial_stock == Decimal('0.00'):
             print(f"   PASS: Initial stock level is correctly 0.00 (returned {initial_stock}).")
        elif initial_stock is not None:
             print(f"   FAIL: Initial stock level expected 0.00, but got {initial_stock}.")
        else:
             print(f"   FAIL: check_stock_level_for_item returned None.")


        # == 2. Test record_inventory_movement (Purchase) ==
        print(f"\n2. Testing record_inventory_movement (Purchase)...")
        purchase_qty = Decimal('100.0')
        purchase_cost = Decimal('55.50') # Should match item cost ideally
        movement_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') # Use datetime
        related_bill_id = 99991 # Example dummy related ID

        movement_purchase_id = record_inventory_movement(
            conn, test_item_id, movement_date, 'Purchase', purchase_qty,
            test_warehouse_id, unit_cost=purchase_cost,
            related_doc_type='Bill', related_doc_id=related_bill_id
        )

        if movement_purchase_id and isinstance(movement_purchase_id, int):
             print(f"   PASS: Inventory 'Purchase' movement recorded with MovementID: {movement_purchase_id}")
             # Verification
             stock_after_purchase = check_stock_level_for_item(conn, test_item_id)
             if stock_after_purchase is not None and stock_after_purchase == purchase_qty:
                 print(f"      PASS: Stock level after purchase is correct ({stock_after_purchase}).")
             elif stock_after_purchase is not None:
                 print(f"      FAIL: Stock level after purchase incorrect. Expected {purchase_qty}, Got {stock_after_purchase}.")
             else:
                 print("      FAIL: Could not check stock level after purchase.")
        else:
            print(f"   FAIL: record_inventory_movement (Purchase) returned unexpected value: {movement_purchase_id}")


        # == 3. Test record_inventory_movement (Sale) ==
        print(f"\n3. Testing record_inventory_movement (Sale)...")
        sale_qty = Decimal('-25.0') # Negative for outgoing
        movement_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        related_invoice_id = 88881 # Example dummy related ID

        movement_sale_id = record_inventory_movement(
            conn, test_item_id, movement_date, 'Sale', sale_qty,
            test_warehouse_id, unit_cost=purchase_cost, # Cost of goods sold
            related_doc_type='Invoice', related_doc_id=related_invoice_id
        )

        if movement_sale_id and isinstance(movement_sale_id, int):
            print(f"   PASS: Inventory 'Sale' movement recorded with MovementID: {movement_sale_id}")
             # Verification
            stock_after_sale = check_stock_level_for_item(conn, test_item_id)
            expected_stock_after_sale = purchase_qty + sale_qty # 100 - 25 = 75
            if stock_after_sale is not None and stock_after_sale == expected_stock_after_sale:
                 print(f"      PASS: Stock level after sale is correct ({stock_after_sale}).")
            elif stock_after_sale is not None:
                 print(f"      FAIL: Stock level after sale incorrect. Expected {expected_stock_after_sale}, Got {stock_after_sale}.")
            else:
                 print("      FAIL: Could not check stock level after sale.")
        else:
            print(f"   FAIL: record_inventory_movement (Sale) returned unexpected value: {movement_sale_id}")

        # == 4. Test record_inventory_movement (Adjustment In) ==
        print(f"\n4. Testing record_inventory_movement (Adjustment-In)...")
        adj_qty = Decimal('5.0') # Positive for incoming adjustment
        movement_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        notes = "Found extra units during cycle count"

        movement_adj_id = record_inventory_movement(
            conn, test_item_id, movement_date, 'Adjustment-In', adj_qty,
            test_warehouse_id, unit_cost=purchase_cost, # Use a standard cost
            notes=notes
        )

        if movement_adj_id and isinstance(movement_adj_id, int):
            print(f"   PASS: Inventory 'Adjustment-In' movement recorded with MovementID: {movement_adj_id}")
             # Verification
            stock_after_adj = check_stock_level_for_item(conn, test_item_id)
            expected_stock_after_adj = expected_stock_after_sale + adj_qty # 75 + 5 = 80
            if stock_after_adj is not None and stock_after_adj == expected_stock_after_adj:
                 print(f"      PASS: Stock level after adjustment is correct ({stock_after_adj}).")
            elif stock_after_adj is not None:
                 print(f"      FAIL: Stock level after adjustment incorrect. Expected {expected_stock_after_adj}, Got {stock_after_adj}.")
            else:
                 print("      FAIL: Could not check stock level after adjustment.")
        else:
            print(f"   FAIL: record_inventory_movement (Adjustment-In) returned unexpected value: {movement_adj_id}")


        # == 5. Test check_stock_level_for_item (Filtered by Warehouse) ==
        print(f"\n5. Testing check_stock_level_for_item (Item ID: {test_item_id}, WH: {test_warehouse_id})...")
        warehouse_stock = check_stock_level_for_item(conn, test_item_id, warehouse_id=test_warehouse_id)
        current_total_stock = check_stock_level_for_item(conn, test_item_id) # Get total again

        if warehouse_stock is not None and warehouse_stock == current_total_stock:
             print(f"   PASS: Stock level filtered by warehouse ({warehouse_stock}) matches total stock ({current_total_stock}) as expected (only one warehouse used).")
        elif warehouse_stock is not None:
             print(f"   FAIL: Filtered stock ({warehouse_stock}) doesn't match total stock ({current_total_stock}).")
        else:
             print(f"   FAIL: check_stock_level_for_item returned None when filtered.")

        # Test with non-existent warehouse filter
        non_existent_wh_id = 999
        print(f"   Testing filter with non-existent Warehouse ID: {non_existent_wh_id}...")
        non_existent_wh_stock = check_stock_level_for_item(conn, test_item_id, warehouse_id=non_existent_wh_id)
        if non_existent_wh_stock is not None and non_existent_wh_stock == Decimal('0.00'):
             print(f"   PASS: Correctly returned 0.00 for non-existent warehouse filter.")
        elif non_existent_wh_stock is not None:
             print(f"   FAIL: Returned {non_existent_wh_stock} for non-existent warehouse filter, expected 0.00.")
        else:
             print(f"   FAIL: check_stock_level_for_item returned None for non-existent warehouse.")


        # == 6. Test view_inventory_item_details ==
        print(f"\n6. Testing view_inventory_item_details (Item ID: {test_item_id})...")
        item_details = view_inventory_item_details(conn, test_item_id)

        if item_details and isinstance(item_details, (dict, sqlite3.Row)):
            if item_details['ItemID'] == test_item_id:
                 print("   PASS: Retrieved details for inventory item.")
                 print(f"      - Item Name : {item_details['ItemName']} (SKU: {item_details['ItemSKU']})")
                 print(f"      - Product Name: {item_details['ProductName']} (SKU: {item_details['ProductSKU']})")
                 print(f"      - Std Cost  : {item_details['StandardCost']:.2f} / {item_details['UnitOfMeasure']}")
                 print(f"      - Sell Price: {item_details['ProductUnitPrice']:.2f}")
                 print(f"      - Inv Acct  : {item_details['InventoryAccountName']} ({item_details['InventoryAssetAccountID']})")
                 print(f"      - COGS Acct : {item_details['COGSAccountName']} ({item_details['COGSAccountID']})")
                 print(f"      - Is Tracked: {item_details['IsTracked']}")
            else:
                 print(f"   FAIL: Retrieved details, but ItemID mismatch (Got {item_details['ItemID']}).")
        elif item_details is None:
             print(f"   FAIL: view_inventory_item_details returned None for ItemID {test_item_id}.")
        else:
             print(f"   FAIL: Expected dict/Row, got {type(item_details)}.")


        print("\n--- Inventory Function Tests Complete ---")

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
            # Optional: Cleanup test data (movements, item, product, warehouse)
            print("\n--- Cleaning up test data ---")
            try:
                if test_item_id:
                     print(f"   Deleting movements for item {test_item_id}...")
                     conn.execute("DELETE FROM StockMovements WHERE ItemID = ?", (test_item_id,))
                if test_item_id:
                     print(f"   Deleting item {test_item_id}...")
                     # Need product ID first
                     prod_id_row = _execute_sql(conn,"SELECT ProductID FROM InventoryItems WHERE ItemID = ?", (test_item_id,), fetchone=True)
                     conn.execute("DELETE FROM InventoryItems WHERE ItemID = ?", (test_item_id,))
                     if prod_id_row:
                          print(f"   Deleting product {prod_id_row['ProductID']}...")
                          conn.execute("DELETE FROM Products WHERE ProductID = ?", (prod_id_row['ProductID'],))
                if test_warehouse_id:
                     print(f"   Deleting warehouse {test_warehouse_id}...")
                     conn.execute("DELETE FROM Warehouses WHERE WarehouseID = ?", (test_warehouse_id,))
                conn.commit()
                print("   Test inventory data cleanup attempted.")
            except sqlite3.Error as e:
                 print(f"   Error during cleanup: {e}")
                 conn.rollback()
            except Exception as e:
                 print(f"   Unexpected error during cleanup: {e}")

            conn.close()
            print("\n--- Database Connection Closed ---")