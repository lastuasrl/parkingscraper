#!/usr/bin/env python3
"""
FORESTIS Hotel Rate Scraper
Collects daily room rates for the base room (35m² Room) for a year ahead.
Uses Selenium with undetected-chromedriver to navigate the SynXis booking engine.

FORESTIS Dolomites - Luxury wellness hotel in Brixen/Bressanone, South Tyrol
https://www.forestis.it/

USAGE:
    python scraper_forestis.py              # Interactive mode (recommended for first run)
    python scraper_forestis.py --days 30    # Scrape 30 days ahead
    python scraper_forestis.py --headless   # Run headless (may fail due to CAPTCHA)

NOTE: The SynXis booking engine uses Imperva WAF which may require solving a
CAPTCHA challenge. Run in interactive mode (default) to solve it manually.
"""

import csv
import io
import json
import re
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configuration
HOTEL_NAME = "FORESTIS Dolomites"
BASE_URL = "https://be.synxis.com/"
HOTEL_PARAMS = {
    "chain": "22402",
    "hotel": "30944",
    "locale": "en-US",
    "src": "24C",
    "filter": "HOTEL",
    "adult": "2",
    "rooms": "1"
}

# Target room: The base "Room" (35 m²)
TARGET_ROOM_KEYWORDS = ["room", "35"]

DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "forestis_rates.csv"
COOKIES_FILE = DATA_DIR / "cookies.json"
SCRAPE_DAYS_AHEAD = 365

CSV_HEADER_COMMENT = """# FORESTIS Dolomites Hotel Rates
# Source: SynXis Booking Engine
# Hotel: FORESTIS, Plancios, Brixen/Bressanone, South Tyrol
# Room Type: Base Room (35 m²)
# Rates are per night for 2 adults
#
"""


def build_booking_url(checkin_date, checkout_date):
    """Build the SynXis booking URL for specific dates."""
    params = HOTEL_PARAMS.copy()
    params["arrive"] = checkin_date.strftime("%Y-%m-%d")
    params["depart"] = checkout_date.strftime("%Y-%m-%d")
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{BASE_URL}?{query_string}"


def setup_driver(headless=False):
    """Set up undetected Chrome driver."""
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")

    driver = uc.Chrome(
        options=options,
        headless=headless,
        use_subprocess=True,
    )
    return driver


def save_cookies(driver):
    """Save browser cookies for session persistence."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cookies = driver.get_cookies()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f)


def load_cookies(driver):
    """Load saved cookies into the browser."""
    if COOKIES_FILE.exists():
        try:
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except:
                    pass
            return True
        except:
            pass
    return False


def is_captcha_page(driver):
    """Check if we're on a CAPTCHA/WAF challenge page."""
    page_source = driver.page_source.lower()
    indicators = ["incapsula", "hcaptcha", "i am human", "security check", "imperva"]
    return any(ind in page_source for ind in indicators)


def wait_for_captcha_solved(driver, timeout=300):
    """Wait for user to solve CAPTCHA (up to 5 minutes)."""
    print("\n" + "=" * 60)
    print("CAPTCHA DETECTED!")
    print("Please solve the 'I am human' checkbox in the browser window.")
    print("The scraper will continue automatically once solved.")
    print("=" * 60 + "\n")

    start_time = time.time()
    while time.time() - start_time < timeout:
        if not is_captcha_page(driver):
            print("CAPTCHA solved! Continuing...")
            save_cookies(driver)
            return True
        time.sleep(2)

    print("CAPTCHA timeout - please try again")
    return False


def wait_for_page_ready(driver, timeout=30):
    """Wait for the booking page to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        page_source = driver.page_source.lower()

        # Check for CAPTCHA
        if is_captcha_page(driver):
            return "captcha"

        # Check for actual booking content
        if any(x in page_source for x in ["room", "rate", "price", "€", "availability"]):
            time.sleep(2)  # Let page fully render
            return "ready"

        time.sleep(1)

    return "timeout"


def extract_price_from_text(text):
    """Extract numeric price from text containing currency."""
    if not isinstance(text, str):
        text = str(text)

    patterns = [
        r'€\s*([\d.,]+)',
        r'([\d.,]+)\s*€',
        r'EUR\s*([\d.,]+)',
        r'([\d.,]+)\s*EUR',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price_str = match.group(1)
            # Handle European number format
            if ',' in price_str and '.' in price_str:
                if price_str.index('.') < price_str.index(','):
                    price_str = price_str.replace('.', '').replace(',', '.')
                else:
                    price_str = price_str.replace(',', '')
            elif ',' in price_str:
                price_str = price_str.replace(',', '.')

            try:
                return float(price_str)
            except ValueError:
                continue
    return None


def extract_room_rate(driver):
    """Extract the base room rate from the booking page."""
    try:
        time.sleep(5)  # Let page fully render

        all_prices = []
        page_source = driver.page_source

        # Extract prices directly from page source using multiple patterns
        # Handle both € symbol and HTML entity
        patterns = [
            r'€\s*([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',  # €795 or €1,045
            r'&#8364;\s*([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',  # HTML entity
            r'EUR\s*([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            r'"price":\s*"?([\d]+(?:\.\d+)?)"?',
            r'"rate":\s*"?([\d]+(?:\.\d+)?)"?',
            r'"amount":\s*"?([\d]+(?:\.\d+)?)"?',
            r'"totalPrice":\s*"?([\d]+(?:\.\d+)?)"?',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, page_source)
            for match in matches:
                # Clean the match
                price_str = match.replace(',', '')  # Remove thousand separator
                try:
                    price = float(price_str)
                    # Filter for reasonable hotel rates (€100 - €10,000 per night)
                    if 100 < price < 10000:
                        all_prices.append(price)
                except ValueError:
                    continue

        # Also try extracting from visible elements
        selectors = [
            "[class*='price']",
            "[class*='rate']",
            "[class*='total']",
            "[class*='amount']",
        ]

        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    text = el.text
                    if text:
                        price = extract_price_from_text(text)
                        if price and 100 < price < 10000:
                            all_prices.append(price)
            except:
                continue

        if all_prices:
            # Return the minimum price (base room rate)
            return min(all_prices)

        return None

    except Exception as e:
        print(f"  Error extracting rate: {e}")
        return None


def check_availability(driver, checkin_date):
    """Check availability and rate for a specific check-in date."""
    checkout_date = checkin_date + timedelta(days=1)
    url = build_booking_url(checkin_date, checkout_date)

    try:
        driver.get(url)
        time.sleep(5)  # Wait longer for page to render

        status = wait_for_page_ready(driver)

        if status == "captcha":
            if not wait_for_captcha_solved(driver):
                return {"available": None, "rate": None, "message": "CAPTCHA timeout"}
            driver.get(url)
            time.sleep(5)
            status = wait_for_page_ready(driver)

        if status == "timeout":
            return {"available": None, "rate": None, "message": "Page load timeout"}

        # First try to extract rate - this is more reliable than checking text
        rate = extract_room_rate(driver)

        if rate:
            return {"available": True, "rate": rate, "message": "OK"}

        # Only check for "not available" if no rates were found
        page_source = driver.page_source.lower()
        no_avail_indicators = [
            "no rooms available for the selected dates",
            "sorry, we have no availability",
            "sold out for these dates",
            "all rooms are booked",
        ]
        for indicator in no_avail_indicators:
            if indicator in page_source:
                return {"available": False, "rate": None, "message": "Not available"}

        return {"available": None, "rate": None, "message": "Could not extract rate"}

    except Exception as e:
        return {"available": None, "rate": None, "message": str(e)}


def load_existing_data():
    """Load existing rate data from CSV."""
    if not DATA_FILE.exists():
        return {}

    existing = {}
    try:
        with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
            lines = f.readlines()
            data_lines = [line for line in lines if not line.startswith('#')]
            if data_lines:
                reader = csv.DictReader(io.StringIO(''.join(data_lines)))
                for row in reader:
                    key = (row["scrape_date"], row["checkin_date"])
                    existing[key] = row
    except Exception as e:
        print(f"Error loading existing data: {e}")

    return existing


def save_to_csv(data):
    """Save rate data to CSV file."""
    if not data:
        return

    fieldnames = ["scrape_date", "scrape_timestamp", "checkin_date", "checkout_date",
                  "room_type", "rate_eur", "available", "status"]

    existing_data = []
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
                lines = f.readlines()
                data_lines = [line for line in lines if not line.startswith('#')]
                if data_lines:
                    reader = csv.DictReader(io.StringIO(''.join(data_lines)))
                    existing_data = list(reader)
        except:
            pass

    existing_data.extend(data)
    existing_data.sort(key=lambda x: (x.get("scrape_date", ""), x.get("checkin_date", "")))

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        f.write(CSV_HEADER_COMMENT)
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_data)

    print(f"Saved {len(data)} new entries ({len(existing_data)} total)")


def run_scraper(days_ahead=SCRAPE_DAYS_AHEAD, headless=False):
    """Run the rate scraper for all dates."""
    print("=" * 70)
    print("FORESTIS Hotel Rate Scraper")
    print(f"Scraping rates for {days_ahead} days ahead")
    print(f"Mode: {'Headless' if headless else 'Interactive (visible browser)'}")
    print(f"Data file: {DATA_FILE}")
    print("=" * 70)

    if not headless:
        print("\nA browser window will open. If you see a CAPTCHA,")
        print("please solve it and the scraper will continue automatically.\n")

    scrape_date = datetime.now().strftime("%Y-%m-%d")
    scrape_timestamp = datetime.now().isoformat()
    existing = load_existing_data()

    driver = setup_driver(headless=headless)

    # Try to load saved cookies
    driver.get(BASE_URL)
    time.sleep(2)
    load_cookies(driver)

    results = []
    start_date = datetime.now()

    try:
        for day_offset in range(days_ahead):
            checkin = start_date + timedelta(days=day_offset)
            checkin_str = checkin.strftime("%Y-%m-%d")
            checkout_str = (checkin + timedelta(days=1)).strftime("%Y-%m-%d")

            if (scrape_date, checkin_str) in existing:
                print(f"[{day_offset+1}/{days_ahead}] {checkin_str}: Already scraped, skipping")
                continue

            print(f"[{day_offset+1}/{days_ahead}] {checkin_str}...", end=" ", flush=True)

            result = check_availability(driver, checkin)

            entry = {
                "scrape_date": scrape_date,
                "scrape_timestamp": scrape_timestamp,
                "checkin_date": checkin_str,
                "checkout_date": checkout_str,
                "room_type": "Room (35 m²)",
                "rate_eur": result["rate"] if result["rate"] else "",
                "available": "Yes" if result["available"] else ("No" if result["available"] is False else "Unknown"),
                "status": result["message"]
            }

            results.append(entry)

            if result["rate"]:
                print(f"€{result['rate']:.2f}")
            elif result["available"] is False:
                print("Not available")
            else:
                print(result["message"])

            time.sleep(2)  # Be polite

            if len(results) % 10 == 0 and results:
                save_to_csv(results)
                results = []

        if results:
            save_to_csv(results)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        if results:
            save_to_csv(results)
    finally:
        try:
            driver.quit()
        except:
            pass

    print("\nScraping complete!")


if __name__ == "__main__":
    days = SCRAPE_DAYS_AHEAD
    headless = False

    if len(sys.argv) > 1:
        i = 1
        while i < len(sys.argv):
            if sys.argv[i] == "--days" and i + 1 < len(sys.argv):
                days = int(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--headless":
                headless = True
                i += 1
            elif sys.argv[i] in ["--help", "-h"]:
                print(__doc__)
                sys.exit(0)
            else:
                i += 1

    run_scraper(days_ahead=days, headless=headless)
