from flask import Flask, request, jsonify
from flask_cors import CORS 
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import time
import requests
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

CORS(app, resources={r"/*/*": {"origins": "*"}}) 

def scrape_company_info(url):
    # Default fallback dictionary
    company_details = {
        "company_name": "Company Name Not Found",
        "linkedin_url": "LinkedIn URL Not Found",
        "company_description": "Description not found.",
        "size": "Company size not found.",
        "location": "Location not found."
    }

    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-dev-shm-usage")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )

        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert.dismiss()
        except:
            pass

        try:
            close_btn = driver.find_element(By.CLASS_NAME, "popup-close")
            close_btn.click()
        except:
            pass

        h1_elements = driver.find_elements(By.TAG_NAME, "h1")
        company_name = h1_elements[0].text.strip() if h1_elements else None
        title = driver.title.strip() if driver.title else None

        og_title = driver.find_elements(By.XPATH, "//meta[@property='og:title']")
        og_title_content = og_title[0].get_attribute("content").strip() if og_title else None

        og_site_name = driver.find_elements(By.XPATH, "//meta[@property='og:site_name']")
        og_site_name_content = og_site_name[0].get_attribute("content").strip() if og_site_name else None

        final_company_name = company_name or title or og_title_content or og_site_name_content or "Company Name Not Found"
        company_details["company_name"] = final_company_name

        og_description = driver.find_elements(By.XPATH, "//meta[@property='og:description']")
        og_description_content = og_description[0].get_attribute("content").strip() if og_description else None

        company_description = og_description_content or extract_about_us_description(driver)
        if company_description and len(company_description) > 150:
            company_description = company_description[:147] + "..."
        company_details["company_description"] = company_description or "Description not found."

        links = driver.find_elements(By.TAG_NAME, "a")
        linked_in_url = None
        for link in links:
            href = link.get_attribute("href")
            if href and "linkedin.com" in href:
                linked_in_url = href
                break
        company_details["linkedin_url"] = linked_in_url or "LinkedIn URL Not Found"

     
        if linked_in_url:
            linkedin_details = scrape_linkedin_details(linked_in_url)
            company_details.update(linkedin_details)

        driver.quit()
    except Exception as e:
        print(f"General scraping error: {e}")

    return company_details

def extract_about_us_description(driver):
    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        about_us_url = None

        for link in links:
            href = link.get_attribute("href")
            text = link.text.lower()
            if href and ("about" in href or "about" in text):
                about_us_url = href
                break

        if about_us_url:
            driver.get(about_us_url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "p"))
            )
            paragraphs = driver.find_elements(By.TAG_NAME, "p")
            description = " ".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 50])
            return description if description else "No description found on About Us page."

        return "About Us page not found."
    except Exception as e:
        print(f"About Us error: {e}")
        return "Error retrieving About Us description."

def scrape_linkedin_details(linked_in_url):
    results = {
        "size": "Company size not found.",
        "location": "Location not found."
    }

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
        }

        response = requests.get(linked_in_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)

        size_pattern = r"Company size\s*(.*?)\s*(?:employees|people)"
        size_match = re.search(size_pattern, text_content, re.IGNORECASE)
        if size_match:
            results["size"] = size_match.group(1).strip()

        location_pattern = r"Location\s*(.*?)\s*(?:Company size|Employees|Industry|Founded)"
        location_match = re.search(location_pattern, text_content, re.IGNORECASE)
        if location_match:
            location = location_match.group(1).strip()
            unwanted_phrases = ["s", "Primary", "Get direction", "Headquarters"]
            for phrase in unwanted_phrases:
                location = location.replace(phrase, "").strip()
            location = re.sub(r"\s{2,}", " ", location).rstrip(",")
            if len(location) > 150:
                location = location[:147] + "..."
            results["location"] = location
    except Exception as e:
        print(f"LinkedIn scrape error: {e}")

    return results

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    url = data.get("url")

    if not url:
        return jsonify({
            "company_name": "Company Name Not Found",
            "linkedin_url": "LinkedIn URL Not Found",
            "company_description": "Description not found.",
            "size": "Company size not found.",
            "location": "Location not found."
        }), 400

    result = scrape_company_info(url)
    return jsonify(result)

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"message": "Hello, World!"})

if __name__ == '__main__':
    print("Server Started")
    app.run(host='0.0.0.0', port=2346, debug=True)
