#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微博超话签到 - 增强版（带重试和备用接口）
"""

import os
import re
import time
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========== 配置 ==========
COOKIE_STR = os.environ.get('WEIBO_COOKIE', '')
EMAIL_USER = os.environ.get('EMAIL_USER', '')
EMAIL_PASS = os.environ.get('EMAIL_PASS', '')
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL', '')

# 超话ID（房东的猫超话）
CONTAINER_ID = '10080801cfe03f62bd4032bff8cb8607eb17e0'

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒

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

# ========== 创建带重试的Session ==========
def create_session():
    """创建带重试机制的Session"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

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

# ========== 方法1：直接API签到 ==========
def sign_via_api(cookies, session):
    """通过直接API签到"""
    sign_url = 'https://i.huati.weibo.com/aj/super/checkin'
    
    params = {
        'id': CONTAINER_ID,
        'status': 0,
        'texta': '签到',
        'textb': '已签到',
        'api': 'http://i.huati.weibo.com/aj/super/checkin',
        '_t': int(time.time() * 1000)
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://weibo.com/',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    print(f"请求URL: {sign_url}")
    print(f"请求参数: {params}")
    
    resp = session.get(sign_url, params=params, cookies=cookies, headers=headers, timeout=30)
    return resp

# ========== 方法2：通过移动端接口签到 ==========
def sign_via_mobile(cookies, session):
    """通过移动端接口签到（备用）"""
    sign_url = 'https://m.weibo.cn/api/container/getIndex'
    
    params = {
        'containerid': CONTAINER_ID,
        'luicode': '10000011',
        'lfid': '100103type=1&q=房东的猫',
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
        'Referer': 'https://m.weibo.cn/',
        'Accept': 'application/json, text/plain, */*',
    }
    
    resp = session.get(sign_url, params=params, cookies=cookies, headers=headers, timeout=30)
    return resp

# ========== 方法3：通过weibo.com主站签到 ==========
def sign_via_weibo(cookies, session):
    """通过weibo.com主站签到（备用）"""
    # 先访问超话页面获取token
    page_url = f'https://weibo.com/p/{CONTAINER_ID}/super_index'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    print(f"访问超话页面: {page_url}")
    resp = session.get(page_url, cookies=cookies, headers=headers, timeout=30)
    
    if resp.status_code != 200:
        return None
    
    # 尝试从页面提取签到API
    import re
    # 查找action-data中的签到信息
    pattern = r'action-data="([^"]*checkin[^"]*)"'
    matches = re.findall(pattern, resp.text)
    
    for match in matches:
        if 'checkin' in match:
            print(f"找到签到配置: {match}")
            # 解析参数
            params = {}
            for item in match.split('&'):
                if '=' in item:
                    k, v = item.split('=', 1)
                    params[k] = v
            
            if 'id' in params:
                sign_url = 'https://i.huati.weibo.com/aj/super/checkin'
                params['_t'] = int(time.time() * 1000)
                
                sign_headers = {
                    'User-Agent': headers['User-Agent'],
                    'Referer': page_url,
                    'X-Requested-With': 'XMLHttpRequest',
                }
                
                return session.get(sign_url, params=params, cookies=cookies, headers=sign_headers, timeout=30)
    
    return None

# ========== 签到主函数 ==========
def do_sign():
    """执行签到（带重试和备用方案）"""
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
    print(f"✓ SUB前缀: {cookies['SUB'][:20]}...")
    
    # 创建带重试的session
    session = create_session()
    
    # 尝试多种签到方法
    methods = [
        ("直接API", sign_via_api),
        ("移动端接口", sign_via_mobile),
        ("主站页面", sign_via_weibo),
    ]
    
    for method_name, method_func in methods:
        print(f"\n--- 尝试方法: {method_name} ---")
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"第{attempt}次尝试...")
                
                if method_name == "移动端接口":
                    resp = method_func(cookies, session)
                    # 移动端接口只是获取页面信息，需要额外处理签到
                    if resp and resp.status_code == 200:
                        data = resp.json()
                        if data.get('ok') == 1:
                            print("✓ 移动端访问成功")
                            # 这里可以继续尝试其他签到方式
                            continue
                elif method_name == "主站页面":
                    resp = method_func(cookies, session)
                    if resp and resp.status_code == 200:
                        try:
                            data = resp.json()
                            code = str(data.get('code', ''))
                            if code == '100000' or '成功' in str(data):
                                print(f"✓ 签到成功!")
                                send_email("微博签到成功", f"<p>签到成功！时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
                                return True
                        except:
                            pass
                else:
                    # 直接API签到
                    resp = method_func(cookies, session)
                    
                    if resp.status_code != 200:
                        print(f"HTTP状态码: {resp.status_code}")
                        continue
                    
                    print(f"响应内容: {resp.text[:200]}")
                    
                    try:
                        data = resp.json()
                        code = str(data.get('code', ''))
                        msg = data.get('msg', '')
                        
                        if code == '100000' or code == '100000':
                            print(f"\n✅ 签到成功! {msg}")
                            send_email("微博签到成功", f"<p>签到成功！时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
                            return True
                        elif code == '382004' or '已签到' in msg or '重复' in msg:
                            print(f"\n📌 今日已签到过: {msg}")
                            send_email("微博签到提醒", f"<p>今日已完成签到，无需重复操作。</p>")
                            return True
                        elif 'login' in msg.lower() or '未登录' in msg:
                            print(f"⚠️ Cookie可能失效: {msg}")
                            raise Exception("Cookie失效")
                        else:
                            print(f"⚠️ 签到响应: code={code}, msg={msg}")
                    except json.JSONDecodeError:
                        print(f"响应不是JSON格式")
                        continue
                
                if attempt < MAX_RETRIES:
                    print(f"等待{RETRY_DELAY}秒后重试...")
                    time.sleep(RETRY_DELAY)
                    
            except requests.exceptions.Timeout:
                print(f"超时，第{attempt}次尝试失败")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
            except Exception as e:
                print(f"错误: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
        
        print(f"方法 '{method_name}' 所有尝试均失败")
    
    # 所有方法都失败
    error_msg = "所有签到方法均失败"
    print(f"\n❌ {error_msg}")
    send_email("微博签到失败", f"<p>{error_msg}</p><p>请检查网络和Cookie状态。</p><p>Cookie前缀: {cookies.get('SUB', '')[:30]}...</p>")
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
