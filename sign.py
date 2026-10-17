#!/usr/bin/env python3
import os
import time
import logging
import smtplib
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
MAX_RETRIES = 3

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
    try:
        WebDriverWait(driver, 5).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, '.gn_name, .face, [node-type="username"]')) > 0
        )
        logger.info("登录状态验证成功")
        return True
    except:
        logger.warning("登录状态验证失败，Cookie可能已失效")
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
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    driver = None
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"第 {attempt + 1}/{MAX_RETRIES} 次尝试")
            driver = webdriver.Chrome(options=chrome_options)
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
            sign_btn = None
            selectors = ['.btn_bed .W_btn_b[action-type="widget_take"]', '[action-type="widget_take"]', '.W_btn_b[action-type="widget_take"]', 'a.W_btn_b:not(.W_btn_a)', '.btn_bed a[class*="btn"]']
            wait = WebDriverWait(driver, 10)
            for selector in selectors:
                try:
                    sign_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    logger.info(f"找到签到按钮: {selector}")
                    break
                except:
                    continue
            if not sign_btn:
                logger.error("未找到签到按钮")
                send_email("微博签到失败", "<p>未找到签到按钮，页面结构可能已变化</p>")
                return False
            btn_text = sign_btn.text
            logger.info(f"签到按钮文字: '{btn_text}'")
            if '已签到' in btn_text or '签到成功' in btn_text:
                logger.info("今日已签到")
                send_email("微博签到提醒", f"<p>今日已签到 - {datetime.now()}</p>")
                return True
            logger.info("点击签到按钮...")
            sign_btn.click()
            time.sleep(3)
            try:
                result_btn = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[action-type="widget_take"]')))
                new_text = result_btn.text
                logger.info(f"签到后按钮文字: '{new_text}'")
                if '已签到' in new_text or '签到成功' in new_text:
                    logger.info("签到成功!")
                    send_email("微博签到成功", f"<p>签到成功！{datetime.now()}</p>")
                    return True
                else:
                    logger.warning(f"签到后按钮未变为'已签到': {new_text}")
                    send_email("微博签到失败", f"<p>点击后按钮文字: {new_text}</p>")
                    return False
            except Exception as e:
                logger.error(f"验证签到结果失败: {e}")
                send_email("微博签到异常", f"<p>点击后无法确认状态: {e}</p>")
                return False
        except Exception as e:
            logger.error(f"第 {attempt + 1} 次尝试失败: {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info(f"等待 5 秒后重试...")
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
