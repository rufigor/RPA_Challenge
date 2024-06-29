# Import the required libraries and classes
import logging
from classes import NewsScraper
from config import INPUT_FILE_PATH
from folders_and_files import read_json_file


def main():

    logging.info("Starting main function")

    scraper = NewsScraper()

    try:
        search_phrase, news_category, months = scraper.load_work_item()
    except:
        dict_parameters = read_json_file(INPUT_FILE_PATH)
        search_phrase = dict_parameters.get('search_phrase')
        news_category = dict_parameters.get('news_category')
        months = dict_parameters.get('months')

    scraper.open_browser_and_search_news(search_phrase)
    news_data = scraper.extract_news_data(search_phrase, news_category, months)
    scraper.save_news_data_to_excel(news_data)
    scraper.browser.close_browser()

    logging.info("Ending main function")


if __name__ == "__main__":
    main()
