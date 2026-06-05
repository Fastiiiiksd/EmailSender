import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import re
from datetime import datetime
import pickle
import json
import tempfile
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64
import shutil

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

CREDENTIALS_JSON = {
    "installed": {
        "client_id": "541987852254-1q6ko2d10k7bdtst83lta5l96lqnn23v.apps.googleusercontent.com",
        "project_id": "mailsend-498510",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "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",
        "redirect_uris": ["http://localhost"]
    }
}

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind('<Enter>', self.show_tip)
        widget.bind('<Leave>', self.hide_tip)
    
    def show_tip(self, event):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT, background="#ffffe0", 
                        relief="solid", borderwidth=1, font=("Segoe UI", 10))
        label.pack()
    
    def hide_tip(self, event):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class SentHistoryWindow:
    def __init__(self, parent, history_file):
        self.window = tk.Toplevel(parent)
        self.window.title("История отправок")
        self.window.geometry("1100x650")
        self.window.configure(bg='#f0f2f5')
        self.history_file = history_file
        self.load_history()
        self.create_widgets()
    
    def load_history(self):
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self.history = json.load(f)
        else:
            self.history = []
    
    def create_widgets(self):
        main_frame = tk.Frame(self.window, bg='#f0f2f5')
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        header_frame = tk.Frame(main_frame, bg='#f0f2f5')
        header_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(header_frame, text="ИСТОРИЯ ОТПРАВОК", font=("Segoe UI", 18, "bold"), bg='#f0f2f5', fg='#1a1a2e').pack(side="left")
        
        info_label = tk.Label(header_frame, text=f"Всего записей: {len(self.history)}", bg='#f0f2f5', fg='#666', font=("Segoe UI", 11))
        info_label.pack(side="right")
        
        tree_frame = tk.Frame(main_frame, bg='#f0f2f5')
        tree_frame.pack(fill="both", expand=True)
        
        scroll_y = tk.Scrollbar(tree_frame)
        scroll_y.pack(side="right", fill="y")
        scroll_x = tk.Scrollbar(tree_frame, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")
        
        columns = ("Дата и время", "Организация", "Email", "Статус")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, height=25)
        
        col_widths = [180, 380, 280, 200]
        for col, width in zip(columns, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width)
        
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        
        self.tree.pack(fill="both", expand=True)
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        for item in reversed(self.history[-500:]):
            self.tree.insert("", "end", values=item)
        
        btn_frame = tk.Frame(main_frame, bg='#f0f2f5')
        btn_frame.pack(fill="x", pady=(15, 0))
        
        btn_clear = tk.Button(btn_frame, text="Очистить историю", command=self.clear_history,
                              bg='#dc3545', fg='white', font=("Segoe UI", 10, "bold"), 
                              padx=20, pady=8, cursor="hand2", relief="ridge", bd=3)
        btn_clear.pack(side="right", padx=5)
        
        btn_refresh = tk.Button(btn_frame, text="Обновить", command=self.refresh,
                                bg='#007bff', fg='white', font=("Segoe UI", 10, "bold"), 
                                padx=20, pady=8, cursor="hand2", relief="ridge", bd=3)
        btn_refresh.pack(side="right", padx=5)
    
    def clear_history(self):
        if messagebox.askyesno("Подтверждение", "Очистить всю историю? Это действие нельзя отменить."):
            self.history = []
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f)
            self.refresh()
    
    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in reversed(self.history[-500:]):
            self.tree.insert("", "end", values=item)

class OrgDetailWindow:
    def __init__(self, parent, org_data):
        self.window = tk.Toplevel(parent)
        self.window.configure(bg='#f0f2f5')
        name = str(org_data.get('Наименование организации', 'Н/Д'))[:60]
        self.window.title("Информация об организации: " + name)
        self.window.geometry("1000x750")
        self.create_widgets(org_data)
    
    def create_widgets(self, org_data):
        main_frame = tk.Frame(self.window, bg='#f0f2f5')
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        tk.Label(main_frame, text="ИНФОРМАЦИЯ ОБ ОРГАНИЗАЦИИ", font=("Segoe UI", 16, "bold"), 
                bg='#f0f2f5', fg='#1a1a2e').pack(pady=(0, 15))
        
        canvas = tk.Canvas(main_frame, bg='#f0f2f5', highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        row = 0
        for key, value in org_data.items():
            if pd.isna(value):
                value = ""
            
            card = tk.Frame(scrollable_frame, bg='white', relief="solid", bd=1)
            card.grid(row=row, column=0, sticky="ew", padx=10, pady=6)
            card.columnconfigure(1, weight=1)
            
            tk.Label(card, text=key, font=("Segoe UI", 11, "bold"),
                     bg='white', fg='#1a1a2e', anchor="w", width=30).grid(row=0, column=0, sticky="nw", padx=15, pady=15)
            
            text_widget = scrolledtext.ScrolledText(card, width=55, height=3, wrap=tk.WORD,
                                                    bg='#f8f9fa', fg='#333', font=("Segoe UI", 10), relief="flat")
            text_widget.grid(row=0, column=1, padx=15, pady=15, sticky="ew")
            text_widget.insert("1.0", str(value))
            text_widget.config(state=tk.DISABLED)
            
            row += 1
        
        scrollable_frame.columnconfigure(0, weight=1)

class EmailSenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mass Email Sender")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f2f5')
        
        self.df = None
        self.file_path = None
        self.service = None
        self.user_email = None
        self.stop_flag = False
        self.sent_organizations = set()
        self.history_file = "sent_history.json"
        self.attachments = []
        
        self.limit_value = 0
        self.delay_value = 1
        self.delete_sent = False
        self.save_history = True
        self.current_filter = "Все"
        
        self.load_settings()
        self.create_widgets()
    
    def extract_emails(self, value):
        if pd.isna(value):
            return []
        text = str(value)
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return emails
    
    def extract_phones(self, value):
        if pd.isna(value):
            return []
        text = str(value)
        phones = re.findall(r'\+?\d[\d\s\-\(\)]{7,}\d', text)
        if not phones:
            phones = re.findall(r'\d{10,11}', text)
        phones = [p for p in phones if len(re.sub(r'\D', '', p)) >= 10]
        return phones
    
    def format_email_display(self, emails):
        if not emails:
            return "Нет"
        if len(emails) == 1:
            return emails[0][:35]
        return emails[0][:30] + " (+" + str(len(emails)-1) + ")"
    
    def format_phone_display(self, phones):
        if not phones:
            return "Нет"
        phones_clean = [re.sub(r'\s+', ' ', p)[:20] for p in phones[:2]]
        if len(phones) == 1:
            return phones_clean[0]
        return phones_clean[0] + " (+" + str(len(phones)-1) + ")"
    
    def load_settings(self):
        if os.path.exists("settings.json"):
            with open("settings.json", "r", encoding='utf-8') as f:
                settings = json.load(f)
                self.limit_value = settings.get("limit", 0)
                self.delay_value = settings.get("delay", 1)
                self.delete_sent = settings.get("delete_sent", False)
                self.save_history = settings.get("save_history", True)
    
    def save_settings(self):
        settings = {
            "limit": self.limit_value,
            "delay": self.delay_value,
            "delete_sent": self.delete_sent,
            "save_history": self.save_history
        }
        with open("settings.json", "w", encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    
    def get_credentials_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(CREDENTIALS_JSON, f)
            return f.name
    
    def add_attachment(self):
        files = filedialog.askopenfilenames(title="Выберите файлы для вложения", 
                                            filetypes=[("Все файлы", "*.*")])
        for file in files:
            if file not in self.attachments:
                self.attachments.append(file)
                self.attachments_listbox.insert(tk.END, os.path.basename(file))
        self.log(f"Добавлено файлов: {len(files)}")
    
    def remove_attachment(self):
        selection = self.attachments_listbox.curselection()
        if selection:
            idx = selection[0]
            self.attachments.pop(idx)
            self.attachments_listbox.delete(idx)
            self.log("Файл удален из вложений")
    
    def clear_attachments(self):
        self.attachments = []
        self.attachments_listbox.delete(0, tk.END)
        self.log("Все вложения удалены")
    
    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.create_main_tab()
        self.create_org_tab()
    
    def create_main_tab(self):
        main_tab = tk.Frame(self.notebook, bg='#f0f2f5')
        self.notebook.add(main_tab, text="Рассылка")
        
        left_frame = tk.Frame(main_tab, bg='white', relief="solid", bd=1)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))
        
        right_frame = tk.Frame(main_tab, bg='white', relief="solid", bd=1)
        right_frame.pack(side="right", fill="both", expand=True, padx=(8, 0))
        
        tk.Label(left_frame, text="АВТОРИЗАЦИЯ", font=("Segoe UI", 13, "bold"), 
                bg='white', fg='#1a1a2e').pack(anchor="w", padx=20, pady=(20, 10))
        
        auth_row = tk.Frame(left_frame, bg='white')
        auth_row.pack(fill="x", padx=20, pady=5)
        
        self.auth_btn = tk.Button(auth_row, text="Авторизовать Gmail", command=self.auth_gmail, 
                                  bg='#28a745', fg='white', font=("Segoe UI", 11, "bold"), 
                                  padx=25, pady=10, cursor="hand2", relief="ridge", bd=3)
        self.auth_btn.pack(side="left")
        
        self.user_email_label = tk.Label(auth_row, text="", bg='white', fg='#6c757d', font=("Segoe UI", 10))
        self.user_email_label.pack(side="left", padx=15)
        
        tk.Label(left_frame, text="ЗАГРУЗКА ФАЙЛА", font=("Segoe UI", 13, "bold"), 
                bg='white', fg='#1a1a2e').pack(anchor="w", padx=20, pady=(20, 10))
        
        file_row = tk.Frame(left_frame, bg='white')
        file_row.pack(fill="x", padx=20, pady=5)
        
        self.file_label = tk.Label(file_row, text="Файл не выбран", bg='#e9ecef', fg='#6c757d', 
                                   font=("Segoe UI", 11), padx=12, pady=10, relief="sunken")
        self.file_label.pack(side="left", fill="x", expand=True)
        
        btn_load = tk.Button(file_row, text="Выбрать файл", command=self.load_file, 
                            bg='#007bff', fg='white', font=("Segoe UI", 11, "bold"), 
                            padx=25, pady=8, cursor="hand2", relief="ridge", bd=3)
        btn_load.pack(side="right", padx=(10, 0))
        
        tk.Label(left_frame, text="ТЕКСТ ПИСЬМА", font=("Segoe UI", 13, "bold"), 
                bg='white', fg='#1a1a2e').pack(anchor="w", padx=20, pady=(20, 10))
        
        tk.Label(left_frame, text="Тема письма:", bg='white', fg='#495057', font=("Segoe UI", 11)).pack(anchor="w", padx=20, pady=(5, 0))
        self.subject_entry = tk.Entry(left_frame, font=("Segoe UI", 12), bg='#f8f9fa', relief="solid", bd=1)
        self.subject_entry.pack(fill="x", padx=20, pady=5)
        self.subject_entry.insert(0, "Коммерческое предложение")
        
        tk.Label(left_frame, text="Текст письма:", bg='white', fg='#495057', font=("Segoe UI", 11)).pack(anchor="w", padx=20, pady=(10, 0))
        self.body_text = scrolledtext.ScrolledText(left_frame, height=10, wrap=tk.WORD, 
                                                   font=("Segoe UI", 11), bg='#f8f9fa', relief="solid", bd=1)
        self.body_text.pack(fill="both", expand=True, padx=20, pady=5)
        
        example = "Уважаемые партнеры!\n\nПредлагаем вам сотрудничество в области производства кухонной мебели.\n\nЖдем вашего ответа.\n\nС уважением,\nОтдел продаж"
        self.body_text.insert("1.0", example)
        
        tk.Label(left_frame, text="ВЛОЖЕНИЯ", font=("Segoe UI", 13, "bold"), 
                bg='white', fg='#1a1a2e').pack(anchor="w", padx=20, pady=(10, 5))
        
        attach_frame = tk.Frame(left_frame, bg='white')
        attach_frame.pack(fill="x", padx=20, pady=5)
        
        btn_add_attach = tk.Button(attach_frame, text="+ Добавить файлы", command=self.add_attachment,
                                   bg='#ffc107', fg='#1a1a2e', font=("Segoe UI", 10, "bold"),
                                   padx=15, pady=5, cursor="hand2", relief="ridge", bd=3)
        btn_add_attach.pack(side="left", padx=5)
        
        btn_remove_attach = tk.Button(attach_frame, text="- Удалить выбранный", command=self.remove_attachment,
                                      bg='#dc3545', fg='white', font=("Segoe UI", 10, "bold"),
                                      padx=15, pady=5, cursor="hand2", relief="ridge", bd=3)
        btn_remove_attach.pack(side="left", padx=5)
        
        btn_clear_attach = tk.Button(attach_frame, text="Очистить все", command=self.clear_attachments,
                                     bg='#6c757d', fg='white', font=("Segoe UI", 10, "bold"),
                                     padx=15, pady=5, cursor="hand2", relief="ridge", bd=3)
        btn_clear_attach.pack(side="left", padx=5)
        
        attach_list_frame = tk.Frame(left_frame, bg='white', relief="solid", bd=1)
        attach_list_frame.pack(fill="x", padx=20, pady=5)
        
        self.attachments_listbox = tk.Listbox(attach_list_frame, height=4, font=("Segoe UI", 9), bg='#f8f9fa')
        self.attachments_listbox.pack(fill="x", padx=5, pady=5)
        
        tk.Label(left_frame, text="Вложено файлов: 0", font=("Segoe UI", 9), bg='white', fg='#6c757d').pack(anchor="w", padx=20, pady=(0, 10))
        
        tk.Label(right_frame, text="УПРАВЛЕНИЕ", font=("Segoe UI", 13, "bold"), 
                bg='white', fg='#1a1a2e').pack(anchor="w", padx=20, pady=(20, 10))
        
        control_frame = tk.Frame(right_frame, bg='white')
        control_frame.pack(fill="x", padx=20, pady=10)
        
        self.send_btn = tk.Button(control_frame, text="НАЧАТЬ РАССЫЛКУ", command=self.start_sending, 
                                  bg='#28a745', fg='white', font=("Segoe UI", 12, "bold"), 
                                  padx=30, pady=12, cursor="hand2", relief="ridge", bd=3, state=tk.DISABLED)
        self.send_btn.pack(side="left", padx=5)
        
        self.history_btn = tk.Button(control_frame, text="ИСТОРИЯ", command=self.open_history, 
                                     bg='#6f42c1', fg='white', font=("Segoe UI", 11, "bold"), 
                                     padx=20, pady=12, cursor="hand2", relief="ridge", bd=3)
        self.history_btn.pack(side="left", padx=5)
        
        sort_frame = tk.Frame(control_frame, bg='white')
        sort_frame.pack(side="left", padx=5)
        
        self.sort_btn = tk.Button(sort_frame, text="СОРТИРОВАТЬ ФАЙЛЫ ?", command=self.sort_files, 
                                  bg='#17a2b8', fg='white', font=("Segoe UI", 11, "bold"), 
                                  padx=20, pady=12, cursor="hand2", relief="ridge", bd=3)
        self.sort_btn.pack(side="left")
        
        sort_tip = ("СОРТИРОВКА ФАЙЛОВ - как это работает:\n\n"
                   "Кнопка создает папку 'Сортированные' рядом с исходным файлом\n"
                   "и внутри создает 4 файла:\n"
                   "• ТОЛЬКО ТЕЛЕФОН - организации только с телефоном\n"
                   "• ТОЛЬКО EMAIL - организации только с email\n"
                   "• ЕСТЬ ВСЕ - организации с email и телефоном\n"
                   "• НЕТ КОНТАКТОВ - организации без контактов\n\n"
                   "Поле 'Email' в Excel:\n"
                   "Может содержать несколько адресов через запятую или пробел\n\n"
                   "Пример валидного Email:\n"
                   "company@mail.ru, info@firma.com, sales@domain.ru\n\n"
                   "Поле 'Телефон' в Excel:\n"
                   "Может содержать несколько номеров\n\n"
                   "Примеры валидных телефонов:\n"
                   "+7(495)123-45-67, 89161234567, 8-916-123-45-67")
        ToolTip(self.sort_btn, sort_tip)
        
        settings_frame = tk.Frame(right_frame, bg='white', relief="solid", bd=1)
        settings_frame.pack(fill="x", padx=20, pady=15)
        
        tk.Label(settings_frame, text="НАСТРОЙКИ", font=("Segoe UI", 11, "bold"), 
                bg='white', fg='#1a1a2e').pack(anchor="w", padx=15, pady=(10, 5))
        
        limit_row = tk.Frame(settings_frame, bg='white')
        limit_row.pack(fill="x", padx=15, pady=5)
        
        tk.Label(limit_row, text="Лимит организаций:", bg='white', fg='#495057', font=("Segoe UI", 10), width=18, anchor="w").pack(side="left")
        self.limit_spin = tk.Spinbox(limit_row, from_=0, to=10000, width=12, font=("Segoe UI", 10), 
                                     command=self.update_limit, relief="solid", bd=1)
        self.limit_spin.pack(side="left", padx=10)
        self.limit_spin.delete(0, tk.END)
        self.limit_spin.insert(0, str(self.limit_value))
        
        limit_help = tk.Button(limit_row, text="?", font=("Segoe UI", 9, "bold"), 
                               bg='#6c757d', fg='white', width=2, height=1,
                               relief="ridge", bd=2, cursor="hand2")
        limit_help.pack(side="left", padx=5)
        limit_tip = ("ЛИМИТ ОРГАНИЗАЦИЙ\n\n"
                    "Ограничивает количество организаций,\n"
                    "которым будет отправлена рассылка.\n\n"
                    "0 - без лимита (отправляет всем)\n"
                    "1-10000 - максимальное количество\n\n"
                    "Пример: если поставить 50, то отправка\n"
                    "прекратится после 50 успешных организаций")
        ToolTip(limit_help, limit_tip)
        
        delay_row = tk.Frame(settings_frame, bg='white')
        delay_row.pack(fill="x", padx=15, pady=5)
        tk.Label(delay_row, text="Задержка (секунд):", bg='white', fg='#495057', font=("Segoe UI", 10), width=18, anchor="w").pack(side="left")
        self.delay_spin = tk.Spinbox(delay_row, from_=0.5, to=10, increment=0.5, width=12, 
                                     font=("Segoe UI", 10), command=self.update_delay, relief="solid", bd=1)
        self.delay_spin.pack(side="left", padx=10)
        self.delay_spin.delete(0, tk.END)
        self.delay_spin.insert(0, str(self.delay_value))
        
        delay_help = tk.Button(delay_row, text="?", font=("Segoe UI", 9, "bold"), 
                               bg='#6c757d', fg='white', width=2, height=1,
                               relief="ridge", bd=2, cursor="hand2")
        delay_help.pack(side="left", padx=5)
        delay_tip = ("ЗАДЕРЖКА МЕЖДУ ПИСЬМАМИ\n\n"
                    "Пауза между отправкой каждого письма.\n\n"
                    "Рекомендуемые значения:\n"
                    "0.5-1 сек - для быстрой рассылки (до 500 писем)\n"
                    "2-3 сек - для большого объема (1000+ писем)\n"
                    "5-10 сек - чтобы не попасть в спам\n\n"
                    "Большая задержка снижает риск блокировки")
        ToolTip(delay_help, delay_tip)
        
        self.delete_var = tk.BooleanVar(value=self.delete_sent)
        cb_delete = tk.Checkbutton(settings_frame, text="Удалять отправленные организации из файла", 
                                   variable=self.delete_var, bg='white', fg='#495057', 
                                   font=("Segoe UI", 10), command=self.update_delete)
        cb_delete.pack(anchor="w", padx=15, pady=5)
        
        self.history_var = tk.BooleanVar(value=self.save_history)
        cb_history = tk.Checkbutton(settings_frame, text="Сохранять историю отправок", 
                                   variable=self.history_var, bg='white', fg='#495057', 
                                   font=("Segoe UI", 10), command=self.update_history)
        cb_history.pack(anchor="w", padx=15, pady=(0, 10))
        
        self.progress = ttk.Progressbar(right_frame, mode='determinate', length=400)
        self.progress.pack(pady=15, padx=20)
        
        self.status_label = tk.Label(right_frame, text="Готов к работе", bg='white', fg='#28a745', 
                                    font=("Segoe UI", 12, "bold"))
        self.status_label.pack(pady=5)
        
        log_frame = tk.LabelFrame(right_frame, text="ЖУРНАЛ ОТПРАВКИ", bg='white', fg='#1a1a2e', 
                                  font=("Segoe UI", 11, "bold"), relief="solid", bd=1)
        log_frame.pack(fill="both", expand=True, padx=20, pady=15)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD, 
                                                  font=("Consolas", 10), bg='#1e1e2e', fg='#a6e22e')
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
    
    def create_org_tab(self):
        org_tab = tk.Frame(self.notebook, bg='#f0f2f5')
        self.notebook.add(org_tab, text="Организации")
        
        top_frame = tk.Frame(org_tab, bg='#f0f2f5')
        top_frame.pack(fill="x", pady=15, padx=20)
        
        filter_frame = tk.Frame(top_frame, bg='#f0f2f5')
        filter_frame.pack(fill="x", pady=(0, 10))
        
        tk.Label(filter_frame, text="Фильтр:", bg='#f0f2f5', fg='#495057', font=("Segoe UI", 11)).pack(side="left", padx=5)
        
        self.filter_var = tk.StringVar(value="Все")
        filters = ["Все", "Только с email", "Только с телефоном", "Есть и email и телефон", "Нет контактов", "По алфавиту А-Я", "По алфавиту Я-А"]
        
        filter_menu = ttk.Combobox(filter_frame, textvariable=self.filter_var, values=filters, 
                                   width=25, font=("Segoe UI", 10), state="readonly")
        filter_menu.pack(side="left", padx=5)
        filter_menu.bind("<<ComboboxSelected>>", self.apply_filter)
        
        tk.Label(top_frame, text="Поиск:", bg='#f0f2f5', fg='#495057', font=("Segoe UI", 11)).pack(side="left", padx=5)
        self.search_entry = tk.Entry(top_frame, font=("Segoe UI", 11), width=30, relief="solid", bd=1)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", self.search_orgs)
        
        btn_refresh = tk.Button(top_frame, text="Обновить", command=self.refresh_org_list, 
                                bg='#007bff', fg='white', font=("Segoe UI", 10, "bold"), 
                                padx=15, pady=6, cursor="hand2", relief="ridge", bd=3)
        btn_refresh.pack(side="left", padx=5)
        
        info_label = tk.Label(top_frame, text="Двойной клик - подробная информация", bg='#f0f2f5', fg='#6c757d', font=("Segoe UI", 10))
        info_label.pack(side="right", padx=10)
        
        tree_frame = tk.Frame(org_tab, bg='#f0f2f5')
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        scroll_y = tk.Scrollbar(tree_frame)
        scroll_y.pack(side="right", fill="y")
        scroll_x = tk.Scrollbar(tree_frame, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")
        
        columns = ("№", "Организация", "ИНН", "Регион", "Email", "Телефоны", "Статус")
        self.org_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                      yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, height=25)
        
        widths = [50, 350, 120, 180, 220, 180, 100]
        for col, width in zip(columns, widths):
            self.org_tree.heading(col, text=col)
            self.org_tree.column(col, width=width)
        
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        
        self.org_tree.pack(fill="both", expand=True)
        scroll_y.config(command=self.org_tree.yview)
        scroll_x.config(command=self.org_tree.xview)
        
        self.org_tree.bind("<Double-1>", self.on_org_double_click)
        
        self.refresh_org_list()
    
    def apply_filter(self, event=None):
        self.current_filter = self.filter_var.get()
        self.refresh_org_list()
    
    def update_limit(self):
        try:
            self.limit_value = int(self.limit_spin.get())
            self.save_settings()
        except:
            pass
    
    def update_delay(self):
        try:
            self.delay_value = float(self.delay_spin.get())
            self.save_settings()
        except:
            pass
    
    def update_delete(self):
        self.delete_sent = self.delete_var.get()
        self.save_settings()
    
    def update_history(self):
        self.save_history = self.history_var.get()
        self.save_settings()
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, "[" + timestamp + "] " + message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def auth_gmail(self):
        if self.service is not None:
            reply = messagebox.askyesno("Деавторизация", "Вы уже авторизованы. Хотите деавторизоваться?")
            if reply:
                self.service = None
                self.user_email = None
                self.auth_btn.config(text="Авторизовать Gmail", bg='#28a745')
                self.user_email_label.config(text="")
                self.send_btn.config(state=tk.DISABLED)
                self.log("Деавторизация выполнена")
            return
        
        creds = None
        token_file = 'token.pickle'
        
        self.log("Авторизация в Gmail...")
        
        if os.path.exists(token_file):
            with open(token_file, 'rb') as t:
                creds = pickle.load(t)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.log("Токен обновлен")
            else:
                creds_file = self.get_credentials_file()
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
                os.unlink(creds_file)
                self.log("Новая авторизация пройдена")
            
            with open(token_file, 'wb') as t:
                pickle.dump(creds, t)
        
        self.service = build('gmail', 'v1', credentials=creds)
        
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            self.user_email = profile.get('emailAddress', 'Почта не определена')
        except:
            self.user_email = 'Почта не определена'
        
        self.auth_btn.config(text="Деавторизовать", bg='#dc3545')
        self.user_email_label.config(text=self.user_email)
        self.log("Gmail авторизован успешно: " + self.user_email)
        if self.df is not None:
            self.send_btn.config(state=tk.NORMAL)
    
    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if not path:
            return
        try:
            self.df = pd.read_excel(path)
            self.file_path = path
            self.file_label.config(text=os.path.basename(path) + " (" + str(len(self.df)) + " организаций)", bg='#d4edda', fg='#155724')
            self.log("Загружено " + str(len(self.df)) + " организаций из " + os.path.basename(path))
            self.refresh_org_list()
            if self.service:
                self.send_btn.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            self.log("Ошибка загрузки: " + str(e))
    
    def refresh_org_list(self):
        if self.df is None:
            return
        
        for item in self.org_tree.get_children():
            self.org_tree.delete(item)
        
        name_col = 'Наименование организации' if 'Наименование организации' in self.df.columns else self.df.columns[1]
        inn_col = 'ИНН' if 'ИНН' in self.df.columns else None
        region_col = 'Регион' if 'Регион' in self.df.columns else None
        phone_col = None
        email_col = None
        
        for col in self.df.columns:
            if 'телефон' in col.lower() or 'phone' in col.lower() or 'тел' in col.lower():
                phone_col = col
            if 'почт' in col.lower() or 'email' in col.lower() or 'mail' in col.lower():
                email_col = col
        
        search_text = self.search_entry.get().lower()
        
        data_rows = []
        for idx, row in self.df.iterrows():
            org_name = str(row[name_col])[:60] if pd.notna(row[name_col]) else "Н/Д"
            
            if search_text and search_text not in org_name.lower():
                continue
            
            inn = str(row[inn_col])[:15] if inn_col and pd.notna(row[inn_col]) else "—"
            region = str(row[region_col])[:25] if region_col and pd.notna(row[region_col]) else "—"
            
            emails = self.extract_emails(row[email_col]) if email_col else []
            has_email = len(emails) > 0
            email_str = self.format_email_display(emails)
            
            phones = self.extract_phones(row[phone_col]) if phone_col else []
            has_phone = len(phones) > 0
            phone_str = self.format_phone_display(phones)
            
            status = "Отправлено" if idx in self.sent_organizations else "Ожидает"
            
            if self.current_filter == "Только с email" and (not has_email or has_phone):
                continue
            if self.current_filter == "Только с телефоном" and (not has_phone or has_email):
                continue
            if self.current_filter == "Есть и email и телефон" and not (has_email and has_phone):
                continue
            if self.current_filter == "Нет контактов" and (has_email or has_phone):
                continue
            
            data_rows.append((idx, org_name, inn, region, email_str, phone_str, status, has_email, has_phone))
        
        if self.current_filter == "По алфавиту А-Я":
            data_rows.sort(key=lambda x: x[1].lower())
        elif self.current_filter == "По алфавиту Я-А":
            data_rows.sort(key=lambda x: x[1].lower(), reverse=True)
        
        for idx, (orig_idx, org_name, inn, region, email_str, phone_str, status, _, _) in enumerate(data_rows):
            self.org_tree.insert("", "end", values=(idx+1, org_name, inn, region, email_str, phone_str, status))
    
    def search_orgs(self, event=None):
        self.refresh_org_list()
    
    def on_org_double_click(self, event):
        selection = self.org_tree.selection()
        if not selection:
            return
        item = self.org_tree.item(selection[0])
        values = item['values']
        if values and self.df is not None:
            idx = values[0] - 1
            row_data = []
            for i, row in self.df.iterrows():
                if i == idx or (self.current_filter != "Все" and i == idx):
                    actual_idx = i
                    break
            else:
                actual_idx = idx
            if 0 <= actual_idx < len(self.df):
                OrgDetailWindow(self.root, self.df.iloc[actual_idx].to_dict())
    
    def sort_files(self):
        if self.df is None:
            messagebox.showwarning("Нет данных", "Сначала загрузите файл")
            return
        
        email_col = None
        phone_col = None
        
        for col in self.df.columns:
            if 'почт' in col.lower() or 'email' in col.lower() or 'mail' in col.lower():
                email_col = col
            if 'телефон' in col.lower() or 'phone' in col.lower() or 'тел' in col.lower():
                phone_col = col
        
        if email_col is None:
            messagebox.showwarning("Нет email", "Колонка с email не найдена")
            return
        
        def has_email(v):
            return len(self.extract_emails(v)) > 0 if pd.notna(v) else False
        
        def has_phone(v):
            return len(self.extract_phones(v)) > 0 if pd.notna(v) else False
        
        mask_email = self.df[email_col].apply(has_email)
        mask_phone = self.df[phone_col].apply(has_phone) if phone_col else pd.Series([False] * len(self.df))
        
        only_phone = self.df[~mask_email & mask_phone]
        only_email = self.df[mask_email & ~mask_phone]
        both = self.df[mask_email & mask_phone]
        none = self.df[~mask_email & ~mask_phone]
        
        base_dir = os.path.dirname(self.file_path)
        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        
        sort_folder = os.path.join(base_dir, "Сортированные")
        folder_counter = 1
        original_folder = sort_folder
        while os.path.exists(sort_folder):
            sort_folder = original_folder + "_" + str(folder_counter)
            folder_counter += 1
        
        os.makedirs(sort_folder, exist_ok=True)
        
        only_phone.to_excel(os.path.join(sort_folder, base_name + "_ТОЛЬКО_ТЕЛЕФОН.xlsx"), index=False)
        only_email.to_excel(os.path.join(sort_folder, base_name + "_ТОЛЬКО_EMAIL.xlsx"), index=False)
        both.to_excel(os.path.join(sort_folder, base_name + "_ЕСТЬ_ВСЕ.xlsx"), index=False)
        none.to_excel(os.path.join(sort_folder, base_name + "_НЕТ_КОНТАКТОВ.xlsx"), index=False)
        
        self.log("Сортировка завершена: телефоны=" + str(len(only_phone)) + ", email=" + str(len(only_email)) + ", есть всё=" + str(len(both)) + ", нет контактов=" + str(len(none)))
        self.log("Файлы сохранены в папку: " + sort_folder)
        messagebox.showinfo("Готово", f"Создано 4 файла в папке:\n{sort_folder}")
    
    def send_one_with_attachments(self, to_email, subject, body, attachments):
        try:
            msg = MIMEMultipart()
            msg['to'] = to_email
            msg['subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
                        msg.attach(part)
            
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            self.service.users().messages().send(userId='me', body={'raw': raw}).execute()
            return True, None
        except Exception as e:
            return False, str(e)
    
    def open_history(self):
        SentHistoryWindow(self.root, self.history_file)
    
    def stop_sending(self):
        self.stop_flag = True
        self.log("Остановка рассылки...")
        self.status_label.config(text="Остановлено", fg='#dc3545')
        self.send_btn.config(text="НАЧАТЬ РАССЫЛКУ", bg='#28a745', command=self.start_sending)
    
    def add_to_history(self, org_name, email, status):
        if not self.save_history:
            return
        entry = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), org_name, email, status]
        history = []
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        history.append(entry)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    
    def send_thread(self, email_col, subject, body, name_col, limit, delete_sent, save_history, delay, attachments):
        if self.service is None:
            self.log("ОШИБКА: Не авторизован")
            return
        
        orgs_to_send = []
        for idx, row in self.df.iterrows():
            if idx in self.sent_organizations:
                continue
            emails = self.extract_emails(row[email_col])
            if emails:
                org_name = str(row[name_col]) if pd.notna(row[name_col]) else "Организация " + str(idx+1)
                orgs_to_send.append((idx, org_name, emails))
        
        if limit > 0:
            orgs_to_send = orgs_to_send[:limit]
        
        total_orgs = len(orgs_to_send)
        if total_orgs == 0:
            self.log("Нет организаций для отправки")
            self.status_label.config(text="Нет организаций", fg='#dc3545')
            self.send_btn.config(state=tk.NORMAL, text="НАЧАТЬ РАССЫЛКУ", bg='#28a745', command=self.start_sending)
            return
        
        self.log("Найдено организаций для отправки: " + str(total_orgs))
        if attachments:
            self.log("Вложено файлов: " + str(len(attachments)) + " - " + ", ".join([os.path.basename(a) for a in attachments]))
        self.status_label.config(text="Отправка 0/" + str(total_orgs), fg='#007bff')
        
        sent_orgs = []
        total_emails_sent = 0
        failed_emails = 0
        
        for org_idx, (idx, org_name, emails) in enumerate(orgs_to_send):
            if self.stop_flag:
                self.log("Остановлено пользователем")
                break
            
            self.log("\n[" + str(org_idx+1) + "/" + str(total_orgs) + "] " + org_name[:50])
            self.log("   Email адресов: " + str(len(emails)))
            
            org_success = True
            
            for email in emails:
                if self.stop_flag:
                    break
                
                self.status_label.config(text="Отправка " + str(org_idx+1) + "/" + str(total_orgs) + " - " + email[:35])
                self.progress['value'] = (org_idx / total_orgs) * 100
                self.root.update_idletasks()
                
                import time
                time.sleep(delay)
                
                ok, err = self.send_one_with_attachments(email, subject, body, attachments)
                
                if ok:
                    total_emails_sent += 1
                    self.log("   УСПЕШНО: " + email)
                    self.add_to_history(org_name, email, "Успешно")
                else:
                    failed_emails += 1
                    org_success = False
                    self.log("   ОШИБКА: " + email + " - " + err[:100])
                    self.add_to_history(org_name, email, "Ошибка: " + err[:50])
            
            if org_success:
                sent_orgs.append(idx)
                self.sent_organizations.add(idx)
                self.log("   Организация обработана успешно")
            else:
                self.log("   Были ошибки при отправке")
            
            self.progress['value'] = ((org_idx + 1) / total_orgs) * 100
            self.status_label.config(text="Отправлено " + str(org_idx+1) + "/" + str(total_orgs))
            self.refresh_org_list()
        
        self.log("\n" + "="*60)
        self.log("ИТОГОВАЯ СТАТИСТИКА:")
        self.log("   Организаций обработано: " + str(len(sent_orgs)) + "/" + str(total_orgs))
        self.log("   Писем отправлено: " + str(total_emails_sent))
        self.log("   Ошибок: " + str(failed_emails))
        self.log("="*60)
        
        if delete_sent and sent_orgs:
            self.df = self.df.drop(index=sent_orgs).reset_index(drop=True)
            self.sent_organizations.clear()
            if self.file_path:
                self.df.to_excel(self.file_path, index=False)
                self.log("Удалено " + str(len(sent_orgs)) + " организаций из исходного файла")
            self.refresh_org_list()
        
        self.status_label.config(text="Готово: " + str(len(sent_orgs)) + " орг, " + str(total_emails_sent) + " писем", fg='#28a745')
        self.send_btn.config(state=tk.NORMAL, text="НАЧАТЬ РАССЫЛКУ", bg='#28a745', command=self.start_sending)
        self.stop_flag = False
    
    def start_sending(self):
        if self.df is None:
            messagebox.showwarning("Нет данных", "Сначала загрузите файл")
            return
        
        if self.service is None:
            messagebox.showwarning("Не авторизован", "Сначала авторизуйте Gmail")
            return
        
        email_col = None
        name_col = 'Наименование организации' if 'Наименование организации' in self.df.columns else self.df.columns[1]
        
        for col in self.df.columns:
            if 'почт' in col.lower() or 'email' in col.lower() or 'mail' in col.lower():
                email_col = col
                break
        
        if email_col is None:
            messagebox.showerror("Ошибка", "Колонка с email не найдена")
            return
        
        subject = self.subject_entry.get().strip()
        body = self.body_text.get("1.0", tk.END).strip()
        
        if not subject or not body:
            messagebox.showwarning("Нет данных", "Введите тему и текст письма")
            return
        
        limit_text = str(self.limit_value) if self.limit_value > 0 else "Без лимита"
        attachments_text = f"\nВложений: {len(self.attachments)}" if self.attachments else ""
        
        if messagebox.askyesno("Подтверждение", "Начать рассылку?\n\nВсего организаций: " + str(len(self.df)) + "\nЛимит: " + limit_text + "\nЗадержка: " + str(self.delay_value) + " сек" + attachments_text + "\n\nПродолжить?"):
            self.stop_flag = False
            self.send_btn.config(state=tk.DISABLED, text="ОСТАНОВИТЬ", bg='#dc3545', command=self.stop_sending)
            self.progress['value'] = 0
            self.log("ЗАПУСК РАССЫЛКИ")
            self.log("Всего организаций: " + str(len(self.df)))
            self.log("Лимит: " + limit_text)
            self.log("Задержка: " + str(self.delay_value) + " сек")
            if self.attachments:
                self.log("Вложения: " + ", ".join([os.path.basename(a) for a in self.attachments]))
            
            attachments_copy = self.attachments.copy()
            
            thread = threading.Thread(target=self.send_thread, args=(email_col, subject, body, name_col, self.limit_value, self.delete_sent, self.save_history, self.delay_value, attachments_copy))
            thread.daemon = True
            thread.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = EmailSenderApp(root)
    root.mainloop()
