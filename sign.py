#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微博超话签到 - 直接调用API版本
"""

import os
import re
import time
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import requests

# ========== 配置 ==========
# 从环境变量读取
COOKIE_STR = os.environ.get('WEIBO_COOKIE', '')
EMAIL_USER = os.environ.get('EMAIL_USER', '')
EMAIL_PASS = os.environ.get('EMAIL_PASS', '')
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL', '')

# 超话ID（房东的猫超话）
CONTAINER_ID = '10080801cfe03f62bd4032bff8cb8607eb17e0'

# ========== 邮件发送 ==========
def send_email(subject, content):
    """发送邮件通知"""
    if not EMAIL_USER or not EMAIL_PASS:
        print("未配置邮箱，跳过通知")
        return
    
    try:
        msg = MIMEText(content, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = NOTIFY_EMAIL or EMAIL_USER
        
        # 判断邮箱类型
        if 'qq.com' in EMAIL_USER:
            server = smtplib.SMTP_SSL('smtp.qq.com', 465)
        elif '163.com' in EMAIL_USER:
            server = smtplib.SMTP_SSL('smtp.163.com', 465)
        elif 'gmail.com' in EMAIL_USER:
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        else:
            server = smtplib.SMTP('smtp.qq.com', 587)
            server.starttls()
        
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"邮件发送成功: {subject}")
    except Exception as e:
        print(f"邮件发送失败: {e}")

# ========== Cookie解析 ==========
def parse_cookie(cookie_str):
    """解析Cookie字符串为字典"""
    cookies = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key] = value
    return cookies

# ========== 获取ST（微博签名参数）==========
def get_st(cookies):
    """获取微博请求签名参数st"""
    try:
        url = 'https://weibo.com/ajax/self/login/crossdomain'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://weibo.com/'
        }
        resp = requests.get(url, cookies=cookies, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 100000:
                return data.get('data', {}).get('st')
    except:
        pass
    return None

# ========== 签到主函数 ==========
def do_sign():
    """执行签到"""
    print(f"\n{'='*50}")
    print(f"开始签到 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")
    
    # 检查Cookie
    if not COOKIE_STR:
        error_msg = "错误: 未配置 WEIBO_COOKIE"
        print(error_msg)
        send_email("微博签到失败", f"<p>{error_msg}</p><p>请在GitHub Secrets中配置Cookie</p>")
        return False
    
    # 解析Cookie
    cookies = parse_cookie(COOKIE_STR)
    
    # 检查关键Cookie
    if 'SUB' not in cookies:
        error_msg = "Cookie无效: 缺少SUB字段"
        print(error_msg)
        send_email("微博签到失败", f"<p>{error_msg}</p><p>请重新获取Cookie</p>")
        return False
    
    print(f"✓ Cookie有效，SUB长度: {len(cookies['SUB'])}")
    
    # 获取st参数（部分接口需要）
    st = get_st(cookies)
    if st:
        print(f"✓ 获取st参数成功")
    
    # 签到API
    sign_url = 'https://i.huati.weibo.com/aj/super/checkin'
    
    # 构建请求参数
    params = {
        'id': CONTAINER_ID,
        'status': 0,
        'texta': '签到',
        'textb': '已签到',
        'api': 'http://i.huati.weibo.com/aj/super/checkin',
        '_t': int(time.time() * 1000)
    }
    
    if st:
        params['st'] = st
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://weibo.com/',
        'Accept': 'application/json, text/plain, */*'
    }
    
    try:
        print(f"正在请求签到接口...")
        resp = requests.get(sign_url, params=params, cookies=cookies, headers=headers, timeout=15)
        
        print(f"响应状态码: {resp.status_code}")
        print(f"响应内容: {resp.text}")
        
        if resp.status_code != 200:
            raise Exception(f"HTTP请求失败: {resp.status_code}")
        
        data = resp.json()
        code = data.get('code')
        msg = data.get('msg', '')
        
        # code=100000 表示成功
        if code == '100000' or code == 100000:
            print(f"\n✅ 签到成功! {msg}")
            send_email("微博签到成功", f"<p>签到成功！时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p><p>超话: 房东的猫</p>")
            return True
        elif code == '382004' or '已签到' in msg:
            print(f"\n📌 今日已签到过: {msg}")
            send_email("微博签到提醒", f"<p>今日已完成签到，无需重复操作。</p>")
            return True
        else:
            print(f"\n❌ 签到失败: code={code}, msg={msg}")
            send_email("微博签到失败", f"<p>签到失败</p><p>错误码: {code}</p><p>错误信息: {msg}</p><p>请手动检查超话页面。</p>")
            return False
            
    except requests.exceptions.RequestException as e:
        error_msg = f"网络请求异常: {e}"
        print(f"❌ {error_msg}")
        send_email("微博签到异常", f"<p>{error_msg}</p>")
        return False
    except json.JSONDecodeError as e:
        error_msg = f"响应解析失败: {e}, 原始响应: {resp.text[:200]}"
        print(f"❌ {error_msg}")
        send_email("微博签到异常", f"<p>{error_msg}</p>")
        return False
    except Exception as e:
        error_msg = f"未知错误: {e}"
        print(f"❌ {error_msg}")
        send_email("微博签到异常", f"<p>{error_msg}</p>")
        return False

# ========== 主入口 ==========
if __name__ == '__main__':
    try:
        result = do_sign()
        exit(0 if result else 1)
    except Exception as e:
        print(f"程序异常: {e}")
        send_email("微博签到异常", f"<p>程序运行异常: {e}</p>")
        exit(1)
