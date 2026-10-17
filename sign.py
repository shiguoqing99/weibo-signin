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

def dump_sign_elements(driver):
    """打印页面上所有文字包含'签到'的元素信息，用于诊断"""
    print("=== 诊断：页面上文字包含'签到'的元素 ===")
    try:
        all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '签到')]")
        if not all_elements:
            print("页面上没有任何文字包含'签到'的元素")
        for el in all_elements[:10]:
            try:
                tag = el.tag_name
                cls = el.get_attribute('class') or ''
                text = (el.text or '')[:50]
                print(f"  <{tag}> class='{cls}' text='{text}'")
            except Exception:
                pass
    except Exception as e:
        print(f"诊断失败: {e}")
    print("=== 诊断结束 ===")

def find_sign_button(driver, max_wait=20):
    """循环查找签到按钮，先滚动到顶部，再逐次尝试"""
    selectors = [
        '[class*="signBtnOverlay"]',
        '.btn_bed .W_btn_b[action-type="widget_take"]',
        '[class*="signBtn"]',
    ]
    start = time.time()
    attempt = 0

    try:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
    except Exception:
        pass

    while time.time() - start < max_wait:
        attempt += 1

        iframes = driver.find_elements(By.TAG_NAME, 'iframe')
        if iframes:
            for idx, iframe in enumerate(iframes):
                try:
                    driver.switch_to.frame(iframe)
                    for sel in selectors:
                        elements = driver.find_elements(By.CSS_SELECTOR, sel)
                        if elements and elements[0].text.strip():
                            btn = elements[0]
                            text = btn.text.strip()
                            print(f"[第{attempt}次] 在 iframe[{idx}] 中找到按钮: {sel}，文字: '{text}'")
                            driver.switch_to.default_content()
                            return btn, text
                    driver.switch_to.default_content()
                except Exception:
                    try:
                        driver.switch_to.default_content()
                    except Exception:
                        pass

        for sel in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    text = (el.text or '').strip()
                    if text:
                        print(f"[第{attempt}次] 找到按钮: {sel}，文字: '{text}'")
                        return el, text
            except Exception:
                pass

        # JS 递归兜底：穿透 Shadow DOM 查找文字为“签到”的可见元素
        try:
            result = driver.execute_script("""
                function findSignIn(root) {
                    let elements = root.querySelectorAll('*');
                    for (let el of elements) {
                        if (el.textContent.trim() === '签到' && el.offsetParent !== null) {
                            return el;
                        }
                        if (el.shadowRoot) {
                            let found = findSignIn(el.shadowRoot);
                            if (found) return found;
                        }
                    }
                    return null;
                }
                return findSignIn(document);
            """)
            if result:
                text = driver.execute_script("return arguments[0].textContent.trim()", result)
                if text == '签到':
                    print(f"[第{attempt}次] 通过 JS 递归查找到签到元素，直接点击")
                    driver.execute_script("arguments[0].click();", result)
                    return "JS_CLICKED", "签到"
        except Exception:
            pass

        try:
            driver.execute_script("window.scrollBy(0, 300);")
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
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        add_cookies(driver, COOKIE_STR)

        print(f"访问: {TOPIC_URL}")
        driver.get(TOPIC_URL)

        # 等待“今日签到”标签出现，说明页面主体已渲染
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '今日签到')]"))
            )
            print("页面主体已渲染（找到'今日签到'标签）")
        except Exception:
            print("等待'今日签到'标签超时")
        time.sleep(3)

        print(f"当前页面标题: {driver.title}")
        print(f"当前页面URL: {driver.current_url}")

        dump_sign_elements(driver)

        sign_btn, btn_text = find_sign_button(driver, max_wait=20)

        if sign_btn is None:
            print("❌ 超时仍未找到签到按钮")
            dump_sign_elements(driver)
            send_email("微博签到失败", "<p>超时未找到签到按钮</p>")
            return False

        # JS_CLICKED 表示按钮已经被 JS 直接点击，无需再点
        if sign_btn == "JS_CLICKED":
            print("已通过 JS 点击签到元素")
            time.sleep(5)
            result_btn, new_text = find_sign_button(driver, max_wait=10)
            if new_text == '已签到' or new_text == '签到':
                print("✅ 签到操作已完成（JS 点击路径）")
                send_email("微博签到成功", f"<p>签到成功！{datetime.now()}</p>")
                return True
            else:
                print(f"JS 点击后状态: {new_text}")
                send_email("微博签到异常", f"<p>JS 点击后状态: {new_text}</p>")
                return False

        print(f"签到按钮文字: {btn_text}")

        if btn_text == '已签到':
            print("今日已签到")
            send_email("微博签到提醒", "<p>今日已签到</p>")
            return True

        driver.execute_script("arguments[0].click();", sign_btn)
        print("已点击签到按钮")
        time.sleep(5)

        result_btn, new_text = find_sign_button(driver, max_wait=10)

        if result_btn is None:
            print("点击后未能重新找到按钮")
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
