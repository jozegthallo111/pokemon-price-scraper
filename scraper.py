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

# ✅ ChromeDriver installed manually at this location in GitHub Actions
CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"
# ✅ Custom Chrome binary path (Chrome v124)
CHROME_BINARY_PATH = "/opt/google/chrome-linux64/chrome"

BASE_URL = "https://www.pricecharting.com"
CATEGORY_URL = "https://www.pricecharting.com/category/pokemon-cards"
PROCESSED_CARDS_FILE = "scraped_cards.txt"
CSV_FILENAME = "allcorectpricees.csv"


def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920x1080")

    # ✅ Force Selenium to use the correct Chrome binary
    options.binary_location = CHROME_BINARY_PATH

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def fetch_console_urls(driver):
    driver.get(CATEGORY_URL)
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.sets")))
    except TimeoutException:
        print("Timeout waiting for console sets container.")
    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href^='/console/']")
    return list({a.get_attribute("href") for a in anchors if a.get_attribute("href").startswith(BASE_URL + "/console/pokemon")})


def get_card_links_from_console(driver, console_url):
    driver.get(console_url)
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
    grade_9_5
