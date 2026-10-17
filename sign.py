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

def find_sign_button_by_text(driver):
    """
    以文字“签到”为锚点查找可点击的签到按钮。
    优先找文字恰好是“签到”的元素，找不到再找包含“签到”的元素。
    返回 (元素, 文字) 或 (None, None)
    """
    # 方式1：文字恰好是“签到”
    try:
        elements = driver.find_elements(By.XPATH, "//*[normalize-space(text())='签到']")
        for el in elements:
            try:
                if el.is_displayed():
                    print(f"找到文字恰好为'签到'的元素: <{el.tag_name}> class='{el.get_attribute('class')}'")
                    return el, '签到'
            except Exception:
                pass
    except Exception:
        pass

    # 方式2：文字包含“签到”，但排除“今日签到”这类统计标签
    try:
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), '签到')]")
        for el in elements:
            try:
                text = (el.text or '').strip()
                if not el.is_displayed():
                    continue
                # 排除明显是统计信息的标签（含数字或“今日”）
                if text == '签到':
                    print(f"找到含'签到'且文字恰好的元素: <{el.tag_name}> class='{el.get_attribute('class')}'")
                    return el, text
                if '签到' in text and not any(ch.isdigit() for ch in text) and '今日' not in text:
                    print(f"找到含'签到'的元素: <{el.tag_name}> class='{el.get_attribute('class')}' text='{text}'")
                    return el, text
            except Exception:
                pass
    except Exception:
        pass

    return None, None

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

        # 诊断：打印所有含“签到”文字的元素
        print("=== 诊断：所有含'签到'文字的元素 ===")
        try:
            all_sign = driver.find_elements(By.XPATH, "//*[contains(text(), '签到')]")
            for el in all_sign[:15]:
                try:
                    print(f"  <{el.tag_name}> class='{el.get_attribute('class')}' text='{(el.text or '')[:40]}' displayed={el.is_displayed()}")
                except Exception:
                    pass
        except Exception as e:
            print(f"诊断失败: {e}")
        print("=== 诊断结束 ===")

        btn, btn_text = find_sign_button_by_text(driver)

        if btn is None:
            print("❌ 仍未找到签到按钮")
            # 兜底：打印所有 class 含 '1sn1l' 的元素
            print("=== 诊断：所有 class 含 '1sn1l' 的元素 ===")
            try:
                elements = driver.execute_script("""
                    var results = [];
                    var all = document.querySelectorAll('[class*="1sn1l"]');
                    for (var i = 0; i < all.length; i++) {
                        results.push({
                            tag: all[i].tagName.toLowerCase(),
                            cls: all[i].className,
                            text: (all[i].textContent || '').trim().slice(0, 40),
                            visible: all[i].offsetParent !== null
                        });
                    }
                    return results;
                """)
                for e in elements[:20]:
                    print(f"  <{e['tag']}> class='{e['cls']}' text='{e['text']}' visible={e['visible']}")
            except Exception as e:
                print(f"诊断失败: {e}")
            print("=== 诊断结束 ===")

            send_email("微博签到失败", "<p>未找到签到按钮</p>")
            return False

        print(f"找到签到按钮，文字: '{btn_text}'")

        if btn_text == '已签到':
            print("今日已签到")
            send_email("微博签到提醒", "<p>今日已签到</p>")
            return True

        driver.execute_script("arguments[0].click();", btn)
        print("已点击签到按钮")
        time.sleep(5)

        # 点击后重新查找，检查文字是否变化
        result_btn, new_text = find_sign_button_by_text(driver)

        if result_btn is None:
            print("点击后未找到按钮，检查页面文字变化...")
            try:
                all_sign = driver.find_elements(By.XPATH, "//*[contains(text(), '签到')]")
                for el in all_sign[:10]:
                    print(f"  点击后含'签到'元素: <{el.tag_name}> text='{(el.text or '')[:40]}'")
            except Exception:
                pass
            send_email("微博签到异常", "<p>点击后无法确认状态</p>")
            return False

        print(f"签到后按钮文字: '{new_text}'")

        if new_text == '已签到':
            print("✅ 签到成功!")
            send_email("微博签到成功", f"<p>签到成功！{datetime.now()}</p>")
            return True
        else:
            print("签到后按钮文字未变为'已签到'")
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
