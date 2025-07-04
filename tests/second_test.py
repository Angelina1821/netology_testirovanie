# pytest tests\second_test.py -s

import pytest
import time
from selenium.webdriver.common.alert import Alert
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException, NoSuchElementException

BASE_URL = "http://localhost:8000/"

def open_rub_balance_card(driver):
    cards = driver.find_elements(By.CLASS_NAME, "g-card_clickable")
    for card in cards:
        if card.find_element(By.TAG_NAME, "h2").text == "Рубли":
            card.click()
            break

def input_numbercard_sum(driver, card_number, sum):
    card_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="0000 0000 0000 0000"]')
    card_input.clear()
    card_input.send_keys(card_number)
    amount_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="1000"]')
    amount_input.clear()
    amount_input.send_keys(sum)

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
    ("30000", "20001", "30'000 ₽", "20'001 ₽"),
    ("3000", "2000", "3'000 ₽", "2'000 ₽"),
    ("-100", "-200", "0 ₽", "0 ₽"), 
])

def test_balance_and_reserv_display(driver, balance, reserved, expected_balance, expected_reserved):
    driver.get(f"{BASE_URL}?balance={balance}&reserved={reserved}")
    text = get_balance_and_reserved_text(driver)
    
    if int(balance) < 0 or int(reserved) < 0:
        pytest.xfail("Известный баг: отрицательные значения баланса/резерва не обрабатываются")

    assert f"На счету: {expected_balance}" in text
    assert f"Резерв: {expected_reserved}" in text

@pytest.mark.parametrize("card_number, transfer_button_expected, comment", [
    ("123456789012345", False, "15 цифр — кнопка 'Перевести' не должна появляться"),
    ("1234567890123456", True, "16 цифр — кнопка 'Перевести' должна появиться"),
    pytest.param("12345678901234567", False, "17 цифр — кнопка 'Перевести' не должна появляться (известный баг)", marks=pytest.mark.xfail),
])
def test_number_card_validation(driver, card_number, transfer_button_expected, comment):
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

    assert button_visible == transfer_button_expected, comment

@pytest.mark.parametrize("card_number,transfer_should_succeed,sum, comment", [
    ("1234567890123456", True, "1000", "16 цифр — перевод должен пройти успешно"),
    pytest.param(
        "12345678901234567", False, "1000", "17 цифр — перевод не должен проходить (известный баг)",
        marks=pytest.mark.xfail(reason="Известный баг: система принимает переводы по номеру с 17 цифрами"),
    )
])
def test_transfer_button_and_operation(driver, card_number, transfer_should_succeed, sum, comment):
    driver.get(f"{BASE_URL}?balance=30000&reserved=20001")
    open_rub_balance_card(driver)
    input_numbercard_sum(driver, card_number, sum)
    driver.find_element(By.CLASS_NAME, "g-button__text").click()

    try:
        alert = Alert(driver)
        alert_text = alert.text.lower()
        alert.accept()
        
        if not transfer_should_succeed:
            # Если перевод не должен был пройти, но прошёл - это баг
            pytest.fail(f"Баг: {comment} - перевод был выполнен успешно")
            
        assert "принят банком" in alert_text, "Не найдено подтверждение успешного перевода"
        
    except NoAlertPresentException:
        if transfer_should_succeed:
            pytest.fail(f"Ошибка: {comment} - не появилось уведомление об успешной операции")

@pytest.mark.parametrize("sum,expected_commission,expect_success,expect_button,comment", [
    pytest.param(
        "1000", "100", True, True,
        "Перевод 1000 руб — комиссия 100 руб, успешный перевод",
    ),
    pytest.param(
        "9099", "900", True, True,
        "Перевод 9099 руб — комиссия 900 руб (должен проходить)",
        marks=pytest.mark.xfail(reason="Известный баг: ошибочное сообщение 'недостаточно средств' при переводе равном доступному остатку"),
    ),
    pytest.param(
        "0", None, False, False,
        "Перевод 0 руб — кнопка не должна появляться",
        marks=pytest.mark.xfail(reason="Известный баг: кнопка активна для 0 руб"),
    ),
    pytest.param(
        "9100", "910", False, False,
        "Перевод 9100 руб — кнопка не появляется (превышение баланса), перевод невозможен",
    )
])
def test_transfer_commission_and_validation(driver, sum, expected_commission, expect_success, expect_button, comment):
    # Настройка теста
    driver.get(f"{BASE_URL}?balance=30000&reserved=20001")
    card_number = "1234567890123456"
    open_rub_balance_card(driver)
    input_numbercard_sum(driver, card_number, sum)

    if expected_commission:
        commission = driver.find_element(By.ID, "comission").text
        assert commission == expected_commission, f"Неверная комиссия: {commission}"

    # Проверка наличия кнопки
    try:
        transfer_button = driver.find_element(By.CLASS_NAME, "g-button__text")
        button_present = transfer_button.is_displayed()
    except NoSuchElementException:
        button_present = False

    assert button_present == expect_button, (
        f"Несоответствие в отображении кнопки. Ожидалось: {expect_button}, Фактически: {button_present}"
    )

    # Если кнопка есть - пробуем выполнить перевод
    if button_present:
        transfer_button.click()
        
        try:
            alert = Alert(driver)
            alert_text = alert.text.lower()
            alert.accept()
            
            if not expect_success:
                pytest.fail(f"Баг: перевод {sum} руб прошел успешно (сообщение: '{alert_text}')")
            assert "принят банком" in alert_text, "Нет подтверждения успешного перевода"
            
        except NoAlertPresentException:
            if expect_success:
                pytest.fail(f"Не появилось подтверждение перевода {sum} руб")


@pytest.mark.parametrize("url_params,expected_balance,expected_reserved,comment", [
    pytest.param(
        "", 
        "0", "0",
        "Без параметров - должен показывать нулевые значения"
    ),
    pytest.param(
        "?balance=30000", 
        "30'000", "0",
        "Только balance=30000 - должен показывать баланс 30000, резерв 0"
    ),
    pytest.param(
        "?reserved=20001", 
        "0", "0",
        "Только reserved=20001 - должен игнорировать резерв без баланса",
        marks=pytest.mark.xfail(reason="Известный баг: резерв отображается без указания баланса, резерв не может быть больше баланса")
    )
])
def test_url_parameters_handling(driver, url_params, expected_balance, expected_reserved, comment):
    driver.get(f"{BASE_URL}{url_params}")
    
    card_text = get_balance_and_reserved_text(driver)

    assert f"На счету: {expected_balance}" in card_text, (
        f"Неверное отображение баланса. Ожидалось: 'На счету: {expected_balance}', "
        f"Фактически: '{card_text}'")
    
    assert f"Резерв: {expected_reserved}" in card_text, (
        f"Неверное отображение резерва. Ожидалось: 'Резерв: {expected_reserved}', "
        f"Фактически: '{card_text}'")
    
@pytest.mark.xfail(reason="Известный баг: комиссия рассчитывается для валютных счетов как для рублевых")
def test_dollar_account_transfer_with_commission_bug(driver):
    driver.get(f"{BASE_URL}?balance=100&currency=usd")
    
    cards = driver.find_elements(By.CLASS_NAME, "g-card_clickable")
    for card in cards:
        if card.find_element(By.TAG_NAME, "h2").text == "Доллары":
            card.click()
            break
    
    input_numbercard_sum(driver, "1234567890123456", "10")
    
    commission = driver.find_element(By.ID, "comission").text
    assert commission == "1", f"Ожидалась комиссия 1$ (10%), получено {commission}$"

@pytest.mark.xfail(reason="Известный баг: система позволяет переводить суммы больше баланса")
def test_dollar_account_insufficient_funds_bug(driver):
    driver.get(f"{BASE_URL}?balance=100&currency=usd")
    
    cards = driver.find_elements(By.CLASS_NAME, "g-card_clickable")
    for card in cards:
        if card.find_element(By.TAG_NAME, "h2").text == "Доллары":
            card.click()
            break
    
    input_numbercard_sum(driver, "1234567890123456", "5000")
    
    try:
        alert = Alert(driver)
        assert "недостаточно средств" in alert.text.lower()
        alert.accept()
    except NoAlertPresentException:
        pytest.fail("Не появилось сообщение о недостатке средств")

@pytest.mark.xfail(reason="Известный баг: резерв отображается без указания баланса для валютных счетов")
def test_currency_reserved_without_balance_bug(driver):
    """Проверка отображения резерва без баланса для валютных счетов"""
    driver.get(f"{BASE_URL}?reserved=50&currency=usd")
    
    cards = driver.find_elements(By.CLASS_NAME, "g-card_clickable")
    for card in cards:
        if card.find_element(By.TAG_NAME, "h2").text == "Доллары":
            card.click()
            break
    
    card_text = ""
    cards = driver.find_elements(By.CSS_SELECTOR, ".g-box.g-card")
    for card in cards:
        if "Доллары" in card.text:
            card_text = card.text
            break
    
    assert "Резерв: 0 $" in card_text, "Баг: резерв отображается без указания баланса"

def test_currency_balance_display(driver):
    """Проверка корректного отображения баланса для валютных счетов"""
    driver.get(f"{BASE_URL}?balance=300&reserved=26&currency=eur")
    
    cards = driver.find_elements(By.CLASS_NAME, "g-card_clickable")
    for card in cards:
        if card.find_element(By.TAG_NAME, "h2").text == "Евро":
            card.click()
            break
    
    card_text = ""
    cards = driver.find_elements(By.CSS_SELECTOR, ".g-box.g-card")
    for card in cards:
        if "Евро" in card.text:
            card_text = card.text
            break
    
    assert "На счету: 300 €" in card_text
    assert "Резерв: 26 €" in card_text