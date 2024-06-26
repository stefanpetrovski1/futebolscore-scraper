from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selectors.current_form_averages_selectors import *
from selectors.general_info_selectors import *
from selectors.next_game_days_until_location_selectors import *
from selectors.last_game_days_since_location_selectors import *
import time
import random
import pandas as pd
import argparse
import os
import concurrent.futures
import threading
from utils.functions import calculate_days_difference, get_team_next_game_location, \
    get_team_last_game_location, get_random_agent, click_element, find_element_text, \
    find_element_by_css
from utils.constants import agents, DAILY_MATCHES_IDS_URL
import requests
import re
from datetime import date


def config_driver() -> webdriver.Chrome:
    chrome_options = webdriver.ChromeOptions()
    agent = get_random_agent(agents)
    chrome_options.add_argument(f"--user-agent={agent}")
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-logging"])
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('log-level=3')
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)

    return driver


def get_match_url(id: int) -> str:
    return f"https://www.futebolscore.com/jogos/computador-{id}"


def get_data(url: str, is_match_todays: bool) -> dict:
    driver = config_driver()
    driver.get(url)

    time.sleep(0.25)

    data = {}

    general_info = get_match_general_info(driver, is_match_todays)

    if general_info is None:
        raise Exception(
            "Current match is from extra low league.")

    last_game_info = get_last_game_info(
        driver, general_info['first_team_name'], general_info['second_team_name'],
        general_info['date_time'])
    next_game_info = get_next_game_info(driver)
    current_form_averages = get_current_form_averages(driver)

    if last_game_info is None or next_game_info is None or current_form_averages is None:
        raise Exception(
            "Current match is from extra low league.")

    data.update(general_info)
    data.update(last_game_info)
    data.update(next_game_info)
    data.update(current_form_averages)

    print(len(data.keys()))

    return data


def get_match_general_info(driver: webdriver.Chrome, is_match_todays: bool) -> dict | None:  # noqa
    general_info = {}

    try:
        general_info['first_team_name'] = find_element_text(
            driver, first_team_name_selector)
        general_info['second_team_name'] = find_element_text(
            driver, second_team_name_selector)

        general_info['league_name'] = find_element_text(
            driver, league_name_selector)
        general_info['date_time'] = find_element_text(
            driver, date_time_selector)

        if is_match_todays:
            general_info['first_team_goals_final_score'] = None
            general_info['second_team_goals_final_score'] = None
            general_info['game_state'] = None
        else:
            general_info['first_team_goals_final_score'] = find_element_text(
                driver, first_team_goals_scored_selector)
            general_info['second_team_goals_final_score'] = find_element_text(
                driver, second_team_goals_scored_selector)
            general_info['game_state'] = find_element_text(
                driver, game_state_selector)

        return general_info
    except Exception as e:
        print(f"Error locating general info section. Returned None.\n{e}")
        return None


def get_last_game_info(driver: webdriver.Chrome, first_team_name: str, second_team_name: str, date_time: str) -> dict | None:  # noqa
    last_game_info = {}
    try:
        first_team_last_game_date = find_element_text(
            driver, first_team_last_game_date_selector)
        second_team_last_game_date = find_element_text(
            driver, second_team_last_game_date_selector)

        last_game_info['first_team_days_since_last_game'] = calculate_days_difference(
            first_team_last_game_date, date_time)
        last_game_info['second_team_days_since_last_game'] = calculate_days_difference(
            second_team_last_game_date, date_time)

        last_game_info['first_team_last_game_location'] = get_team_last_game_location(
            find_element_by_css(
                driver, was_first_team_last_game_at_home_selector),
            first_team_name)
        last_game_info['second_team_last_game_location'] = get_team_last_game_location(
            find_element_by_css(
                driver, was_second_team_last_game_at_home_selector),
            second_team_name)

        return last_game_info
    except NoSuchElementException as e:
        print(f"Error locating last-game info section:\n{e}\nReturned None.")
        return None


def get_next_game_info(driver: webdriver.Chrome) -> dict | None:
    next_game_info = {}

    try:
        next_game_info['first_team_days_until_next_game'] = find_element_text(
            driver, first_team_days_until_next_game_selector)
        next_game_info['second_team_days_until_next_game'] = find_element_text(
            driver, second_team_days_until_next_game_selector)

        next_game_info['first_team_next_game_location'] = get_team_next_game_location(
            find_element_by_css(driver, is_first_team_next_game_at_home_selector))
        next_game_info['second_team_next_game_location'] = get_team_next_game_location(
            find_element_by_css(driver, is_second_team_next_game_at_home_selector))

        return next_game_info

    except NoSuchElementException as e:
        print(f"Error locating next-game info section:\n{e}\nReturned None.")
        return None


def get_current_form_averages(driver: webdriver.Chrome) -> dict | None:
    current_form_averages = {}

    try:
        # All leagues, home+away

        current_form_averages['first_team_total_scoring_average'] = float(
            find_element_text(driver, first_team_scoring_average_selector))
        current_form_averages['second_team_total_scoring_average'] = float(
            find_element_text(driver, second_team_scoring_average_selector))
        current_form_averages['first_team_total_conceding_average'] = float(
            find_element_text(driver, first_team_conceding_average_selector))
        current_form_averages['second_team_total_conceding_average'] = float(
            find_element_text(driver, second_team_conceding_average_selector))

        # Same league, home+away

        click_element(driver, same_league_button_selector)

        current_form_averages['first_team_same_league_scoring_average'] = float(
            find_element_text(driver, first_team_scoring_average_selector))
        current_form_averages['second_team_same_league_scoring_average'] = float(
            find_element_text(driver, second_team_scoring_average_selector))
        current_form_averages['first_team_same_league_conceding_average'] = float(
            find_element_text(driver, first_team_conceding_average_selector))
        current_form_averages['second_team_same_league_conceding_average'] = float(
            find_element_text(driver, second_team_conceding_average_selector))

        # All leagues, grouped by home/away

        click_element(driver, same_league_button_selector)
        click_element(driver, correct_home_away_button_selector)

        current_form_averages['first_team_at_home_scoring_average'] = float(
            find_element_text(driver, first_team_scoring_average_selector))
        current_form_averages['second_team_away_scoring_average'] = float(
            find_element_text(driver, second_team_scoring_average_selector))
        current_form_averages['first_team_at_home_conceding_average'] = float(
            find_element_text(driver, first_team_conceding_average_selector))
        current_form_averages['second_team_away_conceding_average'] = float(
            find_element_text(driver, second_team_conceding_average_selector))

        # Same league, grouped by home/away

        click_element(driver, same_league_button_selector)

        current_form_averages['first_team_same_league_at_home_scoring_average'] = float(
            find_element_text(driver, first_team_scoring_average_selector))
        current_form_averages['second_team_same_league_away_scoring_average'] = float(
            find_element_text(driver, second_team_scoring_average_selector))
        current_form_averages['first_team_same_league_at_home_conceding_average'] = float(
            find_element_text(driver, first_team_conceding_average_selector))
        current_form_averages['second_team_same_league_away_conceding_average'] = float(
            find_element_text(driver, second_team_conceding_average_selector))

        return current_form_averages
    except NoSuchElementException as e:
        print(f"Error locating current form section:\n{e}\nReturned None")
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape football statistics")
    parser.add_argument("-s", type=int,
                        help="Lowest match id to be scraped")
    parser.add_argument("-e", type=int,
                        help="Highest match id to be scraped")

    parser.add_argument("-f", default="data.csv", help="Output file path")
    parser.add_argument("-t", type=int, default=4,
                        help="How many threads to use")

    parser.add_argument('-d', action='store_true',
                        help='Scrape only todays matches')

    args = parser.parse_args()

    return args


def get_today_date_string() -> str:
    today = date.today()
    day = today.day
    month = today.month
    year = today.year

    return f'{year}-{month}-{day}'


def get_daily_matches_ids() -> list[str]:
    user_agent = get_random_agent(agents)
    headers = {'User-Agent': user_agent}
    today_date = get_today_date_string()
    url = f"{DAILY_MATCHES_IDS_URL}&date={today_date}"
    resp = requests.get(url=url, headers=headers)

    if resp.status_code != 200:
        raise Exception('Error fetching the daily matches API')

    matches: list[str] = re.findall(r'A\[[0-9]{1,4}\]=\[[0-9]{7},', resp.text)

    parsed = [m.split('=[')[1][:-1] for m in matches]

    return parsed


def fetch_and_save_data(id: int, file_path: str, lock: threading.Lock,
                        is_match_todays: bool) -> None:
    try:
        delay = random.uniform(2, 7)
        time.sleep(delay)

        print(f"Fetching url with id={id} ...")

        data: dict = get_data(
            get_match_url(id), is_match_todays)
        data.update({"id": id})

        with lock:
            if os.path.exists(file_path):
                old_df = pd.read_csv(file_path)
                new_df = pd.DataFrame([data])
                updated_df = pd.concat([old_df, new_df], ignore_index=True)
                updated_df.to_csv(file_path, index=False)
            else:
                new_df = pd.DataFrame([data])
                new_df.to_csv(file_path, index=False)

        print(f"Page with id={id} success !")
    except Exception as e:
        print(f"Error getting data from match {id},\n{e}")


def main() -> None:
    start = time.time()
    args = parse_args()

    start_id: int | None = args.s
    end_id: int | None = args.e
    file_path: str = args.f
    num_threads: int = args.t
    is_daily: bool = args.d

    lock = threading.Lock()

    if is_daily and start_id is None and end_id is None:
        try:
            ids = get_daily_matches_ids()
        except Exception as e:
            print(e)
    elif start_id and end_id and start_id < end_id and is_daily is False:
        ids = range(start_id, end_id + 1)
    else:
        print('Error entering the arguments. Try again!')
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        executor.map(lambda id: fetch_and_save_data(
            id, file_path, lock, is_daily), ids)

    print(
        f"Finished in: {time.time() - start} seconds / {(time.time()-start)/60} minutes")


if __name__ == "__main__":
    main()
