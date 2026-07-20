# California Purchase Order Data Dictionary
Source: California Open Data Portal — Purchase Order Data (FY 2012–2015)
URL: https://data.ca.gov/dataset/purchase-order-data

## Dataset Overview
- **Rows:** ~376,876 (partial download covering ~43% of full dataset)
- **Fiscal Years:** 2012-2013, 2013-2014, 2014-2015
- **Source System:** California eProcurement (eSCPRS)
- **Threshold:** Purchases exceeding $5,000

## Column Definitions

| # | Column Name | Type | Description |
|---|---|---|---|
| 1 | Creation Date | Date | Date the purchase order was created in the system |
| 2 | Purchase Date | Date | Date the purchase was made |
| 3 | Fiscal Year | String | State fiscal year (e.g. 2013-2014) |
| 4 | LPA Number | String | Leveraged Procurement Agreement number (contract vehicle reference) |
| 5 | Purchase Order Number | String | Unique PO identifier |
| 6 | Requisition Number | String | Internal requisition number linked to PO |
| 7 | Acquisition Type | String | High-level category: IT Goods, NON-IT Goods, IT Services, NON-IT Services |
| 8 | Sub-Acquisition Type | String | Sub-category within acquisition type |
| 9 | Acquisition Method | String | Procurement method used (e.g. WSCA/Coop, Informal Competitive, Formal Competitive) |
| 10 | Sub-Acquisition Method | String | Further detail on acquisition method |
| 11 | Department Name | String | California state department that issued the PO |
| 12 | Supplier Code | String | Unique vendor identifier |
| 13 | Supplier Name | String | Name of the vendor/supplier |
| 14 | Supplier Qualifications | String | Special certifications (e.g. SB = Small Business, DVBE = Disabled Veteran) |
| 15 | Supplier Zip Code | String | Vendor's ZIP code |
| 16 | CalCard | String | Whether purchase was made via CalCard (YES/NO) |
| 17 | Item Name | String | Short name of the item purchased |
| 18 | Item Description | String | Detailed description of the item purchased |
| 19 | Quantity | Number | Number of units purchased |
| 20 | Unit Price | Currency | Price per unit (USD) |
| 21 | Total Price | Currency | Total line item cost (Quantity × Unit Price, USD) |
| 22 | Classification Codes | String | Raw classification code assigned to item |
| 23 | Normalized UNSPSC | String | Standardised UNSPSC 8-digit code for the item |
| 24 | Commodity Title | String | UNSPSC commodity-level description |
| 25 | Class | String | UNSPSC class code (6-digit) |
| 26 | Class Title | String | UNSPSC class description |
| 27 | Family | String | UNSPSC family code (4-digit) |
| 28 | Family Title | String | UNSPSC family description |
| 29 | Segment | String | UNSPSC segment code (2-digit) |
| 30 | Segment Title | String | UNSPSC segment description (top level) |
| 31 | Location | String | Geographic location of the purchasing department |

## UNSPSC Hierarchy (embedded in this dataset)
Segment → Family → Class → Commodity (Normalized UNSPSC)

## Key Use Cases for Chatbot Test
- Spend analysis by department, supplier, or acquisition type
- UNSPSC classification lookup and cross-referencing
- Supplier diversity queries (Supplier Qualifications field)
- Procurement method analysis
- Time-series spend trends across fiscal years
