import pandas as pd
import numpy as np
import re

print("Ingesting raw dataset...")
df = pd.read_csv("nieruchomosci_otodom.csv")

print("Data cleansing process initiated...")

# 1. TOTAL PRICE STANDARDIZATION
df['Cena_Calkowita'] = df['Cena_Calkowita'].astype(str).str.replace(' ', '', regex=False) # Strip thousands separators
df['Cena_Calkowita'] = df['Cena_Calkowita'].str.replace(',', '.', regex=False) # Convert decimal comma to dot
df['Cena_Calkowita'] = df['Cena_Calkowita'].str.replace(r'[^\d.]', '', regex=True) # Retain numeric characters and decimal point only
df['Cena_Calkowita'] = pd.to_numeric(df['Cena_Calkowita'], errors='coerce')

# 2. AREA (SQUARE METERS) STANDARDIZATION
df['Powierzchnia'] = df['Powierzchnia'].astype(str).str.replace(' m²', '', regex=False).str.replace(' ', '', regex=False)
df['Powierzchnia'] = df['Powierzchnia'].str.replace(',', '.', regex=False)
df['Powierzchnia'] = pd.to_numeric(df['Powierzchnia'], errors='coerce')

# 3. ROOM COUNT EXTRACTION
df['Liczba pokoi'] = df['Liczba pokoi'].astype(str).str.extract(r'(\d+)')
df['Liczba pokoi'] = pd.to_numeric(df['Liczba pokoi'], errors='coerce')

# 4. RENT STANDARDIZATION
df['Czynsz'] = df['Czynsz'].astype(str).str.replace(' ', '', regex=False)
df['Czynsz'] = df['Czynsz'].str.replace(',', '.', regex=False)
df['Czynsz'] = df['Czynsz'].str.replace(r'[^\d.]', '', regex=True)
df['Czynsz'] = pd.to_numeric(df['Czynsz'], errors='coerce')

# 5. FLOOR LEVEL PARSING ALGORITHM
def parse_floor_level(value):
    value = str(value).lower()
    if 'parter' in value:
        return 0
    elif 'suterena' in value:
        return -1
    else:
        match = re.search(r'(\d+)', value)
        return float(match.group(1)) if match else np.nan

df['Piętro_num'] = df['Piętro'].apply(parse_floor_level)


# 6. FEATURE ENGINEERING: Extracting premium attributes from unstructured text
text_columns = ['Informacje dodatkowe', 'Bezpieczeństwo', 'Wyposażenie', 'Zabezpieczenia', 'Media']

print("Executing feature extraction from supplementary metadata...")

# Handle missing values and concatenate target columns into a single lowercased corpus
for col in text_columns:
    if col in df.columns:
        df[col] = df[col].fillna('')

df['Wszystkie_cechy'] = df[[c for c in text_columns if c in df.columns]].agg(','.join, axis=1).str.lower()

# Target keywords aligned with BI dashboard requirements
target_features = [
    'balkon',
    'garaż',
    'ogródek',
    'taras',
    'piwnica',
    'klimatyzacja',
    'monitoring',
    'teren zamknięty',
    'oddzielna kuchnia'
]

# Generate binary flags (One-Hot Encoding equivalent) for detected features
for feature in target_features:
    column_name = f"Cecha_{feature.capitalize()}"
    df[column_name] = df['Wszystkie_cechy'].apply(lambda x: 1 if feature in x else 0)

# Drop redundant raw text arrays and temporary columns to optimize dataset size
columns_to_drop = [col for col in text_columns if col in df.columns] + ['Wszystkie_cechy', 'Piętro']
df = df.drop(columns=columns_to_drop, errors='ignore')

print("\n--- PROCESSED DATASET PREVIEW ---")
print(df.columns.tolist())

# Export finalized dataset for Power BI ingestion
output_filename = "nieruchomosci_czyste.csv"
df.to_csv(output_filename, index=False, encoding='utf-8-sig')
print(f"\nExecution successful. Cleansed dataset exported to: {output_filename}")