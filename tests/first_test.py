# pytest tests/first_test.py -s

import pytest
import time
from selenium.webdriver.common.alert import Alert
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoAlertPresentException, NoSuchElementException

BASE_URL = "http://localhost:8000/"

@pytest.fixture
def driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.implicitly_wait(5)
    yield driver
    driver.quit()

def open_rub_balance_card(driver):
    driver.get(driver.current_url)
    cards = driver.find_elements(By.CLASS_NAME, "g-card_clickable")
    for card in cards:
        if card.find_element(By.TAG_NAME, "h2").text == "Рубли":
            card.click()
            return
    raise AssertionError("Карта 'Рубли' не найдена")

def input_card_number(driver, number):
    el = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="0000 0000 0000 0000"]')
    el.clear()
    el.send_keys(number)

def input_amount(driver, amount):
    el = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="1000"]')
    el.clear()
    el.send_keys(amount)

def is_transfer_button_visible(driver):
    try:
        btn = driver.find_element(By.CLASS_NAME, "g-button__text")
        return btn.is_displayed()
    except NoSuchElementException:
        return False

#Test #006: Ввод пустой суммы
@pytest.mark.xfail(reason="Известный баг: поле суммы пустое не блокирует кнопку", strict=False)
def test_empty_sum_shows_button_and_allows_transfer(driver):
    driver.get(f"{BASE_URL}?balance=30000&reserved=20001")
    open_rub_balance_card(driver)
    input_card_number(driver, "1234567890123456")
    input_amount(driver, "")
    # Шаг 4: кнопка не должна быть видна
    assert not is_transfer_button_visible(driver)
    # Шаг 5: попытка перевода
    if is_transfer_button_visible(driver):
        driver.find_element(By.CLASS_NAME, "g-button__text").click()
        try:
            alert = Alert(driver)
            text = alert.text.lower()
            alert.accept()
            pytest.fail("Баг: перевод пустой суммы возможен")
        except NoAlertPresentException:
            pass

#Test #007: Символы и пробел в номере карты
@pytest.mark.parametrize("card_input", ['1234abcd"!№;%:?*абв', " "])
@pytest.mark.xfail(reason="Известный баг: поле карты принимает недопустимые символы", strict=False)
def test_card_field_invalid_symbols_allows_button(card_input, driver):
    driver.get(f"{BASE_URL}?balance=30000&reserved=20001")
    open_rub_balance_card(driver)
    input_card_number(driver, card_input)
    assert not is_transfer_button_visible(driver)

#Test #008: Дробная сумма
@pytest.mark.parametrize("amount_input", ["99,9", "99.9"])
@pytest.mark.xfail(reason="Известный баг: поле суммы допускает дробную часть", strict=False)
def test_fractional_amount_allows_button(amount_input, driver):
    driver.get(f"{BASE_URL}?balance=1000")
    open_rub_balance_card(driver)
    input_card_number(driver, "1234567890123456")
    input_amount(driver, amount_input)
    assert not is_transfer_button_visible(driver)

# Test #009: Большой баланс отображается некорректно
@pytest.mark.parametrize("balance", [
    ("100000000000000000000"),
    ("1000000000000000000000")  # На этом кейсе баг
])
@pytest.mark.xfail(reason="Известный баг: при очень большом числе отображается e+…", strict=False)
def test_large_balance_and_transfer(driver, balance):
    driver.get(f"{BASE_URL}?balance={balance}")
    text = driver.find_element(By.CSS_SELECTOR, ".g-box.g-card").text
    assert "₽" in text and "e+" not in text
    # затем проверяем перевод
    open_rub_balance_card(driver)
    input_card_number(driver, "1234567890123456")
    input_amount(driver, "100000000000000000000")
    assert is_transfer_button_visible(driver)

# Test #010: Отрицательная сумма
@pytest.mark.xfail(reason="Известный баг: поле суммы допускает минус и перевод", strict=False)
def test_negative_amount_allowed_and_transferable(driver):
    driver.get(f"{BASE_URL}?balance=1000")
    open_rub_balance_card(driver)
    input_card_number(driver, "1234567890123456")
    input_amount(driver, "-100")
    assert not is_transfer_button_visible(driver)
