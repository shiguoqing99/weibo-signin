#!/usr/bin/env python3
import os
import time
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

COOKIE_STR = os.environ.get('WEIBO_COOKIE', '')
EMAIL_USER = os.environ.get('EMAIL_USER', '')
EMAIL_PASS = os.environ.get('EMAIL_PASS', '')
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL', '')

TOPIC_URL = 'https://weibo.com/p/10080801cfe03f62bd4032bff8cb8607eb17e0/super_index'
# TOPIC_URL = 'https://weibo.com/p/1008086f1b7983ba4fca7456e28317e78127ed/super_index'
MAX_RETRIES = 3
COOKIE_VALIDATE_URL = "https://weibo.com/ajax/profile/info?uid=1000000000"


def parse_cookies(cookie_str):
    cookies = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key] = value
    return cookies


def send_email(subject, content):
    if not EMAIL_USER or not EMAIL_PASS:
        logger.warning("未配置邮件信息，跳过通知")
        return
    try:
        msg = MIMEText(content, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = NOTIFY_EMAIL or EMAIL_USER
        if 'qq.com' in EMAIL_USER:
            server = smtplib.SMTP_SSL('smtp.qq.com', 465)
        elif '163.com' in EMAIL_USER:
            server = smtplib.SMTP('smtp.163.com', 25)
            server.starttls()
        elif 'gmail.com' in EMAIL_USER:
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        else:
            server = smtplib.SMTP('smtp.qq.com', 587)
            server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        logger.info("邮件发送成功")
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")


def add_cookies(driver, cookie_str):
    cookies = parse_cookies(cookie_str)
    logger.info("访问微博首页...")
    driver.get('https://weibo.com')
    time.sleep(2)
    driver.delete_all_cookies()
    injected = 0
    for key, value in cookies.items():
        try:
            driver.add_cookie({'name': key, 'value': value, 'domain': '.weibo.com', 'path': '/'})
            injected += 1
        except Exception as e:
            logger.debug(f"Cookie注入失败 {key}: {e}")
    logger.info(f"已注入 {injected} 个Cookie")
    driver.refresh()
    time.sleep(3)

    # 接口权威验证 Cookie
    try:
        selenium_cookies = driver.get_cookies()
        cookie_jar = {c['name']: c['value'] for c in selenium_cookies}
        for k, v in cookies.items():
            cookie_jar.setdefault(k, v)

        headers = {
            "User-Agent": driver.execute_script("return navigator.userAgent;"),
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://weibo.com/",
        }
        resp = requests.get(COOKIE_VALIDATE_URL, cookies=cookie_jar, headers=headers, timeout=15)
        data = resp.json()
        if data.get("ok") == 1:
            logger.info("接口验证登录状态：成功")
            return True
        else:
            logger.warning(f"接口验证登录状态失败，返回: {data}")
            return False
    except Exception as e:
        logger.error(f"接口验证时发生异常: {e}")
        return False


def find_sign_button(driver, wait):
    """
    严格寻找签到按钮：只接受可见、文字为「签到」或包含「签到」但不含「已签到」的元素。
    CSS 和 XPath 都尝试，找到返回元素，找不到返回 None。
    """
    css_selectors = [
        '.super_index .W_btn_b',
        '[class*="sign_btn"]',
        '[class*="checkin"]',
        '[class*="qd_btn"]',
        '[class*="btn_sign"]',
        '.W_btn_b',
        'button[class*="btn"]',
    ]
    for selector in css_selectors:
        try:
            elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
        except Exception:
            continue
        for el in elements:
            try:
                if not el.is_displayed():
                    continue
                text = (el.text or '').strip()
                if text and '签到' in text and '已签到' not in text:
                    logger.info(f"CSS 命中签到按钮: {selector} | 文字: '{text}'")
                    return el
            except Exception:
                continue

    # 核心 XPath：class 含 sign 且文字含「签到」但不含「已签到」
    xpath_selectors = [
        '//*[contains(@class, "sign") and contains(normalize-space(.), "签到") and not(contains(normalize-space(.), "已签到"))]',
        '//a[contains(normalize-space(.), "签到") and not(contains(normalize-space(.), "已签到"))]',
        '//button[contains(normalize-space(.), "签到") and not(contains(normalize-space(.), "已签到"))]',
        '//*[contains(@class, "W_btn_b") and contains(normalize-space(.), "签到") and not(contains(normalize-space(.), "已签到"))]',
    ]
    for xp in xpath_selectors:
        try:
            elements = wait.until(EC.presence_of_all_elements_located((By.XPATH, xp)))
        except Exception:
            continue
        for el in elements:
            try:
                if el.is_displayed():
                    text = (el.text or '').strip()
                    # 排除容器级元素：文字过长说明命中的是父节点
                    if text and len(text) <= 10:
                        logger.info(f"XPath 命中签到按钮: {xp} | 文字: '{text}'")
                        return el
            except Exception:
                continue

    return None


def wait_for_signed(driver, timeout=15):
    """
    轮询等待页面上出现「已签到」/「签到成功」标识。
    只匹配文字较短（<= 20 字符）的可见元素，避免抓到整页文本。
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            els = driver.find_elements(
                By.XPATH,
                '//*[contains(normalize-space(.), "已签到") or contains(normalize-space(.), "签到成功")]'
            )
            for el in els:
                if el.is_displayed():
                    text = (el.text or '').strip()
                    if text and len(text) <= 20:
                        logger.info(f"检测到签到完成标识: '{text}'")
                        return True
        except Exception:
            pass
        time.sleep(1)
    return False


def do_sign():
    logger.info(f"开始签到 - {datetime.now()}")
    if not COOKIE_STR:
        logger.error("未配置Cookie")
        send_email("微博签到失败", "<p>未配置Cookie</p>")
        return False

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = None
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"第 {attempt + 1}/{MAX_RETRIES} 次尝试")
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })

            if not add_cookies(driver, COOKIE_STR):
                send_email("微博签到失败", "<p>Cookie已失效，请更新</p>")
                return False

            logger.info(f"访问超话: {TOPIC_URL}")
            driver.get(TOPIC_URL)
            time.sleep(5)

            if 'login' in driver.current_url.lower() or 'passport' in driver.current_url.lower():
                logger.error("被重定向到登录页，Cookie已失效")
                send_email("微博签到失败", "<p>Cookie已失效，被重定向到登录页</p>")
                return False

            wait = WebDriverWait(driver, 10)
            sign_btn = find_sign_button(driver, wait)

            if not sign_btn:
                try:
                    driver.save_screenshot('sign_failure.png')
                    logger.info("已保存页面截图: sign_failure.png")
                except Exception as e:
                    logger.warning(f"截图失败: {e}")
                logger.error("未找到签到按钮，页面结构可能已变化")
                send_email("微博签到失败", "<p>未找到签到按钮，已保存截图</p>")
                return False

            btn_text = (sign_btn.text or '').strip()
            logger.info(f"签到按钮文字: '{btn_text}'")

            if '已签到' in btn_text:
                logger.info("今日已签到")
                send_email("微博签到提醒", f"<p>今日已签到 - {datetime.now()}</p>")
                return True

            logger.info("点击签到按钮...")
            try:
                sign_btn.click()
            except Exception:
                logger.warning("原生点击失败，尝试 JS 点击")
                driver.execute_script("arguments[0].click();", sign_btn)

            if wait_for_signed(driver, timeout=15):
                logger.info("签到成功!")
                send_email("微博签到成功", f"<p>签到成功！{datetime.now()}</p>")
                return True
            else:
                try:
                    driver.save_screenshot('sign_after_click.png')
                    logger.info("已保存点击后截图: sign_after_click.png")
                except Exception as e:
                    logger.warning(f"截图失败: {e}")
                logger.warning("点击后未检测到『已签到』标识，签到可能未成功")
                send_email("微博签到失败", "<p>点击后未检测到签到完成标识，已保存截图</p>")
                return False

        except Exception as e:
            logger.error(f"第 {attempt + 1} 次尝试失败: {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info("等待 5 秒后重试...")
                time.sleep(5)
            else:
                send_email("微博签到异常", f"<p>签到失败，已重试 {MAX_RETRIES} 次: {e}</p>")
                return False
        finally:
            if driver:
                driver.quit()
                driver = None
    return False


if __name__ == '__main__':
    do_sign()
