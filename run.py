"""
run.py
------
End-to-end execution pipeline for Matklok:
  Step 1: Process shelf-life lookup & category waste summary
  Step 2: Estimate item weights & CO2e intensity per kg
  Step 3: Estimate food waste cost & SEK per kg of waste generated
"""

import argparse
from process_food_items import process_food_items_dataset
from estimate_item_weights import estimate_food_item_weights
from estimate_waste_cost import estimate_waste_cost


def run_pipeline(method='literature'):
    print("\n" + "=" * 60)
    print("STEP 1: Process Shelf-Life Lookup & Category Waste Summary")
    print("=" * 60)
    category_summary, product_lookup = process_food_items_dataset()

    print("\n" + "=" * 60)
    print("STEP 2: Estimate Item Weights & CO2e Intensity per kg")
    print("=" * 60)
    df_weighted, summary = estimate_food_item_weights()

    print("\n" + "=" * 60)
    print(f"STEP 3: Estimate Food Waste Cost (Method: {method})")
    print("=" * 60)
    df_cost = estimate_waste_cost(method=method)

    print("\n" + "=" * 60)
    print("  MATKLOK PIPELINE EXECUTION COMPLETE")
    print("=" * 60)
    return category_summary, product_lookup, df_weighted, summary, df_cost


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Run the full Matklok food waste calculation pipeline."
    )
    parser.add_argument(
        '--method',
        default='literature',
        choices=['literature', 'shelf_life'],
        help='Waste rate method for step 3: "literature" (default) or "shelf_life" (data-driven).'
    )
    args = parser.parse_args()
    run_pipeline(method=args.method)
