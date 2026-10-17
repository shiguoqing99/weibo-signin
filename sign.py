#!/usr/bin/env python3
import os
import time
import json
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

def find_and_click_sign(driver):
    """
    用 JS 精准查找 _signBtnOverlay_1sn1l_355 并点击。
    返回 (是否找到, 点击前的文字, 点击后的文字)
    """
    # 等待父容器 _actions_1sn1l_336 出现（最多20秒）
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="_actions_1sn1l_336"]'))
        )
        print("父容器 _actions_1sn1l_336 已出现")
    except Exception:
        print("等待父容器超时，继续尝试 JS 查找")

    # 用 JS 查找签到按钮
    result = driver.execute_script("""
        var btn = document.querySelector('[class*="_signBtnOverlay_1sn1l_355"]');
        if (!btn) {
            // 模糊兜底
            btn = document.querySelector('[class*="signBtnOverlay"]');
        }
        if (!btn) return {found: false};
        var text = (btn.textContent || '').trim();
        var visible = btn.offsetParent !== null;
        return {found: true, text: text, visible: visible, outer: btn.outerHTML.slice(0, 200)};
    """)

    if not result.get('found'):
        print("JS 未找到 _signBtnOverlay_1sn1l_355")
        return False, None, None

    print(f"JS 找到签到按钮: text='{result['text']}', visible={result['visible']}")
    print(f"按钮 HTML 片段: {result['outer']}")

    if result['text'] == '已签到':
        print("今日已签到")
        return True, '已签到', '已签到'

    # 用 JS 点击
    clicked = driver.execute_script("""
        var btn = document.querySelector('[class*="_signBtnOverlay_1sn1l_355"]');
        if (!btn) btn = document.querySelector('[class*="signBtnOverlay"]');
        if (!btn) return false;
        btn.click();
        return true;
    """)
    print(f"JS 点击结果: {clicked}")
    time.sleep(5)

    # 点击后重新读取按钮文字
    after = driver.execute_script("""
        var btn = document.querySelector('[class*="_signBtnOverlay_1sn1l_355"]');
        if (!btn) btn = document.querySelector('[class*="signBtnOverlay"]');
        if (!btn) return null;
        return (btn.textContent || '').trim();
    """)
    print(f"点击后按钮文字: '{after}'")
    return True, result['text'], after

def do_sign():
    print(f"开始签到 - {datetime.now()}")
    if not COOKIE_STR:
        send_email("微博签到失败", "<p>未配置Cookie</p>")
        return False

    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        add_cookies(driver, COOKIE_STR)

        print(f"访问: {TOPIC_URL}")
        driver.get(TOPIC_URL)

        # 等待页面出现含“签到”文字的元素
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '签到')]"))
            )
            print("页面已出现含'签到'文字的元素")
        except Exception:
            print("等待含'签到'文字的元素超时")
        time.sleep(3)

        print(f"当前页面标题: {driver.title}")
        print(f"当前页面URL: {driver.current_url}")

        # 诊断：打印 _actions_1sn1l_336 是否存在
        actions = driver.execute_script("""
            var el = document.querySelector('[class*="_actions_1sn1l_336"]');
            if (!el) return null;
            return {outer: el.outerHTML.slice(0, 500), visible: el.offsetParent !== null};
        """)
        if actions:
            print(f"父容器 _actions_1sn1l_336 存在，visible={actions['visible']}")
            print(f"父容器 HTML: {actions['outer']}")
        else:
            print("父容器 _actions_1sn1l_336 不存在")

        found, before_text, after_text = find_and_click_sign(driver)

        if not found:
            send_email("微博签到失败", "<p>JS 未找到 _signBtnOverlay_1sn1l_355</p>")
            return False

        if before_text == '已签到':
            send_email("微博签到提醒", "<p>今日已签到</p>")
            return True

        if after_text == '已签到':
            print("✅ 签到成功!")
            send_email("微博签到成功", f"<p>签到成功！{datetime.now()}</p>")
            return True
        else:
            print(f"签到后按钮文字未变为'已签到'，实际: '{after_text}'")
            send_email("微博签到失败", f"<p>点击后按钮文字: {after_text}</p>")
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
