import os
import pandas as pd
import numpy as np

def _resolve_input_path(path, default_subfolder='data'):
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

def process_food_items_dataset(
    input_csv_path='data/food-items-all.csv',
    output_lookup_csv='output/gtin_shelf_life_lookup.csv',
    output_summary_csv='output/category_waste_summary.csv',
    include_trash_bags=True
):
    """
    Processes the Food Items CSV dataset according to the exact schema:
    item_id, receipt_id, transaction_date, store_name, receipt_source,
    synthetic_household, raw_name, quantity, unit, line_price_sek, discount_sek,
    is_food, source_barcode_or_article_id, livsmedel_id, product_catalog_id,
    mapping_confidence, classification_method, data_lost, co2e_kg, rise_version
    """
    actual_input = _resolve_input_path(input_csv_path, 'data')
    print(f"Loading dataset from: {actual_input}")
    try:
        df = pd.read_csv(actual_input, sep=None, engine='python', encoding='utf-8-sig')
    except Exception:
        df = pd.read_csv(actual_input)
    
    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    print(f"Loaded columns: {list(df.columns)}")

    # 1. Direct Column Mapping based on exact CSV headers
    # Date
    df['date'] = pd.to_datetime(df['transaction_date'], errors='coerce', format='mixed')
    
    # Financial & Carbon metrics
    df['line_price_sek'] = pd.to_numeric(df['line_price_sek'], errors='coerce').fillna(0)
    df['co2e_kg'] = pd.to_numeric(df['co2e_kg'], errors='coerce').fillna(0)
    
    # Category mapping (livsmedel_id)
    if 'livsmedel_id' in df.columns:
        df['category_id'] = df['livsmedel_id'].astype(str).str.strip()
    elif 'category_id' in df.columns:
        df['category_id'] = df['category_id'].astype(str).str.strip()
    else:
        df['category_id'] = 'CAT_UNKNOWN'

    # Product GTIN / Barcode identifier
    barcode_col = 'source_barcode_or_article_id' if 'source_barcode_or_article_id' in df.columns else 'gtin'
    df['gtin_barcode'] = df[barcode_col].astype(str).str.strip() if barcode_col in df.columns else 'NO_GTIN'

    # Product Name
    name_col = 'raw_name' if 'raw_name' in df.columns else 'clean_name'
    df['clean_name'] = df[name_col].astype(str).str.strip() if name_col in df.columns else 'Unknown Product'

    # Food vs Non-food filtering
    if not include_trash_bags and 'is_food' in df.columns:
        valid_items = df[df['is_food'] == True].copy()
    else:
        valid_items = df.copy()

    # 2. Category shelf-life baselines supporting integer/string IDs (0-23, -1)
    category_baselines = {
        'CAT_-1': 365, '-1': 365,  # Trash bags / non-food
        'CAT_0': 180,  '0': 180,   # Legumes/canned
        'CAT_1': 14,   '1': 14,    # Bread
        'CAT_2': 10,   '2': 10,    # Chark/sausage
        'CAT_3': 90,   '3': 90,    # Snacks
        'CAT_4': 180,  '4': 180,   # Frozen
        'CAT_5': 120,  '5': 120,   # Sweets
        'CAT_6': 7,    '6': 7,     # Fresh berries/tomatoes
        'CAT_7': 7,    '7': 7,     # Fresh fruits & vegetables
        'CAT_8': 30,   '8': 30,    # Juices/jams
        'CAT_9': 180,  '9': 180,   # Beverages
        'CAT_10': 14,  '10': 14,   # Butter/tofu
        'CAT_11': 180, '11': 180,  # Cereal/flour
        'CAT_12': 10,  '12': 10,   # Dairy/milk
        'CAT_13': 180, '13': 180,  # Nuts
        'CAT_14': 21,  '14': 21,   # Cheese
        'CAT_15': 365, '15': 365,  # Rice
        'CAT_16': 365, '16': 365,  # Pasta
        'CAT_17': 14,  '17': 14,   # Vegetables/potatoes
        'CAT_18': 5,   '18': 5,    # Meat/mince
        'CAT_19': 14,  '19': 14,   # Prepared meals
        'CAT_20': 4,   '20': 4,    # Fish/seafood
        'CAT_21': 21,  '21': 21,   # Eggs
        'CAT_22': 60,  '22': 60,   # Sauces
        'CAT_23': 365, '23': 365,  # Tea/coffee
    }

    def get_shelf_life(cat_id):
        cat_str = str(cat_id).strip()
        if cat_str in category_baselines:
            return category_baselines[cat_str]
        clean_key = cat_str if cat_str.startswith('CAT_') else f"CAT_{cat_str.split('.')[0]}"
        return category_baselines.get(clean_key, 14)

    # 3. Aggregations
    category_summary = valid_items.groupby('category_id', as_index=False).agg(
        total_items=('clean_name', 'count'),
        total_spend_sek=('line_price_sek', 'sum'),
        avg_item_price_sek=('line_price_sek', 'mean'),
        total_co2e_kg=('co2e_kg', 'sum'),
        avg_co2e_per_item=('co2e_kg', 'mean')
    )
    category_summary['expected_days_remaining_baseline'] = category_summary['category_id'].apply(get_shelf_life)
    category_summary = category_summary.sort_values(by='expected_days_remaining_baseline', ascending=True)

    product_lookup = valid_items.groupby(['category_id', 'gtin_barcode', 'clean_name'], as_index=False).agg(
        purchase_observations=('line_price_sek', 'count'),
        total_spend_sek=('line_price_sek', 'sum'),
        avg_co2e_kg=('co2e_kg', 'mean')
    )
    product_lookup['expected_days_remaining'] = product_lookup['category_id'].apply(get_shelf_life)

    _ensure_dir(output_summary_csv)
    _ensure_dir(output_lookup_csv)
    category_summary.to_csv(output_summary_csv, index=False)
    product_lookup.to_csv(output_lookup_csv, index=False)

    print(f"Summary saved to: {output_summary_csv}")
    print(f"Lookup table saved to: {output_lookup_csv}")

    return category_summary, product_lookup

if __name__ == '__main__':
    process_food_items_dataset()
