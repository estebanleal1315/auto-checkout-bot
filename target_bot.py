import os
import requests
import random
import time
import yagmail
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from datetime import datetime
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# === CONFIGURATION ===
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1364357171328061590/8f3Q2JU6N83ix1L-oPI7FkhHOWI0xqE6u6FYk4hLj2gZeiBIwhYKekRGUczuUG-gDRQg"
EMAIL_ADDRESS = "estebanleal1315@gmail.com"
EMAIL_PASSWORD = "Pesca12.3"
CHECK_INTERVAL = 10  # seconds
PRODUCT_FILE = "products.txt"
LOG_FILE = "purchase_log.txt"

TARGET_EMAIL = "estebanleal1315@gmail.com"
TARGET_PASSWORD = "pesca123"

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

def send_email_alert(subject, body):
    try:
        yag = yagmail.SMTP(EMAIL_ADDRESS, EMAIL_PASSWORD)
        yag.send(to=EMAIL_ADDRESS, subject=subject, contents=body)
    except Exception as e:
        print("❌ Email error:", e)

def log_purchase(product_url):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now()} - PURCHASED: {product_url}\n")

def log_out_of_stock(product_url):
    with open("out_of_stock_log.txt", "a") as f:
        f.write(f"{datetime.now()} - OUT OF STOCK: {product_url}\n")

def is_in_stock(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    proxy = get_random_proxy()
    try:
        response = requests.get(url, headers=headers, proxies=proxy, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        return "Out of stock" not in soup.text
    except Exception as e:
        print(f"❌ Error checking {url}:", e)
        return False

def auto_buy(url):
    driver_path = os.path.join(os.getcwd(), "chromedriver.exe")
    if not os.path.exists(driver_path):
        print("❌ chromedriver.exe not found!")
        return

    service = Service(driver_path)
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(15)

    try:
        print("🔐 Logging in...")
        driver.get("https://www.target.com/account/sign-in")
        wait = WebDriverWait(driver, 15)

# Wait for and enter email
        email_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
        email_input.send_keys(TARGET_EMAIL)

# Try clicking "Continue" if it exists
        try:
            continue_btn = driver.find_element(By.XPATH, "//button[@data-test='login-continue-button']")
            continue_btn.click()
            print("➡️ Clicked continue")
            time.sleep(1)
        except:
            print("➡️ No continue button — moving on")

# Wait for and enter password
        password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password_input.send_keys(TARGET_PASSWORD)
        password_input.send_keys(Keys.RETURN)

        time.sleep(5)
        print("✅ Logged in.")


        # Purchase loop
        for attempt in range(3):
            try:
                print(f"🛒 Attempting purchase for {url} (Try {attempt + 1})")
                driver.get(url)
                time.sleep(3)

                add_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Add to cart')]")
                add_button.click()
                time.sleep(2)

                driver.get("https://www.target.com/co-cart")
                time.sleep(2)

                try:
                    qty_input = driver.find_element(By.XPATH, "//input[@aria-label='Quantity']")
                    qty_input.clear()
                    qty_input.send_keys("3")
                    qty_input.send_keys(Keys.RETURN)
                    print("✅ Set quantity to 3")
                    time.sleep(2)
                except:
                    print("⚠️ Quantity input not found.")

                checkout_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Checkout')]")
                checkout_btn.click()
                time.sleep(3)

                try:
                    cvc_input = driver.find_element(By.NAME, "creditCard.cvv")
                    cvc_input.send_keys("258")
                    print("✅ CVC filled")
                    time.sleep(1)
                except:
                    print("⚠️ No CVC field found")

                try:
                    place_order_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Place your order')]")
                    place_order_btn.click()
                    print("🎉 Order placed!")
                except:
                    print("⚠️ Could not find 'Place your order' button.")

                log_purchase(url)
                send_discord_alert(f"🎉 Order placed for: {url}")
                send_email_alert("✅ Target Order Placed", f"Your order has been submitted for: {url}")
                break

            except Exception as inner_e:
                print(f"❌ Failed attempt {attempt + 1}: {inner_e}")
                time.sleep(5)

    except Exception as e:
        print(f"❌ Login or browser error: {e}")

    finally:
        time.sleep(1)
        try:
            driver.quit()
        except:
            print("⚠️ Chrome already closed or couldn't connect to shutdown.")



# === MAIN LOOP ===
def read_product_urls():
    with open(PRODUCT_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def main():
    while True:
        urls = read_product_urls()
        for url in urls:
            print(f"🔍 Checking {url}")
            if is_in_stock(url):
                print(f"✅ In stock: {url}")
                auto_buy(url)
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
