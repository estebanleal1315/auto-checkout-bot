import os
import requests
import random
import time
import yagmail
from datetime import datetime
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

# === CONFIGURATION ===
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1364357171328061590/8f3Q2JU6N83ix1L-oPI7FkhHOWI0xqE6u6FYk4hLj2gZeiBIwhYKekRGUczuUG-gDRQg"
CHECK_INTERVAL = 10  # seconds
PRODUCT_FILE = "products.txt"
LOG_FILE = "purchase_log.txt"

proxies = []  # Optional: add rotating proxy URLs

def get_random_proxy():
    if not proxies:
        return None
    chosen = random.choice(proxies)
    return {"http": chosen, "https": chosen}

def send_discord_alert(message):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print("❌ Discord error:", e)

def log_purchase(product_url):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now()} - PURCHASED: {product_url}\n")

def log_out_of_stock(product_url):
    with open("out_of_stock_log.txt", "a") as f:
        f.write(f"{datetime.now()} - OUT OF STOCK: {product_url}\n")

def extract_tcin(url):
    match = re.search(r"/A-(\d+)", url)
    if match:
        return match.group(1)
    digits = re.findall(r"\d{8}", url)
    return digits[0] if digits else None

def setup_headless_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        });
        """
    })
    return driver

def is_in_stock(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    proxy = get_random_proxy()
    tcin = extract_tcin(url)
    if not tcin:
        print("❌ Could not extract TCIN from URL.")
        return False

    api_url = (
        f"https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?"
        f"key=eb2551e2aa2dbba0e8aad6f62f1f32be&tcin={tcin}&channel=web&zip=78223"
    )

    try:
        response = requests.get(api_url, headers=headers, proxies=proxy, timeout=10)
        if response.status_code == 200 and 'product' in response.json().get('data', {}):
            data = response.json()
            product = data['data']['product']
            title = product.get('item', {}).get('product_description', {}).get('title', 'Unknown Product')
            network_status = product.get('available_to_promise_network', {}).get('availability_status', "")
            shipping_options = product.get('fulfillment', {}).get('shipping_options', [])
            shipping_available = any(
                option.get("availability", {}).get("available", False)
                for option in shipping_options
            )

            if network_status == "IN_STOCK" or shipping_available:
                print(f"✅ IN STOCK via API: {title}")
                send_discord_alert(f"🌟 IN STOCK (Shipping): {title}\n{url}")
                log_purchase(url)
                return True
            else:
                print("❌ Out of stock via API.")
                return False

        else:
            print("⚠️ RedSky failed, trying stealth headless browser scrape...")

            driver = setup_headless_browser()
            driver.get(url)
            time.sleep(3)
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            driver.quit()

            buttons = soup.find_all("button", string=re.compile("Add to cart", re.I))
            is_real_add_to_cart = any("disabled" not in btn.attrs for btn in buttons)
            text = soup.get_text().lower()
            out_of_stock_phrases = ["out of stock", "sold out", "not available", "coming soon"]
            contains_out_of_stock = any(phrase in text for phrase in out_of_stock_phrases)

            if is_real_add_to_cart and not contains_out_of_stock:
                print("✅ IN STOCK via fallback scrape (valid button found)")
                send_discord_alert(f"🌟 IN STOCK (Scraped): {url}")
                log_purchase(url)
                return True
            else:
                print("❌ Still out of stock (scrape confirmed)")
                return False

    except Exception as e:
        print(f"❌ Error during stock check: {e}")
        return False

def read_product_urls():
    with open(PRODUCT_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def main():
    while True:
        urls = read_product_urls()
        for url in urls:
            if is_in_stock(url):
                print(f"✅ In stock: {url}")
            else:
                print("❌ Still out of stock.")
                log_out_of_stock(url)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print("⚠️ Bot crashed. Restarting...", e)
            time.sleep(5)
