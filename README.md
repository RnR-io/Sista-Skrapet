# Matklok — Team Explainer

## What is this project?
Matklok takes raw Swedish grocery receipt data and produces per-category
estimates of food spend, weight, CO2 emissions, and the cost of food waste
in SEK per kg.

---

## Project Structure

```text
Matklok/
├── data/
│   └── food-items-all.csv               # Raw input receipts (~45,600 rows)
├── output/
│   ├── category_waste_cost.csv          # Food waste cost estimates & SEK/kg
│   ├── category_waste_summary.csv       # Category spend, count, CO2e, shelf-life
│   ├── category_weight_waste_summary.csv# Category totals with physical weights
│   ├── food-items-with-weights.csv      # Itemized rows enriched with weights & CO2e/kg
│   └── gtin_shelf_life_lookup.csv       # Barcode/GTIN product lookup table
├── run.py                               # Complete pipeline runner (Steps 1–3)
├── process_food_items.py                # Step 1: Shelf-life & category summary
├── estimate_item_weights.py             # Step 2: Weight estimation & CO2e/kg
├── estimate_waste_cost.py               # Step 3: Food waste cost estimation
├── requirements.txt                     # Python dependencies (pandas, numpy)
├── .gitignore                           # Git ignore configuration
├── CHANGES.md                           # Project change log
└── README.md                            # Documentation & guide
```

---

## Installation & Requirements

Install required dependencies using pip:

```bash
pip install -r requirements.txt
```

Required packages:
- `pandas>=2.0.0`
- `numpy>=1.24.0`

---

## Pipeline Overview

```text
    data/food-items-all.csv  (raw receipts, ~45,600 rows)
            |
            |---> process_food_items.py  [Step 1]
            |         |-- output/category_waste_summary.csv
            |         +-- output/gtin_shelf_life_lookup.csv
            |
            |---> estimate_item_weights.py  [Step 2]
            |         |-- output/food-items-with-weights.csv
            |         +-- output/category_weight_waste_summary.csv
            |
            +---> estimate_waste_cost.py  [Step 3]
                      +-- output/category_waste_cost.csv
```

### Running the Pipeline

Run the full end-to-end pipeline (Steps 1 through 3):

```bash
# Default: Literature-based waste rates (Method A)
python3 run.py

# Data-driven: Shelf-life derived waste rates (Method B)
python3 run.py --method shelf_life
```

Or run individual steps standalone:

```bash
python3 process_food_items.py
python3 estimate_item_weights.py
python3 estimate_waste_cost.py --method literature
python3 estimate_waste_cost.py --method shelf_life
```

---

## Raw Data: data/food-items-all.csv
~45,600 receipt line items. Key columns:
  - `transaction_date`   Date of purchase
  - `raw_name`           Product name from receipt
  - `quantity` / `unit`  How many and in what unit (st, kg, etc.)
  - `line_price_sek`     Price paid (SEK)
  - `livsmedel_id`       Food category (CAT_0 to CAT_23, CAT_-1)
  - `co2e_kg`            Carbon footprint (kg CO2e)
  - `is_food`            Boolean - is this a food item?
  - `data_lost`          Boolean - was receipt data corrupted?

---

## Step 1 - process_food_items.py
Cleans and aggregates raw data by category and by product barcode (GTIN).
Assigns shelf-life baseline per category (e.g. fish=4 days, rice=365 days).
Outputs: `output/category_waste_summary.csv`, `output/gtin_shelf_life_lookup.csv`

---

## Step 2 - estimate_item_weights.py
Estimates physical weight (kg) per purchased item. Priority:
  1. Unit is kg -> use quantity directly
  2. Parse weight from product name via regex  e.g. "Yoghurt 500g" -> 0.5 kg
  3. Fall back to category default  e.g. dairy = 1.0 kg
Outputs: `output/food-items-with-weights.csv`, `output/category_weight_waste_summary.csv`

---

## Step 3 - estimate_waste_cost.py
Calculates wasted food volume and its cost in SEK per kg.

Core formula:
  - `waste_kg         = total_weight_kg x waste_rate`
  - `waste_spend_sek  = total_spend_sek x waste_rate`
  - `sek_per_kg_waste = waste_spend_sek / waste_kg`   <-- KEY METRIC

Output columns added in `output/category_waste_cost.csv`:
  - `waste_rate`          fraction of purchased weight wasted
  - `waste_kg`            estimated kg of food wasted
  - `waste_spend_sek`     SEK value of wasted food
  - `sek_per_kg_waste`    SEK per kg of waste generated [KEY METRIC]
  - `waste_co2e_kg`       CO2e attributed to wasted food
  - `co2e_per_kg_waste`   kg CO2e per kg of waste

---

## How Waste Rates Are Calculated

Two methods are supported, selectable via the `--method` flag:

### METHOD A: literature (default)
  Waste rates are hardcoded constants sourced from:
    - Livsmedelsverket PM 2024 - Vad kostar matsvinnet i hemmet
    - Naturvardsverket 2026    - ~44 SEK/kg national average (sanity check)
    - WRAP / FAO household food waste rates
  Run: `python3 estimate_waste_cost.py --method literature`

  Example rates:
    Fresh berries & soft fruit    35%
    Fresh fruit & vegetables      30%
    Vegetables / Potatoes         28%
    Dairy / Milk / Yogurt         25%
    Fresh fish / Seafood          22%
    Bread                         20%
    Cheese                        20%
    Fresh meat / Mince            18%
    Frozen foods                   5%
    Dry pasta / Noodles            3%
    Rice                           3%
    Non-food / Trash bags          0%

### METHOD B: shelf_life (data-driven)
  Waste rate is derived from each category's shelf-life baseline.
  No external sources required.
  Run: `python3 estimate_waste_cost.py --method shelf_life`

  Mapping:
    <= 5 days    ->  30%   (e.g. fresh fish, meat)
    <= 10 days   ->  25%   (e.g. dairy)
    <= 14 days   ->  20%   (e.g. bread, fresh veg)
    <= 30 days   ->  12%   (e.g. jams)
    <= 90 days   ->   8%   (e.g. snacks)
    <= 180 days  ->   5%   (e.g. frozen, beverages)
    > 180 days   ->   3%   (e.g. rice, pasta, coffee)

### FUTURE - Method D: Repurchase gap analysis
  Long gap between repeat purchases of the same product (by gtin_barcode +
  transaction_date) implies the item was used up or wasted before rebuying.
  This would produce data-driven, product-level waste rates without external
  assumptions. The raw data already contains the required columns.

---

## Results Summary (Method A - literature)

  Total estimated waste:    4,519 kg
  Total waste value:      202,762 SEK
  Total waste CO2e:         7,929 kg CO2e
  Overall SEK/kg waste:      44.9 SEK/kg  [target ~44 -- PASS]

Top 5 by waste spend:
  - Fresh fish / Seafood        269 kg    33,892 SEK    125.9 SEK/kg
  - Fresh fruit & vegetables    967 kg    33,734 SEK     34.9 SEK/kg
  - Vegetables / Potatoes       752 kg    24,742 SEK     32.9 SEK/kg
  - Fresh meat / Mince          179 kg    18,858 SEK    105.3 SEK/kg
  - Dairy / Milk / Yogurt     1,114 kg    17,903 SEK     16.1 SEK/kg

Note: Fish and meat have high SEK/kg waste because they are expensive per kg,
not because they have the largest waste volume.

---

## Category Reference

  CAT_-1   Non-food / Trash bags           shelf life: --
  CAT_0    Canned legumes                  shelf life: 180 days
  CAT_1    Bread                           shelf life:  14 days
  CAT_2    Chark / Sausage                 shelf life:  10 days
  CAT_3    Snacks / Chips                  shelf life:  90 days
  CAT_4    Frozen foods                    shelf life: 180 days
  CAT_5    Sweets / Chocolate              shelf life: 120 days
  CAT_6    Fresh berries & soft fruit      shelf life:   7 days
  CAT_7    Fresh fruit & vegetables        shelf life:   7 days
  CAT_8    Juices / Jams                   shelf life:  30 days
  CAT_9    Beverages                       shelf life: 180 days
  CAT_10   Butter / Tofu / Cream           shelf life:  14 days
  CAT_11   Cereal / Flour / Oats           shelf life: 180 days
  CAT_12   Dairy / Milk / Yogurt           shelf life:  10 days
  CAT_13   Nuts                            shelf life: 180 days
  CAT_14   Cheese                          shelf life:  21 days
  CAT_15   Rice                            shelf life: 365 days
  CAT_16   Dry pasta / Noodles             shelf life: 365 days
  CAT_17   Vegetables / Potatoes           shelf life:  14 days
  CAT_18   Fresh meat / Mince              shelf life:   5 days
  CAT_19   Prepared meals / Pizza          shelf life:  14 days
  CAT_20   Fresh fish / Seafood            shelf life:   4 days
  CAT_21   Eggs                            shelf life:  21 days
  CAT_22   Sauces / Condiments             shelf life:  60 days
  CAT_23   Tea / Coffee                    shelf life: 365 days

---

## Open Questions / Next Steps

  [x] Hook estimate_waste_cost.py into run.py as step 3
  [ ] Refine Method A rates with SCB / Livsmedelsverket category-specific data
  [ ] Validate Method A against peer review category definitions
  [ ] Implement Method D: repurchase gap analysis for data-driven validation
  [ ] Per-household breakdowns (synthetic_household column exists in raw data)
