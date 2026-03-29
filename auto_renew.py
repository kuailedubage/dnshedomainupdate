#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

API_BASE_URL = "https://api005.dnshe.com/index.php"

class DNSHEClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _request(self, endpoint, action, method='GET', data=None):
        url = f"{API_BASE_URL}?m=domain_hub&endpoint={endpoint}&action={action}"
        
        headers = {
            'X-API-Key': self.api_key,
            'X-API-Secret': self.api_secret,
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'GET':
                req = urllib.request.Request(url, headers=headers)
            else:
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode('utf-8'))
                return {'success': False, 'error': error_body.get('error', str(e))}
            except:
                return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_subdomains(self):
        return self._request('subdomains', 'list')
    
    def renew_subdomain(self, subdomain_id):
        return self._request('subdomains', 'renew', 'POST', {'subdomain_id': subdomain_id})

class WeChatNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    def send(self, title, content, mentioned_list=None):
        if not self.webhook_url:
            print("未配置企业微信 Webhook URL")
            return False
        
        data = {
            "msgtype": "text",
            "text": {
                "content": f"{title}\n\n{content}"
            }
        }
        
        if mentioned_list:
            data["text"]["mentioned_list"] = mentioned_list
        
        try:
            response = requests.post(self.webhook_url, json=data, timeout=10)
            result = response.json()
            
            if result.get('errcode') == 0:
                print("企业微信通知发送成功")
                return True
            else:
                print(f"企业微信通知发送失败: {result.get('errmsg')}")
                return False
        except Exception as e:
            print(f"企业微信通知发送异常: {e}")
            return False

def parse_api_keys(api_keys_str):
    if not api_keys_str:
        return []
    
    try:
        keys = json.loads(api_keys_str)
        if isinstance(keys, list):
            return keys
        return []
    except:
        return []

def load_api_keys_from_file(file_path='api_keys.json'):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                keys = json.load(f)
                if keys and isinstance(keys, list):
                    return keys
        except Exception as e:
            print(f"从文件加载密钥失败: {e}")
    return []

def load_api_keys():
    api_keys_str = os.environ.get('API_KEYS', '')
    
    if api_keys_str:
        keys = parse_api_keys(api_keys_str)
        if keys:
            print(f"从环境变量加载了 {len(keys)} 个 API 密钥")
            return keys
    
    keys = load_api_keys_from_file()
    if keys:
        print(f"从文件加载了 {len(keys)} 个 API 密钥")
        return keys
    
    print("错误: 未找到 API 密钥配置")
    return []

def renew_all_domains(keys, force_renew=False):
    results = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }
    
    all_subdomains = []
    
    for key in keys:
        try:
            client = DNSHEClient(key['api_key'], key['api_secret'])
            result = client.list_subdomains()
            
            if result.get('success'):
                for sd in result.get('subdomains', []):
                    sd['_key_name'] = key['name']
                    sd['_key_index'] = keys.index(key)
                    all_subdomains.append(sd)
            else:
                results['failed'] += 1
                results['details'].append({
                    'domain': f"加载失败: {key['name']}",
                    'status': 'error',
                    'error': result.get('error', '未知错误')
                })
        except Exception as e:
            results['failed'] += 1
            results['details'].append({
                'domain': f"加载失败: {key['name']}",
                'status': 'error',
                'error': str(e)
            })
    
    results['total'] = len(all_subdomains)
    
    def renew_domain(sd):
        try:
            client = DNSHEClient(keys[sd['_key_index']]['api_key'], 
                                keys[sd['_key_index']]['api_secret'])
            renew_result = client.renew_subdomain(sd['id'])
            return sd, renew_result
        except Exception as e:
            return sd, {'success': False, 'error': str(e)}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(renew_domain, sd): sd for sd in all_subdomains}
        
        for future in as_completed(futures):
            sd, renew_result = future.result()
            
            detail = {
                'domain': sd['full_domain'],
                'key_name': sd.get('_key_name', 'Unknown'),
                'status': 'success' if renew_result.get('success') else 'failed'
            }
            
            if renew_result.get('success'):
                results['success'] += 1
                detail['remaining_days'] = renew_result.get('remaining_days', 0)
                detail['new_expires_at'] = renew_result.get('new_expires_at', '')
                detail['message'] = renew_result.get('message', '')
            else:
                error_msg = renew_result.get('error', '未知错误')
                
                if 'not yet available' in error_msg.lower():
                    results['skipped'] += 1
                    detail['status'] = 'skipped'
                    detail['message'] = '续期尚未可用'
                else:
                    results['failed'] += 1
                    detail['error'] = error_msg
            
            results['details'].append(detail)
    
    return results

def generate_log(results):
    log_lines = []
    log_lines.append("=" * 60)
    log_lines.append(f"域名续期日志 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append("=" * 60)
    log_lines.append("")
    log_lines.append(f"总计: {results['total']} 个域名")
    log_lines.append(f"成功: {results['success']} 个")
    log_lines.append(f"失败: {results['failed']} 个")
    log_lines.append(f"跳过: {results['skipped']} 个")
    log_lines.append("")
    log_lines.append("=" * 60)
    log_lines.append("详细结果:")
    log_lines.append("=" * 60)
    
    for detail in results['details']:
        if detail['status'] == 'success':
            log_lines.append(f"✅ {detail['domain']} ({detail['key_name']})")
            log_lines.append(f"   剩余天数: {detail['remaining_days']} 天")
            log_lines.append(f"   到期时间: {detail['new_expires_at']}")
        elif detail['status'] == 'skipped':
            log_lines.append(f"⏭️  {detail['domain']} ({detail['key_name']})")
            log_lines.append(f"   {detail['message']}")
        elif detail['status'] == 'error':
            log_lines.append(f"❌ {detail['domain']}")
            log_lines.append(f"   错误: {detail['error']}")
        else:
            log_lines.append(f"❌ {detail['domain']} ({detail['key_name']})")
            log_lines.append(f"   错误: {detail.get('error', '未知错误')}")
        log_lines.append("")
    
    return '\n'.join(log_lines)

def generate_wechat_message(results):
    lines = []
    lines.append(f"域名自动续期报告")
    lines.append(f"")
    lines.append(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"")
    lines.append(f"统计信息:")
    lines.append(f"- 总计: {results['total']} 个")
    lines.append(f"- 成功: {results['success']} 个")
    lines.append(f"- 失败: {results['failed']} 个")
    lines.append(f"- 跳过: {results['skipped']} 个")
    lines.append(f"")
    
    if results['failed'] > 0:
        lines.append(f"失败详情:")
        for detail in results['details']:
            if detail['status'] in ['failed', 'error']:
                error = detail.get('error', '未知错误')
                lines.append(f"- {detail.get('domain', 'Unknown')}: {error}")
        lines.append(f"")
    
    if results['success'] > 0:
        lines.append(f"成功续期:")
        success_count = 0
        for detail in results['details']:
            if detail['status'] == 'success' and success_count < 5:
                lines.append(f"- {detail['domain']}: {detail['remaining_days']} 天")
                success_count += 1
        if results['success'] > 5:
            lines.append(f"- ... 还有 {results['success'] - 5} 个域名")
        lines.append(f"")
    
    return '\n'.join(lines)

def main():
    print("开始执行域名自动续期...")
    print("=" * 60)
    
    force_renew = os.environ.get('FORCE_RENEW', 'false').lower() == 'true'
    webhook_url = os.environ.get('WEBHOOK_URL', '')
    
    keys = load_api_keys()
    if not keys:
        print("错误: 无法加载 API 密钥")
        sys.exit(1)
    
    print(f"找到 {len(keys)} 个 API 密钥")
    print(f"强制续期: {'是' if force_renew else '否'}")
    print(f"企业微信通知: {'启用' if webhook_url else '未启用'}")
    print("=" * 60)
    
    results = renew_all_domains(keys, force_renew)
    
    log_content = generate_log(results)
    
    with open('renewal_log.txt', 'w', encoding='utf-8') as f:
        f.write(log_content)
    
    print(log_content)
    print("=" * 60)
    print("日志已保存到 renewal_log.txt")
    
    if webhook_url:
        print("正在发送企业微信通知...")
        notifier = WeChatNotifier(webhook_url)
        
        title = "域名自动续期完成" if results['failed'] == 0 else "域名自动续期完成(有失败)"
        content = generate_wechat_message(results)
        
        if results['failed'] > 0:
            notifier.send(title, content, mentioned_list=['@all'])
        else:
            notifier.send(title, content)
    
    print("执行完成!")
    
    if results['failed'] > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
