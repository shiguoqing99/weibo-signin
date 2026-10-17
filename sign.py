#!/usr/bin/env python3
import os
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

COOKIE_STR = os.environ.get('WEIBO_COOKIE', '')
EMAIL_USER = os.environ.get('EMAIL_USER', '')
EMAIL_PASS = os.environ.get('EMAIL_PASS', '')
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL', '')

TOPIC_URL = 'https://weibo.com/p/10080801cfe03f62bd4032bff8cb8607eb17e0/super_index'

def send_email(subject, content):
    if not EMAIL_USER or not EMAIL_PASS:
        return
    try:
        msg = MIMEText(content, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = NOTIFY_EMAIL or EMAIL_USER

        if 'qq.com' in EMAIL_USER:
            server = smtplib.SMTP_SSL('smtp.qq.com', 465)
        else:
            server = smtplib.SMTP('smtp.qq.com', 587)
            server.starttls()

        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"邮件发送失败: {e}")

def add_cookies(driver, cookie_str):
    """添加Cookie到浏览器"""
    driver.get('https://weibo.com')
    time.sleep(2)

    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            if key in ['SUB', 'SUBP', 'SCF', 'PC_TOKEN', 'ALF']:
                driver.add_cookie({'name': key, 'value': value, 'domain': '.weibo.com'})

    driver.refresh()
    time.sleep(3)

def find_sign_button(driver, max_wait=30):
    """
    循环查找签到按钮，直到找到或超时。
    返回 (按钮元素, 按钮文字) 或 (None, None)
    """
    selectors = [
        '[class*="signBtnOverlay"]',           # 你确认过的新结构
        '.btn_bed .W_btn_b[action-type="widget_take"]',  # 旧结构，兜底
    ]
    start = time.time()
    attempt = 0

    while time.time() - start < max_wait:
        attempt += 1
        for sel in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                if elements:
                    btn = elements[0]
                    text = btn.text.strip()
                    if text:  # 有文字才算真正拿到按钮
                        print(f"[第{attempt}次尝试] 找到按钮，选择器: {sel}，文字: '{text}'")
                        return btn, text
            except Exception:
                pass

        # 没找到，滚动一下页面（有些元素懒加载）
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        except Exception:
            pass

        print(f"[第{attempt}次尝试] 暂未找到签到按钮，等待2秒...")
        time.sleep(2)

    return None, None

def do_sign():
    print(f"开始签到 - {datetime.now()}")

    if not COOKIE_STR:
        send_email("微博签到失败", "<p>未配置Cookie</p>")
        return False

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)

        add_cookies(driver, COOKIE_STR)

        print(f"访问: {TOPIC_URL}")
        driver.get(TOPIC_URL)
        time.sleep(5)

        # 循环查找签到按钮
        sign_btn, btn_text = find_sign_button(driver, max_wait=30)

        if sign_btn is None:
            print("❌ 超时仍未找到签到按钮")
            print(f"当前页面标题: {driver.title}")
            print(f"当前页面URL: {driver.current_url}")
            print("=== 页面源码片段（前2000字符）===")
            print(driver.page_source[:2000])
            print("=== 页面源码片段结束 ===")
            send_email("微博签到失败", "<p>超时未找到签到按钮，可能页面结构已变化或登录态失效</p>")
            return False

        print(f"签到按钮文字: {btn_text}")

        if btn_text == '已签到':
            print("今日已签到")
            send_email("微博签到提醒", "<p>今日已签到</p>")
            return True

        # 点击签到（用 JS 点击更稳）
        driver.execute_script("arguments[0].click();", sign_btn)
        print("已点击签到按钮")
        time.sleep(5)

        # 重新查找按钮，检查文字是否变化
        result_btn, new_text = find_sign_button(driver, max_wait=15)

        if result_btn is None:
            print("点击后未能重新找到按钮，无法确认状态")
            send_email("微博签到异常", "<p>点击后无法确认状态</p>")
            return False

        print(f"签到后按钮文字: {new_text}")

        if new_text == '已签到':
            print("✅ 签到成功!")
            send_email("微博签到成功", f"<p>签到成功！{datetime.now()}</p>")
            return True
        else:
            print(f"签到后按钮未变为'已签到'")
            send_email("微博签到失败", f"<p>点击后按钮文字: {new_text}</p>")
            return False

    except Exception as e:
        print(f"错误: {e}")
        send_email("微博签到异常", f"<p>{e}</p>")
        return False
    finally:
        if driver:
            driver.quit()

if __name__ == '__main__':
    do_sign()
