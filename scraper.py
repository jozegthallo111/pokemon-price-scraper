import time
import csv
import os
import zipfile
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CHROMEDRIVER_PATH = "/content/chromedriver-linux64/chromedriver"
BASE_URL = "https://www.pricecharting.com"
CATEGORY_URL = "https://www.pricecharting.com/category/pokemon-cards"
PROCESSED_CARDS_FILE = "scraped_cards.txt"
CSV_FILENAME = "allcorectpricees.csv"


TARGET_SET_PATHS = [
    "/console/pokemon-promo",
    "/console/pokemon-prismatic-evolutions",
    "/console/pokemon-journey-together",
    "/console/pokemon-scarlet-&-violet-151",
    "/console/pokemon-base-set",
    "/console/pokemon-surging-sparks",
    "/console/pokemon-crown-zenith",
    "/console/pokemon-obsidian-flames",
    "/console/pokemon-paradox-rift",
    "/console/pokemon-scarlet-&-violet",
    "/console/pokemon-paldea-evolved",
    "/console/pokemon-temporal-forces",
    "/console/pokemon-paldean-fates",
    "/console/pokemon-stellar-crown",
    "/console/pokemon-evolving-skies",
    "/console/pokemon-twilight-masquerade",
    "/console/pokemon-evolutions",
    "/console/pokemon-japanese-promo",
    "/console/pokemon-silver-tempest",
    "/console/pokemon-celebrations",
]

def git_save_and_push(files, commit_message="Auto-save data update"):
    """
    Commit and push specified files to GitHub.
    `files` is a list of file paths to add and commit.
    """
    try:
        subprocess.run(["git", "add"] + files, check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print(f"Git push successful for files: {files}")
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")

def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(f"--user-data-dir=/tmp/unique_profile_{int(time.time())}")
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1920, 1080)
    return driver

def fetch_console_urls():
    return [BASE_URL + path for path in TARGET_SET_PATHS]

def get_card_links_from_console(driver, console_url):
    driver.get(console_url)
    time.sleep(2)
    card_links = set()
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        cards = driver.find_elements(By.CSS_SELECTOR, "a[href^='/game/']")
        card_links.update(BASE_URL + card.get_attribute('href') for card in cards)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    return list(card_links)

def clean_price(price_elem):
    if price_elem:
        text = price_elem.text.strip()
        return text if text != "-" else "N/A"
    return "N/A"

def fetch_card_data(driver, card_url):
    driver.get(card_url)
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1#product_name")))
    except TimeoutException:
        print(f"Timeout loading card page: {card_url}")
        return None
    name = driver.find_element(By.CSS_SELECTOR, "h1#product_name").text.strip()
    prices = driver.find_elements(By.CSS_SELECTOR, "span.price.js-price")
    raw_price = clean_price(prices[0]) if len(prices) > 0 else "N/A"
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
    image_url = next((img.get_attribute("src") for img in driver.find_elements(By.CSS_SELECTOR, "img") if img.get_attribute("src") and "1600.jpg" in img.get_attribute("src")), "N/A")
    return {
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

def save_to_csv(data, filename=CSV_FILENAME, write_header=False, mode='a'):
    if not data:
        print("No data to save.")
        return
    with open(filename, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        if write_header:
            writer.writeheader()
        writer.writerows(data)
    print(f"Saved to {filename}")
    # Auto push after saving
    git_save_and_push([filename, PROCESSED_CARDS_FILE], f"Auto-save CSV and processed cards at {time.strftime('%Y-%m-%d %H:%M:%S')}")

def zip_csv_file(csv_filename=CSV_FILENAME, zip_filename="allcorectpricees.zip"):
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(csv_filename, arcname=os.path.basename(csv_filename))
    print(f"Zipped to {zip_filename}")
    # Auto push zip file as well
    git_save_and_push([zip_filename], f"Auto-save ZIP at {time.strftime('%Y-%m-%d %H:%M:%S')}")

def load_processed_cards():
    if not os.path.exists(PROCESSED_CARDS_FILE):
        return set()
    with open(PROCESSED_CARDS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def main():
    driver = init_driver()
    try:
        console_urls = fetch_console_urls()
        processed_cards = load_processed_cards()
        all_cards_data = []
        first_save = True
        processed_count = 0
        for console_url in console_urls:
            print(f"Processing console: {console_url}")
            card_links = get_card_links_from_console(driver, console_url)
            for i, card_url in enumerate(card_links, 1):
                if card_url in processed_cards:
                    continue
                print(f"Scraping card {i}/{len(card_links)}: {card_url}")
                card_data = fetch_card_data(driver, card_url)
                if card_data:
                    all_cards_data.append(card_data)
                    with open(PROCESSED_CARDS_FILE, "a", encoding="utf-8") as f:
                        f.write(card_url + "\n")
                    processed_cards.add(card_url)
                    processed_count += 1
                if processed_count % 10 == 0:
                    save_to_csv(all_cards_data, write_header=first_save)
                    all_cards_data = []
                    first_save = False
                if processed_count > 0 and processed_count % 500 == 0:
                    zip_csv_file()
                time.sleep(1)
        if all_cards_data:
            save_to_csv(all_cards_data, write_header=first_save)
    finally:
        driver.quit()
        print("Driver closed.")

if __name__ == "__main__":
    main()
