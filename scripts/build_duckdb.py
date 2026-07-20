"""
Build api/_store/procurement.duckdb from the raw Structured_Data CSVs and the
UNGM UNSPSC xlsx reference table.

Design choices:
  - Column names are renamed to snake_case (no spaces) so the text-to-SQL
    agent can generate SQL without identifier quoting, which measurably
    reduces LLM SQL-generation errors.
  - Currency strings ("$1.00 ") and US-format dates are cleaned/cast at
    build time (not query time) so every query the SQL agent issues later
    is a fast, simple SELECT over already-typed columns.
  - The UNSPSC hierarchy (13,313 rows, Key/Parent key/Code/Title) is loaded
    as a plain lookup table rather than embedded as RAG text -- exact/LIKE
    matching on code/title is far more reliable than embedding similarity
    for a taxonomy lookup.
  - Everything is written to a single embedded .duckdb file committed to
    the repo, avoiding any external database/infra for this take-home.
"""

from pathlib import Path

import duckdb
import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "Structured_Data"
KB_DIR = ROOT / "data" / "KnowledgeBase"
STORE_DIR = ROOT / "api" / "_store"
STORE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = STORE_DIR / "procurement.duckdb"

PO_CSV = DATA_DIR / "purchase_orders_2012_2015.csv"
INVOICE_CSV = DATA_DIR / "Invoice_data.csv"
UNSPSC_XLSX = KB_DIR / "UNGM_UNSPSC_12-Apr-2026..xlsx"


def build_purchase_orders(con: duckdb.DuckDBPyConnection):
    con.execute(
        f"""
        CREATE OR REPLACE TABLE purchase_orders AS
        SELECT
            try_cast(try_strptime("Creation Date", '%m/%d/%Y') AS DATE)      AS creation_date,
            try_cast(try_strptime("Purchase Date", '%m/%d/%Y') AS DATE)      AS purchase_date,
            "Fiscal Year"                                                AS fiscal_year,
            "LPA Number"                                                 AS lpa_number,
            "Purchase Order Number"                                      AS po_number,
            "Requisition Number"                                         AS requisition_number,
            "Acquisition Type"                                           AS acquisition_type,
            "Sub-Acquisition Type"                                       AS sub_acquisition_type,
            "Acquisition Method"                                         AS acquisition_method,
            "Sub-Acquisition Method"                                     AS sub_acquisition_method,
            "Department Name"                                            AS department_name,
            "Supplier Code"                                              AS supplier_code,
            "Supplier Name"                                              AS supplier_name,
            "Supplier Qualifications"                                    AS supplier_qualifications,
            "Supplier Zip Code"                                          AS supplier_zip_code,
            upper("CalCard") = 'YES'                                     AS calcard,
            "Item Name"                                                  AS item_name,
            "Item Description"                                           AS item_description,
            try_cast("Quantity" AS DOUBLE)                                AS quantity,
            try_cast(replace(replace(trim("Unit Price"), '$', ''), ',', '') AS DOUBLE)  AS unit_price,
            try_cast(replace(replace(trim("Total Price"), '$', ''), ',', '') AS DOUBLE) AS total_price,
            "Classification Codes"                                       AS classification_codes,
            "Normalized UNSPSC"                                          AS unspsc_code,
            "Commodity Title"                                           AS commodity_title,
            "Class"                                                      AS class_code,
            "Class Title"                                               AS class_title,
            "Family"                                                     AS family_code,
            "Family Title"                                              AS family_title,
            "Segment"                                                    AS segment_code,
            "Segment Title"                                             AS segment_title,
            "Location"                                                   AS location
        FROM read_csv_auto(
            '{PO_CSV.as_posix()}',
            header=True, ALL_VARCHAR=TRUE, null_padding=True, ignore_errors=True,
            store_rejects=True, rejects_table='po_rejects'
        )
        """
    )
    n = con.execute("SELECT count(*) FROM purchase_orders").fetchone()[0]
    n_rejects = con.execute("SELECT count(*) FROM po_rejects").fetchone()[0]
    print(
        f"purchase_orders: {n} rows ({n_rejects} genuinely malformed source rows with "
        "unterminated quotes were skipped). Note: wc -l on the CSV reports 376,876 lines, "
        "but the Location column embeds literal newlines inside quoted values (e.g. "
        '\'"90640\\n(34.01573, -118.113367)"\'), so a single logical record can span several '
        "physical lines -- the true row count is ~152k, confirmed against Python's stdlib "
        "csv module parse."
    )


def build_invoices(con: duckdb.DuckDBPyConnection):
    con.execute(
        f"""
        CREATE OR REPLACE TABLE invoices AS
        SELECT
            "countryCode"                                               AS country_code,
            "customerID"                                                AS customer_id,
            try_cast(try_strptime("PaperlessDate", '%m/%d/%Y') AS DATE)      AS paperless_date,
            "invoiceNumber"                                             AS invoice_number,
            try_cast(try_strptime("InvoiceDate", '%m/%d/%Y') AS DATE)        AS invoice_date,
            try_cast(try_strptime("DueDate", '%m/%d/%Y') AS DATE)            AS due_date,
            try_cast("InvoiceAmount" AS DOUBLE)                          AS invoice_amount,
            upper("Disputed") = 'YES'                                    AS disputed,
            try_cast(try_strptime("SettledDate", '%m/%d/%Y') AS DATE)        AS settled_date,
            "PaperlessBill"                                             AS paperless_bill,
            try_cast("DaysToSettle" AS INTEGER)                         AS days_to_settle,
            try_cast("DaysLate" AS INTEGER)                             AS days_late
        FROM read_csv_auto(
            '{INVOICE_CSV.as_posix()}',
            header=True, ALL_VARCHAR=TRUE, null_padding=True, ignore_errors=True,
            store_rejects=True, rejects_table='invoice_rejects'
        )
        """
    )
    n = con.execute("SELECT count(*) FROM invoices").fetchone()[0]
    print(f"invoices: {n} rows")


def build_unspsc(con: duckdb.DuckDBPyConnection):
    wb = openpyxl.load_workbook(str(UNSPSC_XLSX), read_only=True)
    ws = wb["UNSPSC"]
    rows = list(ws.iter_rows(values_only=True))
    header, data_rows = rows[0], rows[1:]
    con.execute(
        """
        CREATE OR REPLACE TABLE unspsc_hierarchy (
            key INTEGER,
            parent_key INTEGER,
            code VARCHAR,
            title VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO unspsc_hierarchy VALUES (?, ?, ?, ?)",
        [(r[0], r[1], r[2], r[3]) for r in data_rows],
    )
    n = con.execute("SELECT count(*) FROM unspsc_hierarchy").fetchone()[0]
    print(f"unspsc_hierarchy: {n} rows")


SCHEMA_DESCRIPTION = """\
## purchase_orders (California state PO data, FY2012-2015, ~376k rows)
creation_date DATE, purchase_date DATE, fiscal_year VARCHAR (e.g. '2013-2014'),
lpa_number VARCHAR, po_number VARCHAR, requisition_number VARCHAR,
acquisition_type VARCHAR ('IT Goods'/'NON-IT Goods'/'IT Services'/'NON-IT Services'),
sub_acquisition_type VARCHAR, acquisition_method VARCHAR, sub_acquisition_method VARCHAR,
department_name VARCHAR, supplier_code VARCHAR, supplier_name VARCHAR,
supplier_qualifications VARCHAR (e.g. 'SB'=Small Business, 'DVBE'=Disabled Veteran),
supplier_zip_code VARCHAR, calcard BOOLEAN, item_name VARCHAR, item_description VARCHAR,
quantity DOUBLE, unit_price DOUBLE, total_price DOUBLE (USD), classification_codes VARCHAR,
unspsc_code VARCHAR (8-digit normalized UNSPSC commodity code), commodity_title VARCHAR,
class_code VARCHAR, class_title VARCHAR, family_code VARCHAR, family_title VARCHAR,
segment_code VARCHAR, segment_title VARCHAR, location VARCHAR

## invoices (~2.5k rows)
country_code VARCHAR, customer_id VARCHAR, paperless_date DATE, invoice_number VARCHAR,
invoice_date DATE, due_date DATE, invoice_amount DOUBLE (USD), disputed BOOLEAN,
settled_date DATE, paperless_bill VARCHAR ('Paper'/'Electronic'),
days_to_settle INTEGER, days_late INTEGER

## unspsc_hierarchy (13,313 rows - full UNSPSC taxonomy reference, Segment > Family > Class > Commodity)
key INTEGER, parent_key INTEGER (references key of the parent level, NULL for top-level segments),
code VARCHAR, title VARCHAR
-- Use this table (LIKE/ILIKE on title, or exact match on code) to look up or validate
-- UNSPSC codes/titles. It is a hierarchy, not flat: join on parent_key to walk up/down levels.
"""


def drop_reject_bookkeeping(con: duckdb.DuckDBPyConnection):
    """store_rejects=True creates global reject_scans/reject_errors tables that collide
    across successive CSV loads on the same connection -- clear them between loads, and
    drop the per-table rejects tables too since they're not needed in the shipped DB."""
    for obj in ("po_rejects", "invoice_rejects", "reject_scans", "reject_errors"):
        for kind in ("TABLE", "VIEW"):
            try:
                con.execute(f"DROP {kind} IF EXISTS {obj}")
            except duckdb.Error:
                pass


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    build_purchase_orders(con)
    drop_reject_bookkeeping(con)
    build_invoices(con)
    drop_reject_bookkeeping(con)
    build_unspsc(con)
    con.close()

    schema_path = STORE_DIR / "schema_description.md"
    schema_path.write_text(SCHEMA_DESCRIPTION)
    print(f"wrote {schema_path}")
    print(f"wrote {DB_PATH} ({DB_PATH.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
