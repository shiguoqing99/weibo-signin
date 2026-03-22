#!/usr/bin/env python3
import os
import time
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import requests

# 环境变量
COOKIE_STR = os.environ.get('WEIBO_COOKIE', '')
EMAIL_USER = os.environ.get('EMAIL_USER', '')
EMAIL_PASS = os.environ.get('EMAIL_PASS', '')
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL', '')

# 超话ID
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

def parse_cookie(cookie_str):
    cookies = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key] = value
    return cookies

def do_sign():
    print(f"开始签到 - {datetime.now()}")
    
    if not COOKIE_STR:
        send_email("微博签到失败", "<p>未配置Cookie</p>")
        return False
    
    cookies = parse_cookie(COOKIE_STR)
    
    if 'SUB' not in cookies:
        send_email("微博签到失败", "<p>Cookie无效</p>")
        return False
    
    # 签到API
    url = 'https://i.huati.weibo.com/aj/super/checkin'
    params = {
        'id': CONTAINER_ID,
        'status': 0,
        'texta': '签到',
        'textb': '已签到',
        '_t': int(time.time() * 1000)
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://weibo.com/',
        'Accept': 'application/json, text/plain, */*',
    }
    
    try:
        resp = requests.get(url, params=params, cookies=cookies, headers=headers, timeout=15)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")
        
        data = resp.json()
        code = str(data.get('code', ''))
        
        if code == '100000':
            print("签到成功")
            send_email("微博签到成功", f"<p>签到成功！{datetime.now()}</p>")
            return True
        elif '382004' in code or '已签到' in resp.text:
            print("今日已签到")
            send_email("微博签到提醒", "<p>今日已签到</p>")
            return True
        else:
            print(f"签到失败: {data}")
            send_email("微博签到失败", f"<p>{data}</p>")
            return False
            
    except Exception as e:
        print(f"错误: {e}")
        send_email("微博签到异常", f"<p>{e}</p>")
        return False

if __name__ == '__main__':
    do_sign()
