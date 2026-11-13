# 🥗 Matklok — Food Waste & Cost Analytics

> Data pipeline analyzing Swedish grocery receipt transactions to estimate food spend, physical weight, CO₂e emissions, and the cost of food waste in **SEK per kg**.

---

## 📌 Project Overview

Matklok processes itemized grocery receipt transactions (~45,600 rows) through a 3-step analytical pipeline to provide category-level insights into:
- 🛒 **Spend & Consumption**: Purchased weight (kg) and cost (SEK)
- 🌍 **Carbon Footprint**: Total CO₂e and carbon intensity (kg CO₂e / kg)
- 🗑️ **Waste Economics**: Waste volume (kg), lost economic value (SEK), and the key metric: **cost of waste (SEK / kg)**

---

## 🗂️ Repository Structure

```text
Matklok/
├── data/
│   └── food-items-all.csv               # Raw receipt transactions (~45,600 rows)
├── output/
│   ├── category_waste_cost.csv          # Final waste economics & SEK/kg estimates
│   ├── category_waste_summary.csv       # Category spend, count, CO2e, shelf-life
│   ├── category_weight_waste_summary.csv# Category totals with physical weights
│   ├── food-items-with-weights.csv      # Item-level transactions with weights & CO2e/kg
│   └── gtin_shelf_life_lookup.csv       # Barcode/GTIN product lookup table
├── run.py                               # Master end-to-end pipeline runner (Steps 1–3)
├── process_food_items.py                # Step 1: Shelf-life baselines & aggregations
├── estimate_item_weights.py             # Step 2: Weight extraction & CO2e intensity
├── estimate_waste_cost.py               # Step 3: Food waste cost estimation (Methods A & B)
├── requirements.txt                     # Python package dependencies
├── .gitignore                           # Git ignore configuration
├── CHANGES.md                           # Project changelog
└── README.md                            # Documentation & user guide
```

---

## ⚙️ Installation

Ensure you have Python 3.10+ installed, then install dependencies:

```bash
pip install -r requirements.txt
```

**Required packages:**
- `pandas>=2.0.0`
- `numpy>=1.24.0`

---

## 🚀 Pipeline & Quickstart

```text
data/food-items-all.csv (Raw Receipts, ~45.6k items)
         │
         ├───▶ [Step 1] process_food_items.py
         │       ├── output/category_waste_summary.csv
         │       └── output/gtin_shelf_life_lookup.csv
         │
         ├───▶ [Step 2] estimate_item_weights.py
         │       ├── output/food-items-with-weights.csv
         │       └── output/category_weight_waste_summary.csv
         │
         └───▶ [Step 3] estimate_waste_cost.py
                 └── output/category_waste_cost.csv
```

### Running the Full Pipeline

Execute all three steps in sequence using `run.py`:

```bash
# Default: Literature-based waste rates (Method A)
python3 run.py

# Alternative: Data-driven shelf-life waste rates (Method B)
python3 run.py --method shelf_life
```

### Running Steps Individually

Each step can also be run as an independent module:

```bash
python3 process_food_items.py
python3 estimate_item_weights.py
python3 estimate_waste_cost.py --method literature
```

---

## 🔍 Pipeline Steps

### 1️⃣ Step 1: Cleaning & Shelf-Life Baseline (`process_food_items.py`)
- Standardizes receipt fields (dates, line prices, GTIN barcodes, and category IDs `CAT_0` to `CAT_23`).
- Assigns expected shelf-life baselines per category (from 4 days for fresh fish to 365 days for dry pasta).
- **Outputs**: `output/category_waste_summary.csv`, `output/gtin_shelf_life_lookup.csv`

### 2️⃣ Step 2: Physical Weight Estimation (`estimate_item_weights.py`)
Because grocery receipts frequently log items in pieces (`st`) rather than weight (`kg`), this step resolves physical item weights using a 3-tier cascade:
1. **Direct Unit**: Uses `quantity` if the transaction unit is already `kg`.
2. **Regex Parsing**: Extracts package sizes directly from product names (e.g., `"Yoghurt 500g"` ➔ `0.5 kg`, `"Mjölk 1.5L"` ➔ `1.5 kg`).
3. **Category Fallbacks**: Uses default piece weights per food category for unlabelled items.
- **Outputs**: `output/food-items-with-weights.csv`, `output/category_weight_waste_summary.csv`

### 3️⃣ Step 3: Food Waste Cost Calculation (`estimate_waste_cost.py`)
Calculates wasted food volume, lost value, and unit costs:
$$\text{waste\_kg} = \text{total\_weight\_kg} \times \text{waste\_rate}$$
$$\text{waste\_spend\_sek} = \text{total\_spend\_sek} \times \text{waste\_rate}$$
$$\text{sek\_per\_kg\_waste} = \frac{\text{waste\_spend\_sek}}{\text{waste\_kg}} \quad \text{(Key Metric)}$$
- **Output**: `output/category_waste_cost.csv`

---

## 📊 Waste Rate Methodology

The model supports two selectable calculation methods via `--method`:

| Method | Type | Description | Primary Sources |
| :--- | :--- | :--- | :--- |
| **Method A: `literature`** *(Default)* | Benchmark | Hardcoded rate constants based on Swedish & international waste studies | Livsmedelsverket PM 2024, Naturvårdsverket 2026, WRAP / FAO |
| **Method B: `shelf_life`** | Data-Driven | Derived systematically from each category's shelf-life baseline | Stepped mapping (shorter shelf life ➔ higher waste rate) |

<details>
<summary><b>Click to expand rate breakdown by category</b></summary>

#### Method A: Benchmark Literature Rates
- Fresh berries & soft fruit: `35%`
- Fresh fruit & vegetables: `30%`
- Vegetables & potatoes: `28%`
- Dairy / milk / yogurt: `25%`
- Fresh fish & seafood: `22%`
- Bread / Bakery: `20%`
- Cheese: `20%`
- Fresh meat / mince: `18%`
- Frozen food: `5%`
- Dry pasta / rice: `3%`
- Non-food / bags: `0%`

#### Method B: Shelf-Life Mapping
- $\le 5$ days: `30%` *(e.g., fresh fish, mince)*
- $\le 10$ days: `25%` *(e.g., dairy, chark)*
- $\le 14$ days: `20%` *(e.g., bread, vegetables)*
- $\le 30$ days: `12%` *(e.g., jams, juices)*
- $\le 90$ days: `8%` *(e.g., snacks, sweets)*
- $\le 180$ days: `5%` *(e.g., frozen foods, beverages)*
- $> 180$ days: `3%` *(e.g., rice, dry pasta, coffee)*

</details>

---

## 📈 Key Findings (Method A - Literature)

### 🎯 Macro Totals
- ⚖️ **Total Estimated Waste**: `4,519.2 kg`
- 💸 **Total Wasted Value**: `202,762 SEK`
- 💨 **Total Waste Carbon Footprint**: `7,928.6 kg CO₂e`
- 🏷️ **Overall Cost per kg Waste**: **`44.9 SEK/kg`** *(Validates Swedish national benchmark of ~44 SEK/kg by Naturvårdsverket 2026)*

### 🏆 Top 5 Categories by Waste Spend

| Category | Category ID | Estimated Waste | Waste Value | Cost of Waste |
| :--- | :---: | :---: | :---: | :---: |
| 🐟 **Fresh fish / Seafood** | `CAT_20` | 269.1 kg | 33,892 SEK | **125.9 SEK/kg** |
| 🍎 **Fresh fruit & vegetables** | `CAT_7` | 966.8 kg | 33,734 SEK | **34.9 SEK/kg** |
| 🥔 **Vegetables / Potatoes** | `CAT_17` | 752.1 kg | 24,742 SEK | **32.9 SEK/kg** |
| 🥩 **Fresh meat / Mince** | `CAT_18` | 179.0 kg | 18,858 SEK | **105.3 SEK/kg** |
| 🥛 **Dairy / Milk / Yogurt** | `CAT_12` | 1,114.2 kg | 17,903 SEK | **16.1 SEK/kg** |

> [!NOTE]
> High spend on fish and meat waste is driven by high unit purchase prices (SEK/kg), whereas fresh produce and dairy drive the highest physical waste volume.

---

## 🏷️ Category Reference

| Category ID | Category Name | Default Shelf Life |
| :--- | :--- | :---: |
| `CAT_-1` | Non-food / Trash bags | — |
| `CAT_0` | Canned legumes | 180 days |
| `CAT_1` | Bread | 14 days |
| `CAT_2` | Chark / Sausage | 10 days |
| `CAT_3` | Snacks / Chips | 90 days |
| `CAT_4` | Frozen foods | 180 days |
| `CAT_5` | Sweets / Chocolate | 120 days |
| `CAT_6` | Fresh berries & soft fruit | 7 days |
| `CAT_7` | Fresh fruit & vegetables | 7 days |
| `CAT_8` | Juices / Jams | 30 days |
| `CAT_9` | Beverages | 180 days |
| `CAT_10` | Butter / Tofu / Cream | 14 days |
| `CAT_11` | Cereal / Flour / Oats | 180 days |
| `CAT_12` | Dairy / Milk / Yogurt | 10 days |
| `CAT_13` | Nuts | 180 days |
| `CAT_14` | Cheese | 21 days |
| `CAT_15` | Rice | 365 days |
| `CAT_16` | Dry pasta / Noodles | 365 days |
| `CAT_17` | Vegetables / Potatoes | 14 days |
| `CAT_18` | Fresh meat / Mince | 5 days |
| `CAT_19` | Prepared meals / Pizza | 14 days |
| `CAT_20` | Fresh fish / Seafood | 4 days |
| `CAT_21` | Eggs | 21 days |
| `CAT_22` | Sauces / Condiments | 60 days |
| `CAT_23` | Tea / Coffee | 365 days |

---

## 🗺️ Roadmap & Next Steps

- [x] Hook `estimate_waste_cost.py` into `run.py` as Step 3
- [ ] Refine Method A rates with SCB / Livsmedelsverket category-specific surveys
- [ ] Validate Method A against peer-reviewed household waste data
- [ ] **Method D Implementation**: Repurchase gap analysis (using `transaction_date` + `gtin_barcode` to derive empirical waste rates)
- [ ] Household breakdown analysis (leveraging `synthetic_household` field)
