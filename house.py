from time import sleep

import requests
from bs4 import BeautifulSoup
from redfin import Redfin
from retry import retry
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options

BASE_URL = 'https://www.seetheproperty.com/story/39{}'

REDFIN_CLIENT = Redfin()


def address_is_listed(address):
    response = REDFIN_CLIENT.search(address)

    url = response['payload']['exactMatch']['url']
    initial_info = REDFIN_CLIENT.initial_info(url)
    property_id = initial_info['payload']['propertyId']
    try:
        listing_id = initial_info['payload']['listingId']
    # Have to assume that a lack of listing ID means it's unlisted.
    except KeyError:
        return False
    avm_details = REDFIN_CLIENT.avm_details(property_id, listing_id)
    return avm_details['payload']['isActivish']


def verify_location(url, location):
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    title = soup.find_all("title")

    is_in_austin = False
    address = None
    if title:
        title = title[0].text
        match = (location in title)

        if match:
            is_in_austin = True
            address_pieces = title.split(',')
            address = ','.join(address_pieces[:3])

    return is_in_austin, address


def init_driver(url):
    opts = Options()
    opts.add_argument("--headless")
    driver = webdriver.Chrome('./chromedriver', options=opts)

    # Verify Type of House
    driver.get(url)
    sleep(1)
    return driver


def _determine_size(driver):

    @retry(tries=2, delay=1)
    def _inner():
        lot_size = driver.find_element_by_xpath(
            "//span[text()='lot size']/preceding-sibling::h3"
        ).text
    # Has enough space
    try:
        lot_size = _inner()
        # Account for folks putting "acres" at the end of the size.
        lot_size = lot_size.split(' ')[0]
        lot_size = float(lot_size)
        is_enough_outdoor_space = lot_size > 0.13
    except NoSuchElementException:
        is_enough_outdoor_space = True

    try:
        inside_space = driver.find_element_by_xpath(
            "//span[text()='square feet']/preceding-sibling::h3").text
        # Account for folks putting "acres" at the end of the size.
        inside_space = float(inside_space.replace(',', ''))
        is_enough_indoor_space = inside_space > 1500
    except NoSuchElementException:
        is_enough_indoor_space = True

    return is_enough_outdoor_space and is_enough_indoor_space


def _determine_type(driver):
    @retry(tries=2, delay=1)
    def _inner():
        house_type = driver.find_element_by_xpath(
            "//span[text()='Property Type']/following-sibling::span").text
        return house_type == 'Single Family'

    try:
        is_single_family = _inner()
    except NoSuchElementException:
        is_single_family = True

    return is_single_family


def _determine_if_for_sale(driver):
    @retry(tries=2, delay=1)
    def _inner():
        for_sale = driver.find_element_by_xpath(
            "//span[text()='Listing Type']/following-sibling::span"
        ).text
        return for_sale == 'For Sale'

    try:
        is_for_sale = _inner()
    except NoSuchElementException:
        is_for_sale = True

    return is_for_sale


def _determine_price(driver, ideal_price):

    @retry(tries=2, delay=1)
    def _inner():
        price = driver.find_element_by_xpath(
            "//span[text()='asking']/preceding-sibling::h3").text
        price = float(price.replace(',', '').replace('$', '').replace(' ', ''))
        return price < ideal_price

    # Check price
    try:
        is_in_budget = _inner()
    except NoSuchElementException:
        is_in_budget = True
    return is_in_budget

def _determine_beds(driver, ideal_beds):
    @retry(tries=2, delay=1)
    def _inner():
        beds = driver.find_element_by_xpath(
            "//span[text()='bed']/preceding-sibling::h3").text
        beds = int(beds)
        return beds > ideal_beds

    # Has enough bedrooms
    try:
        has_enough_beds = _inner()
    except NoSuchElementException:
        has_enough_beds = True
    return has_enough_beds


def determine_if_suitable(url, beds, price):

    driver = init_driver(url)

    # If the element doesn't appear, we should assume broadly.
    is_single_family = _determine_type(driver)
    is_for_sale = _determine_if_for_sale(driver)
    is_in_budget = _determine_price(driver, price)
    has_enough_beds = _determine_beds(driver, beds)
    is_enough_space = _determine_size(driver)

    if is_single_family and is_for_sale and is_in_budget and has_enough_beds and is_enough_space:
        return True


def run_house_search(beds, loc, price, id_start, increments):
    potential = []
    issue_addresses = []
    for i in range(id_start, id_start + increments):
        url = BASE_URL.format(i)
        # if i % 50 == 0:
        #     print(f'Currently looking at {url}')

        try:
            is_in_austin, address = verify_location(url, loc)

            if 'Sample Tour' in address:
                # Effectively ignore this one, it hasn't been populated.
                continue

            if is_in_austin:
                is_suitable = determine_if_suitable(url, beds, price)
                if is_suitable:
                    is_listed = address_is_listed(address)
                    # We want to find the ones currently off-market.
                    if not is_listed:
                        print(f'found a match at {url}!')
                        potential.append(url)
        except Exception:
            issue_addresses.append((address, url))

    print(f'Potentials! {potential}')
    print(f'Broken Shit! {issue_addresses}')

