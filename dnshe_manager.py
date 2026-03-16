#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
import json
import urllib.request
import urllib.error
import os
import threading
from datetime import datetime, timedelta

# API配置
API_BASE_URL = "https://api005.dnshe.com/index.php"

# 密钥存储文件
KEYS_FILE = "api_keys.json"

# 可注册的根域名
ROOT_DOMAINS = ['cc.cd', 'us.ci', 'cn.mt', 'ccwu.cc', 'bbroot.com']

# 颜色主题
COLORS = {
    'bg': '#f5f7fa',
    'card_bg': '#ffffff',
    'primary': '#4a90d9',
    'primary_hover': '#3a7bc8',
    'success': '#52c41a',
    'danger': '#ff4d4f',
    'warning': '#faad14',
    'text': '#303133',
    'text_secondary': '#909399',
    'border': '#dcdfe6',
}


class DNSHEClient:
    """DNSHE API客户端"""
    
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
    
    def register_subdomain(self, subdomain, rootdomain):
        return self._request('subdomains', 'register', 'POST', {'subdomain': subdomain, 'rootdomain': rootdomain})
    
    def get_subdomain(self, subdomain_id):
        return self._request('subdomains', 'get', 'GET', {'subdomain_id': subdomain_id})
    
    def delete_subdomain(self, subdomain_id):
        return self._request('subdomains', 'delete', 'POST', {'subdomain_id': subdomain_id})
    
    def renew_subdomain(self, subdomain_id):
        return self._request('subdomains', 'renew', 'POST', {'subdomain_id': subdomain_id})
    
    def list_dns_records(self, subdomain_id):
        return self._request('dns_records', 'list', 'GET', {'subdomain_id': subdomain_id})
    
    def create_dns_record(self, subdomain_id, record_type, content, ttl=600, name=None, priority=None):
        data = {'subdomain_id': subdomain_id, 'type': record_type, 'content': content, 'ttl': ttl}
        if name: data['name'] = name
        if priority: data['priority'] = priority
        return self._request('dns_records', 'create', 'POST', data)
    
    def delete_dns_record(self, record_id):
        return self._request('dns_records', 'delete', 'POST', {'record_id': record_id})
    
    def get_quota(self):
        return self._request('quota', 'get')


class KeyManager:
    """API密钥管理器"""
    
    @staticmethod
    def load_keys():
        """从配置文件加载密钥"""
        if os.path.exists(KEYS_FILE):
            try:
                with open(KEYS_FILE, 'r', encoding='utf-8') as f:
                    keys = json.load(f)
                    if keys and isinstance(keys, list):
                        return keys
            except Exception as e:
                print(f"加载密钥失败: {e}")
        
        return []
    
    @staticmethod
    def save_keys(keys):
        with open(KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(keys, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def add_key(name, api_key, api_secret):
        keys = KeyManager.load_keys()
        keys.append({'name': name, 'api_key': api_key, 'api_secret': api_secret})
        KeyManager.save_keys(keys)
        return keys
    
    @staticmethod
    def remove_key(index):
        keys = KeyManager.load_keys()
        if 0 <= index < len(keys):
            keys.pop(index)
            KeyManager.save_keys(keys)
        return keys


class DNSHEManagerApp:
    """DNSHE域名管理程序"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("DNSHE 域名管理器")
        self.root.geometry("1100x750")
        self.root.configure(bg=COLORS['bg'])
        
        self.keys = KeyManager.load_keys()
        self.all_subdomains = []
        self.current_subdomain = None
        self.dns_records = []
        
        self._setup_style()
        self._setup_ui()
        
        # 启动时加载数据
        self._load_all_domains()
        
        # 启动时检查到期
        self.root.after(500, self._check_expiry)
    
    def _setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('TFrame', background=COLORS['bg'])
        style.configure('Card.TFrame', background=COLORS['card_bg'])
        style.configure('TLabel', background=COLORS['bg'], foreground=COLORS['text'], font=('微软雅黑', 10))
        style.configure('Card.TLabel', background=COLORS['card_bg'], foreground=COLORS['text'])
        style.configure('TLabelframe', background=COLORS['card_bg'], bordercolor=COLORS['border'])
        style.configure('TLabelframe.Label', background=COLORS['card_bg'], foreground=COLORS['primary'], 
                       font=('微软雅黑', 10, 'bold'))
    
    def _create_card(self, parent, **kwargs):
        return tk.Frame(parent, bg=COLORS['card_bg'], relief='flat', borderwidth=1, 
                        highlightbackground=COLORS['border'], highlightthickness=1, **kwargs)
    
    def _create_btn(self, parent, text, command, style_type):
        btn = tk.Button(parent, text=text, command=command, 
                       font=('微软雅黑', 9), relief='flat', cursor='hand2', padx=10, pady=4)
        
        if style_type == 'primary':
            btn.config(bg=COLORS['primary'], fg='white', activebackground=COLORS['primary_hover'], activeforeground='white')
        elif style_type == 'success':
            btn.config(bg=COLORS['success'], fg='white', activebackground='#47a617', activeforeground='white')
        elif style_type == 'danger':
            btn.config(bg=COLORS['danger'], fg='white', activebackground='#e64345', activeforeground='white')
        elif style_type == 'secondary':
            btn.config(bg=COLORS['text_secondary'], fg='white', activebackground='#7a7d83', activeforeground='white')
        
        return btn
    
    def _setup_ui(self):
        # 顶部标题栏
        header = tk.Frame(self.root, bg=COLORS['primary'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="🌐 DNSHE 域名管理器", bg=COLORS['primary'], 
                fg='white', font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT, padx=20)
        
        # 主容器
        main_container = tk.Frame(self.root, bg=COLORS['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # 顶部工具栏
        toolbar_card = self._create_card(main_container)
        toolbar_card.pack(fill=tk.X, pady=(0, 10))
        
        toolbar = tk.Frame(toolbar_card, bg=COLORS['card_bg'])
        toolbar.pack(padx=15, pady=10)
        
        self._create_btn(toolbar, "🔑 管理API密钥", self._open_key_manager, 'primary').pack(side=tk.LEFT, padx=5)
        self._create_btn(toolbar, "🔄 刷新全部", self._load_all_domains, 'secondary').pack(side=tk.LEFT, padx=5)
        
        # 内容区
        content_frame = tk.Frame(main_container, bg=COLORS['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧：域名列表
        left_card = self._create_card(content_frame)
        left_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        
        tk.Label(left_card, text="📋 全部域名列表", bg=COLORS['card_bg'], 
                font=('微软雅黑', 11, 'bold'), fg=COLORS['primary']).pack(anchor=tk.W, padx=15, pady=(12, 5))
        
        # 搜索栏
        search_frame = tk.Frame(left_card, bg=COLORS['card_bg'])
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Label(search_frame, text="🔍", bg=COLORS['card_bg']).pack(side=tk.LEFT)
        self.search_entry = tk.Entry(search_frame, font=('微软雅黑', 10), relief='flat', 
                                     highlightthickness=1, highlightbackground=COLORS['border'])
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind('<KeyRelease>', self._on_search)
        
        # 域名列表
        list_frame = tk.Frame(left_card, bg=COLORS['card_bg'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.domain_listbox = tk.Listbox(list_frame, font=('Consolas', 10), bg='#fafafa',
                                         fg=COLORS['text'], relief='flat', borderwidth=1,
                                         highlightbackground=COLORS['border'], highlightthickness=1,
                                         selectbackground=COLORS['primary'], selectforeground='white')
        self.domain_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.domain_listbox.bind('<<ListboxSelect>>', self._on_domain_selected)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.domain_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.domain_listbox.config(yscrollcommand=scrollbar.set)
        
        # 按钮栏
        btn_frame = tk.Frame(left_card, bg=COLORS['card_bg'])
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 12))
        
        self._create_btn(btn_frame, "➕ 注册域名", self._register_subdomain, 'success').pack(side=tk.LEFT, padx=3)
        self._create_btn(btn_frame, "🗑️ 删除域名", self._delete_subdomain, 'danger').pack(side=tk.LEFT, padx=3)
        self._create_btn(btn_frame, "⏰ 续期域名", self._renew_subdomain, 'primary').pack(side=tk.LEFT, padx=3)
        
        # 右侧面板
        right_frame = tk.Frame(content_frame, bg=COLORS['bg'])
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))
        
        # 域名详情
        detail_card = self._create_card(right_frame)
        detail_card.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(detail_card, text="📝 域名详情", bg=COLORS['card_bg'], 
                font=('微软雅黑', 11, 'bold'), fg=COLORS['primary']).pack(anchor=tk.W, padx=15, pady=(12, 5))
        
        self.detail_text = tk.Text(detail_card, height=12, font=('Consolas', 9), bg='#fafafa',
                                   fg=COLORS['text'], relief='flat', borderwidth=1,
                                   highlightbackground=COLORS['border'], highlightthickness=1)
        self.detail_text.pack(fill=tk.X, padx=15, pady=(0, 12))
        
        # DNS记录
        dns_card = self._create_card(right_frame)
        dns_card.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(dns_card, text="🔍 DNS记录", bg=COLORS['card_bg'], 
                font=('微软雅黑', 11, 'bold'), fg=COLORS['primary']).pack(anchor=tk.W, padx=15, pady=(12, 5))
        
        dns_list_frame = tk.Frame(dns_card, bg=COLORS['card_bg'])
        dns_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.dns_listbox = tk.Listbox(dns_list_frame, font=('Consolas', 10), bg='#fafafa',
                                      fg=COLORS['text'], relief='flat', borderwidth=1,
                                      highlightbackground=COLORS['border'], highlightthickness=1,
                                      selectbackground=COLORS['primary'], selectforeground='white')
        self.dns_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        dns_scrollbar = ttk.Scrollbar(dns_list_frame, orient=tk.VERTICAL, command=self.dns_listbox.yview)
        dns_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.dns_listbox.config(yscrollcommand=dns_scrollbar.set)
        
        # DNS按钮栏
        dns_btn_frame = tk.Frame(dns_card, bg=COLORS['card_bg'])
        dns_btn_frame.pack(fill=tk.X, padx=10, pady=(5, 12))
        
        self._create_btn(dns_btn_frame, "🔄 刷新记录", self._refresh_dns_records, 'secondary').pack(side=tk.LEFT, padx=3)
        self._create_btn(dns_btn_frame, "➕ 添加记录", self._add_dns_record, 'success').pack(side=tk.LEFT, padx=3)
        self._create_btn(dns_btn_frame, "🗑️ 删除记录", self._delete_dns_record, 'danger').pack(side=tk.LEFT, padx=3)
    
    def _load_all_domains(self):
        """加载所有密钥的域名"""
        self.all_subdomains = []
        self._show_loading(True)
        self.domain_listbox.delete(0, tk.END)
        self.domain_listbox.insert(0, "⏳ 正在加载域名数据...")
        
        def load_domains():
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            
            loaded_keys = 0
            total_keys = len(self.keys)
            subdomains_to_renew = []
            lock = threading.Lock()
            
            # 第一步：收集所有需要续期的域名
            for key in self.keys:
                try:
                    client = DNSHEClient(key['api_key'], key['api_secret'])
                    result = client.list_subdomains()
                    
                    if result.get('success'):
                        for sd in result.get('subdomains', []):
                            sd['_key_name'] = key['name']
                            sd['_key_index'] = self.keys.index(key)
                            subdomains_to_renew.append(sd)
                    else:
                        # 加载失败的key，记录一下
                        with lock:
                            self.all_subdomains.append({
                                'full_domain': f"❌ 加载失败: {key['name']} - {result.get('error', '未知错误')}",
                                'status': 'error',
                                '_key_name': key['name'],
                                '_key_index': self.keys.index(key)
                            })
                except Exception as e:
                    with lock:
                        self.all_subdomains.append({
                            'full_domain': f"❌ 加载失败: {key['name']} - {str(e)}",
                            'status': 'error',
                            '_key_name': key['name'],
                            '_key_index': self.keys.index(key)
                        })
                
                loaded_keys += 1
                # 更新加载进度
                progress = (loaded_keys / total_keys) * 100 if total_keys > 0 else 100
                self.root.after(0, lambda p=progress: self._update_loading_status(p))
            
            # 第二步：使用线程池并行执行续期操作
            def renew_domain(sd):
                try:
                    client = DNSHEClient(self.keys[sd['_key_index']]['api_key'], 
                                      self.keys[sd['_key_index']]['api_secret'])
                    renew_result = client.renew_subdomain(sd['id'])
                    return sd, renew_result
                except Exception as e:
                    return sd, {'success': False, 'error': str(e)}
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(renew_domain, sd): sd for sd in subdomains_to_renew}
                
                for future in as_completed(futures):
                    sd, renew_result = future.result()
                    
                    if renew_result.get('success'):
                        sd['_remaining_days'] = renew_result.get('remaining_days', 0)
                        sd['_new_expires_at'] = renew_result.get('new_expires_at', '')
                    else:
                        # 续期失败，记录错误信息
                        sd['_remaining_days'] = None
                        error_msg = renew_result.get('error', '未知错误')
                        sd['_renew_error'] = error_msg
                        # 如果是续期尚未可用，标记为 >180天
                        if 'not yet available' in error_msg.lower():
                            sd['_renew_not_available'] = True
                    
                    # 添加到列表
                    with lock:
                        self.all_subdomains.append(sd)
            
            self.root.after(0, self._finish_loading)
            
            self.root.after(0, self._finish_loading)
        
        threading.Thread(target=load_domains, daemon=True).start()
    
    def _show_loading(self, show):
        """显示/隐藏加载动画"""
        if show:
            if not hasattr(self, 'loading_frame'):
                self.loading_frame = tk.Frame(self.domain_listbox.master, bg=COLORS['card_bg'])
                self.loading_label = tk.Label(self.loading_frame, text="⏳ 加载中...", 
                                            bg='#fafafa', fg=COLORS['primary'], 
                                            font=('微软雅黑', 14))
                self.loading_label.pack(pady=20)
            
            self.loading_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=1, relheight=1)
            self.domain_listbox.config(state='disabled')
        else:
            if hasattr(self, 'loading_frame'):
                self.loading_frame.place_forget()
            self.domain_listbox.config(state='normal')
    
    def _update_loading_status(self, progress):
        """更新加载进度"""
        self.domain_listbox.delete(0, tk.END)
        self.domain_listbox.insert(0, f"⏳ 正在加载域名和剩余天数... {int(progress)}%")
    
    def _finish_loading(self):
        """加载完成"""
        self._show_loading(False)
        self._display_all_domains()
    
    def _display_all_domains(self):
        """显示所有域名"""
        self.domain_listbox.delete(0, tk.END)
        
        keyword = self.search_entry.get().strip().lower()
        
        # 过滤域名
        filtered = []
        for d in self.all_subdomains:
            if not keyword or keyword in d.get('full_domain', '').lower():
                filtered.append(d)
        
        if not filtered:
            self.domain_listbox.insert(0, "暂无域名")
            return
        
        for sd in filtered:
            # 处理错误信息
            if sd.get('status') == 'error':
                display = sd['full_domain']
                self.domain_listbox.insert(tk.END, display)
                continue
            
            # 使用续期操作获取的剩余天数
            days_left = sd.get('_remaining_days')
            
            # 显示格式
            status_icon = "✅" if sd['status'] == 'active' else "⏸️"
            key_tag = f"[{sd.get('_key_name', 'Unknown')}]"
            
            # 如果续期不可用，直接显示 >180天
            if sd.get('_renew_not_available'):
                display = f"{status_icon} {sd['full_domain']} {key_tag} 🟢 >180天"
            elif days_left is not None and isinstance(days_left, (int, float)):
                # 根据剩余天数显示不同颜色和警告
                if days_left <= 0:
                    days_str = f"🔴 已过期"
                elif days_left <= 30:
                    days_str = f"🔴 {int(days_left)}天"
                elif days_left <= 90:
                    days_str = f"🟡 {int(days_left)}天"
                else:
                    days_str = f"🟢 {int(days_left)}天"
                display = f"{status_icon} {sd['full_domain']} {key_tag} {days_str}"
            else:
                # 续期信息未获取到，显示状态
                display = f"{status_icon} {sd['full_domain']} {key_tag} [{sd.get('status', 'unknown')}]"
            
            self.domain_listbox.insert(tk.END, display)
    
    def _on_search(self, event):
        self._display_all_domains()
    
    def _on_domain_selected(self, event):
        selection = self.domain_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index < len(self.all_subdomains):
            keyword = self.search_entry.get().strip().lower()
            filtered = [d for d in self.all_subdomains if not keyword or keyword in d.get('full_domain', '').lower()]
            
            if index < len(filtered):
                self.current_subdomain = filtered[index]
                self._show_detail()
                self._refresh_dns_records()
    
    def _show_detail(self):
        self.detail_text.delete('1.0', tk.END)
        
        if not self.current_subdomain:
            return
        
        sd = self.current_subdomain
        detail = f"""所属密钥: {sd.get('_key_name', 'Unknown')}
ID: {sd.get('id')}
子域名: {sd.get('subdomain')}
根域名: {sd.get('rootdomain')}
完整域名: {sd.get('full_domain')}
状态: {sd.get('status')}
创建时间: {sd.get('created_at')}
更新时间: {sd.get('updated_at')}"""
        
        self.detail_text.insert('1.0', detail)
    
    def _get_current_client(self):
        if not self.current_subdomain:
            return None
        key_index = self.current_subdomain.get('_key_index', 0)
        if 0 <= key_index < len(self.keys):
            key = self.keys[key_index]
            return DNSHEClient(key['api_key'], key['api_secret'])
        return None
    
    def _register_subdomain(self):
        if not self.keys:
            messagebox.showwarning("警告", "请先添加API密钥")
            self._open_key_manager()
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("注册子域名")
        dialog.geometry("400x320")
        dialog.configure(bg=COLORS['card_bg'])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        form_frame = tk.Frame(dialog, bg=COLORS['card_bg'])
        form_frame.pack(padx=25, pady=20)
        
        # 选择密钥
        tk.Label(form_frame, text="API密钥:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=0, column=0, sticky=tk.W, pady=10)
        key_combo = ttk.Combobox(form_frame, values=[k['name'] for k in self.keys], width=25, state='readonly', font=('微软雅黑', 10))
        key_combo.current(0)
        key_combo.grid(row=0, column=1, padx=10)
        
        # 子域名
        tk.Label(form_frame, text="子域名:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=1, column=0, sticky=tk.W, pady=10)
        subdomain_entry = ttk.Entry(form_frame, width=27, font=('微软雅黑', 10))
        subdomain_entry.grid(row=1, column=1, padx=10)
        
        # 根域名
        tk.Label(form_frame, text="根域名:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=2, column=0, sticky=tk.W, pady=10)
        root_combo = ttk.Combobox(form_frame, values=ROOT_DOMAINS, width=25, state='readonly', font=('微软雅黑', 10))
        root_combo.current(0)
        root_combo.grid(row=2, column=1, padx=10)
        
        # 配额信息
        quota_frame = tk.Frame(dialog, bg='#f5f7fa', relief='flat', borderwidth=1, highlightbackground=COLORS['border'], highlightthickness=1)
        quota_frame.pack(fill=tk.X, padx=25, pady=(0, 10))
        
        tk.Label(quota_frame, text="📊 配额信息", bg='#f5f7fa', font=('微软雅黑', 9, 'bold'), fg=COLORS['primary']).pack(anchor=tk.W, padx=10, pady=(8, 5))
        
        quota_label = tk.Label(quota_frame, text="加载中...", bg='#f5f7fa', font=('微软雅黑', 9), fg=COLORS['text'])
        quota_label.pack(anchor=tk.W, padx=10, pady=(0, 8))
        
        # 更新配额信息的函数
        def update_quota():
            key_idx = key_combo.current()
            if key_idx >= 0 and key_idx < len(self.keys):
                # 先显示加载状态
                quota_label.config(text="⏳ 加载中...", fg=COLORS['text_secondary'])
                
                def load_quota_data():
                    key = self.keys[key_idx]
                    client = DNSHEClient(key['api_key'], key['api_secret'])
                    result = client.get_quota()
                    
                    def update_display():
                        if result.get('success'):
                            quota = result.get('quota', {})
                            available = quota.get('available', 0)
                            color = COLORS['success'] if available > 2 else COLORS['warning'] if available > 0 else COLORS['danger']
                            text = f"已用: {quota.get('used')} | 基础: {quota.get('base')} | 邀请奖励: {quota.get('invite_bonus')} | 总计: {quota.get('total')} | 可用: {available}"
                            quota_label.config(text=text, fg=color)
                        else:
                            quota_label.config(text=f"加载失败: {result.get('error', '未知错误')}", fg=COLORS['danger'])
                    
                    dialog.after(0, update_display)
                
                # 使用线程异步加载
                threading.Thread(target=load_quota_data, daemon=True).start()
        
        # 密钥选择改变时更新配额
        key_combo.bind('<<ComboboxSelected>>', lambda e: update_quota())
        
        # 初始加载配额
        def load_quota_initial():
            dialog.after(100, update_quota)
        
        btn_frame = tk.Frame(dialog, bg=COLORS['card_bg'])
        btn_frame.pack(pady=15)
        
        def do_register():
            key_idx = key_combo.current()
            subdomain = subdomain_entry.get().strip()
            rootdomain = root_combo.get()
            
            if not subdomain:
                messagebox.showwarning("警告", "请输入子域名")
                return
            
            key = self.keys[key_idx]
            client = DNSHEClient(key['api_key'], key['api_secret'])
            result = client.register_subdomain(subdomain, rootdomain)
            
            if result.get('success'):
                messagebox.showinfo("成功", f"子域名注册成功: {result.get('full_domain')}")
                dialog.destroy()
                self._load_all_domains()
            else:
                messagebox.showerror("错误", result.get('error', '注册失败'))
        
        self._create_btn(btn_frame, "➕ 注册", do_register, 'success').pack(side=tk.LEFT, padx=5)
        self._create_btn(btn_frame, "取消", dialog.destroy, 'secondary').pack(side=tk.LEFT, padx=5)
        
        # 启动时加载配额
        load_quota_initial()
    
    def _delete_subdomain(self):
        if not self.current_subdomain:
            messagebox.showwarning("警告", "请先选择要删除的域名")
            return
        
        sd = self.current_subdomain
        if messagebox.askyesno("确认", f"确定要删除域名 '{sd['full_domain']}' 吗?"):
            client = self._get_current_client()
            if client:
                result = client.delete_subdomain(sd['id'])
                if result.get('success'):
                    messagebox.showinfo("成功", "域名已删除")
                    self.current_subdomain = None
                    self.detail_text.delete('1.0', tk.END)
                    self.dns_listbox.delete(0, tk.END)
                    self._load_all_domains()
                else:
                    messagebox.showerror("错误", result.get('error', '删除失败'))
    
    def _renew_subdomain(self):
        if not self.current_subdomain:
            messagebox.showwarning("警告", "请先选择要续期的域名")
            return
        
        sd = self.current_subdomain
        if messagebox.askyesno("确认", f"确定要续期域名 '{sd['full_domain']}' 吗?"):
            client = self._get_current_client()
            if client:
                result = client.renew_subdomain(sd['id'])
                if result.get('success'):
                    msg = f"✅ 续期成功!\n\n剩余天数: {result.get('remaining_days')}天\n新到期时间: {result.get('new_expires_at')}"
                    messagebox.showinfo("成功", msg)
                    self._load_all_domains()
                else:
                    messagebox.showerror("错误", result.get('error', '续期失败'))
    
    def _refresh_dns_records(self):
        if not self.current_subdomain:
            return
        
        client = self._get_current_client()
        if not client:
            return
        
        def do_request():
            result = client.list_dns_records(self.current_subdomain['id'])
            self.root.after(0, lambda: self._display_dns_records(result))
        
        threading.Thread(target=do_request, daemon=True).start()
    
    def _display_dns_records(self, result):
        self.dns_listbox.delete(0, tk.END)
        
        if not result.get('success'):
            return
        
        records = result.get('records', [])
        self.dns_records = records
        
        if not records:
            self.dns_listbox.insert(0, "暂无DNS记录")
            return
        
        type_icons = {'A': '📍', 'AAAA': '📍', 'CNAME': '🔗', 'MX': '📧', 'TXT': '📝'}
        
        for record in records:
            icon = type_icons.get(record['type'], '📄')
            display = f"{icon} {record['type']}  {record['name']} → {record['content']}  [TTL:{record['ttl']}]"
            self.dns_listbox.insert(tk.END, display)
    
    def _add_dns_record(self):
        if not self.current_subdomain:
            messagebox.showwarning("警告", "请先选择域名")
            return
        
        client = self._get_current_client()
        if not client:
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("添加DNS记录")
        dialog.geometry("380x260")
        dialog.configure(bg=COLORS['card_bg'])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        form_frame = tk.Frame(dialog, bg=COLORS['card_bg'])
        form_frame.pack(padx=25, pady=20)
        
        tk.Label(form_frame, text="记录类型:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=0, column=0, sticky=tk.W, pady=10)
        type_combo = ttk.Combobox(form_frame, values=['A', 'AAAA', 'CNAME', 'MX', 'TXT'], width=22, font=('微软雅黑', 10), state='readonly')
        type_combo.current(0)
        type_combo.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(form_frame, text="记录值:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=1, column=0, sticky=tk.W, pady=10)
        content_entry = ttk.Entry(form_frame, width=25, font=('Consolas', 10))
        content_entry.grid(row=1, column=1, padx=10, pady=10)
        
        tk.Label(form_frame, text="TTL:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=2, column=0, sticky=tk.W, pady=10)
        ttl_entry = ttk.Entry(form_frame, width=25, font=('微软雅黑', 10))
        ttl_entry.insert(0, '600')
        ttl_entry.grid(row=2, column=1, padx=10, pady=10)
        
        tk.Label(form_frame, text="记录名:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=3, column=0, sticky=tk.W, pady=10)
        name_entry = ttk.Entry(form_frame, width=25, font=('微软雅黑', 10))
        name_entry.grid(row=3, column=1, padx=10, pady=10)
        
        btn_frame = tk.Frame(dialog, bg=COLORS['card_bg'])
        btn_frame.pack(pady=15)
        
        def do_create():
            record_type = type_combo.get()
            content = content_entry.get().strip()
            ttl = ttl_entry.get().strip()
            name = name_entry.get().strip()
            
            if not content:
                messagebox.showwarning("警告", "请填写记录值")
                return
            
            try:
                ttl = int(ttl) if ttl else 600
            except ValueError:
                ttl = 600
            
            result = client.create_dns_record(
                self.current_subdomain['id'], record_type, content, ttl, name if name else None
            )
            
            if result.get('success'):
                messagebox.showinfo("成功", "DNS记录创建成功")
                dialog.destroy()
                self._refresh_dns_records()
            else:
                messagebox.showerror("错误", result.get('error', '创建失败'))
        
        self._create_btn(btn_frame, "➕ 创建", do_create, 'success').pack(side=tk.LEFT, padx=5)
        self._create_btn(btn_frame, "取消", dialog.destroy, 'secondary').pack(side=tk.LEFT, padx=5)
    
    def _delete_dns_record(self):
        selection = self.dns_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的DNS记录")
            return
        
        client = self._get_current_client()
        if not client:
            return
        
        index = selection[0]
        if index < len(self.dns_records):
            record = self.dns_records[index]
            if messagebox.askyesno("确认", f"确定要删除DNS记录 '{record['name']}' 吗?"):
                result = client.delete_dns_record(record['id'])
                
                if result.get('success'):
                    messagebox.showinfo("成功", "DNS记录已删除")
                    self._refresh_dns_records()
                else:
                    messagebox.showerror("错误", result.get('error', '删除失败'))
    
    def _open_key_manager(self):
        """打开密钥管理窗口"""
        KeyManagerWindow(self.root, self.keys, self._on_keys_changed)
    
    def _on_keys_changed(self):
        """密钥变更回调"""
        self.keys = KeyManager.load_keys()
        self._load_all_domains()
    
    def _check_expiry(self):
        """检查域名到期并提醒"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        expiring_domains = []
        lock = threading.Lock()
        
        def check():
            # 收集所有域名
            all_subdomains = []
            for key in self.keys:
                client = DNSHEClient(key['api_key'], key['api_secret'])
                result = client.list_subdomains()
                if result.get('success'):
                    for sd in result.get('subdomains', []):
                        sd['_key_index'] = self.keys.index(key)
                        all_subdomains.append(sd)
            
            # 使用线程池并行执行续期操作
            def renew_domain(sd):
                try:
                    client = DNSHEClient(self.keys[sd['_key_index']]['api_key'], 
                                      self.keys[sd['_key_index']]['api_secret'])
                    renew_result = client.renew_subdomain(sd['id'])
                    return sd, renew_result
                except Exception as e:
                    return sd, {'success': False, 'error': str(e)}
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(renew_domain, sd): sd for sd in all_subdomains}
                
                for future in as_completed(futures):
                    sd, renew_result = future.result()
                    
                    if renew_result.get('success'):
                        days_left = renew_result.get('remaining_days', 0)
                        expires_at = renew_result.get('new_expires_at', '未知')
                        
                        if 0 < days_left <= 180:
                            with lock:
                                expiring_domains.append({
                                    'domain': sd['full_domain'],
                                    'days': days_left,
                                    'expires': expires_at,
                                    'key': self.keys[sd['_key_index']]['name']
                                })
        
        def on_done():
            if expiring_domains:
                # 按剩余天数排序
                expiring_domains.sort(key=lambda x: x['days'])
                
                msg = "⚠️ 以下域名即将到期（不足180天）:\n\n"
                for d in expiring_domains:
                    color = "🔴" if d['days'] <= 30 else "🟡" if d['days'] <= 90 else "🟢"
                    msg += f"{color} {d['domain']}\n   剩余: {d['days']}天 | 到期: {d['expires']} | 密钥: {d['key']}\n\n"
                
                msg += "请及时续期！"
                messagebox.showwarning("域名到期提醒", msg)
        
        threading.Thread(target=lambda: (check(), self.root.after(0, on_done())), daemon=True).start()


class KeyManagerWindow:
    """密钥管理窗口"""
    
    def __init__(self, parent, keys, callback):
        self.parent = parent
        self.keys = list(keys)
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title("API密钥管理")
        self.window.geometry("950x500")
        self.window.configure(bg=COLORS['bg'])
        self.window.transient(parent)
        self.window.grab_set()
        
        self._setup_ui()
        self._refresh_key_list()
    
    def _setup_ui(self):
        # 标题
        header = tk.Frame(self.window, bg=COLORS['primary'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="🔑 API密钥管理", bg=COLORS['primary'], 
                fg='white', font=('微软雅黑', 16, 'bold')).pack(side=tk.LEFT, padx=20)
        
        # 主容器
        main_frame = tk.Frame(self.window, bg=COLORS['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # 左侧：密钥列表
        left_card = tk.Frame(self.window, bg=COLORS['card_bg'], relief='flat', borderwidth=1, 
                            highlightbackground=COLORS['border'], highlightthickness=1)
        left_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 8), pady=15, ipadx=20)
        
        tk.Label(left_card, text="📋 密钥列表", bg=COLORS['card_bg'], 
                font=('微软雅黑', 11, 'bold'), fg=COLORS['primary']).pack(anchor=tk.W, padx=15, pady=(12, 5))
        
        # 密钥列表
        list_frame = tk.Frame(left_card, bg=COLORS['card_bg'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.key_listbox = tk.Listbox(list_frame, font=('Consolas', 10), bg='#fafafa',
                                      fg=COLORS['text'], relief='flat', borderwidth=1,
                                      highlightbackground=COLORS['border'], highlightthickness=1,
                                      selectbackground=COLORS['primary'], selectforeground='white')
        self.key_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.key_listbox.bind('<<ListboxSelect>>', self._on_key_selected)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.key_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.key_listbox.config(yscrollcommand=scrollbar.set)
        
        # 按钮
        btn_frame = tk.Frame(left_card, bg=COLORS['card_bg'])
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 12))
        
        self._create_btn(btn_frame, "➕ 添加", self._add_key, 'success').pack(side=tk.LEFT, padx=3)
        self._create_btn(btn_frame, "🗑️ 删除", self._delete_key, 'danger').pack(side=tk.LEFT, padx=3)
        
        # 右侧：详情和配额
        right_frame = tk.Frame(self.window, bg=COLORS['bg'])
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(8, 15), pady=15)
        
        # 密钥详情
        detail_card = tk.Frame(right_frame, bg=COLORS['card_bg'], relief='flat', borderwidth=1, 
                              highlightbackground=COLORS['border'], highlightthickness=1)
        detail_card.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(detail_card, text="🔍 密钥详情", bg=COLORS['card_bg'], 
                font=('微软雅黑', 11, 'bold'), fg=COLORS['primary']).pack(anchor=tk.W, padx=15, pady=(12, 5))
        
        self.key_detail_text = tk.Text(detail_card, height=5, font=('Consolas', 9), bg='#fafafa',
                                       fg=COLORS['text'], relief='flat', borderwidth=1,
                                       highlightbackground=COLORS['border'], highlightthickness=1)
        self.key_detail_text.pack(fill=tk.X, padx=15, pady=(0, 12))
        
        # 配额信息
        quota_card = tk.Frame(right_frame, bg=COLORS['card_bg'], relief='flat', borderwidth=1, 
                             highlightbackground=COLORS['border'], highlightthickness=1)
        quota_card.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(quota_card, text="📊 配额信息", bg=COLORS['card_bg'], 
                font=('微软雅黑', 11, 'bold'), fg=COLORS['primary']).pack(anchor=tk.W, padx=15, pady=(12, 5))
        
        self.quota_text = tk.Text(quota_card, font=('Consolas', 10), bg='#fafafa',
                                  fg=COLORS['text'], relief='flat', borderwidth=1,
                                  highlightbackground=COLORS['border'], highlightthickness=1)
        self.quota_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 12))
        
        # 底部按钮
        bottom_frame = tk.Frame(self.window, bg=COLORS['bg'])
        bottom_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        self._create_btn(bottom_frame, "💾 保存并关闭", self._save_and_close, 'primary').pack(side=tk.RIGHT)
    
    def _create_btn(self, parent, text, command, style_type):
        btn = tk.Button(parent, text=text, command=command, 
                       font=('微软雅黑', 9), relief='flat', cursor='hand2', padx=10, pady=4)
        
        if style_type == 'primary':
            btn.config(bg=COLORS['primary'], fg='white', activebackground=COLORS['primary_hover'], activeforeground='white')
        elif style_type == 'success':
            btn.config(bg=COLORS['success'], fg='white', activebackground='#47a617', activeforeground='white')
        elif style_type == 'danger':
            btn.config(bg=COLORS['danger'], fg='white', activebackground='#e64345', activeforeground='white')
        elif style_type == 'secondary':
            btn.config(bg=COLORS['text_secondary'], fg='white', activebackground='#7a7d83', activeforeground='white')
        
        return btn
    
    def _refresh_key_list(self):
        self.key_listbox.delete(0, tk.END)
        
        for key in self.keys:
            self.key_listbox.insert(tk.END, f"📌 {key['name']} ({key['api_key'][:15]}...)")
    
    def _on_key_selected(self, event):
        selection = self.key_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index < len(self.keys):
            key = self.keys[index]
            self.key_detail_text.delete('1.0', tk.END)
            self.key_detail_text.insert('1.0', f"名称: {key['name']}\nAPI Key: {key['api_key']}\nAPI Secret: {key['api_secret']}")
            
            # 获取配额
            client = DNSHEClient(key['api_key'], key['api_secret'])
            result = client.get_quota()
            
            self.quota_text.delete('1.0', tk.END)
            if result.get('success'):
                quota = result.get('quota', {})
                self.quota_text.insert('1.0', f"✅ 配额查询成功\n\n已用: {quota.get('used')}\n基础配额: {quota.get('base')}\n邀请奖励: {quota.get('invite_bonus')}\n总计: {quota.get('total')}\n可用: {quota.get('available')}")
            else:
                self.quota_text.insert('1.0', f"❌ 配额查询失败\n\n{result.get('error', '未知错误')}")
    
    def _add_key(self):
        dialog = tk.Toplevel(self.window)
        dialog.title("添加API密钥")
        dialog.geometry("400x250")
        dialog.configure(bg=COLORS['card_bg'])
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        form_frame = tk.Frame(dialog, bg=COLORS['card_bg'])
        form_frame.pack(padx=25, pady=20)
        
        tk.Label(form_frame, text="密钥名称:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=0, column=0, sticky=tk.W, pady=12)
        name_entry = ttk.Entry(form_frame, width=35, font=('微软雅黑', 10))
        name_entry.grid(row=0, column=1, padx=10)
        
        tk.Label(form_frame, text="API Key:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=1, column=0, sticky=tk.W, pady=12)
        api_key_entry = ttk.Entry(form_frame, width=35, font=('Consolas', 10))
        api_key_entry.grid(row=1, column=1, padx=10)
        
        tk.Label(form_frame, text="API Secret:", bg=COLORS['card_bg'], font=('微软雅黑', 10)).grid(row=2, column=0, sticky=tk.W, pady=12)
        api_secret_entry = ttk.Entry(form_frame, width=35, font=('Consolas', 10), show='*')
        api_secret_entry.grid(row=2, column=1, padx=10)
        
        show_var = tk.BooleanVar()
        tk.Checkbutton(form_frame, text="显示Secret", bg=COLORS['card_bg'], variable=show_var,
                       command=lambda: api_secret_entry.config(show='' if show_var.get() else '*')).grid(row=3, column=1, sticky=tk.W)
        
        btn_frame = tk.Frame(dialog, bg=COLORS['card_bg'])
        btn_frame.pack(pady=15)
        
        def save_key():
            name = name_entry.get().strip()
            api_key = api_key_entry.get().strip()
            api_secret = api_secret_entry.get().strip()
            
            if not name or not api_key or not api_secret:
                messagebox.showwarning("警告", "请填写所有字段")
                return
            
            self.keys.append({'name': name, 'api_key': api_key, 'api_secret': api_secret})
            self._refresh_key_list()
            dialog.destroy()
        
        self._create_btn(btn_frame, "💾 保存", save_key, 'primary').pack(side=tk.LEFT, padx=5)
        self._create_btn(btn_frame, "取消", dialog.destroy, 'secondary').pack(side=tk.LEFT, padx=5)
    
    def _delete_key(self):
        selection = self.key_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的密钥")
            return
        
        index = selection[0]
        key = self.keys[index]
        
        if messagebox.askyesno("确认", f"确定要删除密钥 '{key['name']}' 吗?"):
            self.keys.pop(index)
            self._refresh_key_list()
            self.key_detail_text.delete('1.0', tk.END)
            self.quota_text.delete('1.0', tk.END)
    
    def _save_and_close(self):
        KeyManager.save_keys(self.keys)
        self.callback()
        self.window.destroy()


def main():
    root = tk.Tk()
    app = DNSHEManagerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
