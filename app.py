from flask import Flask, request, jsonify
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
from webdriver_manager.chrome import ChromeDriverManager  # New import

app = Flask(__name__)

final_company_name = ""

def scrape_company_info(url):
    try:
        print("Inside scrape_company_info function")
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')

        # Use webdriver-manager to automatically get the correct ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        print("Created driver object")

        driver.get(url)

        # Wait for a specific element to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        print("Page loaded successfully")

        # Extract potential company names
        company_name = None
        h1_elements = driver.find_elements(By.TAG_NAME, "h1")
        if h1_elements:
            company_name = h1_elements[0].text.strip()

        title = driver.title.strip() if driver.title else None

        og_title = driver.find_elements(By.XPATH, "//meta[@property='og:title']")
        og_title_content = og_title[0].get_attribute("content").strip() if og_title else None

        og_site_name = driver.find_elements(By.XPATH, "//meta[@property='og:site_name']")
        og_site_name_content = og_site_name[0].get_attribute("content").strip() if og_site_name else None

        # Determine the most appropriate company name
        global final_company_name
        final_company_name = company_name or title or og_title_content or og_site_name_content or "Company Name Not Found"

        print("Extracted company name:", final_company_name)

        # Extract OG description
        og_description = driver.find_elements(By.XPATH, "//meta[@property='og:description']")
        og_description_content = og_description[0].get_attribute("content").strip() if og_description else None

        company_description = og_description_content if og_description_content else extract_about_us_description(driver)

        # Truncate description if needed
        if company_description and len(company_description) > 150:
            company_description = company_description[:147] + "..."

        # Find LinkedIn URL
        linked_in_url = None
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and "linkedin.com" in href:
                linked_in_url = href
                break

        print("Extracted LinkedIn URL:", linked_in_url)

        # Store details in a dictionary
        company_details = {
            "company_name": final_company_name,
            "linkedin_url": linked_in_url or "LinkedIn URL Not Found",
            "company_description": company_description or "Description not found."
        }

        if linked_in_url:
            linkedin_details = scrape_linkedin_details(linked_in_url)
            company_details.update(linkedin_details)

        driver.quit()
        return company_details

    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}

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
            description = " ".join([p.text.strip() for p in paragraphs if p.text.strip() and len(p.text.strip()) > 50])

            return description if description else "No description found on About Us page."

        return "About Us page not found."

    except Exception as e:
        return f"An error occurred while extracting About Us description: {str(e)}"

def scrape_linkedin_details(linked_in_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
        }

        response = requests.get(linked_in_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)

        # Extract company name
        company_name_pattern = r"^(.*?)\s*\|"
        company_name_match = re.search(company_name_pattern, text_content)
        company_name = company_name_match.group(1).strip() if company_name_match else final_company_name

        # Extract company size
        size_pattern = r"Company size\s*(.*?)\s*(?:employees|people)"
        size_match = re.search(size_pattern, text_content, re.IGNORECASE)
        company_size = size_match.group(1).strip() if size_match else "Company size not found."

        # Extract location
        location_pattern = r"Location\s*(.*?)\s*(?:Company size|Employees|Industry|Founded)"
        location_match = re.search(location_pattern, text_content, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else "Location not found."

        # Cleanup location
        unwanted_phrases = ["s", "Primary", "Get direction", "Headquarters"]
        for phrase in unwanted_phrases:
            location = location.replace(phrase, "").strip()

        location = re.sub(r"\s{2,}", " ", location)
        location = location.rstrip(",")

        if len(location) > 150:
            location = location[:147] + "..."

        return {
            "company_name": company_name,
            "size": company_size,
            "location": location
        }

    except Exception as e:
        print(f"An error occurred while scraping LinkedIn: {e}")
        return {"error": str(e)}

@app.route('/scrape', methods=['POST'])
def scrape():
    print("Requested")
    data = request.get_json()
    url = data.get("url")

    if not url:
        return jsonify({"error": "URL is required"}), 400

    result = scrape_company_info(url)
    return jsonify(result)

@app.route('/test', methods=['GET'])
def test():
    print("Requested")
    return jsonify({"message": "Hello, World!"})

if __name__ == '__main__':
    print("Server Started")
    app.run(host='0.0.0.0', port=5001, debug=True)
