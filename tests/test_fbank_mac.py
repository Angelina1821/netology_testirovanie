# test_fbank_mac.py

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

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

def get_balance_and_reserved_text(driver):
    cards = driver.find_elements(By.CSS_SELECTOR, ".g-box.g-card")
    for card in cards:
        if "Рубли" in card.text:
            return card.text
    raise Exception("Блок 'Рубли' не найден на странице!")

@pytest.mark.parametrize("balance,reserved,expected_balance,expected_reserved", [
    ("50000", "10000", "50'000 ₽", "10'000 ₽"),
    ("0", "0", "0 ₽", "0 ₽"),
    ("999999", "888888", "999'999 ₽", "888'888 ₽"),
])
def test_dynamic_balance_display(driver, balance, reserved, expected_balance, expected_reserved):
    driver.get(f"{BASE_URL}?balance={balance}&reserved={reserved}")
    text = get_balance_and_reserved_text(driver)
    assert f"На счету: {expected_balance}" in text
    assert f"Резерв: {expected_reserved}" in text

def test_mobile_adaptivity(driver):
    driver.set_window_size(375, 812)  # iPhone X
    driver.get(BASE_URL)
    text = get_balance_and_reserved_text(driver)
    assert "На счету:" in text
    assert "Резерв:" in text

def test_extremely_small_width(driver):
    driver.set_window_size(96, 800)
    driver.get(BASE_URL)
    text = get_balance_and_reserved_text(driver)
    assert "На счету:" in text
    assert "Резерв:" in text

@pytest.mark.parametrize("balance,reserved", [
    pytest.param(
        "abc", "xyz",
        marks=pytest.mark.xfail(reason="Известный баг: приложение не обрабатывает буквенные значения"),
    ),
    pytest.param(
        "!!!@@@###", "***&&&",
        marks=pytest.mark.xfail(reason="Известный баг: приложение не обрабатывает специальные символы"),
    ),
])
def test_invalid_symbols_in_balance(driver, balance, reserved):
    driver.get(f"{BASE_URL}?balance={balance}&reserved={reserved}")
    text = get_balance_and_reserved_text(driver)
    
    if "0 ₽" not in text:
        if "NaN" in text:
            pytest.xfail("Известный баг: приложение возвращает NaN вместо 0")
        else:
            pytest.fail(f"Критическая ошибка: некорректные значения ({balance}, {reserved}) отображаются как {text}")
    
    assert "На счету: 0 ₽" in text, "Неверное отображение баланса"
    assert "Резерв: 0 ₽" in text, "Неверное отображение резерва"

def test_large_numbers_in_balance(driver):
    driver.get(f"{BASE_URL}?balance=12345678901234567890&reserved=98765432109876543210")
    text = get_balance_and_reserved_text(driver)
    assert "На счету:" in text
    assert "Резерв:" in text
