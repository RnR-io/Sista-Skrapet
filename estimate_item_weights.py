import os
import re
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

def estimate_food_item_weights(
    input_csv_path='data/food-items-all.csv',
    output_csv_path='output/food-items-with-weights.csv',
    output_summary_csv='output/category_weight_waste_summary.csv'
):
    """
    Estimates item weights (in kg) and total product weight for food transactions
    to refine CO2e emission calculations and food waste reporting (g/kg).
    """
    actual_input = _resolve_input_path(input_csv_path, 'data')
    print(f"Loading dataset from: {actual_input}")
    try:
        df = pd.read_csv(actual_input, sep=None, engine='python', encoding='utf-8-sig')
    except Exception:
        df = pd.read_csv(actual_input)
        
    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    
    # Identify relevant columns dynamically based on exact dataset headers
    cat_col = next((c for c in ['livsmedel_id', 'category_id', 'Category_ID', 'category'] if c in df.columns), 'livsmedel_id')
    df['category_id'] = df[cat_col].astype(str).str.strip()
    
    name_col = next((c for c in ['raw_name', 'clean_name', 'product_name'] if c in df.columns), 'raw_name')
    unit_col = next((c for c in ['unit', 'Unit'] if c in df.columns), 'unit')
    qty_col = next((c for c in ['quantity', 'Quantity', 'qty'] if c in df.columns), 'quantity')
    price_col = next((c for c in ['line_price_sek', 'price', 'price_sek'] if c in df.columns), 'line_price_sek')
    co2_col = next((c for c in ['co2e_kg', 'co2e', 'co2'] if c in df.columns), 'co2e_kg')
    
    df['qty_num'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(1.0)
    df['price_num'] = pd.to_numeric(df[price_col], errors='coerce').fillna(0.0)
    df['co2_num'] = pd.to_numeric(df[co2_col], errors='coerce').fillna(0.0)
    
    # Regex Helper Function for package size extraction
    def extract_package_weight_kg(text):
        if not isinstance(text, str):
            return None
        text_lower = text.lower().replace(',', '.')
        
        # Match kilograms, liters, grams, dl, ml
        match_kg = re.search(r'(\d+(?:\.\d+)?)\s*kg\b', text_lower)
        if match_kg:
            return float(match_kg.group(1))
            
        match_l = re.search(r'(\d+(?:\.\d+)?)\s*l\b', text_lower)
        if match_l:
            return float(match_l.group(1))
            
        match_g = re.search(r'(\d+(?:\.\d+)?)\s*g\b', text_lower)
        if match_g:
            return float(match_g.group(1)) / 1000.0
            
        match_dl = re.search(r'(\d+(?:\.\d+)?)\s*dl\b', text_lower)
        if match_dl:
            return float(match_dl.group(1)) / 10.0
            
        match_ml = re.search(r'(\d+(?:\.\d+)?)\s*ml\b', text_lower)
        if match_ml:
            return float(match_ml.group(1)) / 1000.0
            
        return None

    # Baseline piece weights (in kg) for items sold per piece ('st') without size in title
    category_piece_weights = {
        'CAT_0': 0.40, '0': 0.40,     # Canned beans / legumes
        'CAT_1': 0.50, '1': 0.50,     # Bread loaf / tortillas pack
        'CAT_2': 0.25, '2': 0.25,     # Chark / sausage / ham
        'CAT_3': 0.20, '3': 0.20,     # Chips / snacks bag
        'CAT_4': 0.50, '4': 0.50,     # Ice cream / frozen
        'CAT_5': 0.15, '5': 0.15,     # Sweets / chocolate
        'CAT_6': 0.25, '6': 0.25,     # Berries punnet / tomatoes
        'CAT_7': 0.30, '7': 0.30,     # Fresh fruits & vegetables piece
        'CAT_8': 0.50, '8': 0.50,     # Juices / jams bottle
        'CAT_9': 1.00, '9': 1.00,     # Beverages / soda bottle
        'CAT_10': 0.30, '10': 0.30,   # Butter / tofu / cream
        'CAT_11': 0.75, '11': 0.75,   # Cereal / flour / oats
        'CAT_12': 1.00, '12': 1.00,   # Milk / yogurt / dairy
        'CAT_13': 0.20, '13': 0.20,   # Nuts bag
        'CAT_14': 0.40, '14': 0.40,   # Cheese block
        'CAT_15': 1.00, '15': 1.00,   # Rice bag
        'CAT_16': 0.50, '16': 0.50,   # Dry pasta / noodles
        'CAT_17': 0.35, '17': 0.35,   # Vegetables / potatoes
        'CAT_18': 0.50, '18': 0.50,   # Fresh meat / mince tray
        'CAT_19': 0.40, '19': 0.40,   # Prepared meals / pizza
        'CAT_20': 0.40, '20': 0.40,   # Fresh fish / seafood
        'CAT_21': 0.45, '21': 0.45,   # Eggs carton
        'CAT_22': 0.30, '22': 0.30,   # Sauces / condiments
        'CAT_23': 0.10, '23': 0.10,   # Tea / coffee
        'CAT_-1': 0.10, '-1': 0.10,   # Trash bags / non-food
    }

    def calc_row_weight(row):
        u = str(row[unit_col]).strip().lower() if unit_col in row else ''
        q = row['qty_num']
        name = str(row[name_col]) if name_col in row else ''
        cat = str(row['category_id']).strip()
        
        # 1. Direct weight if unit is kg
        if u == 'kg':
            return q
            
        # 2. Extract from product name
        extracted_unit_wt = extract_package_weight_kg(name)
        if extracted_unit_wt is not None:
            return extracted_unit_wt * q
            
        # 3. Fallback category piece weight
        fallback_wt = category_piece_weights.get(cat, 0.30)
        return fallback_wt * q

    # Calculate item weights and CO2e intensity per kg
    df['estimated_total_weight_kg'] = df.apply(calc_row_weight, axis=1)
    df['co2e_per_kg'] = np.where(
        df['estimated_total_weight_kg'] > 0,
        df['co2_num'] / df['estimated_total_weight_kg'],
        0.0
    )

    # Save itemized output and category weight summary
    _ensure_dir(output_csv_path)
    _ensure_dir(output_summary_csv)
    df.to_csv(output_csv_path, index=False)
    
    summary = df.groupby('category_id', as_index=False).agg(
        total_items=('qty_num', 'count'),
        total_quantity=('qty_num', 'sum'),
        total_weight_kg=('estimated_total_weight_kg', 'sum'),
        total_spend_sek=('price_num', 'sum'),
        total_co2e_kg=('co2_num', 'sum')
    )
    summary['avg_co2e_per_kg'] = summary['total_co2e_kg'] / summary['total_weight_kg']
    summary['price_per_kg_sek'] = summary['total_spend_sek'] / summary['total_weight_kg']
    summary = summary.sort_values(by='total_weight_kg', ascending=False)
    summary.to_csv(output_summary_csv, index=False)

    print(f"Itemized weights saved to: {output_csv_path}")
    print(f"Weight summary saved to: {output_summary_csv}")

    return df, summary

if __name__ == '__main__':
    estimate_food_item_weights()
