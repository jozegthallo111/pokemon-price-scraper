import time
import csv
import os
import zipfile
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configuration for GitHub Actions or local
CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver" if os.getenv('GITHUB_ACTIONS') else "/usr/local/bin/chromedriver"
BASE_URL = "https://www.pricecharting.com"
CSV_FILENAME = "japanese_cards.csv"
ZIP_FILENAME = "japanese_cards.zip"
PROCESSED_CARDS_FILE = "scraped_cards_japanese.txt"

# Keywords to identify Japanese cards
JAPANESE_CARD_KEYWORDS = ["japanese", "jpn", "japan"]
# Keywords to exclude sets from scraping
EXCLUDE_SET_KEYWORDS = ["japanese", "chinese"]

def init_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1920, 1080)
    return driver

def get_card_links(driver, set_url):
    try:
        driver.get(set_url)
        time.sleep(2)
        card_links = set()
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            cards = driver.find_elements(By.CSS_SELECTOR, "a[href^='/game/']")
            card_links.update(card.get_attribute('href') for card in cards)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        print(f"Extracted {len(card_links)} card links from set page.")
        return list(card_links)
    except Exception as e:
        print(f"Error getting card links from {set_url}: {str(e)}")
        return []

def get_japanese_set_links(driver):
    try:
        driver.get(f"{BASE_URL}/category/pokemon-cards")
        time.sleep(3)
        links = driver.find_elements(By.CSS_SELECTOR, "div.sets a")
        
        filtered_links = [
            link.get_attribute("href") for link in links 
            if not any(excl_keyword in link.text.lower() for excl_keyword in EXCLUDE_SET_KEYWORDS)
        ]
        
        print(f"Filtered set links count: {len(filtered_links)}")
        return filtered_links
    except Exception as e:
        print(f"Error getting set links: {str(e)}")
        return []

def clean_price(price_elem):
    if price_elem:
        text = price_elem.text.strip()
        return text if text != "-" else "N/A"
    return "N/A"

def fetch_card_data(driver, card_url):
    try:
        driver.get(card_url)
        wait = WebDriverWait(driver, 10)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1#product_name")))
        except TimeoutException:
            print(f"Timeout loading card page: {card_url}")
            return None

        name = driver.find_element(By.CSS_SELECTOR, "h1#product_name").text.strip()
        if not any(word in name.lower() for word in JAPANESE_CARD_KEYWORDS):
            print(f"Skipped non-Japanese card: {name}")
            return None

        prices = driver.find_elements(By.CSS_SELECTOR, "span.price.js-price")
        raw_price = clean_price(prices[0]) if prices else "N/A"

        # Filter low-value cards (<$10)
        try:
            numeric_price = float(raw_price.replace("$", "").replace(",", ""))
            if numeric_price < 10:
                print(f"Skipped low-value card: {name} (${numeric_price})")
                return None
        except ValueError:
            pass

        grade_7 = clean_price(prices[1]) if len(prices) > 1 else "N/A"
        grade_8 = clean_price(prices[2]) if len(prices) > 2 else "N/A"
        grade_9 = clean_price(prices[3]) if len(prices) > 3 else "N/A"
        grade_9_5 = clean_price(prices[4]) if len(prices) > 4 else "N/A"
        psa_10 = clean_price(prices[5]) if len(prices) > 5 else "N/A"

        try:
            rarity = driver.find_element(By.CSS_SELECTOR, "td.details[itemprop='description']").text.strip()
        except NoSuchElementException:
            rarity = "none"
        try:
            model_number = driver.find_element(By.CSS_SELECTOR, "td.details[itemprop='model-number']").text.strip()
        except NoSuchElementException:
            model_number = "N/A"

        image_url = next(
            (img.get_attribute("src") for img in driver.find_elements(By.CSS_SELECTOR, "img")
             if img.get_attribute("src") and "1600.jpg" in img.get_attribute("src")), 
            "N/A"
        )

        card_data = {
            "Name": name,
            "Raw Price": raw_price,
            "Grade 7 Price": grade_7,
            "Grade 8 Price": grade_8,
            "Grade 9 Price": grade_9,
            "Grade 9.5 Price": grade_9_5,
            "PSA 10 Price": psa_10,
            "Rarity": rarity,
            "Model Number": model_number,
            "Image URL": image_url,
            "Card URL": card_url
        }
        print(f"Fetched data for card: {name}")
        return card_data
    except Exception as e:
        print(f"Error fetching data for {card_url}: {str(e)}")
        return None

def save_to_csv(data, filename=CSV_FILENAME, write_header=False, mode='a'):
    if not data:
        print("No data to save.")
        return
    try:
        # If writing header, open with 'w' else append 'a'
        open_mode = 'w' if write_header else 'a'
        with open(filename, open_mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            if write_header:
                writer.writeheader()
            writer.writerows(data)
        print(f"Saved {len(data)} cards to {filename}")
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")

def create_zip():
    try:
        with zipfile.ZipFile(ZIP_FILENAME, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists(CSV_FILENAME):
                zipf.write(CSV_FILENAME)
            else:
                print(f"Warning: CSV file {CSV_FILENAME} not found to add to zip.")
            if os.path.exists(PROCESSED_CARDS_FILE):
                zipf.write(PROCESSED_CARDS_FILE)
        print(f"Created zip file: {ZIP_FILENAME}")
    except Exception as e:
        print(f"Error creating zip file: {str(e)}")

def main():
    driver = init_driver()
    try:
        # Load processed cards from file
        processed_cards = set()
        if os.path.exists(PROCESSED_CARDS_FILE):
            with open(PROCESSED_CARDS_FILE, "r", encoding="utf-8") as f:
                processed_cards = set(line.strip() for line in f if line.strip())
            print(f"Loaded {len(processed_cards)} processed cards.")

        all_cards_data = []
        first_save = not os.path.exists(CSV_FILENAME)
        processed_count = 0

        japanese_set_links = get_japanese_set_links(driver)
        print(f"Found {len(japanese_set_links)} sets after filtering.")
        
        for set_url in japanese_set_links:
            print(f"Processing set: {set_url}")
            card_links = get_card_links(driver, set_url)
            print(f"Found {len(card_links)} cards in set.")
            
            for card_url in card_links:
                if card_url in processed_cards:
                    print(f"Already processed: {card_url}")
                    continue
                card_data = fetch_card_data(driver, card_url)
                if card_data:
                    all_cards_data.append(card_data)
                    # Append processed card URL immediately
                    with open(PROCESSED_CARDS_FILE, "a", encoding="utf-8") as f:
                        f.write(card_url + "\n")
                    processed_cards.add(card_url)
                    processed_count += 1
                # Save every 1000 cards
                if processed_count > 0 and processed_count % 1000 == 0:
                    save_to_csv(all_cards_data, write_header=first_save)
                    all_cards_data = []
                    first_save = False
                time.sleep(1)  # Be polite with requests

        # Save remaining cards
        if all_cards_data:
            save_to_csv(all_cards_data, write_header=first_save)
        
        create_zip()

        # Debug: list files in current directory after scraping & saving
        print("Files in current directory after scraping:")
        print("\n".join(os.listdir(".")))
        
    except Exception as e:
        print(f"Error in main execution: {str(e)}")
    finally:
        driver.quit()
        print("Driver closed.")

if __name__ == "__main__":
    main()
