"""
estimate_waste_cost.py
----------------------
Estimates the cost of food waste in Swedish Krona per kg of waste generated,
per food category.

Methodology
-----------
  waste_kg          = total_weight_kg  x waste_rate
  sek_per_kg_waste  = total_spend_sek  x waste_rate / waste_kg
  waste_spend_sek   = total_spend_sek  x waste_rate
  waste_co2e_kg     = total_co2e_kg    x waste_rate

Two methods for determining waste_rate are supported (select via --method):

  METHOD A: literature (default)
    Waste rates are hardcoded constants sourced from:
      - Livsmedelsverket PM 2024 "Vad kostar matsvinnet i hemmet"
      - Naturvardsverket 2026 (sanity check: ~44 SEK/kg national average)
      - WRAP / FAO household food waste rates by category

  METHOD B: shelf_life (data-driven)
    Waste rate is derived from each category's shelf-life baseline using
    a stepped mapping. No external sources required.
      <= 5 days   -> 30%
      <= 10 days  -> 25%
      <= 14 days  -> 20%
      <= 30 days  -> 12%
      <= 90 days  ->  8%
      <= 180 days ->  5%
      > 180 days  ->  3%

  FUTURE — Method D: Repurchase gap analysis
    Long gap between repeat purchases of the same product (by gtin_barcode +
    transaction_date) implies the item was used up or wasted. This would
    produce data-driven, product-level waste rates without external assumptions.
    The raw data already contains the required columns.
"""

import os
import argparse
import pandas as pd
import numpy as np

def _resolve_input_path(path, default_subfolder='output'):
    """Resolves input file path, checking given path, default subfolder, or root."""
    if os.path.exists(path):
        return path
    candidate = os.path.join(default_subfolder, path)
    if os.path.exists(candidate):
        return candidate
    base_candidate = os.path.basename(path)
    if os.path.exists(base_candidate):
        return base_candidate
    return path

def _ensure_dir(filepath):
    """Ensures parent directory for a given file exists."""
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

# ---------------------------------------------------------------------------
# Method A: Literature-sourced waste rates (fraction of purchased weight wasted)
# Sources: Livsmedelsverket 2024, Naturvardsverket 2026, WRAP 2020, FAO
# ---------------------------------------------------------------------------
CATEGORY_WASTE_RATES = {
    'CAT_-1': 0.00,  # Non-food / trash bags - not food waste
    'CAT_0':  0.08,  # Canned legumes - very low waste, long shelf life
    'CAT_1':  0.20,  # Bread - significant household waste (~20%)
    'CAT_2':  0.15,  # Chark/sausage - moderate, refrigerated
    'CAT_3':  0.05,  # Snacks/chips - low, eaten before expiry
    'CAT_4':  0.05,  # Frozen - low, frozen preserves for months
    'CAT_5':  0.08,  # Sweets/chocolate - low waste
    'CAT_6':  0.35,  # Fresh berries/soft fruit - very high waste rate
    'CAT_7':  0.30,  # Fresh fruit & vegetables - high (Livsmedelsverket ~30%)
    'CAT_8':  0.10,  # Juices/jams - moderate
    'CAT_9':  0.05,  # Beverages - low
    'CAT_10': 0.12,  # Butter/tofu/cream - moderate
    'CAT_11': 0.05,  # Cereal/flour/oats - very low
    'CAT_12': 0.25,  # Dairy/milk/yogurt - high (Livsmedelsverket ~25%)
    'CAT_13': 0.05,  # Nuts - very low, long shelf life
    'CAT_14': 0.20,  # Cheese - moderate-high (mould, forgotten)
    'CAT_15': 0.03,  # Rice - very low
    'CAT_16': 0.03,  # Dry pasta - very low
    'CAT_17': 0.28,  # Vegetables/potatoes - high (WRAP ~28%)
    'CAT_18': 0.18,  # Fresh meat/mince - moderate-high (use-by dates)
    'CAT_19': 0.15,  # Prepared meals/pizza - moderate
    'CAT_20': 0.22,  # Fresh fish/seafood - high (short shelf life)
    'CAT_21': 0.08,  # Eggs - low
    'CAT_22': 0.10,  # Sauces/condiments - moderate (forgotten in fridge)
    'CAT_23': 0.05,  # Tea/coffee - very low
}

# Human-readable category names for reporting
CATEGORY_NAMES = {
    'CAT_-1': 'Non-food / Trash bags',
    'CAT_0':  'Canned legumes',
    'CAT_1':  'Bread',
    'CAT_2':  'Chark / Sausage',
    'CAT_3':  'Snacks / Chips',
    'CAT_4':  'Frozen foods',
    'CAT_5':  'Sweets / Chocolate',
    'CAT_6':  'Fresh berries & soft fruit',
    'CAT_7':  'Fresh fruit & vegetables',
    'CAT_8':  'Juices / Jams',
    'CAT_9':  'Beverages',
    'CAT_10': 'Butter / Tofu / Cream',
    'CAT_11': 'Cereal / Flour / Oats',
    'CAT_12': 'Dairy / Milk / Yogurt',
    'CAT_13': 'Nuts',
    'CAT_14': 'Cheese',
    'CAT_15': 'Rice',
    'CAT_16': 'Dry pasta / Noodles',
    'CAT_17': 'Vegetables / Potatoes',
    'CAT_18': 'Fresh meat / Mince',
    'CAT_19': 'Prepared meals / Pizza',
    'CAT_20': 'Fresh fish / Seafood',
    'CAT_21': 'Eggs',
    'CAT_22': 'Sauces / Condiments',
    'CAT_23': 'Tea / Coffee',
}


# ---------------------------------------------------------------------------
# Method B: Derive waste rate from shelf-life baseline (data-driven)
# ---------------------------------------------------------------------------
def waste_rate_from_shelf_life(days):
    """
    Returns an estimated waste rate based on product shelf life in days.
    Shorter shelf life -> higher assumed waste rate.
    No external sources required.
    """
    if days <= 5:   return 0.30   # e.g. fresh fish, meat
    if days <= 10:  return 0.25   # e.g. dairy
    if days <= 14:  return 0.20   # e.g. bread, fresh veg
    if days <= 30:  return 0.12   # e.g. jams, juices
    if days <= 90:  return 0.08   # e.g. snacks
    if days <= 180: return 0.05   # e.g. frozen, beverages
    return 0.03                   # e.g. rice, pasta, coffee


def estimate_waste_cost(
    input_csv='output/category_weight_waste_summary.csv',
    output_csv='output/category_waste_cost.csv',
    waste_rates: dict = None,
    method='literature',
    shelf_life_csv='output/category_waste_summary.csv',
):
    """
    Reads the category weight & waste summary and computes:
      - waste_rate            : fraction of purchased weight wasted
      - waste_kg              : estimated kg wasted per category
      - waste_spend_sek       : SEK value of wasted food
      - sek_per_kg_waste      : SEK per kg of waste generated  <- key metric
      - waste_co2e_kg         : CO2e attributed to wasted food
      - co2e_per_kg_waste     : kg CO2e per kg of waste

    Parameters
    ----------
    input_csv       : path to category_weight_waste_summary.csv
    output_csv      : path to write the enriched output
    waste_rates     : optional dict override {category_id: rate}
    method          : 'literature' (default) or 'shelf_life'
                        literature  -> Approach A: hardcoded rates from
                                       Livsmedelsverket/WRAP/FAO
                        shelf_life  -> Approach B: rates derived from
                                       shelf-life baseline (data-driven)
    shelf_life_csv  : path to category_waste_summary.csv (used by shelf_life method)

    Returns
    -------
    pd.DataFrame with all original columns plus waste columns
    """
    actual_input = _resolve_input_path(input_csv, 'output')
    df = pd.read_csv(actual_input)
    df.columns = df.columns.str.strip()

    # --- Determine waste rates based on chosen method ---
    if waste_rates is not None:
        # Explicit override always wins
        rates = waste_rates
        print("Using custom waste rates (explicit override)")

    elif method == 'shelf_life':
        # Method B: derive from shelf-life data
        actual_sl = _resolve_input_path(shelf_life_csv, 'output')
        sl = pd.read_csv(actual_sl)
        sl.columns = sl.columns.str.strip()
        sl_map = dict(zip(sl['category_id'], sl['expected_days_remaining_baseline']))
        rates = {cat: waste_rate_from_shelf_life(days) for cat, days in sl_map.items()}
        print("Using shelf-life derived waste rates (Method B - data-driven)")

    else:
        # Method A: literature-sourced constants (default)
        rates = CATEGORY_WASTE_RATES
        print("Using literature-sourced waste rates (Method A - Livsmedelsverket/WRAP/FAO)")

    # Map waste rate and category name
    df['waste_rate'] = df['category_id'].map(rates).fillna(0.15)  # default 15%
    df['category_name'] = df['category_id'].map(CATEGORY_NAMES).fillna(df['category_id'])

    # Core waste calculations
    df['waste_kg']         = df['total_weight_kg'] * df['waste_rate']
    df['waste_spend_sek']  = df['total_spend_sek']  * df['waste_rate']
    df['waste_co2e_kg']    = df['total_co2e_kg']    * df['waste_rate']

    # SEK per kg of waste (the key metric)
    df['sek_per_kg_waste'] = np.where(
        df['waste_kg'] > 0,
        df['waste_spend_sek'] / df['waste_kg'],
        np.nan
    )

    # CO2e per kg of waste
    df['co2e_per_kg_waste'] = np.where(
        df['waste_kg'] > 0,
        df['waste_co2e_kg'] / df['waste_kg'],
        np.nan
    )

    # Sort by waste_spend_sek descending
    df = df.sort_values('waste_spend_sek', ascending=False)
    _ensure_dir(output_csv)
    df.to_csv(output_csv, index=False)
    print(f"Waste cost estimate saved to: {output_csv}")

    # --- Summary printout ---
    total_waste_kg    = df['waste_kg'].sum()
    total_waste_spend = df['waste_spend_sek'].sum()
    total_waste_co2e  = df['waste_co2e_kg'].sum()
    overall_sek_per_kg = total_waste_spend / total_waste_kg if total_waste_kg > 0 else 0

    print(f"\n{'='*55}")
    print(f"  FOOD WASTE COST SUMMARY  [method: {method}]")
    print(f"{'='*55}")
    print(f"  Total estimated waste:       {total_waste_kg:>10.1f} kg")
    print(f"  Total waste value:           {total_waste_spend:>10.0f} SEK")
    print(f"  Total waste CO2e:            {total_waste_co2e:>10.1f} kg CO2e")
    print(f"  OVERALL SEK per kg waste:    {overall_sek_per_kg:>10.1f} SEK/kg")
    print(f"  (Sanity check target: ~44 SEK/kg -- Naturvardsverket 2026)")
    print(f"{'='*55}")
    print(f"\n  Top 5 categories by waste spend:")
    top5 = df[df['waste_kg'] > 0].head(5)[
        ['category_name', 'waste_kg', 'waste_spend_sek', 'sek_per_kg_waste']
    ]
    print(top5.to_string(index=False))
    print(f"\n  NOTE: Waste rates are {method}-sourced.")
    print(f"  Future work: validate via repurchase gap analysis (Method D)")
    print(f"  using transaction_date + gtin_barcode columns in the raw data.")

    return df


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Estimate food waste cost (SEK/kg) per category.'
    )
    parser.add_argument(
        '--method',
        default='literature',
        choices=['literature', 'shelf_life'],
        help=(
            'Waste rate method: '
            '"literature" (default) uses Livsmedelsverket/WRAP/FAO constants; '
            '"shelf_life" derives rates from shelf-life baseline (data-driven).'
        )
    )
    args = parser.parse_args()
    estimate_waste_cost(method=args.method)
