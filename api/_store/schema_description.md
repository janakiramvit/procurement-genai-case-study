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
