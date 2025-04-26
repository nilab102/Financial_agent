-- Financial Management Database Creation Script
-- SQLite3 Version

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- =============================================
-- Core Tables
-- =============================================

-- 1. Departments Table
CREATE TABLE Departments (
    DepartmentID INTEGER PRIMARY KEY AUTOINCREMENT,
    DepartmentName TEXT NOT NULL,
    Description TEXT,
    ManagerID INTEGER NULL
);

-- 2. Positions Table
CREATE TABLE Positions (
    PositionID INTEGER PRIMARY KEY AUTOINCREMENT,
    PositionTitle TEXT NOT NULL,
    Description TEXT,
    DepartmentID INTEGER,
    FOREIGN KEY (DepartmentID) REFERENCES Departments(DepartmentID)
);

-- 3. Employees Table
CREATE TABLE Employees (
    EmployeeID INTEGER PRIMARY KEY AUTOINCREMENT,
    FirstName TEXT NOT NULL,
    LastName TEXT NOT NULL,
    Email TEXT,
    Phone TEXT,
    HireDate DATE,
    DepartmentID INTEGER,
    PositionID INTEGER,
    ReportsTo INTEGER,
    -- Salary field can represent ANNUAL salary for Salary type,
    -- but is less relevant for Hourly. Rely on EmployeePayrollInfo primarily.
    Salary DECIMAL(15,2),
    Status TEXT CHECK(Status IN ('Active', 'Inactive')),
    FOREIGN KEY (DepartmentID) REFERENCES Departments(DepartmentID),
    FOREIGN KEY (PositionID) REFERENCES Positions(PositionID),
    FOREIGN KEY (ReportsTo) REFERENCES Employees(EmployeeID)
);

-- Alter Departments to add ManagerID foreign key now that Employees exists
-- Using a TRIGGER is complex for setting ManagerID based on Position Title.
-- It's often better handled by application logic or manual update after employee creation.
-- Removing the trigger for simplicity and robustness. ManagerID should be updated manually
-- or via application logic when a manager is assigned/changed.
-- CREATE TRIGGER set_department_manager_fk ... END; -- Removed

-- =============================================
-- Payroll Information Table (NEW)
-- =============================================

    -- 3b. Employee Payroll Info Table
    CREATE TABLE EmployeePayrollInfo (
        EmployeePayrollID INTEGER PRIMARY KEY AUTOINCREMENT,
        EmployeeID INTEGER NOT NULL UNIQUE,              -- Foreign key to Employees table (1-to-1 link)
        PayType TEXT NOT NULL CHECK(PayType IN ('Salary', 'Hourly')), -- Type of pay structure
        PayFrequency TEXT NOT NULL CHECK(PayFrequency IN ('Weekly', 'Bi-Weekly', 'Semi-Monthly', 'Monthly')), -- How often paid
        AnnualSalary DECIMAL(15,2) NULL,                 -- Annual salary amount (if PayType is 'Salary')
        HourlyRate DECIMAL(10,2) NULL,                   -- Rate per hour (if PayType is 'Hourly')
        OvertimeEligible INTEGER NOT NULL DEFAULT 1,     -- Flag for overtime eligibility (1=Yes, 0=No)
        LastUpdated DATETIME DEFAULT CURRENT_TIMESTAMP,  -- Timestamp of last update
        UpdatedBy INTEGER NULL,                          -- EmployeeID who last updated this record

        FOREIGN KEY (EmployeeID) REFERENCES Employees(EmployeeID) ON DELETE CASCADE, -- Cascade delete if employee is removed
        FOREIGN KEY (UpdatedBy) REFERENCES Employees(EmployeeID),

        -- Add the CHECK constraint directly here for SQLite compatibility
        CHECK (
            (PayType = 'Salary' AND AnnualSalary IS NOT NULL AND HourlyRate IS NULL) OR
            (PayType = 'Hourly' AND AnnualSalary IS NULL AND HourlyRate IS NOT NULL)
        ) -- Added CHECK constraint here
    );

-- =============================================
-- Financial Operations Tables
-- =============================================

-- 4. Chart of Accounts
CREATE TABLE ChartOfAccounts (
    AccountID INTEGER PRIMARY KEY AUTOINCREMENT,
    AccountNumber TEXT NOT NULL UNIQUE,
    AccountName TEXT NOT NULL,
    AccountType TEXT NOT NULL CHECK(AccountType IN ('Asset', 'Liability', 'Equity', 'Revenue', 'Expense')),
    ParentAccountID INTEGER,
    Description TEXT,
    IsActive INTEGER DEFAULT 1,
    BalanceType TEXT NOT NULL CHECK(BalanceType IN ('Debit', 'Credit')),
    FOREIGN KEY (ParentAccountID) REFERENCES ChartOfAccounts(AccountID)
);

-- 5. Fiscal Years
CREATE TABLE FiscalYears (
    FiscalYearID INTEGER PRIMARY KEY AUTOINCREMENT,
    StartDate DATE NOT NULL,
    EndDate DATE NOT NULL,
    IsClosed INTEGER DEFAULT 0,
    Description TEXT
);

-- 6. Fiscal Periods
CREATE TABLE FiscalPeriods (
    PeriodID INTEGER PRIMARY KEY AUTOINCREMENT,
    FiscalYearID INTEGER NOT NULL,
    PeriodNumber INTEGER NOT NULL,
    StartDate DATE NOT NULL,
    EndDate DATE NOT NULL,
    IsClosed INTEGER DEFAULT 0,
    ClosedBy INTEGER,
    ClosedDate DATE,
    FOREIGN KEY (FiscalYearID) REFERENCES FiscalYears(FiscalYearID),
    FOREIGN KEY (ClosedBy) REFERENCES Employees(EmployeeID)
);

-- 7. General Ledger
CREATE TABLE GeneralLedger (
    LedgerEntryID INTEGER PRIMARY KEY AUTOINCREMENT,
    EntryDate DATE NOT NULL,
    Description TEXT,
    AccountID INTEGER NOT NULL,
    DebitAmount DECIMAL(15,2) DEFAULT 0,
    CreditAmount DECIMAL(15,2) DEFAULT 0,
    EntryType TEXT,
    Reference TEXT,
    ApprovedBy INTEGER,
    CreatedBy INTEGER NOT NULL,
    CreationDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (AccountID) REFERENCES ChartOfAccounts(AccountID),
    FOREIGN KEY (ApprovedBy) REFERENCES Employees(EmployeeID),
    FOREIGN KEY (CreatedBy) REFERENCES Employees(EmployeeID)
);

-- =============================================
-- Treasury Management Tables
-- =============================================

-- 8. Bank Accounts
CREATE TABLE BankAccounts (
    BankAccountID INTEGER PRIMARY KEY AUTOINCREMENT,
    AccountName TEXT NOT NULL,
    AccountNumber TEXT NOT NULL,
    BankName TEXT NOT NULL,
    BankBranch TEXT,
    IBAN TEXT,
    Currency TEXT DEFAULT 'USD',
    AccountType TEXT,
    OpenDate DATE,
    CurrentBalance DECIMAL(15,2) DEFAULT 0,
    LastReconciliationDate DATE,
    IsActive INTEGER DEFAULT 1
);

-- 9. Cash Transactions
CREATE TABLE CashTransactions (
    TransactionID INTEGER PRIMARY KEY AUTOINCREMENT,
    TransactionDate DATE NOT NULL,
    BankAccountID INTEGER NOT NULL,
    TransactionType TEXT CHECK(TransactionType IN ('Deposit', 'Withdrawal', 'Transfer')),
    Amount DECIMAL(15,2) NOT NULL,
    Description TEXT,
    Reference TEXT,
    RelatedAccountID INTEGER,
    CreatedBy INTEGER NOT NULL,
    CreationDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (BankAccountID) REFERENCES BankAccounts(BankAccountID),
    FOREIGN KEY (RelatedAccountID) REFERENCES ChartOfAccounts(AccountID),
    FOREIGN KEY (CreatedBy) REFERENCES Employees(EmployeeID)
);

-- =============================================
-- Accounts Receivable Tables
-- =============================================

-- 10. Customers
CREATE TABLE Customers (
    CustomerID INTEGER PRIMARY KEY AUTOINCREMENT,
    CustomerName TEXT NOT NULL,
    ContactPerson TEXT,
    Email TEXT,
    Phone TEXT,
    Address TEXT,
    TaxID TEXT,
    CreditLimit DECIMAL(15,2),
    PaymentTerms TEXT,
    IsActive INTEGER DEFAULT 1
);

-- 11. Invoices
CREATE TABLE Invoices (
    InvoiceID INTEGER PRIMARY KEY AUTOINCREMENT,
    InvoiceNumber TEXT NOT NULL UNIQUE,
    CustomerID INTEGER NOT NULL,
    InvoiceDate DATE NOT NULL,
    DueDate DATE NOT NULL,
    TotalAmount DECIMAL(15,2) NOT NULL,
    PaidAmount DECIMAL(15,2) DEFAULT 0,
    -- Balance calculation depends on how partial payments are handled.
    -- Using GENERATED column is efficient if supported and logic is simple.
    -- If complex allocation happens, manual update might be needed.
    Balance DECIMAL(15,2) GENERATED ALWAYS AS (TotalAmount - PaidAmount) STORED,
    Status TEXT DEFAULT 'Draft' CHECK(Status IN ('Draft', 'Issued', 'Paid', 'Overdue', 'Cancelled')),
    PaymentTerms TEXT,
    CreatedBy INTEGER NOT NULL,
    CreationDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID),
    FOREIGN KEY (CreatedBy) REFERENCES Employees(EmployeeID)
);

-- 12. Invoice Items
CREATE TABLE InvoiceItems (
    InvoiceItemID INTEGER PRIMARY KEY AUTOINCREMENT,
    InvoiceID INTEGER NOT NULL,
    Description TEXT NOT NULL,
    Quantity DECIMAL(10,2) NOT NULL,
    UnitPrice DECIMAL(15,2) NOT NULL,
    TaxRate DECIMAL(5,2) DEFAULT 0,
    -- Generated columns for TaxAmount and LineTotal simplify updates
    TaxAmount DECIMAL(15,2) GENERATED ALWAYS AS (Quantity * UnitPrice * TaxRate / 100) STORED,
    LineTotal DECIMAL(15,2) GENERATED ALWAYS AS (Quantity * UnitPrice * (1 + TaxRate / 100)) STORED,
    AccountID INTEGER, -- Revenue or Deferred Revenue account
    FOREIGN KEY (InvoiceID) REFERENCES Invoices(InvoiceID) ON DELETE CASCADE, -- Cascade delete items if invoice is deleted
    FOREIGN KEY (AccountID) REFERENCES ChartOfAccounts(AccountID)
);

-- 13. Customer Payments
CREATE TABLE CustomerPayments (
    PaymentID INTEGER PRIMARY KEY AUTOINCREMENT,
    CustomerID INTEGER NOT NULL,
    PaymentDate DATE NOT NULL,
    Amount DECIMAL(15,2) NOT NULL,
    PaymentMethod TEXT,
    Reference TEXT,
    BankAccountID INTEGER,
    Notes TEXT,
    CreatedBy INTEGER NOT NULL,
    CreationDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID),
    FOREIGN KEY (BankAccountID) REFERENCES BankAccounts(BankAccountID),
    FOREIGN KEY (CreatedBy) REFERENCES Employees(EmployeeID)
);

-- =============================================
-- Accounts Payable Tables
-- =============================================

-- 14. Vendors
CREATE TABLE Vendors (
    VendorID INTEGER PRIMARY KEY AUTOINCREMENT,
    VendorName TEXT NOT NULL,
    ContactPerson TEXT,
    Email TEXT,
    Phone TEXT,
    Address TEXT,
    TaxID TEXT,
    PaymentTerms TEXT,
    IsActive INTEGER DEFAULT 1
);

-- 15. Bills
CREATE TABLE Bills (
    BillID INTEGER PRIMARY KEY AUTOINCREMENT,
    BillNumber TEXT NOT NULL UNIQUE,
    VendorID INTEGER NOT NULL,
    BillDate DATE NOT NULL,
    DueDate DATE NOT NULL,
    TotalAmount DECIMAL(15,2) NOT NULL,
    PaidAmount DECIMAL(15,2) DEFAULT 0,
    Balance DECIMAL(15,2) GENERATED ALWAYS AS (TotalAmount - PaidAmount) STORED,
    Status TEXT DEFAULT 'Draft' CHECK(Status IN ('Draft', 'Received', 'Paid', 'Overdue', 'Cancelled')),
    CreatedBy INTEGER NOT NULL,
    CreationDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (VendorID) REFERENCES Vendors(VendorID),
    FOREIGN KEY (CreatedBy) REFERENCES Employees(EmployeeID)
);

-- 16. Bill Items
CREATE TABLE BillItems (
    BillItemID INTEGER PRIMARY KEY AUTOINCREMENT,
    BillID INTEGER NOT NULL,
    Description TEXT NOT NULL,
    Quantity DECIMAL(10,2) NOT NULL,
    UnitPrice DECIMAL(15,2) NOT NULL,
    TaxRate DECIMAL(5,2) DEFAULT 0,
    TaxAmount DECIMAL(15,2) GENERATED ALWAYS AS (Quantity * UnitPrice * TaxRate / 100) STORED,
    LineTotal DECIMAL(15,2) GENERATED ALWAYS AS (Quantity * UnitPrice * (1 + TaxRate / 100)) STORED,
    AccountID INTEGER, -- Expense or Asset account
    FOREIGN KEY (BillID) REFERENCES Bills(BillID) ON DELETE CASCADE,
    FOREIGN KEY (AccountID) REFERENCES ChartOfAccounts(AccountID)
);

-- 17. Vendor Payments
CREATE TABLE VendorPayments (
    PaymentID INTEGER PRIMARY KEY AUTOINCREMENT,
    VendorID INTEGER NOT NULL,
    PaymentDate DATE NOT NULL,
    Amount DECIMAL(15,2) NOT NULL,
    PaymentMethod TEXT,
    Reference TEXT,
    BankAccountID INTEGER,
    Notes TEXT,
    CreatedBy INTEGER NOT NULL,
    CreationDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (VendorID) REFERENCES Vendors(VendorID),
    FOREIGN KEY (BankAccountID) REFERENCES BankAccounts(BankAccountID),
    FOREIGN KEY (CreatedBy) REFERENCES Employees(EmployeeID)
);

-- =============================================
-- Tax Management Tables
-- =============================================

-- 18. Tax Rates
CREATE TABLE TaxRates (
    TaxRateID INTEGER PRIMARY KEY AUTOINCREMENT,
    TaxName TEXT NOT NULL,
    Rate DECIMAL(5,2) NOT NULL,
    Description TEXT,
    IsActive INTEGER DEFAULT 1
);

-- 19. Tax Returns
CREATE TABLE TaxReturns (
    TaxReturnID INTEGER PRIMARY KEY AUTOINCREMENT,
    TaxType TEXT NOT NULL,
    PeriodStart DATE NOT NULL,
    PeriodEnd DATE NOT NULL,
    DueDate DATE NOT NULL,
    TotalTaxAmount DECIMAL(15,2) NOT NULL,
    Status TEXT DEFAULT 'Draft' CHECK(Status IN ('Draft', 'Filed', 'Paid')),
    FiledBy INTEGER,
    FilingDate DATE,
    Notes TEXT,
    FOREIGN KEY (FiledBy) REFERENCES Employees(EmployeeID)
);

-- =============================================
-- Financial Planning & Analysis Tables
-- =============================================

-- 20. Budgets
CREATE TABLE Budgets (
    BudgetID INTEGER PRIMARY KEY AUTOINCREMENT,
    BudgetName TEXT NOT NULL,
    FiscalYearID INTEGER NOT NULL,
    DepartmentID INTEGER,
    Description TEXT,
    Status TEXT DEFAULT 'Draft' CHECK(Status IN ('Draft', 'Approved', 'Closed')),
    CreatedBy INTEGER NOT NULL,
    ApprovedBy INTEGER,
    CreationDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    ApprovalDate DATE,
    FOREIGN KEY (FiscalYearID) REFERENCES FiscalYears(FiscalYearID),
    FOREIGN KEY (DepartmentID) REFERENCES Departments(DepartmentID),
    FOREIGN KEY (CreatedBy) REFERENCES Employees(EmployeeID),
    FOREIGN KEY (ApprovedBy) REFERENCES Employees(EmployeeID)
);

-- 21. Budget Items
CREATE TABLE BudgetItems (
    BudgetItemID INTEGER PRIMARY KEY AUTOINCREMENT,
    BudgetID INTEGER NOT NULL,
    AccountID INTEGER NOT NULL,
    PeriodID INTEGER NOT NULL,
    PlannedAmount DECIMAL(15,2) NOT NULL,
    ActualAmount DECIMAL(15,2) DEFAULT 0,
    -- Variance might be better calculated in reports than stored
    Variance DECIMAL(15,2) GENERATED ALWAYS AS (PlannedAmount - ActualAmount) STORED,
    Notes TEXT,
    FOREIGN KEY (BudgetID) REFERENCES Budgets(BudgetID),
    FOREIGN KEY (AccountID) REFERENCES ChartOfAccounts(AccountID),
    FOREIGN KEY (PeriodID) REFERENCES FiscalPeriods(PeriodID)
);

-- 22. Financial Reports
CREATE TABLE FinancialReports (
    ReportID INTEGER PRIMARY KEY AUTOINCREMENT,
    ReportName TEXT NOT NULL,
    ReportType TEXT CHECK(ReportType IN ('Income Statement', 'Balance Sheet', 'Cash Flow', 'Custom')),
    FiscalYearID INTEGER,
    PeriodID INTEGER,
    GenerationDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    GeneratedBy INTEGER NOT NULL,
    Parameters TEXT, -- Store generation parameters (e.g., JSON string)
    Description TEXT,
    FOREIGN KEY (FiscalYearID) REFERENCES FiscalYears(FiscalYearID),
    FOREIGN KEY (PeriodID) REFERENCES FiscalPeriods(PeriodID),
    FOREIGN KEY (GeneratedBy) REFERENCES Employees(EmployeeID)
);

-- =============================================
-- Audit and Control Tables
-- =============================================

-- 23. Audit Logs
CREATE TABLE AuditLogs (
    LogID INTEGER PRIMARY KEY AUTOINCREMENT,
    TableName TEXT NOT NULL,
    RecordID INTEGER, -- Allow NULL for system actions like Login
    ActionType TEXT NOT NULL CHECK(ActionType IN (
        'Insert', 'Update', 'Delete', -- Original values
        'Login', 'Logout', 'FailedLogin', 'System', 'Approve', 'Reject', 'Void' -- Add other allowed types
    )),
    OldValue TEXT, -- Consider storing changes as JSON diffs for large records
    NewValue TEXT,
    ChangedBy INTEGER,
    ChangeDate DATETIME DEFAULT CURRENT_TIMESTAMP,
    IPAddress TEXT,
    FOREIGN KEY (ChangedBy) REFERENCES Employees(EmployeeID)
);

-- 24. Approval Workflows
CREATE TABLE ApprovalWorkflows (
    WorkflowID INTEGER PRIMARY KEY AUTOINCREMENT,
    WorkflowName TEXT NOT NULL,
    Description TEXT,
    Status TEXT CHECK(Status IN ('Active', 'Inactive')) DEFAULT 'Active'
);

-- 25. Approval Steps
CREATE TABLE ApprovalSteps (
    StepID INTEGER PRIMARY KEY AUTOINCREMENT,
    WorkflowID INTEGER NOT NULL,
    StepNumber INTEGER NOT NULL,
    ApproverPositionID INTEGER NOT NULL, -- Link to Position, not specific Employee
    IsRequired INTEGER DEFAULT 1,
    Condition TEXT, -- Optional condition for step (e.g., 'Amount > 50000')
    Description TEXT,
    FOREIGN KEY (WorkflowID) REFERENCES ApprovalWorkflows(WorkflowID),
    FOREIGN KEY (ApproverPositionID) REFERENCES Positions(PositionID)
);

-- =============================================
-- Inventory Management Tables
-- =============================================

-- 26. Product Catalog Table
CREATE TABLE Products (
    ProductID INTEGER PRIMARY KEY AUTOINCREMENT, -- Primary key identifier for each product
    ProductSKU TEXT UNIQUE,                     -- Unique Stock Keeping Unit or product code
    ProductName TEXT NOT NULL,                  -- Name of the product or service
    Description TEXT,                           -- Detailed description of the product
    UnitPrice REAL NOT NULL,                    -- Standard selling price per unit (Use DECIMAL for precision)
    IsActive INTEGER NOT NULL DEFAULT 1         -- Boolean flag (1=active, 0=inactive)
);

-- 27. Warehouse Table (Needed for StockMovements)
CREATE TABLE Warehouses (
    WarehouseID INTEGER PRIMARY KEY AUTOINCREMENT, -- Primary key identifier
    WarehouseName TEXT NOT NULL UNIQUE,            -- Name of the warehouse
    Location TEXT                              -- Physical address or description
);

-- 28. Inventory Items Table
CREATE TABLE InventoryItems (
    ItemID INTEGER PRIMARY KEY AUTOINCREMENT,         -- Primary key identifier for each inventory item
    ProductID INTEGER NOT NULL,                     -- Foreign key to the Products table
    ItemSKU TEXT NOT NULL UNIQUE,                   -- Unique Stock Keeping Unit for the inventory item
    ItemName TEXT NOT NULL,                         -- Name of the inventory item
    Description TEXT,                               -- Detailed description of the inventory item
    UnitOfMeasure TEXT NOT NULL,                    -- Unit used for tracking (e.g., Each, Kg, Box, Litre)
    StandardCost REAL NOT NULL,                     -- Standard or average cost per unit (Use DECIMAL)
    InventoryAssetAccountID INTEGER NOT NULL,       -- FK to ChartOfAccounts for the Inventory Asset account
    COGSAccountID INTEGER NOT NULL,                 -- FK to ChartOfAccounts for the Cost of Goods Sold expense account
    ReorderPoint REAL,                              -- Minimum quantity level that triggers reordering (Use DECIMAL)
    PreferredVendorID INTEGER,                      -- FK to Vendors table for the preferred supplier (optional)
    IsTracked INTEGER NOT NULL DEFAULT 1,           -- Whether inventory levels are actively tracked (1=Yes, 0=No)

    FOREIGN KEY (ProductID) REFERENCES Products(ProductID),
    FOREIGN KEY (InventoryAssetAccountID) REFERENCES ChartOfAccounts(AccountID),
    FOREIGN KEY (COGSAccountID) REFERENCES ChartOfAccounts(AccountID),
    FOREIGN KEY (PreferredVendorID) REFERENCES Vendors(VendorID)
);

-- 29. Stock Movements Table
CREATE TABLE StockMovements (
    MovementID INTEGER PRIMARY KEY AUTOINCREMENT, -- Primary key identifier for each stock movement
    ItemID INTEGER NOT NULL,                      -- Foreign key to the InventoryItems table
    MovementDate TEXT NOT NULL,                   -- Date and time the movement occurred (ISO format recommended: YYYY-MM-DD HH:MM:SS)
    MovementType TEXT NOT NULL CHECK(MovementType IN ('Purchase', 'Sale', 'Adjustment-In', 'Adjustment-Out', 'Transfer-In', 'Transfer-Out', 'Assembly-Used', 'Assembly-Produced')), -- Type of movement
    QuantityChange REAL NOT NULL,                 -- Change in quantity (+ for in, - for out) (Use DECIMAL)
    UnitCost REAL,                                -- Cost per unit for this specific movement (important for costing) (Use DECIMAL)
    WarehouseID INTEGER NOT NULL,                 -- Foreign key to Warehouses table
    RelatedDocumentType TEXT,                     -- Type of related document (e.g., Bill, Invoice, AdjustmentNote)
    RelatedDocumentID INTEGER,                    -- ID of the related document (e.g., BillID, InvoiceID)
    RelatedDocumentItemID INTEGER,                -- ID of the specific line item in the related document (e.g., BillItemID, InvoiceItemID)
    Notes TEXT,                                   -- Optional notes explaining the movement

    FOREIGN KEY (ItemID) REFERENCES InventoryItems(ItemID),
    FOREIGN KEY (WarehouseID) REFERENCES Warehouses(WarehouseID)
    -- Note: No direct FK for RelatedDocumentID due to polymorphism. Application logic handles this link.
);

-- Index for StockMovements
CREATE INDEX idx_stockmovements_item_date ON StockMovements (ItemID, MovementDate);


-- =============================================
-- Fixed Assets Table
-- =============================================

-- 30. Fixed Assets Table
CREATE TABLE FixedAssets (
    AssetID INTEGER PRIMARY KEY AUTOINCREMENT,      -- Primary key identifier for each asset
    AssetName TEXT NOT NULL,                        -- Name or description of the asset
    AssetTag TEXT UNIQUE,                           -- Unique physical tag number for the asset (optional)
    PurchaseDate TEXT NOT NULL,                     -- Date when asset was purchased (ISO format YYYY-MM-DD)
    PurchaseCost REAL NOT NULL,                     -- Original cost of the asset (Use DECIMAL)
    SalvageValue REAL NOT NULL DEFAULT 0,           -- Estimated residual value at the end of useful life (Use DECIMAL)
    DepreciationMethod TEXT NOT NULL CHECK(DepreciationMethod IN ('Straight-line', 'Declining Balance', 'Sum-of-Years-Digits', 'None')), -- Method used for calculating depreciation
    UsefulLife INTEGER NOT NULL,                    -- Expected useful life (e.g., in months or years - ensure consistency)
    DepreciationStartDate TEXT NOT NULL,            -- Date depreciation calculation begins (ISO format YYYY-MM-DD)
    AccumulatedDepreciation REAL NOT NULL DEFAULT 0,-- Total depreciation recorded to date (Use DECIMAL)
    CurrentValue REAL GENERATED ALWAYS AS (PurchaseCost - AccumulatedDepreciation) STORED, -- Current book value (calculated) (Use DECIMAL)
    AssetAccountID INTEGER NOT NULL,                -- FK to ChartOfAccounts (e.g., Machinery, Buildings)
    AccumDeprAccountID INTEGER NOT NULL,            -- FK to ChartOfAccounts (e.g., Acc Depr - Machinery)
    DeprExpenseAccountID INTEGER NOT NULL,          -- FK to ChartOfAccounts (e.g., Depreciation Expense)
    Status TEXT NOT NULL DEFAULT 'Active' CHECK(Status IN ('Active', 'Disposed', 'Sold', 'Retired')), -- Status of the asset
    DisposalDate TEXT,                              -- Date asset was disposed or sold (ISO format YYYY-MM-DD)
    DisposalPrice REAL,                             -- Amount received upon disposal/sale (Use DECIMAL)

    FOREIGN KEY (AssetAccountID) REFERENCES ChartOfAccounts(AccountID),
    FOREIGN KEY (AccumDeprAccountID) REFERENCES ChartOfAccounts(AccountID),
    FOREIGN KEY (DeprExpenseAccountID) REFERENCES ChartOfAccounts(AccountID)
);

-- =============================================
-- Insert Sample Data (Continue...)
-- =============================================

-- Sample Departments
INSERT INTO Departments (DepartmentName, Description) VALUES
('Board', 'Board of Directors'),
('Executive', 'Executive Leadership'),
('Finance', 'Finance Department'),
('Investor Relations', 'Investor Relations Team'),
('Treasury', 'Treasury Department'),
('Controlling', 'Financial Controlling Team'),
('Tax', 'Tax Management & Reporting'),
('Financial Planning', 'Financial Planning & Analysis'),
('Human Resources', 'HR Department'); -- Added HR

-- Sample Positions
INSERT INTO Positions (PositionTitle, Description, DepartmentID) VALUES
('Board Member', 'Member of the Board of Directors', 1),
('Chief Executive Officer', 'Company CEO', 2),
('Chief Financial Officer', 'Company CFO', 3),
('Internal Auditor', 'Internal Audit Function', 2),
('Investor Relations Manager', 'Manages investor communications', 4),
('Treasurer', 'Manages company cash and investments', 5),
('Controller', 'Manages accounting and reporting', 6),
('Tax Manager', 'Manages tax compliance and planning', 7),
('Financial Planning Manager', 'Manages financial planning and analysis', 8),
('Accountant', 'Accounting staff', 6),
('Financial Analyst', 'Financial analysis staff', 8),
('Cash Management Specialist', 'Manages cash operations', 5),
('Risk Management Specialist', 'Manages financial risks', 5),
('Investment Analyst', 'Manages investments', 5),
('Financial Institution Relations Manager', 'Manages banking relationships', 5),
('External Financing Specialist', 'Manages debt and equity funding', 5),
('Accounts Receivable Specialist', 'Manages customer accounts', 6),
('Accounts Payable Specialist', 'Manages vendor payments', 6),
('MIS Specialist', 'Manages financial information systems', 6),
('HR Manager', 'Manages Human Resources', 9), -- Added HR Position
('Payroll Specialist', 'Processes payroll', 9); -- Added Payroll Position

-- Sample Employees
INSERT INTO Employees (FirstName, LastName, Email, Phone, HireDate, DepartmentID, PositionID, ReportsTo, Salary, Status) VALUES
('John', 'Smith', 'john.smith@company.com', '555-1000', '2020-01-15', 2, 2, NULL, 250000.00, 'Active'),
('Jane', 'Doe', 'jane.doe@company.com', '555-1001', '2020-02-10', 3, 3, 1, 200000.00, 'Active'),
('Michael', 'Jones', 'michael.jones@company.com', '555-1002', '2020-03-15', 2, 4, 1, 120000.00, 'Active'),
('Emily', 'Brown', 'emily.brown@company.com', '555-1003', '2020-04-20', 4, 5, 2, 110000.00, 'Active'),
('David', 'Wilson', 'david.wilson@company.com', '555-1004', '2020-05-10', 5, 6, 2, 130000.00, 'Active'),
('Sarah', 'Miller', 'sarah.miller@company.com', '555-1005', '2020-06-15', 6, 7, 2, 125000.00, 'Active'),
('Robert', 'Taylor', 'robert.taylor@company.com', '555-1006', '2020-07-20', 7, 8, 2, 115000.00, 'Active'),
('Laura', 'Anderson', 'laura.anderson@company.com', '555-1007', '2020-08-15', 8, 9, 2, 118000.00, 'Active'),
('James', 'Thomas', 'james.thomas@company.com', '555-1008', '2021-01-05', 6, 10, 6, 85000.00, 'Active'), -- Accountant
('Patricia', 'Jackson', 'patricia.jackson@company.com', '555-1009', '2021-02-10', 8, 11, 8, 82000.00, 'Active'), -- Fin Analyst
('Richard', 'White', 'richard.white@company.com', '555-1010', '2021-03-15', 5, 12, 5, 78000.00, 'Active'), -- Cash Mgmt
('Linda', 'Harris', 'linda.harris@company.com', '555-1011', '2021-04-20', 5, 13, 5, 80000.00, 'Active'), -- Risk Mgmt
('Charles', 'Clark', 'charles.clark@company.com', '555-1012', '2021-05-10', 5, 14, 5, 82000.00, 'Active'), -- Inv Analyst
('Elizabeth', 'Lewis', 'elizabeth.lewis@company.com', '555-1013', '2021-06-15', 5, 15, 5, 85000.00, 'Active'), -- Bank Rel
('William', 'Young', 'william.young@company.com', '555-1014', '2021-07-20', 5, 16, 5, 83000.00, 'Active'), -- Ext Fin
('Jennifer', 'Walker', 'jennifer.walker@company.com', '555-1015', '2021-08-10', 6, 17, 6, 75000.00, 'Active'), -- AR Spec
('Daniel', 'Hall', 'daniel.hall@company.com', '555-1016', '2021-09-15', 6, 18, 6, 75000.00, 'Active'), -- AP Spec
('Karen', 'Allen', 'karen.allen@company.com', '555-1017', '2021-10-20', 6, 19, 6, 78000.00, 'Active'), -- MIS Spec
('Peter', 'Adams', 'peter.adams@company.com', '555-1018', '2022-01-10', 9, 20, 2, 140000.00, 'Active'), -- HR Manager
('Susan', 'Baker', 'susan.baker@company.com', '555-1019', '2022-02-15', 9, 21, 20, 70000.00, 'Active'); -- Payroll Spec

-- Sample Employee Payroll Info (NEW)
-- Make sure these align with Employees table data where applicable
-- Use EmployeeID from the INSERT statements above
INSERT INTO EmployeePayrollInfo (EmployeeID, PayType, PayFrequency, AnnualSalary, HourlyRate, OvertimeEligible, UpdatedBy) VALUES
(1, 'Salary', 'Semi-Monthly', 250000.00, NULL, 0, 1), -- CEO
(2, 'Salary', 'Semi-Monthly', 200000.00, NULL, 0, 1), -- CFO
(3, 'Salary', 'Semi-Monthly', 120000.00, NULL, 0, 1), -- Auditor
(4, 'Salary', 'Semi-Monthly', 110000.00, NULL, 0, 1), -- IR Mgr
(5, 'Salary', 'Semi-Monthly', 130000.00, NULL, 0, 1), -- Treasurer
(6, 'Salary', 'Semi-Monthly', 125000.00, NULL, 0, 1), -- Controller
(7, 'Salary', 'Semi-Monthly', 115000.00, NULL, 0, 1), -- Tax Mgr
(8, 'Salary', 'Semi-Monthly', 118000.00, NULL, 0, 1), -- FP Mgr
(9, 'Hourly', 'Bi-Weekly', NULL, 40.87, 1, 1), -- Accountant (Approx 85k/yr / 2080 hrs)
(10, 'Hourly', 'Bi-Weekly', NULL, 39.42, 1, 1), -- Fin Analyst (Approx 82k/yr)
(11, 'Hourly', 'Bi-Weekly', NULL, 37.50, 1, 1), -- Cash Mgmt (Approx 78k/yr)
(12, 'Hourly', 'Bi-Weekly', NULL, 38.46, 1, 1), -- Risk Mgmt (Approx 80k/yr)
(13, 'Hourly', 'Bi-Weekly', NULL, 39.42, 1, 1), -- Inv Analyst (Approx 82k/yr)
(14, 'Hourly', 'Bi-Weekly', NULL, 40.87, 1, 1), -- Bank Rel (Approx 85k/yr)
(15, 'Hourly', 'Bi-Weekly', NULL, 39.90, 1, 1), -- Ext Fin (Approx 83k/yr)
(16, 'Hourly', 'Bi-Weekly', NULL, 36.06, 1, 1), -- AR Spec (Approx 75k/yr)
(17, 'Hourly', 'Bi-Weekly', NULL, 36.06, 1, 1), -- AP Spec (Approx 75k/yr)
(18, 'Hourly', 'Bi-Weekly', NULL, 37.50, 1, 1), -- MIS Spec (Approx 78k/yr)
(19, 'Salary', 'Semi-Monthly', 140000.00, NULL, 0, 1), -- HR Mgr
(20, 'Hourly', 'Bi-Weekly', NULL, 33.65, 1, 1); -- Payroll Spec (Approx 70k/yr)

-- Sample Chart of Accounts (Add Payroll related accounts if needed)
INSERT INTO ChartOfAccounts (AccountNumber, AccountName, AccountType, ParentAccountID, Description, IsActive, BalanceType) VALUES
-- Assets
('1000', 'Assets', 'Asset', NULL, 'All company assets', 1, 'Debit'),
('1100', 'Current Assets', 'Asset', 1, 'Assets expected to be converted to cash within one year', 1, 'Debit'),
('1110', 'Cash and Cash Equivalents', 'Asset', 2, 'Cash and short-term investments', 1, 'Debit'),
('1111', 'Cash in Bank - Operating', 'Asset', 3, 'Main checking account', 1, 'Debit'), -- Specific name
('1112', 'Cash in Bank - Payroll', 'Asset', 3, 'Payroll checking account', 1, 'Debit'), -- Payroll cash
('1113', 'Cash on Hand', 'Asset', 3, 'Physical cash', 1, 'Debit'),
('1120', 'Short-term Investments', 'Asset', 2, 'Investments maturing within one year', 1, 'Debit'),
('1130', 'Accounts Receivable', 'Asset', 2, 'Amounts owed by customers', 1, 'Debit'),
('1140', 'Inventory', 'Asset', 2, 'Goods held for sale', 1, 'Debit'),
('1150', 'Prepaid Expenses', 'Asset', 2, 'Expenses paid in advance', 1, 'Debit'),
('1200', 'Non-current Assets', 'Asset', 1, 'Long-term assets', 1, 'Debit'),
('1210', 'Property, Plant and Equipment', 'Asset', 11, 'Tangible long-term assets', 1, 'Debit'), -- Corrected ParentID
('1211', 'Land', 'Asset', 12, 'Land owned by the company', 1, 'Debit'),
('1212', 'Buildings', 'Asset', 12, 'Buildings owned by the company', 1, 'Debit'),
('1213', 'Equipment', 'Asset', 12, 'Equipment owned by the company', 1, 'Debit'),
('1214', 'Vehicles', 'Asset', 12, 'Vehicles owned by the company', 1, 'Debit'),
('1215', 'Accumulated Depreciation - Buildings', 'Asset', 12, 'Accumulated depreciation of Buildings', 1, 'Credit'), -- Specific Accum Depr
('1216', 'Accumulated Depreciation - Equipment', 'Asset', 12, 'Accumulated depreciation of Equipment', 1, 'Credit'),
('1217', 'Accumulated Depreciation - Vehicles', 'Asset', 12, 'Accumulated depreciation of Vehicles', 1, 'Credit'),
('1220', 'Intangible Assets', 'Asset', 11, 'Non-physical assets', 1, 'Debit'),
('1221', 'Goodwill', 'Asset', 21, 'Goodwill from acquisitions', 1, 'Debit'),
('1222', 'Patents', 'Asset', 21, 'Patents owned by the company', 1, 'Debit'),
('1223', 'Trademarks', 'Asset', 21, 'Trademarks owned by the company', 1, 'Debit'),

-- Liabilities
('2000', 'Liabilities', 'Liability', NULL, 'All company liabilities', 1, 'Credit'),
('2100', 'Current Liabilities', 'Liability', 25, 'Liabilities due within one year', 1, 'Credit'),
('2110', 'Accounts Payable', 'Liability', 26, 'Amounts owed to vendors', 1, 'Credit'),
('2120', 'Short-term Loans', 'Liability', 26, 'Loans due within one year', 1, 'Credit'),
('2130', 'Accrued Expenses Payable', 'Liability', 26, 'Expenses incurred but not yet paid', 1, 'Credit'), -- Renamed slightly
('2131', 'Accrued Salaries and Wages', 'Liability', 29, 'Salaries/wages earned but not paid', 1, 'Credit'), -- Specific Accrual
('2132', 'Accrued Payroll Taxes Payable', 'Liability', 29, 'Employer/Employee taxes owed', 1, 'Credit'), -- Specific Accrual
('2133', 'Accrued Benefits Payable', 'Liability', 29, 'Benefit costs owed (e.g., insurance)', 1, 'Credit'), -- Specific Accrual
('2140', 'Income Tax Payable', 'Liability', 26, 'Income taxes owed', 1, 'Credit'),
('2150', 'Current Portion of Long-term Debt', 'Liability', 26, 'Long-term debt due within one year', 1, 'Credit'),
('2200', 'Non-current Liabilities', 'Liability', 25, 'Long-term liabilities', 1, 'Credit'),
('2210', 'Long-term Loans', 'Liability', 35, 'Loans due after one year', 1, 'Credit'),
('2220', 'Bonds Payable', 'Liability', 35, 'Bonds issued by the company', 1, 'Credit'),
('2230', 'Deferred Tax Liabilities', 'Liability', 35, 'Taxes deferred to future periods', 1, 'Credit'),

-- Equity
('3000', 'Equity', 'Equity', NULL, 'Owner''s equity', 1, 'Credit'),
('3100', 'Common Stock', 'Equity', 39, 'Common stock issued', 1, 'Credit'),
('3200', 'Preferred Stock', 'Equity', 39, 'Preferred stock issued', 1, 'Credit'),
('3300', 'Additional Paid-in Capital', 'Equity', 39, 'Capital in excess of par value', 1, 'Credit'),
('3400', 'Retained Earnings', 'Equity', 39, 'Accumulated earnings', 1, 'Credit'),
('3500', 'Treasury Stock', 'Equity', 39, 'Stock repurchased by the company', 1, 'Debit'),
('3600', 'Accumulated Other Comprehensive Income', 'Equity', 39, 'Other comprehensive income', 1, 'Credit'),

-- Revenue
('4000', 'Revenue', 'Revenue', NULL, 'Income from operations', 1, 'Credit'),
('4100', 'Sales Revenue', 'Revenue', 46, 'Revenue from sales', 1, 'Credit'),
('4200', 'Service Revenue', 'Revenue', 46, 'Revenue from services', 1, 'Credit'),
('4300', 'Rental Revenue', 'Revenue', 46, 'Revenue from rentals', 1, 'Credit'),
('4400', 'Interest Revenue', 'Revenue', 46, 'Revenue from interest', 1, 'Credit'),
('4500', 'Other Revenue', 'Revenue', 46, 'Other revenue sources', 1, 'Credit'),

-- Expenses
('5000', 'Expenses', 'Expense', NULL, 'All company expenses', 1, 'Debit'),
('5100', 'Cost of Goods Sold', 'Expense', 52, 'Direct costs of products sold', 1, 'Debit'),
('5200', 'Operating Expenses', 'Expense', 52, 'General operating costs', 1, 'Debit'),
('5210', 'Salaries and Wages Expense', 'Expense', 54, 'Gross employee compensation', 1, 'Debit'), -- Specific Expense
('5220', 'Payroll Tax Expense', 'Expense', 54, 'Employer portion of payroll taxes', 1, 'Debit'), -- Specific Expense
('5230', 'Employee Benefits Expense', 'Expense', 54, 'Cost of employee benefits', 1, 'Debit'), -- Specific Expense
('5300', 'Rent Expense', 'Expense', 54, 'Rent for facilities', 1, 'Debit'),
('5400', 'Utilities Expense', 'Expense', 54, 'Electricity, water, etc.', 1, 'Debit'),
('5500', 'Depreciation Expense', 'Expense', 52, 'Depreciation of assets', 1, 'Debit'),
('5600', 'Interest Expense', 'Expense', 52, 'Interest on loans', 1, 'Debit'),
('5700', 'Marketing Expense', 'Expense', 54, 'Marketing and advertising', 1, 'Debit'),
('5800', 'Office Supplies Expense', 'Expense', 54, 'Office supplies', 1, 'Debit'),
('5900', 'Travel Expense', 'Expense', 54, 'Business travel', 1, 'Debit'),
('6000', 'Professional Fees', 'Expense', 54, 'Legal, consulting, etc.', 1, 'Debit'),
('6100', 'Income Tax Expense', 'Expense', 52, 'Income taxes', 1, 'Debit');


-- Sample Fiscal Years (No change needed)
INSERT INTO FiscalYears (StartDate, EndDate, IsClosed, Description) VALUES
('2023-01-01', '2023-12-31', 1, 'Fiscal Year 2023'),
('2024-01-01', '2024-12-31', 0, 'Fiscal Year 2024'),
('2025-01-01', '2025-12-31', 0, 'Fiscal Year 2025');

-- Sample Fiscal Periods (No change needed)
INSERT INTO FiscalPeriods (FiscalYearID, PeriodNumber, StartDate, EndDate, IsClosed, ClosedBy, ClosedDate) VALUES
-- 2023 Periods (All Closed)
(1, 1, '2023-01-01', '2023-01-31', 1, 2, '2023-02-15'), (1, 2, '2023-02-01', '2023-02-28', 1, 2, '2023-03-15'), (1, 3, '2023-03-01', '2023-03-31', 1, 2, '2023-04-15'), (1, 4, '2023-04-01', '2023-04-30', 1, 2, '2023-05-15'), (1, 5, '2023-05-01', '2023-05-31', 1, 2, '2023-06-15'), (1, 6, '2023-06-01', '2023-06-30', 1, 2, '2023-07-15'), (1, 7, '2023-07-01', '2023-07-31', 1, 2, '2023-08-15'), (1, 8, '2023-08-01', '2023-08-31', 1, 2, '2023-09-15'), (1, 9, '2023-09-01', '2023-09-30', 1, 2, '2023-10-15'), (1, 10, '2023-10-01', '2023-10-31', 1, 2, '2023-11-15'), (1, 11, '2023-11-01', '2023-11-30', 1, 2, '2023-12-15'), (1, 12, '2023-12-01', '2023-12-31', 1, 2, '2024-01-15'),
-- 2024 Periods (Some Closed)
(2, 1, '2024-01-01', '2024-01-31', 1, 2, '2024-02-15'), (2, 2, '2024-02-01', '2024-02-29', 1, 2, '2024-03-15'), (2, 3, '2024-03-01', '2024-03-31', 1, 2, '2024-04-15'), (2, 4, '2024-04-01', '2024-04-30', 1, 2, '2024-05-15'), (2, 5, '2024-05-01', '2024-05-31', 1, 2, '2024-06-15'), (2, 6, '2024-06-01', '2024-06-30', 1, 2, '2024-07-15'), (2, 7, '2024-07-01', '2024-07-31', 1, 2, '2024-08-15'), (2, 8, '2024-08-01', '2024-08-31', 1, 2, '2024-09-15'), (2, 9, '2024-09-01', '2024-09-30', 1, 2, '2024-10-15'), (2, 10, '2024-10-01', '2024-10-31', 1, 2, '2024-11-15'), (2, 11, '2024-11-01', '2024-11-30', 0, NULL, NULL), (2, 12, '2024-12-01', '2024-12-31', 0, NULL, NULL),
-- 2025 Periods (Some Closed, some Open)
(3, 1, '2025-01-01', '2025-01-31', 1, 2, '2025-02-15'), -- Jan Closed
(3, 2, '2025-02-01', '2025-02-28', 1, 2, '2025-03-15'), -- Feb Closed
(3, 3, '2025-03-01', '2025-03-31', 0, NULL, NULL), -- Mar Open
(3, 4, '2025-04-01', '2025-04-30', 0, NULL, NULL), (3, 5, '2025-05-01', '2025-05-31', 0, NULL, NULL), (3, 6, '2025-06-01', '2025-06-30', 0, NULL, NULL), (3, 7, '2025-07-01', '2025-07-31', 0, NULL, NULL), (3, 8, '2025-08-01', '2025-08-31', 0, NULL, NULL), (3, 9, '2025-09-01', '2025-09-30', 0, NULL, NULL), (3, 10, '2025-10-01', '2025-10-31', 0, NULL, NULL), (3, 11, '2025-11-01', '2025-11-30', 0, NULL, NULL), (3, 12, '2025-12-01', '2025-12-31', 0, NULL, NULL);


-- Sample Bank Accounts (Use Payroll account ID '5' from CoA)
INSERT INTO BankAccounts (AccountName, AccountNumber, BankName, BankBranch, IBAN, Currency, AccountType, OpenDate, CurrentBalance, LastReconciliationDate, IsActive) VALUES
('Main Operating Account', '1234567890', 'First National Bank', 'Downtown Branch', 'US12345678901234567890', 'USD', 'Checking', '2020-01-05', 1250000.00, '2025-03-31', 1), -- ID 1 (CoA 4)
('Payroll Account', '2345678901', 'First National Bank', 'Downtown Branch', 'US23456789012345678901', 'USD', 'Checking', '2020-01-05', 350000.00, '2025-03-31', 1), -- ID 2 (CoA 5)
('Tax Reserve Account', '3456789012', 'First National Bank', 'Downtown Branch', 'US34567890123456789012', 'USD', 'Savings', '2020-01-05', 420000.00, '2025-03-31', 1), -- ID 3
('Short-term Investment', '4567890123', 'Investment Bank', 'Financial District', 'US45678901234567890123', 'USD', 'Money Market', '2020-02-10', 1800000.00, '2025-03-31', 1), -- ID 4
('Euro Account', '5678901234', 'International Bank', 'International Branch', 'EU56789012345678901234', 'EUR', 'Checking', '2020-03-15', 450000.00, '2025-03-31', 1); -- ID 5

-- Sample Cash Transactions (Adjust for Payroll Account 2)
INSERT INTO CashTransactions (TransactionDate, BankAccountID, TransactionType, Amount, Description, Reference, RelatedAccountID, CreatedBy, CreationDate) VALUES
('2025-03-01', 1, 'Deposit', 250000.00, 'Customer payment batch', 'DEP-25030101', 8, 2, '2025-03-01 09:15:00'), -- AR = 8
('2025-03-05', 1, 'Withdrawal', 180000.00, 'Vendor payment batch', 'WIT-25030501', 27, 2, '2025-03-05 10:30:00'), -- AP = 27
('2025-03-10', 2, 'Deposit', 350000.00, 'Transfer for payroll', 'DEP-25031001', 55, 2, '2025-03-10 11:45:00'), -- Salaries Exp = 55
('2025-03-15', 2, 'Withdrawal', 320000.00, 'Monthly payroll', 'WIT-25031501', 55, 2, '2025-03-15 13:00:00'), -- Salaries Exp = 55
('2025-03-20', 3, 'Deposit', 120000.00, 'Tax reserve funding', 'DEP-25032001', 33, 2, '2025-03-20 14:15:00'), -- Inc Tax Pay = 33
('2025-03-25', 4, 'Deposit', 500000.00, 'Investment funding', 'DEP-25032501', 7, 2, '2025-03-25 15:30:00'), -- ShortTerm Inv = 7
('2025-03-30', 5, 'Deposit', 200000.00, 'EUR funding for international payments', 'DEP-25033001', 4, 2, '2025-03-30 16:45:00'); -- Cash Op = 4

-- Sample Customers (No change needed)
INSERT INTO Customers (CustomerName, ContactPerson, Email, Phone, Address, TaxID, CreditLimit, PaymentTerms, IsActive) VALUES
('Acme Corporation', 'John Customer', 'john.customer@acme.com', '555-2000', '123 Business St, Business City, BC 12345', '12-3456789', 250000.00, 'Net 30', 1), ('Beta Enterprises', 'Jane Client', 'jane.client@beta.com', '555-2001', '456 Commerce Ave, Commerce City, CC 23456', '23-4567890', 150000.00, 'Net 30', 1), ('Gamma Industries', 'Bob Buyer', 'bob.buyer@gamma.com', '555-2002', '789 Industry Blvd, Industry Town, IT 34567', '34-5678901', 200000.00, 'Net 45', 1), ('Delta Services', 'Alice Account', 'alice.account@delta.com', '555-2003', '321 Service Rd, Service Village, SV 45678', '45-6789012', 100000.00, 'Net 15', 1), ('Epsilon Tech', 'Mike Manager', 'mike.manager@epsilon.com', '555-2004', '654 Tech Parkway, Tech City, TC 56789', '56-7890123', 300000.00, 'Net 45', 1);

-- Sample Invoices (Adjust AccountIDs based on CoA inserts above)
INSERT INTO Invoices (InvoiceNumber, CustomerID, InvoiceDate, DueDate, TotalAmount, PaidAmount, Status, PaymentTerms, CreatedBy, CreationDate) VALUES
('INV-2025-0001', 1, '2025-03-01', '2025-03-31', 125000.00, 125000.00, 'Paid', 'Net 30', 16, '2025-03-01 09:00:00'),
('INV-2025-0002', 2, '2025-03-05', '2025-04-04', 75000.00, 0.00, 'Issued', 'Net 30', 16, '2025-03-05 10:00:00'),
('INV-2025-0003', 3, '2025-03-10', '2025-04-24', 95000.00, 50000.00, 'Issued', 'Net 45', 16, '2025-03-10 11:00:00'),
('INV-2025-0004', 4, '2025-03-15', '2025-03-30', 42000.00, 42000.00, 'Paid', 'Net 15', 16, '2025-03-15 12:00:00'),
('INV-2025-0005', 5, '2025-03-20', '2025-05-04', 150000.00, 0.00, 'Issued', 'Net 45', 16, '2025-03-20 13:00:00');

-- Sample Invoice Items (Adjust AccountIDs based on CoA inserts above)
-- Sales Revenue = 47, Service Revenue = 48
INSERT INTO InvoiceItems (InvoiceID, Description, Quantity, UnitPrice, TaxRate, AccountID) VALUES
(1, 'Product A - Enterprise License', 5, 20000.00, 10.00, 47), -- Sales Rev
(1, 'Implementation Services', 100, 250.00, 10.00, 48), -- Service Rev
(2, 'Product B - Professional License', 15, 5000.00, 0.00, 47), -- Sales Rev
(3, 'Product C - Custom Development', 1, 95000.00, 0.00, 48), -- Service Rev
(4, 'Product A - Standard License', 6, 7000.00, 0.00, 47), -- Sales Rev
(5, 'Hardware Solution X', 10, 15000.00, 0.00, 47); -- Sales Rev

-- Sample Customer Payments (Bank AccountID 1 = Main Operating)
INSERT INTO CustomerPayments (CustomerID, PaymentDate, Amount, PaymentMethod, Reference, BankAccountID, Notes, CreatedBy, CreationDate) VALUES
(1, '2025-03-25', 125000.00, 'Wire Transfer', 'WIRE-ACME-25032501', 1, 'Payment for INV-2025-0001', 16, '2025-03-25 14:00:00'),
(3, '2025-03-27', 50000.00, 'Check', 'CHECK-12345', 1, 'Partial payment for INV-2025-0003', 16, '2025-03-27 15:00:00'),
(4, '2025-03-28', 42000.00, 'ACH', 'ACH-DELTA-25032801', 1, 'Payment for INV-2025-0004', 16, '2025-03-28 16:00:00');

-- Sample Vendors (No change needed)
INSERT INTO Vendors (VendorName, ContactPerson, Email, Phone, Address, TaxID, PaymentTerms, IsActive) VALUES
('Supplier One', 'Sam Supplier', 'sam.supplier@supplierone.com', '555-3000', '123 Supply St, Supplier City, SC 12345', '67-8901234', 'Net 30', 1), ('Vendor Two', 'Vera Vendor', 'vera.vendor@vendortwo.com', '555-3001', '456 Vendor Ave, Vendor City, VC 23456', '78-9012345', 'Net 15', 1), ('Provider Three', 'Paul Provider', 'paul.provider@providerthree.com', '555-3002', '789 Provider Blvd, Provider Town, PT 34567', '89-0123456', 'Net 45', 1), ('Manufacturer Four', 'Mary Manufacturer', 'mary.manufacturer@manufacturerfour.com', '555-3003', '321 Manufacturing Rd, Manufacturing Village, MV 45678', '90-1234567', 'Net 30', 1), ('Contractor Five', 'Carl Contractor', 'carl.contractor@contractorfive.com', '555-3004', '654 Contractor Parkway, Contractor City, CC 56789', '01-2345678', 'Net 15', 1);

-- Sample Bills (Adjust AccountIDs based on CoA inserts above)
INSERT INTO Bills (BillNumber, VendorID, BillDate, DueDate, TotalAmount, PaidAmount, Status, CreatedBy, CreationDate) VALUES
('BILL-2025-0001', 1, '2025-03-02', '2025-04-01', 85000.00, 85000.00, 'Paid', 17, '2025-03-02 09:00:00'),
('BILL-2025-0002', 2, '2025-03-07', '2025-03-22', 42000.00, 42000.00, 'Paid', 17, '2025-03-07 10:00:00'),
('BILL-2025-0003', 3, '2025-03-12', '2025-04-26', 65000.00, 0.00, 'Received', 17, '2025-03-12 11:00:00'),
('BILL-2025-0004', 4, '2025-03-17', '2025-04-16', 78000.00, 0.00, 'Received', 17, '2025-03-17 12:00:00'),
('BILL-2025-0005', 5, '2025-03-22', '2025-04-06', 35000.00, 0.00, 'Received', 17, '2025-03-22 13:00:00');

-- Sample Bill Items (Adjust AccountIDs based on CoA inserts above)
-- COGS = 53, Office Supplies = 62, Prof Fees = 64, Equipment = 15, Salaries = 55
INSERT INTO BillItems (BillID, Description, Quantity, UnitPrice, TaxRate, AccountID) VALUES
(1, 'Raw Materials - Type A', 10000, 8.50, 0.00, 53), -- COGS
(2, 'Office Supplies Bulk Order', 1, 42000.00, 0.00, 62), -- Office Supp Exp
(3, 'IT Consulting Services - Q1', 1, 65000.00, 0.00, 64), -- Prof Fees
(4, 'Manufacturing Widget Press X2', 2, 39000.00, 0.00, 15), -- Equipment (Asset)
(5, 'Contract Labor - March Services', 700, 50.00, 0.00, 55); -- Salaries Exp (Treating as contractor payroll exp)

-- Sample Vendor Payments (Bank AccountID 1 = Main Operating)
INSERT INTO VendorPayments (VendorID, PaymentDate, Amount, PaymentMethod, Reference, BankAccountID, Notes, CreatedBy, CreationDate) VALUES
(1, '2025-03-26', 85000.00, 'ACH', 'ACH-SUPP1-25032601', 1, 'Payment for BILL-2025-0001', 17, '2025-03-26 14:00:00'),
(2, '2025-03-20', 42000.00, 'Wire Transfer', 'WIRE-VEND2-25032001', 1, 'Payment for BILL-2025-0002', 17, '2025-03-20 15:00:00');

-- Sample Tax Rates (No change needed)
INSERT INTO TaxRates (TaxName, Rate, Description, IsActive) VALUES
('No Tax', 0.00, 'No tax applied', 1), ('Sales Tax', 8.50, 'Standard sales tax', 1), ('VAT', 20.00, 'Value Added Tax for international', 1), ('Reduced VAT', 10.00, 'Reduced Value Added Tax rate', 1);

-- Sample Tax Returns (No change needed)
INSERT INTO TaxReturns (TaxType, PeriodStart, PeriodEnd, DueDate, TotalTaxAmount, Status, FiledBy, FilingDate, Notes) VALUES
('Sales Tax', '2025-01-01', '2025-01-31', '2025-02-20', 42500.00, 'Filed', 7, '2025-02-15', 'January 2025 Sales Tax Return'), ('Sales Tax', '2025-02-01', '2025-02-28', '2025-03-20', 38750.00, 'Filed', 7, '2025-03-15', 'February 2025 Sales Tax Return'), ('VAT', '2025-01-01', '2025-03-31', '2025-04-30', 95000.00, 'Draft', NULL, NULL, 'Q1 2025 VAT Return');

-- Sample Budgets (No change needed)
INSERT INTO Budgets (BudgetName, FiscalYearID, DepartmentID, Description, Status, CreatedBy, ApprovedBy, CreationDate, ApprovalDate) VALUES
('Annual Corporate Budget 2025', 3, NULL, 'Main company budget for 2025', 'Approved', 8, 2, '2024-11-15 10:00:00', '2024-12-10'), ('Finance Department Budget 2025', 3, 3, 'Finance department budget for 2025', 'Approved', 8, 2, '2024-11-16 10:00:00', '2024-12-10'), ('Treasury Department Budget 2025', 3, 5, 'Treasury department budget for 2025', 'Approved', 8, 2, '2024-11-17 10:00:00', '2024-12-10'), ('Controlling Department Budget 2025', 3, 6, 'Controlling department budget for 2025', 'Approved', 8, 2, '2024-11-18 10:00:00', '2024-12-10'), ('Tax Department Budget 2025', 3, 7, 'Tax department budget for 2025', 'Approved', 8, 2, '2024-11-19 10:00:00', '2024-12-10');

-- Sample Budget Items (Adjust AccountIDs and PeriodIDs based on inserts above)
-- PeriodIDs for 2025: Jan=25, Feb=26, Mar=27, Apr=28
-- CoA IDs: Sales Rev=47, COGS=53, Salaries=55, Prof Fees = 64
INSERT INTO BudgetItems (BudgetID, AccountID, PeriodID, PlannedAmount, ActualAmount, Notes) VALUES
-- Corporate Budget - Revenue Accounts (brief sample)
(1, 47, 25, 500000.00, 510000.00, 'Sales revenue - Jan 2025'),
(1, 47, 26, 520000.00, 490000.00, 'Sales revenue - Feb 2025'),
(1, 47, 27, 550000.00, 0.00, 'Sales revenue - Mar 2025'),
(1, 47, 28, 570000.00, 0.00, 'Sales revenue - Apr 2025'),

-- Corporate Budget - Major Expense Accounts (brief sample)
(1, 53, 25, 250000.00, 245000.00, 'COGS - Jan 2025'),
(1, 53, 26, 260000.00, 235000.00, 'COGS - Feb 2025'),
(1, 53, 27, 275000.00, 0.00, 'COGS - Mar 2025'),
(1, 53, 28, 285000.00, 0.00, 'COGS - Apr 2025'),

(1, 55, 25, 120000.00, 118000.00, 'Salaries - Jan 2025'),
(1, 55, 26, 120000.00, 122000.00, 'Salaries - Feb 2025'),
(1, 55, 27, 125000.00, 0.00, 'Salaries - Mar 2025'),
(1, 55, 28, 125000.00, 0.00, 'Salaries - Apr 2025'),

-- Finance Department Budget (sample)
(2, 55, 25, 35000.00, 34500.00, 'Finance salaries - Jan 2025'),
(2, 55, 26, 35000.00, 35000.00, 'Finance salaries - Feb 2025'),
(2, 55, 27, 37000.00, 0.00, 'Finance salaries - Mar 2025'),
(2, 64, 25, 12000.00, 11800.00, 'Finance professional fees - Jan 2025'), -- Changed Account to Prof Fees
(2, 64, 26, 8000.00, 8200.00, 'Finance professional fees - Feb 2025'),
(2, 64, 27, 8000.00, 0.00, 'Finance professional fees - Mar 2025');


-- Sample Financial Reports (Adjust PeriodIDs based on inserts above)
-- PeriodIDs for 2025: Jan=25, Feb=26
INSERT INTO FinancialReports (ReportName, ReportType, FiscalYearID, PeriodID, GenerationDate, GeneratedBy, Parameters, Description) VALUES
('January 2025 Income Statement', 'Income Statement', 3, 25, '2025-02-10 09:00:00', 6, '{"detailed": true, "comparative": false}', 'Monthly income statement for January 2025'),
('February 2025 Income Statement', 'Income Statement', 3, 26, '2025-03-10 09:00:00', 6, '{"detailed": true, "comparative": true}', 'Monthly income statement for February 2025'),
('January 2025 Balance Sheet', 'Balance Sheet', 3, 25, '2025-02-10 10:00:00', 6, '{"detailed": true}', 'Monthly balance sheet as of January 31, 2025'),
('February 2025 Balance Sheet', 'Balance Sheet', 3, 26, '2025-03-10 10:00:00', 6, '{"detailed": true}', 'Monthly balance sheet as of February 28, 2025'),
('January 2025 Cash Flow Statement', 'Cash Flow', 3, 25, '2025-02-10 11:00:00', 6, '{"detailed": true}', 'Monthly cash flow statement for January 2025'),
('February 2025 Cash Flow Statement', 'Cash Flow', 3, 26, '2025-03-10 11:00:00', 6, '{"detailed": true}', 'Monthly cash flow statement for February 2025'),
('Q1 2025 Budget vs Actual', 'Custom', 3, NULL, '2025-04-05 09:00:00', 8, '{"type": "budget_comparison", "period_start": "2025-01-01", "period_end": "2025-03-31"}', 'Q1 2025 Budget to Actual Comparison');

-- Sample Approval Workflows (No change needed)
INSERT INTO ApprovalWorkflows (WorkflowName, Description, Status) VALUES
('Invoice Approval', 'Workflow for approving customer invoices', 'Active'), ('Payment Approval', 'Workflow for approving vendor payments', 'Active'), ('Budget Approval', 'Workflow for approving annual budgets', 'Active'), ('Financial Report Approval', 'Workflow for approving financial reports', 'Active');

-- Sample Approval Steps (No change needed)
INSERT INTO ApprovalSteps (WorkflowID, StepNumber, ApproverPositionID, IsRequired, Description) VALUES
-- Invoice Approval Workflow
(1, 1, 7, 1, 'Controller approval'), (1, 2, 3, 0, 'CFO approval for invoices over $50,000'), -- Made step 2 optional (IsRequired=0)
-- Payment Approval Workflow
(2, 1, 6, 1, 'Treasurer approval'), (2, 2, 7, 1, 'Controller approval'), (2, 3, 3, 0, 'CFO approval for payments over $50,000'), -- Made step 3 optional
-- Budget Approval Workflow
(3, 1, 7, 1, 'Controller review'), (3, 2, 3, 1, 'CFO approval'), (3, 3, 2, 1, 'CEO final approval'),
-- Financial Report Approval Workflow
(4, 1, 7, 1, 'Controller review and approval'), (4, 2, 3, 1, 'CFO approval');

-- Sample Audit Logs (No change needed)
INSERT INTO AuditLogs (TableName, RecordID, ActionType, OldValue, NewValue, ChangedBy, ChangeDate, IPAddress) VALUES
('Invoices', 2, 'Update', '{"Status": "Draft"}', '{"Status": "Issued"}', 16, '2025-03-05 10:30:00', '192.168.1.101'),
('Invoices', 3, 'Update', '{"Status": "Draft"}', '{"Status": "Issued"}', 16, '2025-03-10 11:30:00', '192.168.1.101'),
('Bills', 3, 'Update', '{"Status": "Draft"}', '{"Status": "Received"}', 17, '2025-03-12 11:30:00', '192.168.1.102'),
('Invoices', 1, 'Update', '{"Status": "Issued", "PaidAmount": 0.00}', '{"Status": "Paid", "PaidAmount": 125000.00}', 16, '2025-03-25 14:30:00', '192.168.1.101'),
('GeneralLedger', 1, 'Insert', NULL, '{"EntryDate": "2025-03-01", "AccountID": 8, "DebitAmount": 125000.00}', 2, '2025-03-01 09:30:00', '192.168.1.100'); -- AR = 8

-- Sample General Ledger Entries (Adjust AccountIDs based on CoA inserts above)
-- AR=8, SalesRev=47, CashOp=4, AP=27, COGS=53, SalariesExp=55
INSERT INTO GeneralLedger (EntryDate, Description, AccountID, DebitAmount, CreditAmount, EntryType, Reference, ApprovedBy, CreatedBy, CreationDate) VALUES
-- Revenue recognition INV-2025-0001 (Assume single line for simplicity in sample GL)
('2025-03-01', 'Revenue recognition - INV-2025-0001', 8, 125000.00, 0.00, 'Sale', 'INV-2025-0001', 2, 6, '2025-03-01 10:00:00'), -- Dr AR
('2025-03-01', 'Revenue recognition - INV-2025-0001', 47, 0.00, 125000.00, 'Sale', 'INV-2025-0001', 2, 6, '2025-03-01 10:00:00'), -- Cr Sales Rev

-- Payment received INV-2025-0001
('2025-03-25', 'Payment received - INV-2025-0001', 4, 125000.00, 0.00, 'Payment', 'WIRE-ACME-25032501', 2, 16, '2025-03-25 14:15:00'), -- Dr Cash Op
('2025-03-25', 'Payment received - INV-2025-0001', 8, 0.00, 125000.00, 'Payment', 'WIRE-ACME-25032501', 2, 16, '2025-03-25 14:15:00'), -- Cr AR

-- Purchase recorded BILL-2025-0001 (Assume single line COGS)
('2025-03-02', 'Purchase recorded - BILL-2025-0001', 53, 85000.00, 0.00, 'Purchase', 'BILL-2025-0001', 2, 6, '2025-03-02 10:00:00'), -- Dr COGS
('2025-03-02', 'Purchase recorded - BILL-2025-0001', 27, 0.00, 85000.00, 'Purchase', 'BILL-2025-0001', 2, 6, '2025-03-02 10:00:00'), -- Cr AP

-- Payment made BILL-2025-0001
('2025-03-26', 'Payment made - BILL-2025-0001', 27, 85000.00, 0.00, 'Payment', 'ACH-SUPP1-25032601', 2, 17, '2025-03-26 14:15:00'), -- Dr AP
('2025-03-26', 'Payment made - BILL-2025-0001', 4, 0.00, 85000.00, 'Payment', 'ACH-SUPP1-25032601', 2, 17, '2025-03-26 14:15:00'), -- Cr Cash Op

-- Payroll entry (Simplified - Gross Pay to Expense, Net Pay from Cash)
-- Cash Payroll Account = 5
('2025-03-15', 'Monthly payroll expense', 55, 320000.00, 0.00, 'Payroll', 'PR-202503', 2, 20, '2025-03-15 13:30:00'), -- Dr Salaries Exp
('2025-03-15', 'Monthly payroll cash disb.', 5, 0.00, 320000.00, 'Payroll', 'PR-202503', 2, 20, '2025-03-15 13:30:00'); -- Cr Cash Payroll

-- Sample Warehouses
INSERT INTO Warehouses (WarehouseName, Location) VALUES
('Main Warehouse', '100 Industrial Way'),
('Retail Backroom', '123 Retail St');

-- Sample Products
INSERT INTO Products (ProductSKU, ProductName, UnitPrice, Description) VALUES
('PROD-A', 'Product A', 250.00, 'Standard Product A'),
('PROD-B', 'Product B', 500.00, 'Premium Product B');

-- Sample Inventory Items (Link to Products and CoA)
-- Inventory Asset = 9, COGS = 53
INSERT INTO InventoryItems (ProductID, ItemSKU, ItemName, UnitOfMeasure, StandardCost, InventoryAssetAccountID, COGSAccountID, ReorderPoint) VALUES
(1, 'ITEM-A001', 'Product A - Unit', 'Each', 150.00, 9, 53, 50.0),
(2, 'ITEM-B001', 'Product B - Unit', 'Each', 300.00, 9, 53, 25.0);

-- Sample Stock Movements
INSERT INTO StockMovements (ItemID, MovementDate, MovementType, QuantityChange, UnitCost, WarehouseID, RelatedDocumentType, RelatedDocumentID) VALUES
(1, '2025-01-10 10:00:00', 'Purchase', 200.0, 150.00, 1, 'Bill', 1), -- Purchase for Bill 1 Item (assume this was Bill 1)
(2, '2025-01-15 11:00:00', 'Purchase', 100.0, 300.00, 1, 'Bill', 4), -- Purchase for Bill 4 (assume Equip was Item B)
(1, '2025-03-01 14:00:00', 'Sale', -5.0, 150.00, 1, 'Invoice', 1), -- Sale for Invoice 1 (Assume Item A)
(2, '2025-03-05 15:00:00', 'Sale', -15.0, 300.00, 1, 'Invoice', 2); -- Sale for Invoice 2 (Assume Item B)

-- Sample Fixed Assets (Link to CoA)
-- Asset Accounts: Equipment = 15, Vehicles = 16
-- Accum Depr: Equipment = 18, Vehicles = 19
-- Depr Expense = 59
INSERT INTO FixedAssets (AssetName, AssetTag, PurchaseDate, PurchaseCost, SalvageValue, DepreciationMethod, UsefulLife, DepreciationStartDate, AssetAccountID, AccumDeprAccountID, DeprExpenseAccountID) VALUES
('Delivery Van 1', 'VAN-001', '2023-05-15', 35000.00, 5000.00, 'Straight-line', 5, '2023-06-01', 16, 19, 59),
('Main Server Rack', 'SRV-001', '2024-01-20', 15000.00, 1000.00, 'Straight-line', 3, '2024-02-01', 15, 18, 59);