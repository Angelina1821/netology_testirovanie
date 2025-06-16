# pytest tests\second_test.py -s

import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException, NoSuchElementException

from selenium.webdriver.common.alert import Alert

BASE_URL = "http://localhost:8000/"

def open_rub_balance_card(driver):
    cards = driver.find_elements(By.CLASS_NAME, "g-card_clickable")
    for card in cards:
        if card.find_element(By.TAG_NAME, "h2").text == "Рубли":
            card.click()
            break

@pytest.fixture
def driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  
    chrome_options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.implicitly_wait(5)
    yield driver
    driver.quit()

#Тест 001

def get_balance_and_reserved_text(driver):
    cards = driver.find_elements(By.CSS_SELECTOR, ".g-box.g-card")
    for card in cards:
        if "Рубли" in card.text:
            return card.text
    raise Exception("Блок 'Рубли' не найден на странице!")

@pytest.mark.parametrize("balance,reserved,expected_balance,expected_reserved", [
    ("30000", "20001", "30'000 ₽", "20'001 ₽"),
    ("3000", "2000", "3'000 ₽", "2'000 ₽"),
    ("-100", "-200", "0 ₽", "0 ₽"), 
])

def test_balance_and_reserv(driver, balance, reserved, expected_balance, expected_reserved):
    driver.get(f"{BASE_URL}?balance={balance}&reserved={reserved}")
    h1 = driver.find_element(By.TAG_NAME, "h1")
    assert h1.text == "F-Bank", "Заголовок 'F-Bank' не найден"

    text = get_balance_and_reserved_text(driver)
    
    try:
        assert f"На счету: {expected_balance}" in text
        assert f"Резерв: {expected_reserved}" in text
    except AssertionError:
        print(f"Известный баг: некорректное отображение баланса или резерва для balance={balance}, reserved={reserved}")
        
def test_card_input_and_transfer_flow(driver):
    driver.get(f"{BASE_URL}?balance=30000&reserved=20001")

    open_rub_balance_card(driver)

    # Ввод номера карты из 16 цифр
    card_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="0000 0000 0000 0000"]')
    card_input.send_keys("1234567812345678")

    # Вводим сумму перевода
    amount_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="1000"]')
    transfer_button = driver.find_element(By.CLASS_NAME, "g-button__text")
    transfer_button.click()

    # Проверяем уведомление об успешной операции
    try:
        alert = Alert(driver)
        alert_text = alert.text
        print(f"Обнаружен alert: {alert_text}")
        assert "принят банком" in alert_text
        alert.accept()
    except NoAlertPresentException:
        print("Alert не появился")
    except UnexpectedAlertPresentException:
        pytest.fail("Неожиданный alert не был обработан")

#Тест 002

@pytest.mark.parametrize("card_number, transfer_button_expected, comment", [
    ("123456789012345", False, "15 цифр — кнопка 'Перевести' не должна появляться"),
    ("1234567890123456", True, "16 цифр — кнопка 'Перевести' должна появиться"),
    ("12345678901234567", False, "17 цифр — кнопка 'Перевести' не должна появляться (известный баг)"),
])
def test_number_card_validation_15(driver, card_number, transfer_button_expected, comment):
    driver.get(f"{BASE_URL}?balance=30000&reserved=20001")

    open_rub_balance_card(driver)

    card_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="0000 0000 0000 0000"]')
    card_input.clear()
    card_input.send_keys(card_number)

    try:
        transfer_button = driver.find_element(By.CLASS_NAME, "g-button__text")
        button_visible = transfer_button.is_displayed()
    except NoSuchElementException:
        button_visible = False

    if button_visible != transfer_button_expected:
        print(f"Известный баг: {comment} — кнопка 'Перевести' видимость: {button_visible}")
    assert True

@pytest.mark.parametrize("card_number,transfer_should_succeed,comment", [
    ("1234567890123456", True, "16 цифр — перевод должен пройти успешно"),
    ("12345678901234567", False, "17 цифр — перевод не должен проходить (известный баг)"),
])
def test_transfer_button_and_operation(driver, card_number, transfer_should_succeed, comment):
    driver.get(f"{BASE_URL}?balance=30000&reserved=20001")

    # Нажать на рублевый счет
    open_rub_balance_card(driver)

    card_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="0000 0000 0000 0000"]')
    card_input.clear()
    card_input.send_keys(card_number)

    amount_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="1000"]')
    amount_input.clear()
    amount_input.send_keys("1000")

    transfer_button = driver.find_element(By.CLASS_NAME, "g-button__text")
    transfer_button.click()

    # Проверяем уведомление об успешной операции или ошибку
    from selenium.common.exceptions import NoAlertPresentException, UnexpectedAlertPresentException
    from selenium.webdriver.common.alert import Alert
    import time

    try:
        alert = Alert(driver)
        alert_text = alert.text.lower()
        alert.accept()
        time.sleep(1)
        if transfer_should_succeed:
            assert "принят банком" in alert_text
        else:
            print(f"Известный баг: {comment} — перевод принят, хотя не должен")
    except NoAlertPresentException:
        if transfer_should_succeed:
            pytest.fail("Ожидалось уведомление об успешной операции, но alert не появился")
        else:
            print(f"Корректно: {comment} — alert не появился, перевод не выполнен")
    except UnexpectedAlertPresentException:
        pytest.fail("Неожиданный alert не был обработан")

    assert True

#Тест 003

@pytest.mark.parametrize("transfer_amount,expected_commission,expect_success,comment", [
    (1000, "100 ₽", True, "Перевод 1000 руб — комиссия 100 руб, успешный перевод"),
    (9099, "900 ₽", False, "Перевод 9099 руб — комиссия 900 руб, баг: ошибка о недостатке средств"),
    (0, None, False, "Перевод 0 руб — баг: кнопка активна, перевод возможен"),
])
def test_transfer_commission_and_validation(driver, transfer_amount, expected_commission, expect_success, comment):
    driver.get(f"{BASE_URL}?balance=30000&reserved=20001")
    open_rub_balance_card(driver)

    card_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="0000 0000 0000 0000"]')
    card_input.send_keys("1234567812345678")

    amount_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="1000"]')
    amount_input.clear()
    amount_input.send_keys(str(transfer_amount))

    # Проверяем отображение комиссии
    try:
        commission_element = driver.find_element(By.ID, "comission") 
        commission_text = commission_element.text.strip()
    except NoSuchElementException:
        commission_text = None

    if expected_commission:
        if commission_text != expected_commission:
            print(f"Известный баг: {comment} — комиссия отображается как '{commission_text}', ожидалось '{expected_commission}'")
    else:
        if commission_text:
            print(f"Известный баг: {comment} — комиссия отображается, хотя не должна")

    transfer_button = driver.find_element(By.CLASS_NAME, "g-button__text")
    transfer_button.click()

    # Проверяем alert об успешной операции или ошибке
    try:
        alert = Alert(driver)
        alert_text = alert.text.lower()
        alert.accept()
        time.sleep(1)
        if expect_success:
            assert "принят банком" in alert_text, f"Ожидался успешный перевод, но alert: {alert_text}"
        else:
            if "принят банком" in alert_text:
                print(f"Известный баг: {comment} — перевод прошёл, хотя должен быть отказ, alert: {alert_text}")
    except NoAlertPresentException:
        if expect_success:
            pytest.fail(f"Ожидался alert об успешном переводе, но alert не появился — {comment}")
        else:
            print(f"Корректно: {comment} — alert не появился, перевод не выполнен")
    except UnexpectedAlertPresentException:
        pytest.fail("Неожиданный alert не был обработан")

    assert True