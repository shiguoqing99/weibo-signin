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
CONTAINER_ID = '10080801cfe03f62bd4032bff8cb8607eb17e0'

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

        # 等待页面基础框架加载（“今日签到”标签出现即说明主体已渲染）
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '今日签到')]"))
            )
            print("页面主体已渲染（找到'今日签到'标签）")
        except Exception:
            print("等待'今日签到'标签超时，继续尝试接口调用")
        time.sleep(3)

        print(f"当前页面标题: {driver.title}")
        print(f"当前页面URL: {driver.current_url}")

        # 直接通过页面上下文调用签到接口，绕过 UI 按钮渲染问题
        print("尝试直接调用签到接口...")
        sign_result = driver.execute_script("""
            var containerid = arguments[0];
            var timestamp = new Date().getTime();
            var url = 'https://weibo.com/p/aj/general/button?api=http://i.huati.weibo.com/ajax/super/checkindone&id='
                      + containerid + '&syn_weibo=0&_=' + timestamp;

            return fetch(url, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(function(r) { return r.json(); })
            .then(function(data) { return JSON.stringify(data); })
            .catch(function(e) { return JSON.stringify({error: e.toString()}); });
        """, CONTAINER_ID)

        print(f"接口返回: {sign_result}")

        try:
            result_data = json.loads(sign_result)
            code = str(result_data.get('code', ''))
            msg = str(result_data.get('msg', ''))

            if code == '100000':
                print("✅ 签到成功（通过接口直接调用）!")
                send_email("微博签到成功", f"<p>签到成功！{datetime.now()}</p>")
                return True
            elif '已签' in msg:
                print("ℹ️ 今日已签到")
                send_email("微博签到提醒", "<p>今日已签到</p>")
                return True
            else:
                print(f"❌ 接口返回失败: {result_data}")
                send_email("微博签到失败", f"<p>接口返回: {result_data}</p>")
                return False
        except Exception as e:
            print(f"解析结果失败: {e}, 原始返回: {sign_result}")
            send_email("微博签到异常", f"<p>解析失败: {e}</p>")
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
