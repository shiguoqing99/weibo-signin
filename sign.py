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

TOPIC_URL = 'https://weibo.com/p/1008089e28e16dc078315dffce410da0740f3a/super_index'

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
            # 只添加关键的认证Cookie
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
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
        # 添加Cookie
        add_cookies(driver, COOKIE_STR)
        
        # 访问超话页面
        print(f"访问: {TOPIC_URL}")
        driver.get(TOPIC_URL)
        time.sleep(5)
        
        # 精确查找签到按钮（通过action-type属性）
        try:
            wait = WebDriverWait(driver, 10)
            # 使用更精确的选择器
            sign_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '.btn_bed .W_btn_b[action-type="widget_take"]')
            ))
            
            btn_text = sign_btn.text
            print(f"签到按钮文字: {btn_text}")
            
            # 检查是否已签到（按钮文字为"已签到"）
            if btn_text == '已签到':
                print("今日已签到")
                send_email("微博签到提醒", "<p>今日已签到</p>")
                return True
            
            # 未签到，点击签到
            sign_btn.click()
            print("已点击签到按钮")
            time.sleep(3)
            
            # 检查签到结果
            try:
                result_btn = driver.find_element(By.CSS_SELECTOR, '.btn_bed .W_btn_b[action-type="widget_take"]')
                new_text = result_btn.text
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
                print(f"检查结果失败: {e}")
                send_email("微博签到异常", f"<p>点击后无法确认状态: {e}</p>")
                return False
                
        except Exception as e:
            print(f"未找到签到按钮: {e}")
            send_email("微博签到失败", f"<p>未找到签到按钮，可能页面结构已变化</p>")
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
