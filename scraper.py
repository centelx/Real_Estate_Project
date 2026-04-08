from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import json
import os

def configure_browser():
    print("Initializing browser cloaking configuration...")
    options = Options()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    return driver

# ==========================================
# ENVIRONMENT VARIABLES
# ==========================================
TOTAL_PAGES = 140
LINKS_FILE = "zebrane_linki.txt"
OUTPUT_CSV = "nieruchomosci_otodom.csv"

driver = configure_browser()
scraped_links = []

# ==========================================
# PHASE 1: URL EXTRACTION (WITH RESUME CAPABILITY)
# ==========================================
if os.path.exists(LINKS_FILE):
    print(f"\n--- CACHE LOCATED: '{LINKS_FILE}' ---")
    print("Bypassing search engine iteration. Ingesting cached URLs...")
    with open(LINKS_FILE, 'r', encoding='utf-8') as f:
        scraped_links = [line.strip() for line in f if line.strip()]
    print(f"Successfully loaded {len(scraped_links)} URLs from cache.")
else:
    print(f"\n--- PHASE 1: ITERATING TARGET DIRECTORY ({TOTAL_PAGES} PAGES) ---")
    for page in range(1, TOTAL_PAGES + 1):
        print(f"Scanning directory pagination: {page}/{TOTAL_PAGES}...")
        url = f"https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/mazowieckie/warszawa/warszawa/warszawa?limit=36&ownerTypeSingleSelect=ALL&by=DEFAULT&direction=DESC&page={page}"
        driver.get(url)

        if page == 1:
            try:
                cookie_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
                )
                cookie_button.click()
                print("Consent modal dismissed.")
            except:
                pass

        time.sleep(random.uniform(2.0, 3.5))

        listings = driver.find_elements(By.CSS_SELECTOR, 'a[data-cy="listing-item-link"]')
        for listing in listings:
            href = listing.get_attribute('href')
            if href and not href.startswith('http'):
                href = "https://www.otodom.pl" + href
            if href and href not in scraped_links:
                scraped_links.append(href)

    # Persist scraped URLs to mitigate potential runtime interruptions
    with open(LINKS_FILE, 'w', encoding='utf-8') as f:
        for href in scraped_links:
            f.write(href + "\n")
    print(f"URL extraction complete. {len(scraped_links)} unique endpoints persisted to '{LINKS_FILE}'.")


# ==========================================
# PHASE 2: METADATA PARSING & BATCH PROCESSING
# ==========================================
print("\n--- PHASE 2: SCRAPING LISTING METADATA ---")

processed_urls = set()
is_initial_write = True

# Validate existing dataset to prevent redundant network requests
if os.path.exists(OUTPUT_CSV):
    try:
        existing_df = pd.read_csv(OUTPUT_CSV)
        if 'Link' in existing_df.columns:
            processed_urls = set(existing_df['Link'].tolist())
            is_initial_write = False
            print(f"Existing dataset detected. {len(processed_urls)} records already in database.")
    except Exception as e:
        print(f"Warning: Dataset validation failed: {e}")

# Filter workload array against existing database entries
pending_urls = [href for href in scraped_links if href not in processed_urls]
print(f"Queued for extraction: {len(pending_urls)} records.\n")

data_batch = []

for idx, target_url in enumerate(pending_urls, 1):
    print(f"Fetching payload [{idx}/{len(pending_urls)}]...")
    driver.get(target_url)

    time.sleep(random.uniform(2.0, 4.0))
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    listing_payload = {
        'Link': target_url,
        'Tytuł': None,
        'Cena_Calkowita': None,
    }

    try:
        title_node = soup.find('h1', {'data-cy': 'adPageAdTitle'})
        listing_payload['Tytuł'] = title_node.text.strip() if title_node else None

        price_node = soup.find('strong', {'data-cy': 'adPageHeaderPrice'})
        listing_payload['Cena_Calkowita'] = price_node.text.strip() if price_node else None

        script_tags = soup.find_all('script', type='application/ld+json')
        for script in script_tags:
            if not script.string:
                continue

            json_blob = json.loads(script.string)
            if isinstance(json_blob, dict) and "@graph" in json_blob:
                for node in json_blob["@graph"]:
                    if "additionalProperty" in node:
                        for property_obj in node["additionalProperty"]:
                            prop_name = property_obj.get("name")
                            prop_value = property_obj.get("value")
                            if prop_name and prop_value:
                                listing_payload[prop_name] = prop_value

        data_batch.append(listing_payload)

    except Exception as e:
        print(f" -> Parsing exception encountered on current node: {e}")

    # Commit transactions in chunks to optimize memory and ensure persistence
    if idx % 100 == 0 or idx == len(pending_urls):
        batch_df = pd.DataFrame(data_batch)
        batch_df.to_csv(OUTPUT_CSV, mode='a', header=is_initial_write, index=False, encoding='utf-8-sig')

        print(f"\n---> Data batch committed to persistence layer. (Progress: {idx}/{len(pending_urls)}) <---")

        is_initial_write = False
        data_batch = []

driver.quit()
print(f"\nExecution finalized. Web scraping pipeline terminated. Proceed to execute cleaner.py pipeline.")