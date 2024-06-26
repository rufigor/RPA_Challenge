import json
import logging
import os
import re
import time
import urllib.request
from datetime import datetime

from dateutil.relativedelta import relativedelta
from robocorp.tasks import task
from RPA.Browser.Selenium import Selenium
from RPA.Excel.Files import Files
from RPA.Robocorp.WorkItems import WorkItems


def main():
    scraper = NewsScraper()

    logging.info("Starting main function")

    try:
        search_phrase, news_category, months = scraper.load_work_item()
    except:
        search_phrase, news_category, months = 'Nasdaq', "Business", 3

    scraper.open_browser_and_search_news(search_phrase)
    news_data = scraper.extract_news_data(search_phrase, news_category, months)
    scraper.save_news_data_to_excel(news_data)
    scraper.browser.close_browser()


class NewsScraper:
    """
    A class to scrape news articles from a website and save the data to an Excel file.
    """

    def __init__(self):
        """
        Initialize the NewsScraper with required libraries and file paths.
        """
        logging.info("Initializing NewsScraper")
        self.browser = Selenium()
        self.excel = Files()
        self.work_items = WorkItems()
        self.input_file_path = 'input_work_item.json'
        self.output_file_path = 'output_work_item.json'
        self.output_img_path = './output/'

    def load_work_item(self):
        """
        Load the input work item containing the search parameters.

        Returns:
            tuple: Contains the search phrase, news category, and number of months.
        """
        logging.info("Loading work item")
        input_data = self.work_items.get_input_work_item()
        logging.info("Work Items Loaded Successfully")

        try:
            # If running on Control room Cloud
            search_phrase = input_data.payload['payload']["search_phrase"]
            months = input_data.payload['payload']["months"]
            news_category = input_data.payload['payload']["news_category"]
        except KeyError:
            # If running on Local Environment
            search_phrase = input_data.payload["search_phrase"]
            months = input_data.payload["months"]
            news_category = input_data.payload["news_category"]

        logging.info(
            f"Loaded search phrase: {search_phrase}, news category: {news_category}, "
            f"months: {months}"
        )
        return search_phrase, news_category, months

    def download_image(self, url, filename):
        """
        Download an image from a given URL.

        Args:
            url (str): The URL of the image to download.
            filename (str): The local filename to save the image as.
        """
        try:
            logging.info(f"Downloading image from {url}")
            urllib.request.urlretrieve(url, filename)
        except Exception as e:
            logging.error(f"An error occurred while downloading the image: {e}")

    def search_phrase_count(self, title, description, phrase):
        """
        Count the occurrences of a search phrase in the title and description.

        Args:
            title (str): The title of the news article.
            description (str): The description of the news article.
            phrase (str): The search phrase to count.

        Returns:
            int: The total count of the search phrase in the title and description.
        """
        count_title = title.lower().count(phrase.lower())
        count_description = description.lower().count(phrase.lower())
        logging.info(
            f"Found {count_title} occurrences in title and "
            f"{count_description} in description for phrase '{phrase}'"
        )
        return count_title + count_description

    def contains_money(self, text):
        """
        Check if the text contains any monetary values.

        Args:
            text (str): The text to check for monetary values.

        Returns:
            bool: True if the text contains monetary values, False otherwise.
        """
        patterns = [
            r'\$\d+(?:,\d{3})*(?:\.\d{2})?',
            r'\d+\s+dollars',
            r'\d+\s+USD'
        ]
        for pattern in patterns:
            if re.search(pattern, text):
                logging.info(f"Text contains monetary value: {text}")
                return True
        return False

    def open_browser_and_search_news(self, search_phrase):
        """
        Open the browser, navigate to the news website, and perform a search.

        Args:
            search_phrase (str): The phrase to search for.
        """
        logging.info(f"Opening browser and searching for phrase: {search_phrase}")
        self.browser.open_available_browser("https://www.latimes.com/")
        self.browser.maximize_browser_window()
        self.browser.wait_until_element_is_visible(
            "xpath://button[@data-element='search-button']", timeout=40)
        self.browser.click_element_when_visible("xpath://button[@data-element='search-button']")
        self.browser.input_text_when_element_is_visible(
            'xpath://input[@data-element="search-form-input"]', search_phrase)
        self.browser.click_element_when_visible('xpath://button[@data-element="search-submit-button"]')

    def should_process_article(self, date, months):
        """
        Determine if an article should be processed based on its date.

        Args:
            date (str): The date of the news article.
            months (int): The number of months to look back.

        Returns:
            str: "Break" if the article should not be processed, "Continue" otherwise.
        """
        try:
            date_formats = [
                "%b %d, %Y",  # Apr 22, 2024
                "%b. %d, %Y",  # Apr. 22, 2024
                "%B %d, %Y",  # April 22, 2024
                "%B. %d, %Y",  # April. 22, 2024
                "%d %B %Y",  # 22 April 2024
                "%d %b %Y",  # 22 Apr 2024
                "%d %b. %Y",  # 22 Apr. 2024
                "%Y-%m-%d",  # 2024-04-22
                "%m/%d/%Y",  # 04/22/2024
                "%d/%m/%Y",  # 22/04/2024
                "%m-%d-%Y",  # 04-22-2024
                "%d-%m-%Y"  # 22-04-2024
            ]

            article_date = None
            for fmt in date_formats:
                try:
                    article_date = datetime.strptime(date, fmt)
                    break
                except ValueError:
                    continue

            if article_date is None:
                logging.error(f"Error processing article date: {date}")

            # Calculate the start of the period to include articles
            if months > 0:
                cutoff_date = (datetime.now() - relativedelta(months=months - 1)).replace(day=1)
            else:
                cutoff_date = datetime.now().replace(day=1)

            if article_date < cutoff_date:
                logging.info(f"Article date {article_date} is before cutoff date {cutoff_date}, skipping article")
                return "Break"
        except Exception as e:
            logging.error(f"Error processing article date: {e}")

        return "Continue"

    def extract_page_data(self, articles, search_phrase, news_data, months):
        """
        Extract data from the list of articles.

        Args:
            articles (list): List of article elements to extract data from.
            search_phrase (str): The phrase to search for.
            news_data (list): List to store the extracted news data.
            months (int): The number of months to look back for news articles.
        """
        for index, article in enumerate(articles):
            article_xpath = 'xpath:(//ul[@class="search-results-module-results-menu"]//li'
            self.browser.wait_until_element_is_enabled(
                '{}//h3)[{}]'.format(article_xpath, index + 1), timeout=20)
            time.sleep(2)
            title = self.browser.get_text(
                '{}//h3)[{}]'.format(article_xpath, index + 1))
            logging.info(f"Extracting article {index + 1}: {title}")
            date = self.browser.get_text(
                '{}//p[@class="promo-timestamp"])[{}]'.format(article_xpath, index + 1))

            # Check date range
            if self.should_process_article(date, months) == "Break":
                return "Break"

            description = self.browser.get_text(
                '{}//p[@class="promo-description"])[{}]'.format(article_xpath, index + 1))

            try:
                image_url = str(self.browser.get_element_attribute(
                    '{}//source[@type="image/webp"])[{}]'.format(article_xpath, index + 1), "srcset")).split(',')[
                    0].split(' ')[0]

                # Download image
                img_name = image_url.split('%')[-1]
                if '.jpg' not in img_name:
                    img_name = img_name + '.jpg'
                image_filename = self.output_img_path + f"{img_name}"

                self.download_image(image_url, image_filename)
            except Exception as e:
                logging.error(f"Error extracting image: {e}")
                image_filename = "No image"

            # Analyze text
            search_count = self.search_phrase_count(title, description, search_phrase)
            contains_money_flag = self.contains_money(description)

            news_entry = [title, date, description, image_filename, search_count, contains_money_flag]
            news_data.append(news_entry)

    def run_keyword_and_return_status(self, keyword, *args):
        """
        Run a keyword function and return its status.

        Args:
            keyword (function): The keyword function to run.
            *args: Arguments to pass to the keyword function.

        Returns:
            tuple: (status, result) where status is a boolean indicating success,
                   and result is the result of the keyword function.
        """
        try:
            result = keyword(*args)
            return True, result
        except Exception as e:
            logging.error(f"Keyword failed: {e}")
            return False, None

    def select_news_category(self, news_category):
        """
        Select the news category on the website if specified.

        Args:
            news_category (str): The category of news to filter by.
        """
        if news_category is not None:
            logging.info(f"Selecting news category: {news_category}")
            self.browser.click_element_when_visible('//span[@class="see-all-text"]')
            try:
                self.browser.click_button_when_visible(
                    '(//ul[@class="search-filter-menu"])[1]//span[contains(translate(text(),'
                    ' "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{}")]/../input'.format(
                        news_category.lower()))
            except Exception:
                logging.error("The Search Phrase category not found on page")

    def extract_news_data(self, search_phrase=None, news_category=None, months=0):
        """
        Extract news data from the website based on the search phrase and category.

        Args:
            search_phrase (str): The phrase to search for.
            news_category (str): The category of news to filter by.
            months (int): The number of months to look back for news articles.

        Returns:
            list: A list of extracted news data entries.
        """
        logging.info(f"Extracting news data for phrase: {search_phrase}, category: {news_category}, months: {months}")
        self.browser.wait_until_element_is_visible(
            'xpath:(//ul[@class="search-results-module-results-menu"]//li)[1]', timeout=20)
        # Selecting the latest News
        self.browser.select_from_list_by_label('xpath://select[@class="select-input"]', 'Newest')
        self.run_keyword_and_return_status(self.select_news_category, news_category)
        time.sleep(2)
        news_data = []
        pages = None
        try:
            self.browser.wait_until_element_is_visible(
                'xpath://div[@class="search-results-module-page-counts"]',
                timeout=20
            )
            page_num = int(str(self.browser.get_text(
                'xpath://div[@class="search-results-module-page-counts"]').split(' ')[-1]).replace(',', ''))
        except:
            logging.error('Invalid Page number')

        for i in range(1, page_num):
            self.browser.wait_until_element_is_visible(
                'xpath:(//ul[@class="search-results-module-results-menu"]//li)[1]', timeout=20)
            articles = self.browser.get_webelements('xpath://ul[@class="search-results-module-results-menu"]//li')

            status, result = self.run_keyword_and_return_status(
                self.extract_page_data, articles, search_phrase, news_data, months)
            if result == 'Break':
                break
            # Clicking on Next page
            next_page_link = self.browser.get_element_attribute(
                'xpath://div[@class="search-results-module-next-page"]/a', 'href')
            self.browser.go_to(next_page_link)

        return news_data

    def save_news_data_to_excel(self, news_data):
        """
        Save the extracted news data to an Excel file.

        Args:
            news_data (list): The list of news data entries to save.
        """
        logging.info("Saving news data to Excel")
        output_file = os.path.join("output", "news_data.xlsx")
        self.excel.create_workbook(output_file)
        header = ["Title", "Date", "Description", "Image filename", "Search count", "Contains money flag"]
        self.excel.append_rows_to_worksheet([header], header=False)

        for data in news_data:
            self.excel.append_rows_to_worksheet([data], header=False)

        self.excel.save_workbook()
        self.excel.close_workbook()

    def load_payload_from_json(self, file_path):
        """
        Load payload data from a JSON file.

        Args:
            file_path (str): The path to the JSON file.

        Returns:
            dict: The payload data.
        """
        logging.info(f"Loading payload from {file_path}")
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data["payload"]


if __name__ == "__main__":
    main()
