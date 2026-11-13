# Matklok - Project Change Log

---

## 2026-11-13

### REORGANIZATION: Repository cleanup and GitHub preparation

- **Folder Structure**:
  - Organized raw receipt input data into `data/food-items-all.csv`.
  - Moved all generated pipeline outputs and lookups to `output/` (`category_waste_cost.csv`, `category_waste_summary.csv`, `category_weight_waste_summary.csv`, `food-items-with-weights.csv`, `gtin_shelf_life_lookup.csv`).
- **Pipeline Runner (`run.py`)**:
  - Hooked `estimate_waste_cost.py` into `run.py` as Step 3 to provide full end-to-end execution.
  - Added CLI flag `--method` (`literature` or `shelf_life`) to choose waste estimation method for step 3.
- **Path Resolution**:
  - Added automatic path resolution across `process_food_items.py`, `estimate_item_weights.py`, and `estimate_waste_cost.py` to seamlessly handle `data/` and `output/` directories with fallback to root.
  - Ensured output directories are automatically created if they do not exist.
- **Git & Packaging**:
  - Added comprehensive `.gitignore` for Python, macOS, editor files, and archives.
  - Added `requirements.txt` (`pandas>=2.0.0`, `numpy>=1.24.0`).
  - Removed cache and system artifacts (`.DS_Store`, `__pycache__`).
  - Initialized Git repository on `main` branch.

---

## 2026-11-01

### UPDATED: estimate_waste_cost.py

Added two selectable waste rate methods via --method CLI flag:

  METHOD A: literature (default) -- unchanged behaviour
    Hardcoded constants from Livsmedelsverket PM 2024, Naturvardsverket 2026,
    WRAP/FAO. Primary result for reporting.
    Run: python3 estimate_waste_cost.py --method literature

  METHOD B: shelf_life (NEW, data-driven)
    Waste rate derived from each category's shelf-life baseline using a
    stepped mapping. No external sources required.
      <= 5 days   -> 30%   (e.g. fish, fresh meat)
      <= 10 days  -> 25%   (e.g. dairy)
      <= 14 days  -> 20%   (e.g. bread, fresh veg)
      <= 30 days  -> 12%   (e.g. jams)
      <= 90 days  ->  8%   (e.g. snacks)
      <= 180 days ->  5%   (e.g. frozen, beverages)
      > 180 days  ->  3%   (e.g. rice, pasta, coffee)
    Run: python3 estimate_waste_cost.py --method shelf_life

  Method B results (first run):
    Total estimated waste : 4,408 kg
    Total waste value     : 218,239 SEK
    Total waste CO2e      : 9,752 kg CO2e
    Overall SEK/kg waste  : 49.5 SEK/kg

Added console note flagging Method D (repurchase gap analysis) as a
future validation path using transaction_date + gtin_barcode columns.

Added argparse CLI so method can be selected at runtime without editing code.

Added waste_rate_from_shelf_life() as a standalone utility function.

---

## 2026-10-28

### ADDED: estimate_waste_cost.py

Purpose:
  Estimates the cost of food waste in Swedish Krona per kg of waste
  generated, broken down by food category.

Methodology:
  waste_kg         = total_weight_kg x waste_rate
  waste_spend_sek  = total_spend_sek x waste_rate
  sek_per_kg_waste = waste_spend_sek / waste_kg   <-- KEY METRIC
  waste_co2e_kg    = total_co2e_kg   x waste_rate

Sources:
  Livsmedelsverket PM 2024 - Vad kostar matsvinnet i hemmet
  Naturvardsverket 2026    - ~700 SEK/person/year / ~16 kg/person/year = ~44 SEK/kg
  WRAP / FAO household food waste rates by category

Key result (first run):
  Total estimated waste : 4,519 kg
  Total waste value     : 202,762 SEK
  Total waste CO2e      : 7,929 kg CO2e
  Overall SEK/kg waste  : 44.9 SEK/kg  [target ~44 -- PASS]


### ADDED: category_waste_cost.csv

Output file produced by estimate_waste_cost.py.
Contains all columns from category_weight_waste_summary.csv plus:
  waste_rate          fraction of purchased weight wasted
  waste_kg            estimated kg of food wasted
  waste_spend_sek     SEK value of wasted food
  sek_per_kg_waste    SEK per kg of waste generated [KEY METRIC]
  waste_co2e_kg       CO2e attributed to wasted food
  co2e_per_kg_waste   kg CO2e per kg of waste

---

## Pre-existing files (unchanged)

  run.py
    Entry point. Runs process_food_items_dataset() and
    estimate_food_item_weights() in sequence.

  process_food_items.py
    Parses raw receipts, assigns shelf-life per category.
    Outputs: category_waste_summary.csv, gtin_shelf_life_lookup.csv

  estimate_item_weights.py
    Estimates product weights via regex + category fallbacks.
    Computes CO2e/kg intensity per item.
    Outputs: food-items-with-weights.csv, category_weight_waste_summary.csv

  food-items-all.csv
    Raw input (~45,600 grocery receipt line items).

  food-items-with-weights.csv
    Enriched output with estimated_total_weight_kg and co2e_per_kg per item.

  gtin_shelf_life_lookup.csv
    Per-product GTIN reference: shelf-life, spend, CO2e.

  category_waste_summary.csv
    Per-category totals: items, spend, CO2e, shelf-life baseline.

  category_weight_waste_summary.csv
    Per-category totals with weight, CO2e/kg, price/kg.
