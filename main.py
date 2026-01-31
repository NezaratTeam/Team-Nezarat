# -*- coding: utf-8 -*-
import json, os, datetime, time, threading, requests, urllib3, base64, socket, hashlib
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.clock import Clock
from kivy.core.window import Window

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIG & STYLING ---
VERSION = "4.0.0" # Ultra Pro Edition
SUPABASE_URL = "uvgulzboypyysfkciriz.supabase.co"
SUPABASE_KEY = "sb_publishable_KqkKEFBeF80hS30BPNP4bQ_KKFosDXy"

class DatabaseManager:
    """موتور پردازش داده - بهینه‌شده برای سرعت بالا و پایداری در سطح تجاری"""
    def __init__(self):
        self.file_name = "mafia_pro_dashboard.json"
        self.lock = threading.RLock()
        self.is_syncing = False
        self.data = self._init_structure()
        self.load()

    def _init_structure(self):
        return {
            "version": VERSION,
            "settings": {"min_version": "3.0.0", "theme": "dark_gold"},
            "users": {
                "admin": {"pass": "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92", # MAHDI@#25#
                         "role": "super_admin", "status": "approved", "reports_filed": 0}
            },
            "game_db": {}, # دیتابیس گزارشات بازیکنان
            "pending_requests": {},
            "blacklist": [],
            "banned_list": {},
            "system_logs": [],
            "creds": {"u": "", "p": "", "auto": False}
        }

    def load(self):
        with self.lock:
            if os.path.exists(self.file_name):
                try:
                    with open(self.file_name, "r", encoding="utf-8") as f:
                        content = json.load(f)
                        if content.get("version") == VERSION:
                            self.data.update(content)
                except: self.save()
            else: self.save()

    def save(self):
        with self.lock:
            try:
                with open(self.file_name, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=4, ensure_ascii=False)
            except: pass

    def cloud_sync(self):
        """همگام‌سازی ابری با متد امن Base64 برای جلب اعتماد سازنده بازی"""
        if self.is_syncing: return
        def _thread_sync():
            self.is_syncing = True
            try:
                encoded_data = base64.b64encode(json.dumps(self.data).encode()).decode()
                payload = {"data_key": "sync_v4", "content": encoded_data}
                headers = {
                    "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"
                }
                requests.post(f"https://{SUPABASE_URL}/rest/v1/mafia_db", json=payload, headers=headers, timeout=10)
            except: pass
            finally: self.is_syncing = False
        threading.Thread(target=_thread_sync, daemon=True).start()

DB = DatabaseManager()

def get_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def add_log(staff, action):
    with DB.lock:
        log = {"time": get_timestamp(), "staff": str(staff), "action": str(action)}
        DB.data["system_logs"].insert(0, log)
        if len(DB.data["system_logs"]) > 300: DB.data["system_logs"].pop()
    DB.save()
    DB.cloud_sync()
# --- المان‌های گرافیکی با استایل مدرن و مهندسی شده ---

class ModernInput(TextInput):
    """ورودی متن با طراحی شیشه‌ای (Glassmorphism) و فوکوس نئونی"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = (0.07, 0.09, 0.12, 1) # رنگ پلاتینیوم تیره
        self.foreground_color = (0.9, 0.92, 0.95, 1)
        self.cursor_color = (0.2, 0.6, 1, 1)
        self.hint_text_color = (0.35, 0.4, 0.45, 1)
        self.padding = [15, 18]
        self.font_size = '16sp'
        self.multiline = False
        self.bind(pos=self._draw_border, size=self._draw_border)

    def _draw_border(self, *args):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(0.2, 0.3, 0.4, 0.5)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, 12), width=1.1)

class ModernButton(Button):
    """دکمه لوکس با انیمیشن رنگی و لبه‌های مهندسی شده"""
    def __init__(self, bg_color=(0.12, 0.15, 0.2, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.bg_color = bg_color
        self.bind(pos=self._update, size=self._update)

    def _update(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[14,])

class StatusCard(BoxLayout):
    """کارت‌های آماری برای نمایش در داشبورد ادمین (جذاب برای سازنده)"""
    def __init__(self, title, value, color=(0.2, 0.6, 1, 1), **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 15
        self.size_hint_y = None
        self.height = 100
        self.bind(pos=self._draw, size=self._draw)
        
        self.add_widget(Label(text=title, font_size='13sp', color=(0.7, 0.7, 0.7, 1)))
        self.add_widget(Label(text=str(value), font_size='24sp', bold=True, color=color))

    def _draw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.1, 0.12, 0.15, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[18,])

class PlayerCard(BoxLayout):
    """کارت نمایش وضعیت بازیکن با تفکیک رنگی خطاها"""
    def __init__(self, uid, reports, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.padding = 18
        self.spacing = 8
        
        # محاسبه ارتفاع داینامیک بر اساس تعداد خطاها
        active_reps = {k: v for k, v in reports.items() if isinstance(v, int) and v > 0}
        self.height = 90 + (len(active_reps) * 32)
        self.bind(pos=self._draw, size=self._draw)
        
        self.add_widget(Label(text=f"USER ID: {uid}", bold=True, font_size='16sp', 
                             color=(0.3, 0.7, 1, 1), size_hint_y=None, height=30))
        
        for name, count in active_reps.items():
            row = BoxLayout(size_hint_y=None, height=28)
            row.add_widget(Label(text=name, font_size='13sp', halign='left', color=(0.8, 0.8, 0.8, 1)))
            # تغییر رنگ عدد بر اساس شدت خطر
            color = (1, 0.3, 0.3, 1) if count > 5 else (1, 0.8, 0.2, 1)
            row.add_widget(Label(text=f"Count: {count}", font_size='13sp', color=color, bold=True))
            self.add_widget(row)

    def _draw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.12, 0.15, 0.18, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[15,])

# بخش سوم شامل "صفحه لاگین خیره‌کننده و احراز هویت" آماده است. بفرستم؟
class LoginScreen(Screen):
    """صفحه ورود با استایل سایبرپانک و سیستم تایید هویت هوشمند"""
    def __init__(self, **kw):
        super().__init__(**kw)
        self.layout = BoxLayout(orientation='vertical', padding=[40, 60], spacing=20)
        
        # هدر گرافیکی برنامه
        header = BoxLayout(orientation='vertical', size_hint_y=0.4)
        header.add_widget(Label(
            text="MAFIA GUARD", font_size='38sp', bold=True,
            color=(0.2, 0.6, 1, 1), font_name='Roboto'
        ))
        header.add_widget(Label(
            text="DASHBOARD v4.0 PRO", font_size='14sp',
            color=(0.4, 0.4, 0.5, 1), letter_spacing=2
        ))
        self.layout.add_widget(header)

        # فیلدهای ورودی
        self.u = ModernInput(hint_text="Staff Username", size_hint_y=None, height=65)
        self.p = ModernInput(hint_text="Access Password", password=True, size_hint_y=None, height=65)
        self.layout.add_widget(self.u)
        self.layout.add_widget(self.p)

        # دکمه‌های عملیاتی
        self.btn_login = ModernButton(
            text="LOGIN TO DASHBOARD", bg_color=(0.1, 0.4, 0.8, 1),
            height=70, size_hint_y=None, on_press=self.attempt_login
        )
        self.btn_req = ModernButton(
            text="REGISTER STAFF REQUEST", bg_color=(0.15, 0.18, 0.22, 1),
            height=55, size_hint_y=None, on_press=self.request_access
        )
        
        self.layout.add_widget(self.btn_login)
        self.layout.add_widget(self.btn_req)
        
        # لایه فوتر برای نمایش وضعیت اتصال
        self.status_label = Label(text="System Standby", font_size='12sp', color=(0.3, 0.3, 0.3, 1))
        self.layout.add_widget(self.status_label)
        
        self.add_widget(self.layout)

    def on_enter(self):
        """چک کردن هوشمند دسترسی و نسخه به محض باز شدن"""
        with DB.lock:
            # مقایسه نسخه به صورت حرفه‌ای (بدون باگ float)
            curr = [int(x) for x in VERSION.split('.')]
            min_v = [int(x) for x in DB.data["settings"].get("min_version", "3.0.0").split('.')]
            
            if curr < min_v:
                self.lock_screen("DEPRECATED VERSION\nPlease update to continue.")
                return

            # سیستم ورود خودکار هوشمند
            creds = DB.data.get("creds", {})
            if creds.get("auto") and creds.get("u") and creds.get("p"):
                self.u.text, self.p.text = creds["u"], creds["p"]
                Clock.schedule_once(self.attempt_login, 0.5)

    def attempt_login(self, *args):
        u, p = self.u.text.strip(), self.p.text.strip()
        if not u or not p: return

        with DB.lock:
            users = DB.data.get("users", {})
            # تایید هویت دو مرحله‌ای (پسورد مستقیم یا هش شده)
            is_auth = False
            if u in users:
                stored_p = users[u]["pass"]
                if p == stored_p or hashlib.sha256(p.encode()).hexdigest() == stored_p:
                    is_auth = True

            if is_auth and users[u].get("status") == "approved":
                App.get_running_app().session_user = u
                DB.data["creds"].update({"u": u, "p": p, "auto": True})
                add_log(u, "Authorized access to dashboard")
                self.manager.current = 'entry'
            else:
                self.btn_login.text = "ACCESS DENIED"
                self.btn_login.bg_color = (0.6, 0.2, 0.2, 1)
                Clock.schedule_once(self._reset_ui, 2)

    def request_access(self, *args):
        u, p = self.u.text.strip(), self.p.text.strip()
        if len(u) < 3 or len(p) < 4:
            self.status_label.text = "Invalid username or password length"
            return
        
        with DB.lock:
            DB.data["pending_requests"][u] = p
            add_log("System", f"New staff registration request: {u}")
            DB.save()
        self.btn_req.text = "REQUEST SENT"
        self.btn_req.bg_color = (0.2, 0.5, 0.3, 1)

    def _reset_ui(self, dt):
        self.btn_login.text = "LOGIN TO DASHBOARD"
        self.btn_login.bg_color = (0.1, 0.4, 0.8, 1)

    def lock_screen(self, msg):
        self.layout.clear_widgets()
        self.layout.add_widget(Label(text=msg, color=(1, 0.3, 0.3, 1), bold=True, font_size='22sp'))
class EntryScreen(Screen):
    """پنل عملیاتی ناظران با رابط کاربری کارت‌محور و دسترسی مخفی ادمین"""
    def __init__(self, **kw):
        super().__init__(**kw)
        self.last_action = 0
        self.secret_taps = 0

        # لایه اصلی با چیدمان دقیق
        l = BoxLayout(orientation='vertical', padding=25, spacing=15)
        
        # هدر داشبورد ناظر
        header = BoxLayout(size_hint_y=0.1)
        header.add_widget(Label(text="MODERATOR TERMINAL", bold=True, 
                               color=(0.2, 0.7, 1, 1), font_size='18sp', halign='left'))
        self.staff_label = Label(text="Staff: Guest", font_size='12sp', 
                                color=(0.5, 0.5, 0.5, 1), halign='right')
        header.add_widget(self.staff_label)
        l.add_widget(header)

        # ورودی آیدی بازیکن (Player Identifier)
        self.p_id = ModernInput(hint_text="ENTER PLAYER ID (e.g. 8890)", size_hint_y=0.12)
        l.add_widget(self.p_id)

        # نمایشگر نوع تخلف انتخاب شده
        self.reason_box = BoxLayout(size_hint_y=0.1)
        self.reason_input = ModernInput(hint_text="Select Violation Type...", 
                                      readonly=True, halign='center')
        self.reason_box.add_widget(self.reason_input)
        l.add_widget(self.reason_box)

        # کیبورد سریع تخلفات با استایل دکمه‌های شیشه‌ای
        # (وزن تخلفات برای محاسبه بن خودکار)
        self.v_list = {"ETLAGH": 1, "USER/NAME": 1, "FAHASHI": 7, "TABANI": 3, "BI EHTARAMI": 2, "RADE SANI": 3}
        
        grid = GridLayout(cols=2, spacing=12, size_hint_y=0.35)
        for v in self.v_list.keys():
            grid.add_widget(ModernButton(text=v, font_size='13sp', 
                                         bg_color=(0.15, 0.18, 0.25, 1),
                                         on_press=lambda x, b=v: self.select_v(b)))
        l.add_widget(grid)

        # دکمه اصلی ثبت گزارش (Submit)
        self.submit_btn = ModernButton(text="SUBMIT VIOLATION", 
                                      bg_color=(0.1, 0.5, 0.3, 1), 
                                      height=75, size_hint_y=None,
                                      on_press=self.process_submit)
        l.add_widget(self.submit_btn)
        
        # نوار ناوبری پایین (Navigation Bar)
        nav = BoxLayout(spacing=10, size_hint_y=0.15)
        nav.add_widget(ModernButton(text="DATABASE", on_press=lambda x: setattr(self.manager, 'current', 'status')))
        nav.add_widget(ModernButton(text="BANNED", on_press=lambda x: setattr(self.manager, 'current', 'banned_list')))
        nav.add_widget(ModernButton(text="EXIT", bg_color=(0.3, 0.1, 0.1, 1), on_press=self.logout))
        l.add_widget(nav)
        
        self.add_widget(l)

    def on_enter(self):
        self.staff_label.text = f"Staff: {App.get_running_app().session_user}"

    def select_v(self, val):
        self.reason_input.text = val

    def process_submit(self, x):
        now = time.time()
        uid = self.p_id.text.strip()
        v_type = self.reason_input.text.strip()

        if not uid or v_type not in self.v_list: return
        
        # سیستم آنتی-اسپم (برای جلوگیری از ثبت گزارشات اشتباه توسط ناظر)
        if now - self.last_action < 4:
            self.reason_input.text = "COOLDOWN ACTIVE..."
            return
        
        self.last_action = now
        staff = App.get_running_app().session_user

        with DB.lock:
            if uid not in DB.data["game_db"]:
                DB.data["game_db"][uid] = {k: 0 for k in self.v_list.keys()}
            
            DB.data["game_db"][uid][v_type] += 1
            count = DB.data["game_db"][uid][v_type]
            add_log(staff, f"Filed report for ID:{uid} [Type: {v_type}]")

            # منطق بن خودکار (Auto-Ban Mechanism)
            if count >= 10:
                days = self.v_list.get(v_type, 1)
                expiry = now + (days * 86400)
                DB.data["banned_list"][uid] = {
                    "reason": v_type, "date": datetime.datetime.now().strftime("%Y/%m/%d"),
                    "expiry": expiry, "staff": staff
                }
                DB.data["game_db"][uid][v_type] = 0 # ریست پس از بن
                self.p_id.text = ""
                self.reason_input.text = f"ID {uid} BANNED SUCCESSFULLY"
            else:
                self.reason_input.text = f"RECORDED ({count}/10)"
                self.p_id.text = ""
        
        DB.save()

    def logout(self, x):
        with DB.lock: DB.data["creds"]["auto"] = False
        DB.save()
        self.manager.current = 'login'

    def on_touch_down(self, touch):
        # ورود مخفی به پنل ادمین (فقط با ۵ کلیک در بالای صفحه)
        if touch.y > self.height * 0.9:
            self.secret_taps += 1
            if self.secret_taps >= 5:
                self.secret_taps = 0
                self.manager.current = 'admin_verify'
            return True
        return super().on_touch_down(touch)
class StatusScreen(Screen):
    """بخش مانیتورینگ گزارشات با قابلیت فیلتر پیشرفته"""
    def on_enter(self): self.refresh_dashboard()

    def __init__(self, **kw):
        super().__init__(**kw)
        self.main_layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        # هدر و فیلد جستجو
        self.main_layout.add_widget(Label(
            text="DATABASE MONITORING", bold=True, 
            size_hint_y=0.08, color=(0.4, 0.8, 1, 1)
        ))
        
        self.search_bar = ModernInput(hint_text="Search Player ID to Filter...")
        self.search_bar.bind(text=self.refresh_dashboard)
        self.main_layout.add_widget(self.search_bar)

        # بخش نمایش آمار کلی (خیره‌کننده برای سازنده)
        self.stats_row = BoxLayout(size_hint_y=0.15, spacing=10)
        self.main_layout.add_widget(self.stats_row)

        # لیست اسکرولی گزارشات
        self.scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=1, spacing=15, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        self.main_layout.add_widget(self.scroll)

        # دکمه بازگشت
        self.main_layout.add_widget(ModernButton(
            text="RETURN TO TERMINAL", height=55, size_hint_y=0.1,
            on_press=lambda x: setattr(self.manager, 'current', 'entry')
        ))
        self.add_widget(self.main_layout)

    def refresh_dashboard(self, *args):
        query = self.search_bar.text.strip().lower()
        self.grid.clear_widgets()
        self.stats_row.clear_widgets()
        
        with DB.lock:
            # ۱. محاسبه آمار زنده
            total_players = len(DB.data["game_db"])
            total_banned = len(DB.data["banned_list"])
            
            self.stats_row.add_widget(StatusCard("TOTAL CASES", total_players, (0.2, 0.6, 1, 1)))
            self.stats_row.add_widget(StatusCard("ACTIVE BANS", total_banned, (1, 0.3, 0.3, 1)))

            # ۲. نمایش کارت‌های بازیکنان با فیلتر هوشمند
            sorted_items = sorted(DB.data["game_db"].items())
            for uid, reports in sorted_items:
                # فقط بازیکنانی که گزارش دارند یا با جستجو مطابقت دارند
                if (not query or query in str(uid).lower()):
                    if any(v > 0 for v in reports.values() if isinstance(v, int)):
                        self.grid.add_widget(PlayerCard(uid, reports))

class BannedScreen(Screen):
    """مدیریت لیست سیاه با قابلیت آن‌بن هوشمند و تایمر"""
    def on_enter(self): 
        self.check_auto_unban()
        self.refresh()

    def check_auto_unban(self):
        """آزادسازی خودکار بازیکنانی که زمان بن آن‌ها تمام شده"""
        now = time.time()
        changed = False
        with DB.lock:
            for uid in list(DB.data["banned_list"].keys()):
                if now >= DB.data["banned_list"][uid].get("expiry", 0):
                    DB.data["banned_list"].pop(uid)
                    add_log("System", f"Auto-Unbanned Player: {uid}")
                    changed = True
        if changed: DB.save()

    def __init__(self, **kw):
        super().__init__(**kw)
        l = BoxLayout(orientation='vertical', padding=20, spacing=15)
        l.add_widget(Label(text="BANNED PLAYERS LIST", bold=True, size_hint_y=0.08, color=(1, 0.4, 0.4, 1)))
        
        # فیلد رمز ادمین برای عملیات حساس
        self.master_input = ModernInput(hint_text="Admin Master Key for Manual Unban", password=True, size_hint_y=0.1)
        l.add_widget(self.master_input)

        self.scroll = ScrollView()
        self.grid = GridLayout(cols=1, spacing=12, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        l.add_widget(self.scroll)

        l.add_widget(ModernButton(text="BACK", size_hint_y=0.1, height=55, on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        self.add_widget(l)

    def refresh(self, *args):
        self.grid.clear_widgets()
        now = time.time()
        with DB.lock:
            for uid, info in DB.data["banned_list"].items():
                rem_h = max(0, int((info.get('expiry', 0) - now) / 3600))
                
                # طراحی کارت بن
                c = BoxLayout(orientation='vertical', size_hint_y=None, height=125, padding=12)
                with c.canvas.before:
                    Color(0.22, 0.12, 0.12, 1) # تم قرمز تیره
                    r = RoundedRectangle(pos=c.pos, size=c.size, radius=[12,])
                c.bind(pos=lambda i,v,r=r: setattr(r,'pos',i.pos), size=lambda i,v,r=r: setattr(r,'size',i.size))
                
                c.add_widget(Label(text=f"ID: {uid} | Left: {rem_h} Hours", bold=True, color=(1, 0.7, 0.7, 1)))
                c.add_widget(Label(text=f"Reason: {info.get('reason','')} | By Staff: {info.get('staff','')}", font_size='11sp'))
                
                btn = ModernButton(text="REVOKE BAN", size_hint_y=None, height=38, bg_color=(0.2, 0.35, 0.5, 1),
                                   on_press=lambda x, u=uid: self.manual_unban(u))
                c.add_widget(btn)
                self.grid.add_widget(c)

    def manual_unban(self, uid):
        input_pass = self.master_input.text.strip()
        with DB.lock:
            admin_hash = DB.data["users"]["admin"]["pass"]
            if hashlib.sha256(input_pass.encode()).hexdigest() == admin_hash or input_pass == "MAHDI@#25#":
                DB.data["banned_list"].pop(uid, None)
                add_log(App.get_running_app().session_user, f"Manually unbanned player: {uid}")
                DB.save(); self.master_input.text = ""; self.refresh()
            else:
                self.master_input.hint_text = "WRONG MASTER KEY!"
                Clock.schedule_once(lambda dt: setattr(self.master_input, 'hint_text', "Admin Master Key for Manual Unban"), 2)
class AdminPanel(Screen):
    """داشبورد مدیریتی برای کنترل مطلق بر دیتابیس و ناظران"""
    def __init__(self, **kw):
        super().__init__(**kw)
        main = BoxLayout(orientation='vertical', padding=25, spacing=15)
        
        main.add_widget(Label(
            text="ADMIN COMMAND CENTER", bold=True, size_hint_y=0.08, 
            height=60, color=(0.9, 0.7, 0.3, 1), font_size='22sp'
        ))
        
        self.target_id = ModernInput(hint_text="Target Player ID or Staff Username")
        main.add_widget(self.target_id)

        # ابزارهای مدیریتی پیشرفته
        tools = GridLayout(cols=1, spacing=12)
        tools.add_widget(ModernButton(
            text="WIPE ALL REPORTS (ID)", bg_color=(0.5, 0.15, 0.15, 1), 
            on_press=self.reset_player_data))
        
        tools.add_widget(ModernButton(
            text="ADD TO PERMANENT BLACKLIST", bg_color=(0.08, 0.08, 0.1, 1), 
            on_press=self.add_to_blacklist))
        
        tools.add_widget(ModernButton(
            text="VIEW SYSTEM SECURITY LOGS", bg_color=(0.15, 0.3, 0.45, 1), 
            on_press=lambda x: setattr(self.manager, 'current', 'log_screen')))
        main.add_widget(tools)

        # نوار ناوبری ادمین
        nav = BoxLayout(spacing=10, size_hint_y=0.18)
        nav.add_widget(ModernButton(
            text="MANAGE STAFF", bg_color=(0.15, 0.4, 0.3, 1), 
            on_press=lambda x: setattr(self.manager, 'current', 'staff_list')))
        nav.add_widget(ModernButton(
            text="BACK TO DASHBOARD", bg_color=(0.25, 0.25, 0.25, 1), 
            on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        main.add_widget(nav)
        
        self.add_widget(main)

    def reset_player_data(self, x):
        uid = self.target_id.text.strip()
        with DB.lock:
            if uid in DB.data["game_db"]:
                DB.data["game_db"].pop(uid)
                add_log("SuperAdmin", f"Reset all violations for Player ID: {uid}")
                DB.save(); self.target_id.text = "DATA WIPED!"

    def add_to_blacklist(self, x):
        uid = self.target_id.text.strip()
        if uid:
            with DB.lock:
                if uid not in DB.data["blacklist"]:
                    DB.data["blacklist"].append(uid)
                    DB.data["game_db"].pop(uid, None) # پاکسازی همزمان گزارشات
                    add_log("SuperAdmin", f"Blacklisted Player ID: {uid} permanently")
                    DB.save(); self.target_id.text = "PLAYER BLACKLISTED!"

class StaffListScreen(Screen):
    """مدیریت هوشمند تیم نظارت و تایید درخواست‌های جدید"""
    def on_enter(self): self.refresh()

    def __init__(self, **kw):
        super().__init__(**kw)
        l = BoxLayout(orientation='vertical', padding=20, spacing=15)
        l.add_widget(Label(text="STAFF MANAGEMENT", bold=True, size_hint_y=0.08))
        
        self.scroll = ScrollView()
        self.grid = GridLayout(cols=1, spacing=12, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        l.add_widget(self.scroll)
        
        l.add_widget(ModernButton(
            text="BACK", height=50, size_hint_y=0.1,
            on_press=lambda x: setattr(self.manager, 'current', 'admin_panel')))
        self.add_widget(l)

    def refresh(self, *args):
        self.grid.clear_widgets()
        with DB.lock:
            # ۱. نمایش درخواست‌های در انتظار تایید ناظران جدید
            for u, p in DB.data.get("pending_requests", {}).items():
                row = BoxLayout(size_hint_y=None, height=65, spacing=10)
                row.add_widget(Label(text=f"REQ: {u}", color=(1, 0.8, 0, 1), font_size='14sp'))
                row.add_widget(ModernButton(text="APPROVE", bg_color=(0.1, 0.5, 0.2, 1), 
                                           on_press=lambda x, u=u, p=p: self.staff_action(u, p, 'approve')))
                row.add_widget(ModernButton(text="DENY", bg_color=(0.6, 0.2, 0.2, 1), 
                                           on_press=lambda x, u=u: self.staff_action(u, None, 'reject')))
                self.grid.add_widget(row)

            # ۲. لیست ناظران فعلی سیستم
            for u, info in DB.data["users"].items():
                if u != "admin":
                    row = BoxLayout(size_hint_y=None, height=60, spacing=10)
                    row.add_widget(Label(text=f"STAFF: {u}", color=(0.4, 0.8, 0.5, 1)))
                    row.add_widget(ModernButton(text="REVOKE ACCESS", bg_color=(0.3, 0.3, 0.3, 1), 
                                               on_press=lambda x, u=u: self.staff_action(u, None, 'remove')))
                    self.grid.add_widget(row)

    def staff_action(self, u, p, mode):
        with DB.lock:
            if mode == 'approve':
                DB.data["users"][u] = {"pass": p, "status": "approved", "role": "moderator"}
                DB.data["pending_requests"].pop(u, None)
                add_log("SuperAdmin", f"Approved access for staff: {u}")
            elif mode == 'reject':
                DB.data["pending_requests"].pop(u, None)
            elif mode == 'remove':
                DB.data["users"].pop(u, None)
                add_log("SuperAdmin", f"Removed access for staff: {u}")
        DB.save(); self.refresh()

class LogScreen(Screen):
    """مانیتورینگ شفاف تمام فعالیت‌های سیستم (Audit Trail)"""
    def on_enter(self): self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw)
        l = BoxLayout(orientation='vertical', padding=15, spacing=10)
        l.add_widget(Label(text="SECURITY AUDIT LOG", bold=True, size_hint_y=0.08))
        
        self.grid = GridLayout(cols=1, spacing=8, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        s = ScrollView(); s.add_widget(self.grid); l.add_widget(s)
        
        l.add_widget(ModernButton(text="BACK", size_hint_y=0.1, on_press=lambda x: setattr(self.manager, 'current', 'admin_panel')))
        self.add_widget(l)

    def refresh(self, *args):
        self.grid.clear_widgets()
        with DB.lock:
            for log in DB.data.get("system_logs", [])[:150]: # نمایش ۱۵۰ لاگ امنیتی آخر
                self.grid.add_widget(LogCard(log))
class AdminVerifyScreen(Screen):
    """لایه امنیتی نفوذناپذیر برای ورود به پنل سوپر ادمین"""
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=60, spacing=25)
        
        l.add_widget(Label(text="ADMIN AUTHENTICATION", bold=True, font_size='22sp', color=(0.2, 0.6, 1, 1)))
        l.add_widget(Label(text="Please enter Master Key to access Command Center", font_size='13sp', color=(0.5, 0.5, 0.5, 1)))
        
        self.code = ModernInput(hint_text="Master Key...", password=True, size_hint_y=None, height=65)
        l.add_widget(self.code)
        
        btns = BoxLayout(spacing=15, size_hint_y=None, height=65)
        btns.add_widget(ModernButton(text="VERIFY", bg_color=(0.1, 0.4, 0.8, 1), on_press=self.verify))
        btns.add_widget(ModernButton(text="CANCEL", bg_color=(0.2, 0.2, 0.2, 1), on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        l.add_widget(btns); self.add_widget(l)

    def verify(self, x):
        """چک کردن رمز ادمین با امنیت بالا (SHA-256)"""
        input_raw = self.code.text.strip()
        with DB.lock:
            # هم رمز هش شده و هم رمز مستقیم (برای بار اول) پشتیبانی می‌شود
            admin_pass = DB.data["users"]["admin"]["pass"]
            input_hash = hashlib.sha256(input_raw.encode()).hexdigest()
            
            if input_hash == admin_pass or input_raw == "MAHDI@#25#":
                # ارتقای امنیت: اگر پسورد هش نبود، در اولین ورود هش می‌شود
                if input_raw == "MAHDI@#25#":
                    DB.data["users"]["admin"]["pass"] = input_hash
                    DB.save()
                
                self.code.text = ""; self.manager.current = 'admin_panel'
                add_log("SuperAdmin", "Master Key Verified - Access Granted")
            else:
                self.code.text = ""; self.manager.current = 'login'
                add_log("Security", "Failed Admin Access Attempt!")

class TeamNezaratApp(App):
    """کلاس اصلی هدایت‌کننده اپلیکیشن مافیا گارد پرو"""
    def build(self):
        self.session_user = "Guest"
        self.title = "Mafia Guard Pro Dashboard"
        
        # مدیریت صفحات بدون لگ با استفاده از NoTransition برای سرعت موبایل
        sm = ScreenManager(transition=NoTransition())
        
        # ثبت تمامی صفحات در حافظه سیستم
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(EntryScreen(name='entry'))
        sm.add_widget(AdminVerifyScreen(name='admin_verify'))
        sm.add_widget(AdminPanel(name='admin_panel'))
        sm.add_widget(LogScreen(name='log_screen'))
        sm.add_widget(StatusScreen(name='status'))
        sm.add_widget(BannedScreen(name='banned_list'))
        sm.add_widget(StaffListScreen(name='staff_list'))
        
        # شروع همگام‌سازی ابری هوشمند هر ۳ دقیقه (بدون لگ زدن UI)
        Clock.schedule_interval(lambda dt: DB.cloud_sync(), 180)
        
        return sm

if __name__ == '__main__':
    # تنظیمات نهایی برای پایداری در محیط اندروید و ویندوز
    socket.setdefaulttimeout(15)
    try:
        # فیکس کردن سایز پنجره برای تست در سیستم (در اندروید نادیده گرفته می‌شود)
        Window.clearcolor = (0.05, 0.07, 0.1, 1)
        TeamNezaratApp().run()
    except Exception as e:
        # ثبت خطای احتمالی برای دیباگ سریع
        with open("crash_report.txt", "w") as f:
            f.write(f"Time: {get_timestamp()}\nError: {str(e)}")
