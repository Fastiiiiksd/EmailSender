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
import base64

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

class EmailSenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mass Email Sender")
        self.root.geometry("950x800")
        self.df = None
        self.file_path = None
        self.service = None
        self.stop_flag = False
        self.create_widgets()

    def create_widgets(self):
        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        f1 = tk.LabelFrame(main, text="1. Excel File", font=("Arial", 10, "bold"))
        f1.pack(fill="x", pady=5)
        self.file_label = tk.Label(f1, text="No file selected", fg="gray")
        self.file_label.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        btn_load = tk.Button(f1, text="Load File", command=self.load_file, bg="#4CAF50", fg="white")
        btn_load.pack(side="right", padx=5, pady=5)

        f2 = tk.LabelFrame(main, text="2. Gmail Authorization", font=("Arial", 10, "bold"))
        f2.pack(fill="x", pady=5)
        self.auth_btn = tk.Button(f2, text="Authorize Gmail Account", command=self.auth_gmail, bg="#2196F3", fg="white", width=25)
        self.auth_btn.pack(pady=10)
        self.auth_status = tk.Label(f2, text="Not authorized", fg="red")
        self.auth_status.pack()

        f3 = tk.LabelFrame(main, text="3. Email Content", font=("Arial", 10, "bold"))
        f3.pack(fill="both", expand=True, pady=5)
        tk.Label(f3, text="Subject:").pack(anchor="w", padx=5)
        self.subject = tk.Entry(f3, width=80)
        self.subject.pack(fill="x", padx=5, pady=5)
        self.subject.insert(0, "Commercial offer")
        tk.Label(f3, text="Body:").pack(anchor="w", padx=5)
        self.body = scrolledtext.ScrolledText(f3, height=12, wrap=tk.WORD)
        self.body.pack(fill="both", expand=True, padx=5, pady=5)
        example = "Dear Sirs,\n\nWe would like to offer our kitchen furniture.\n\nBest regards,\nSales Department"
        self.body.insert("1.0", example)

        f4 = tk.Frame(main)
        f4.pack(fill="x", pady=10)
        self.sort_btn = tk.Button(f4, text="Sort Files", command=self.sort_files, bg="#2196F3", fg="white", width=15)
        self.sort_btn.pack(side="left", padx=5)
        self.send_btn = tk.Button(f4, text="Start Sending", command=self.start_sending, bg="#FF9800", fg="white", width=15, state=tk.DISABLED)
        self.send_btn.pack(side="left", padx=5)
        self.stop_btn = tk.Button(f4, text="Stop", command=self.stop_sending, bg="#f44336", fg="white", width=15, state=tk.DISABLED)
        self.stop_btn.pack(side="left", padx=5)
        self.progress = ttk.Progressbar(f4, mode='determinate', length=300)
        self.progress.pack(side="left", padx=20)
        self.status = tk.Label(f4, text="Ready", fg="green")
        self.status.pack(side="left", padx=10)

        f5 = tk.LabelFrame(main, text="Log", font=("Arial", 10, "bold"))
        f5.pack(fill="both", expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(f5, height=12, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def get_credentials_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(CREDENTIALS_JSON, f)
            return f.name

    def auth_gmail(self):
        creds = None
        token_file = 'token.pickle'
        
        if os.path.exists(token_file):
            with open(token_file, 'rb') as t:
                creds = pickle.load(t)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds_file = self.get_credentials_file()
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
                os.unlink(creds_file)
            
            with open(token_file, 'wb') as t:
                pickle.dump(creds, t)
        
        self.service = build('gmail', 'v1', credentials=creds)
        self.auth_status.config(text="Authorized!", fg="green")
        self.log("Gmail authorized successfully")
        if self.df is not None:
            self.send_btn.config(state=tk.NORMAL)

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if not path:
            return
        try:
            self.df = pd.read_excel(path)
            self.file_path = path
            self.file_label.config(text=f"Loaded: {os.path.basename(path)}", fg="green")
            self.log(f"Loaded {len(self.df)} rows")
            for col in self.df.columns:
                if 'почт' in col.lower() or 'email' in col.lower() or 'mail' in col.lower():
                    self.log(f"Email column found: '{col}'")
                    break
            if self.service:
                self.send_btn.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.log(f"Error: {e}")

    def sort_files(self):
        if self.df is None:
            messagebox.showwarning("No data", "Load file first")
            return
        
        email_col = None
        phone_col = None
        
        for col in self.df.columns:
            if 'почт' in col.lower() or 'email' in col.lower() or 'mail' in col.lower():
                email_col = col
            if 'телефон' in col.lower() or 'phone' in col.lower() or 'тел' in col.lower():
                phone_col = col
        
        if not email_col:
            messagebox.showwarning("No email column", "Email column not found")
            return
        
        def has_email(v):
            if pd.isna(v):
                return False
            return bool(re.match(r"[^@]+@[^@]+\.[^@]+", str(v).strip()))
        
        def has_phone(v):
            if pd.isna(v):
                return False
            return len(str(v).strip()) > 0 and str(v).strip() != 'nan'
        
        mask_email = self.df[email_col].apply(has_email)
        mask_phone = self.df[phone_col].apply(has_phone) if phone_col else pd.Series([False] * len(self.df))
        
        only_phone = self.df[~mask_email & mask_phone]
        only_email = self.df[mask_email & ~mask_phone]
        both = self.df[mask_email & mask_phone]
        none = self.df[~mask_email & ~mask_phone]
        
        base = os.path.splitext(self.file_path)[0]
        
        only_phone.to_excel(f"{base}_ONLY_PHONE.xlsx", index=False)
        only_email.to_excel(f"{base}_ONLY_EMAIL.xlsx", index=False)
        both.to_excel(f"{base}_BOTH.xlsx", index=False)
        none.to_excel(f"{base}_NO_CONTACTS.xlsx", index=False)
        
        self.log(f"Sorted: only_phone={len(only_phone)}, only_email={len(only_email)}, both={len(both)}, none={len(none)}")
        messagebox.showinfo("Done", "Files saved next to original file")

    def stop_sending(self):
        self.stop_flag = True
        self.log("Stopping...")

    def send_one(self, to_email, subject, body):
        try:
            msg = MIMEMultipart()
            msg['to'] = to_email
            msg['subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            self.service.users().messages().send(userId='me', body={'raw': raw}).execute()
            return True, None
        except Exception as e:
            return False, str(e)

    def send_thread(self, email_col, subject, body):
        if not self.service:
            self.log("ERROR: Not authorized")
            return
        
        emails = []
        for _, row in self.df.iterrows():
            val = row[email_col]
            if pd.notna(val) and isinstance(val, str):
                clean = val.strip()
                if re.match(r"[^@]+@[^@]+\.[^@]+", clean):
                    emails.append(clean)
        
        total = len(emails)
        if total == 0:
            self.log("No valid emails found")
            self.status.config(text="No emails")
            self.send_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            return
        
        sent = 0
        failed = 0
        
        for i, email in enumerate(emails):
            if self.stop_flag:
                self.log("Stopped by user")
                break
            
            self.log(f"Sending to: {email}")
            self.status.config(text=f"{i+1}/{total}")
            self.progress['value'] = (i / total) * 100
            self.root.update_idletasks()
            
            ok, err = self.send_one(email, subject, body)
            
            if ok:
                sent += 1
                self.log(f"OK: {email}")
            else:
                failed += 1
                self.log(f"FAIL: {email} - {err}")
            
            self.progress['value'] = ((i + 1) / total) * 100
        
        self.log(f"\n=== FINISHED ===")
        self.log(f"Total: {total}")
        self.log(f"Sent: {sent}")
        self.log(f"Failed: {failed}")
        
        self.status.config(text=f"Done: {sent}/{total}")
        self.send_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.stop_flag = False

    def start_sending(self):
        if not self.df:
            messagebox.showwarning("No data", "Load file first")
            return
        
        if not self.service:
            messagebox.showwarning("Not authorized", "Click 'Authorize Gmail Account' first")
            return
        
        email_col = None
        for col in self.df.columns:
            if 'почт' in col.lower() or 'email' in col.lower() or 'mail' in col.lower():
                email_col = col
                break
        
        if not email_col:
            messagebox.showerror("Error", "Email column not found")
            return
        
        subject = self.subject.get().strip()
        body = self.body.get("1.0", tk.END).strip()
        
        if not subject or not body:
            messagebox.showwarning("Missing data", "Enter subject and body")
            return
        
        self.stop_flag = False
        self.send_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.sort_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0
        
        t = threading.Thread(target=self.send_thread, args=(email_col, subject, body))
        t.daemon = True
        t.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = EmailSenderApp(root)
    root.mainloop()
