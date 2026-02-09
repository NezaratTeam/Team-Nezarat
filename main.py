# -*- coding: utf-8 -*-
# بخش ۱ از ۷ - تنظیمات زیرساخت جدید (Smart Delta Sync)
import json, os, datetime, time, threading, requests, urllib3, socket
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.utils import platform
from kivy.uix.popup import Popup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIG (اتصال هوشمند به هاست پارس‌پک) ---
CURRENT_VERSION = "1.2" 

# آدرس روت هاست (متصل به index.php)
IRAN_BRIDGE_URL = "https://devconnect-123.ir"

# کلید امنیتی دقیق برای عبور از سد امنیتی هاست
API_SECRET_KEY = "MAHDI_SECURE_TOKEN_2024"

# هدرهای بهینه شده برای پایداری در پینگ ۳۰۰ms و اندروید
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Mobile)',
    'Content-Type': 'application/json',
    'X-API-KEY': API_SECRET_KEY,
    'Connection': 'keep-alive'
}

db_lock = threading.RLock()
_is_syncing = False
_NET_STATUS = False 
_PING_VALUE = "0"
TIME_OFFSET = 0 

# صف هوشمند برای ارسال فقط "تغییرات جدید" (تفاضلی)
SYNC_QUEUE = [] 

DB_FILE = "mafia_guard_v32.json"

# ساختار دیتای اولیه
DATA = {
    "version": CURRENT_VERSION,
    "last_sync_etag": 0,
    "last_cleanup_time": 0,
    "users": {"admin": {"pass": "MAHDI@#25#", "status": "approved", "device": ""}}, 
    "permissions": [],
    "game_db": {}, "pending_requests": {}, "blacklist": [], "banned_list": {}, 
    "global_notice": "نظارت آنلاین خوش آمدید", "staff_activity": [], "ejected_users": [], 
    "saved_creds": {"u": "", "p": "", "auto_login": False}
}
# -*- coding: utf-8 -*-
# بخش ۲ از ۷ - موتور همگام‌سازی تفاضلی و مدیریت زمان ایران

def sync_time_offset():
    """هماهنگی دقیق با ساعت رسمی ایران از طریق سرور"""
    global TIME_OFFSET, _NET_STATUS, _PING_VALUE
    try:
        st = time.time()
        # درخواست برای دریافت زمان دقیق از هدر سرور ایران
        r = requests.get(IRAN_BRIDGE_URL, headers=HEADERS, timeout=10, verify=False)
        _PING_VALUE = str(int((time.time() - st) * 1000))
        if r.status_code == 200:
            _NET_STATUS = True
            server_date = r.headers.get('Date')
            if server_date:
                # تبدیل زمان GMT سرور به زمان محلی سیستم با احتساب اختلاف ساعت ایران
                sd = datetime.datetime.strptime(server_date, '%a, %d %b %Y %H:%M:%S GMT')
                # زمان ایران معمولاً GMT+3.5 است، اما با استفاده از Timestamp هماهنگ می‌شود
                TIME_OFFSET = sd.timestamp() - time.time()
        else:
            _NET_STATUS = False
    except: 
        _NET_STATUS = False
        _PING_VALUE = "999"

def get_accurate_now():
    """دریافت تایم استمپ دقیق ثانیه‌ای بر اساس ساعت ایران"""
    return time.time() + TIME_OFFSET

def get_full_time_ir():
    """نمایش تاریخ و ساعت کامل شمسی/میلادی به وقت ایران"""
    # اضافه کردن ۳.۵ ساعت (۱۲۶۰۰ ثانیه) برای تنظیم دقیق روی لوکیشن ایران
    now = datetime.datetime.fromtimestamp(get_accurate_now() + 12600)
    return now.strftime('%Y-%m-%d %H:%M:%S')

def save_db(change_data=None):
    """ذخیره محلی و ارسال هوشمند 'فقط تغییرات' به هاست"""
    global DATA, SYNC_QUEUE
    with db_lock:
        # اگر تغییر جدیدی (مثل گزارش) ثبت شده، به صف ارسال اضافه کن
        if change_data:
            # اضافه کردن فیلدها برای هماهنگی با ستون‌های SQL
            change_data["staff_name"] = getattr(App.get_running_app(), 'session_user', 'System')
            change_data["report_time"] = get_full_time_ir()
            SYNC_QUEUE.append(change_data)
        
        try:
            with open(DB_FILE, "w", encoding='utf-8') as f:
                json.dump(DATA, f, indent=4, ensure_ascii=False)
        except: pass
    
    # اجرای موتور ارسال هوشمند در پس‌زمینه بدون قفل کردن اپلیکیشن
    if not _is_syncing:
        threading.Thread(target=smart_sync_engine, daemon=True).start()

def smart_sync_engine():
    """ارسال تفاضلی: فقط دیتای تغییر یافته را می‌فرستد (بسیار کم حجم و سریع)"""
    global _is_syncing, _NET_STATUS, SYNC_QUEUE
    if not SYNC_QUEUE: return
    _is_syncing = True
    
    try:
        with db_lock:
            # بسته‌بندی هوشمند: کل دیتا + لیست تغییرات اخیر
            payload = {
                "full_data": DATA,
                "changes": SYNC_QUEUE,
                "timestamp": get_accurate_now()
            }
            # کپی از تغییراتی که قرار است ارسال شوند
            current_batch = list(SYNC_QUEUE)

        # ارسال با Timeout بالا (۳۰ ثانیه) برای پایداری در پینگ‌های ضعیف اندروید
        r = requests.post(
            IRAN_BRIDGE_URL, 
            json=payload, 
            headers=HEADERS, 
            timeout=30,
            verify=False 
        )
        
        if r.status_code == 200 and "OK_SUCCESS" in r.text:
            _NET_STATUS = True
            with db_lock:
                # پس از تایید هاست، موارد ارسال شده را از صف حذف کن
                for item in current_batch:
                    if item in SYNC_QUEUE: SYNC_QUEUE.remove(item)
        else:
            _NET_STATUS = False
    except:
        _NET_STATUS = False
    finally:
        _is_syncing = False
# -*- coding: utf-8 -*-
# بخش ۳ از ۷ - همگام‌سازی ابری و کلاس‌های گرافیکی پایه

def check_auto_unban():
    now = get_accurate_now()
    changed = False
    with db_lock:
        # اصلاح برای اطمینان از سلامت دیتاتایپ برای جلوگیری از خطا در هاست
        if isinstance(DATA.get("banned_list"), list): DATA["banned_list"] = {}
        
        for uid in list(DATA["banned_list"].keys()):
            if now >= DATA["banned_list"][uid].get("expiry", 0):
                DATA["banned_list"].pop(uid)
                changed = True
    if changed: save_db({"action": "auto_unban"})

def load_db():
    global DATA
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding='utf-8') as f:
                with db_lock: DATA.update(json.load(f))
        except: pass
    
    # اطمینان از صحت ساختار دیکشنری پس از لود
    if not isinstance(DATA.get("banned_list"), dict): DATA["banned_list"] = {}
    if not isinstance(DATA.get("game_db"), dict): DATA["game_db"] = {}
    
    check_auto_unban()
    # فراخوانی موتور دریافت اطلاعات از هاست در بدو اجرا
    threading.Thread(target=fetch_cloud_engine, daemon=True).start()

def fetch_cloud_engine(on_complete=None):
    global _NET_STATUS, DATA
    try:
        # درخواست GET به هاست برای دریافت آخرین وضعیت دیتابیس
        r = requests.get(IRAN_BRIDGE_URL, headers=HEADERS, timeout=15, verify=False)
        if r.status_code == 200:
            _NET_STATUS = True
            # دریافت دیتای کامل از فایل JSON روی هاست
            cloud = r.json()
            
            if cloud and isinstance(cloud, dict) and "users" in cloud:
                with db_lock:
                    # همگام‌سازی بخش‌های مختلف دیتابیس با رعایت منطق ادمین
                    for key in cloud:
                        if key == "users":
                            DATA["users"].update(cloud["users"])
                        elif key == "staff_activity":
                            # فقط ادمین کل فعالیت‌ها را جایگزین می‌کند
                            if getattr(App.get_running_app(), 'session_user', '') == 'admin':
                                DATA[key] = cloud[key]
                        else:
                            # جلوگیری از تبدیل دیکشنری به لیست در هنگام دریافت دیتای خالی از هاست
                            if key in ["banned_list", "game_db"] and isinstance(cloud[key], list):
                                DATA[key] = {}
                            else:
                                DATA[key] = cloud[key]
                
                check_auto_unban()
                if on_complete: on_complete(True)
        else:
            if on_complete: on_complete(False)
    except:
        if on_complete: on_complete(False)

class ConnectionLight(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'; self.size_hint = (None, None); self.size = (95, 25); self.spacing = 5
        self.led = Label(size_hint=(None, None), size=(12, 12))
        self.ping_lbl = Label(text="0ms", font_size='10sp', color=(0.8, 0.8, 0.8, 1))
        self.add_widget(self.led); self.add_widget(self.ping_lbl)
        Clock.schedule_interval(self.update_status, 5)
    
    def update_status(self, dt):
        threading.Thread(target=sync_time_offset, daemon=True).start()
        self.ping_lbl.text = f"{_PING_VALUE}ms"
        self.led.canvas.before.clear()
        with self.led.canvas.before:
            # سبز برای اتصال برقرار، قرمز برای قطع اتصال
            Color(0.2, 0.8, 0.2, 1) if _NET_STATUS else Color(0.8, 0.2, 0.2, 1)
            RoundedRectangle(pos=self.led.pos, size=self.led.size, radius=[6,])

class ModernButton(Button):
    def __init__(self, bg_color=(0.18, 0.22, 0.3, 1), radius=[12,], **kwargs):
        super().__init__(**kwargs); self.background_normal = ""; self.background_color = (0,0,0,0)
        self.bg_color = bg_color; self.radius = radius; self.bind(pos=self._upd, size=self._upd)
    def _upd(self, *args):
        self.canvas.before.clear()
        with self.canvas.before: Color(*self.bg_color); RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
# -*- coding: utf-8 -*-
# بخش ۴ از ۷ - ورودی‌های مدرن و صفحه ورود هوشمند

class DynamicBlinkingInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.readonly = True; self.halign = 'center'
        self.background_normal = ""; self.background_color = (0.1, 0.12, 0.16, 1)
        self.foreground_color = (0.9, 0.9, 0.9, 1); self.is_blinking = False
        self._blink_ev = None
    
    def start_ban_blink(self, reason_text):
        if not self.is_blinking:
            self.is_blinking = True
            self.text = f"!!! BAN {reason_text} !!!"
            self._blink_ev = Clock.schedule_interval(self._do_blink, 0.3)
            Clock.schedule_once(lambda dt: self.stop_blink(""), 5)

    def stop_blink(self, default_text=""):
        if self._blink_ev: Clock.unschedule(self._blink_ev); self._blink_ev = None
        self.is_blinking = False; self.text = default_text
        self.background_color = (0.1, 0.12, 0.16, 1)

    def _do_blink(self, dt):
        self.background_color = [0.8, 0, 0, 1] if self.background_color == [0.1, 0.12, 0.16, 1] else [0.1, 0.12, 0.16, 1]

class ModernInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.background_normal = ""; self.background_color = (0.1, 0.12, 0.16, 1)
        self.foreground_color = (0.9, 0.9, 0.9, 1); self.padding = [10, 10, 10, 10]; self.multiline = False

def add_staff_log(target_id, action):
    """ثبت سوابق فعالیت ناظر با تاریخ و ساعت دقیق از سرور"""
    staff = getattr(App.get_running_app(), 'session_user', 'System')
    entry = {"staff": staff, "target": target_id, "action": action, "time": get_full_time_ir()}
    with db_lock:
        if "staff_activity" not in DATA: DATA["staff_activity"] = []
        DATA["staff_activity"].insert(0, entry)
    # افزودن لاگ به صف ارسال تفاضلی
    save_db({"action": "log", "entry": entry})

class LoginScreen(Screen):
    def on_enter(self): 
        # هماهنگ‌سازی ساعت با سرور جدید در بدو ورود
        threading.Thread(target=sync_time_offset, daemon=True).start()
        with db_lock:
            creds = DATA.get("saved_creds", {})
            u, p, auto = creds.get("u", ""), creds.get("p", ""), creds.get("auto_login", False)
        if u and p and auto:
            self.u.text, self.p.text = u, p
            Clock.schedule_once(self.login, 0.5)

    def __init__(self, **kw):
        super().__init__(**kw); self.layout = BoxLayout(orientation='vertical', padding=40, spacing=15)
        h = BoxLayout(size_hint_y=0.1); h.add_widget(ConnectionLight()); h.add_widget(Label()); self.layout.add_widget(h)
        self.layout.add_widget(Label(text="TEAM NEZARAT", font_size='32sp', bold=True, color=(0.4, 0.6, 0.8, 1), size_hint_y=0.2))
        self.u, self.p = ModernInput(hint_text="Username"), ModernInput(hint_text="Password", password=True)
        self.layout.add_widget(self.u); self.layout.add_widget(self.p)
        self.layout.add_widget(ModernButton(text="VOROOOD", height=65, bg_color=(0.2, 0.4, 0.3, 1), on_press=self.login))
        self.layout.add_widget(ModernButton(text="DARKHASTE OZVIYAT", height=55, bg_color=(0.2, 0.24, 0.3, 1), on_press=self.req))
        self.add_widget(self.layout)

    def login(self, x=None):
        self.u.hint_text = "VASYB BE TUNEL..."
        # استعلام لحظه‌ای از دیتابیس هاست جدید قبل از ورود
        threading.Thread(target=fetch_cloud_engine, args=(self.execute_login,), daemon=True).start()

    def execute_login(self, success):
        Clock.schedule_once(lambda dt: self._final_login_check())

    def _final_login_check(self):
        u, p = self.u.text.strip(), self.p.text.strip()
        # شناسایی دیوایس برای قفل سخت‌افزاری
        dev_id = socket.gethostname() if platform != 'android' else "ANDROID-NODE" 
        
        with db_lock:
            # بررسی دسترسی ادمین با پسورد هاردکد شده
            if u == "admin" and p == "MAHDI@#25#":
                App.get_running_app().session_user = u
                DATA["saved_creds"] = {"u": u, "p": p, "auto_login": True}
                save_db({"action": "admin_login"})
                self.manager.current = 'entry'
                return

            # بررسی یوزرهای معمولی در دیتابیس سینک شده از هاست
            if u in DATA["users"] and DATA["users"][u]["pass"] == p:
                user_info = DATA["users"][u]
                if user_info.get("status") == "approved":
                    if u in DATA.get("ejected_users", []): DATA["ejected_users"].remove(u)
                    
                    if not user_info.get("device"): 
                        user_info["device"] = dev_id
                        save_db({"action": "device_lock", "u": u, "dev": dev_id})
                    
                    if user_info["device"] == dev_id:
                        App.get_running_app().session_user = u
                        DATA["saved_creds"] = {"u": u, "p": p, "auto_login": True}
                        save_db({"action": "user_login", "u": u})
                        self.manager.current = 'entry'
                    else:
                        self.u.text = "GOSHI MOJAZ NIST!"
                else:
                    self.u.text = "TAYID NASHODID YA EKRAJID"
            else:
                self.u.text = "KHATA DAR VOROD"

    def req(self, x):
        u, p = self.u.text.strip(), self.p.text.strip()
        if u and p: 
            with db_lock: DATA["pending_requests"][u] = p
            save_db({"action": "request_join", "u": u, "p": p})
            self.u.text = "DAR KHAST ERSAL SHOD"
# -*- coding: utf-8 -*-
# بخش ۵ از ۷ - پنل اصلی گزارش‌دهی و مانیتورینگ آنی

BAN_DAYS_MAP = {"ETLAGH": 1, "USER/NAME": 2, "FAHASHI": 3, "TABANI": 5, "BI EHTARAMI": 4, "RADE SANI": 7}

class EntryScreen(Screen):
    def on_enter(self):
        self.monitor_ev = Clock.schedule_interval(self.check_ejection, 10)
        self.update_notice_display()

    def update_notice_display(self):
        self.notice_lbl.text = DATA.get("global_notice", "نظارت آنلاین")

    def check_ejection(self, dt):
        u = getattr(App.get_running_app(), 'session_user', '')
        if u in DATA.get("ejected_users", []):
            Clock.unschedule(self.monitor_ev)
            self.manager.current = 'login'
            App.get_running_app().root.get_screen('login').u.text = "EKRAJ SHODID!"

    def __init__(self, **kw):
        super().__init__(**kw); self.taps = 0; self.last_tap = 0
        l = BoxLayout(orientation='vertical', padding=20, spacing=12)
        h = BoxLayout(size_hint_y=0.05); h.add_widget(ConnectionLight()); h.add_widget(Label()); l.add_widget(h)
        
        self.notice_lbl = Label(text="", size_hint_y=0.05, color=(1, 0.8, 0.2, 1), bold=True)
        l.add_widget(self.notice_lbl)

        l.add_widget(Label(text="PANELE NEZARAT", bold=True, size_hint_y=0.08, font_size='20sp', color=(0.5, 0.6, 0.8, 1)))
        self.p_id = ModernInput(hint_text="ID Karbar", size_hint_y=0.1)
        l.add_widget(self.p_id)
        
        self.reason_box = DynamicBlinkingInput(hint_text="ENTEKHABE KHALAF", size_hint_y=0.08)
        l.add_widget(self.reason_box)
        
        grid = GridLayout(cols=2, spacing=10, size_hint_y=0.28)
        self.v_list = ["ETLAGH", "USER/NAME", "FAHASHI", "TABANI", "BI EHTARAMI", "RADE SANI"]
        for v in self.v_list: 
            grid.add_widget(ModernButton(text=v, font_size='13sp', on_press=lambda x, b=v: self.select_khalaf(b)))
        l.add_widget(grid)
        
        acts = BoxLayout(orientation='vertical', spacing=10, size_hint_y=0.41)
        acts.add_widget(ModernButton(text="SABT ANII (FAST)", bg_color=(0.4, 0.25, 0.25, 1), on_press=self.submit))
        
        row_btns = BoxLayout(spacing=10, size_hint_y=0.3)
        row_btns.add_widget(ModernButton(text="REPORTS", on_press=lambda x: setattr(self.manager, 'current', 'status')))
        row_btns.add_widget(ModernButton(text="BAN LIST", on_press=lambda x: setattr(self.manager, 'current', 'banned_list')))
        acts.add_widget(row_btns)
        
        acts.add_widget(ModernButton(text="KHOROOJ", bg_color=(0.3, 0.2, 0.2, 1), size_hint_y=0.25, on_press=self.logout))
        l.add_widget(acts); self.add_widget(l)

    def select_khalaf(self, name):
        self.reason_box.stop_blink(name)
        uid = self.p_id.text.strip()
        with db_lock:
            if not isinstance(DATA.get("game_db"), dict): DATA["game_db"] = {}
            if uid and uid in DATA["game_db"]:
                if DATA["game_db"][uid].get(name, 0) >= 10:
                    self.reason_box.start_ban_blink(name)

    def logout(self, x):
        with db_lock: DATA["saved_creds"]["auto_login"] = False
        save_db({"action": "logout"})
        self.manager.current = 'login'

    def submit(self, x):
        uid, vt = self.p_id.text.strip(), self.reason_box.text.strip()
        if not uid or vt not in self.v_list: return
        with db_lock:
            if not isinstance(DATA.get("game_db"), dict): DATA["game_db"] = {}
            if uid not in DATA["game_db"]: DATA["game_db"][uid] = {v:0 for v in self.v_list}
            DATA["game_db"][uid][vt] += 1
            count = DATA["game_db"][uid][vt]
            add_staff_log(uid, f"GozARESH: {vt} (Count: {count})")
            
            if count >= 10:
                days = BAN_DAYS_MAP.get(vt, 1)
                expiry = get_accurate_now() + (days * 86400)
                ban_entry = {"reason": vt, "date": get_full_time_ir(), "expiry": expiry}
                if not isinstance(DATA.get("banned_list"), dict): DATA["banned_list"] = {}
                DATA["banned_list"][uid] = ban_entry
                DATA["game_db"][uid][vt] = 0
                self.reason_box.start_ban_blink(vt)
                save_db({"action": "auto_ban", "uid": uid, "info": ban_entry})
            else:
                save_db({"action": "report", "uid": uid, "khalaf": vt, "new_count": count})
        self.p_id.text = ""

    def on_touch_down(self, t):
        if t.y > self.height * 0.9:
            u = getattr(App.get_running_app(), 'session_user', '')
            if u == "admin":
                now = time.time()
                self.taps = self.taps + 1 if now - self.last_tap < 1.5 else 1
                self.last_tap = now
                if self.taps >= 5: self.manager.current = 'admin_verify'; self.taps = 0
                return True
        return super().on_touch_down(t)
# -*- coding: utf-8 -*-
# بخش ۶ از ۷ - سیستم نمایش دیتای ابری و مدیریت جریمه‌ها

class StatusScreen(Screen):
    def on_enter(self): self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw)
        l = BoxLayout(orientation='vertical', padding=15, spacing=18)
        l.add_widget(Label(text="DETAILED REPORTS", bold=True, size_hint_y=0.08, color=(0.4, 0.7, 0.9, 1)))
        self.search = ModernInput(hint_text="Search Player ID...", size_hint_y=0.1)
        self.search.bind(text=self.refresh); l.add_widget(self.search)
        self.scroll = ScrollView(size_hint_y=0.6)
        self.grid = GridLayout(cols=1, spacing=25, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid); l.add_widget(self.scroll)
        l.add_widget(ModernButton(text="LISTE SIAH (Blacklist)", size_hint_y=0.08, bg_color=(0.5, 0.1, 0.1, 1), 
                                  on_press=lambda x: setattr(self.manager, 'current', 'blacklist_view')))
        self.adm_key = ModernInput(hint_text="Pass (If no permission)", password=True, size_hint_y=0.08)
        l.add_widget(self.adm_key)
        l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=0.08, on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        self.add_widget(l)

    def refresh(self, *args):
        self.grid.clear_widgets(); q = self.search.text.strip().lower()
        with db_lock:
            if not isinstance(DATA.get("game_db"), dict): DATA["game_db"] = {}
            items = list(DATA.get("game_db", {}).items())
            for uid, reps in items:
                if q and q not in uid.lower(): continue
                active = [f"{k}: {v}" for k, v in reps.items() if v > 0]
                if active:
                    card = BoxLayout(orientation='vertical', size_hint_y=None, height=185, padding=18, spacing=10)
                    with card.canvas.before:
                        Color(0.15, 0.17, 0.22, 1); r = RoundedRectangle(pos=card.pos, size=card.size, radius=[12,])
                    card.bind(pos=lambda ins,v,r=r: setattr(r,'pos',ins.pos), size=lambda ins,v,r=r: setattr(r,'size',ins.size))
                    row1 = BoxLayout(size_hint_y=0.3)
                    row1.add_widget(Label(text=f"ID: {uid}", bold=True, font_size='18sp'))
                    row1.add_widget(ModernButton(text="RESET", size_hint_x=0.3, bg_color=(0.5, 0.2, 0.2, 1), on_press=lambda x, i=uid: self.quick_unb(i)))
                    card.add_widget(row1)
                    ig = GridLayout(cols=2, size_hint_y=0.7, spacing=10)
                    for r_t in active: ig.add_widget(Label(text=r_t, font_size='12sp', color=(0.8, 0.8, 0.9, 1)))
                    card.add_widget(ig); self.grid.add_widget(card)

    def quick_unb(self, uid):
        u = getattr(App.get_running_app(), 'session_user', '')
        is_permitted = u == "admin" or u in DATA.get("permissions", [])
        if is_permitted or self.adm_key.text == "MAHDI@#25#":
            with db_lock:
                if isinstance(DATA.get("game_db"), dict): DATA["game_db"].pop(uid, None)
            save_db({"action": "reset_player", "uid": uid})
            self.adm_key.text = ""; self.refresh()
        else: self.adm_key.text = "PERMISSION DENIED"

class BlacklistScreen(Screen):
    def on_enter(self): self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=10)
        l.add_widget(Label(text="PERMANENT BLACKLIST", bold=True, size_hint_y=0.1, color=(1, 0.2, 0.2, 1)))
        self.scroll = ScrollView(); self.grid = GridLayout(cols=1, spacing=12, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height')); self.scroll.add_widget(self.grid); l.add_widget(self.scroll)
        self.key = ModernInput(hint_text="Pass (If no permission)", password=True, size_hint_y=0.1)
        l.add_widget(self.key)
        l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=0.1, on_press=lambda x: setattr(self.manager, 'current', 'status')))
        self.add_widget(l)

    def refresh(self):
        self.grid.clear_widgets()
        with db_lock:
            bl_list = DATA.get("blacklist")
            if not isinstance(bl_list, list): DATA["blacklist"] = []; bl_list = []
            for uid in bl_list:
                c = BoxLayout(size_hint_y=None, height=65, padding=10)
                with c.canvas.before: Color(0.1, 0.1, 0.1, 1); RoundedRectangle(pos=c.pos, size=c.size, radius=[8,])
                c.add_widget(Label(text=f"BANNED ID: {uid}", bold=True, color=(1, 0.4, 0.4, 1)))
                c.add_widget(ModernButton(text="REMOVE", size_hint_x=0.3, bg_color=(0.2, 0.4, 0.2, 1), 
                                   on_press=lambda x, i=uid: self.un_blacklist(i)))
                self.grid.add_widget(c)

    def un_blacklist(self, uid):
        u = getattr(App.get_running_app(), 'session_user', '')
        is_permitted = u == "admin" or u in DATA.get("permissions", [])
        if is_permitted or self.key.text == "MAHDI@#25#":
            with db_lock: 
                if isinstance(DATA.get("blacklist"), list) and uid in DATA["blacklist"]: 
                    DATA["blacklist"].remove(uid)
            save_db({"action": "remove_blacklist", "uid": uid})
            self.key.text = ""; self.refresh()
        else: self.key.text = "NO PERMISSION"
# -*- coding: utf-8 -*-
# بخش ۷ از ۷ - مدیریت کلان (Owner Dashboard) و اجرای نهایی اپلیکیشن

class BannedScreen(Screen):
    def on_enter(self): 
        check_auto_unban(); self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=15)
        l.add_widget(Label(text="LISTE BANNED (MOGHATI)", bold=True, size_hint_y=0.1, color=(0.8, 0.4, 0.4, 1)))
        self.key = ModernInput(hint_text="Pass (If no permission)", password=True, size_hint_y=0.1)
        l.add_widget(self.key)
        self.scroll = ScrollView(size_hint_y=0.7); self.grid = GridLayout(cols=1, spacing=15, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height')); self.scroll.add_widget(self.grid); l.add_widget(self.scroll)
        l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=0.1, on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        self.add_widget(l)

    def refresh(self, *args):
        self.grid.clear_widgets(); now = get_accurate_now()
        with db_lock:
            if not isinstance(DATA.get("banned_list"), dict): DATA["banned_list"] = {}
            items = list(DATA.get("banned_list", {}).items())
        for uid, info in items:
            rem_h = max(0, int((info.get('expiry', 0) - now) / 3600))
            c = BoxLayout(orientation='vertical', size_hint_y=None, height=115, padding=10, spacing=5)
            with c.canvas.before: Color(0.2, 0.1, 0.14, 1); r = RoundedRectangle(pos=c.pos, size=c.size, radius=[12,])
            c.add_widget(Label(text=f"ID: {uid} | Khalaf: {info.get('reason')}", bold=True, font_size='14sp'))
            c.add_widget(Label(text=f"Time Left: {rem_h}h", font_size='11sp', color=(0.7,0.7,0.7,1)))
            c.add_widget(ModernButton(text="UNBAN", size_hint_y=None, height=35, on_press=lambda x, i=uid: self.secure_unb(i)))
            self.grid.add_widget(c)

    def secure_unb(self, uid):
        u = getattr(App.get_running_app(), 'session_user', '')
        is_permitted = u == "admin" or u in DATA.get("permissions", [])
        if is_permitted or self.key.text == "MAHDI@#25#":
            with db_lock: 
                if isinstance(DATA.get("banned_list"), dict) and uid in DATA["banned_list"]: DATA["banned_list"].pop(uid)
            save_db({"action": "unban_player", "uid": uid})
            self.key.text = ""; self.refresh()

class AdminPanel(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=25, spacing=15)
        l.add_widget(Label(text="OWNER DASHBOARD (v1.2)", bold=True, size_hint_y=0.1, font_size='22sp'))
        btn_grid = GridLayout(cols=1, spacing=12, size_hint_y=0.7)
        btn_grid.add_widget(ModernButton(text="TAYIDE NAZERIN (Requests)", bg_color=(0.1, 0.4, 0.4, 1), on_press=self.show_req_popup))
        btn_grid.add_widget(ModernButton(text="LIST & EKRAJE NAZERIN", bg_color=(0.2, 0.3, 0.5, 1), on_press=self.show_staff_mgmt))
        btn_grid.add_widget(ModernButton(text="LOGS & PERFORMANCE", bg_color=(0.5, 0.3, 0.1, 1), on_press=self.show_staff_logs))
        btn_grid.add_widget(ModernButton(text="NOTICE & BLACKLIST", bg_color=(0.4, 0.1, 0.1, 1), on_press=self.show_tools_popup))
        btn_grid.add_widget(ModernButton(text="MODIRIYATE DASTRESI", bg_color=(0.3, 0.3, 0.3, 1), on_press=self.show_perm_mgmt))
        l.add_widget(btn_grid)
        l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=0.15, bg_color=(0.2, 0.2, 0.2, 1), on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        self.add_widget(l)

    def show_perm_mgmt(self, x):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView(); grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height')); scroll.add_widget(grid)
        with db_lock:
            for u in DATA.get("users", {}):
                if u == "admin": continue
                if DATA["users"][u].get("status") != "approved": continue
                row = BoxLayout(size_hint_y=None, height=50, spacing=10)
                is_granted = u in DATA.get("permissions", [])
                btn_txt = "Laghv Dastresi" if is_granted else "Ete dastreasi"
                row.add_widget(Label(text=u))
                row.add_widget(ModernButton(text=btn_txt, bg_color=(0.4,0.2,0.2,1) if is_granted else (0.2,0.4,0.2,1),
                                            on_press=lambda x, user=u: self.toggle_perm(user)))
                grid.add_widget(row)
        box.add_widget(scroll); pop = Popup(title="Management Permissions", content=box, size_hint=(0.9, 0.8)); pop.open()

    def toggle_perm(self, u):
        with db_lock:
            if u in DATA["permissions"]: DATA["permissions"].remove(u)
            else: DATA["permissions"].append(u)
        save_db({"action": "toggle_permission", "u": u})

    def show_req_popup(self, x):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView(); grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height')); scroll.add_widget(grid)
        with db_lock:
            for u, p in list(DATA.get("pending_requests", {}).items()):
                row = BoxLayout(size_hint_y=None, height=50, spacing=5)
                row.add_widget(Label(text=f"User: {u}", font_size='13sp'))
                row.add_widget(ModernButton(text="OK", bg_color=(0,0.5,0,1), on_press=lambda x, user=u, pas=p: self.approve(user, pas)))
                grid.add_widget(row)
        box.add_widget(scroll); pop = Popup(title="New Requests", content=box, size_hint=(0.9, 0.8)); pop.open()

    def approve(self, u, p):
        with db_lock:
            if u in DATA.get("ejected_users", []): DATA["ejected_users"].remove(u)
            DATA["users"][u] = {"pass": p, "status": "approved", "device": ""}
            if u in DATA["pending_requests"]: DATA["pending_requests"].pop(u)
            add_staff_log(u, "TAYID MAJJAD")
        save_db({"action": "approve_user", "u": u, "p": p})

    def show_staff_mgmt(self, x):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView(); grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height')); scroll.add_widget(grid)
        with db_lock:
            for u, info in DATA.get("users", {}).items():
                if info.get("status") == "approved" and u != "admin":
                    row = BoxLayout(size_hint_y=None, height=55, padding=5, spacing=5)
                    row.add_widget(Label(text=f"Nazer: {u}", bold=True))
                    row.add_widget(ModernButton(text="EKRAJ", bg_color=(0.6, 0.1, 0.1, 1), on_press=lambda x, user=u: self.eject(user)))
                    grid.add_widget(row)
        box.add_widget(scroll); pop = Popup(title="Staff Management", content=box, size_hint=(0.95, 0.85)); pop.open()

    def eject(self, u):
        with db_lock:
            if u in DATA.get("permissions", []): DATA["permissions"].remove(u)
            if u not in DATA["ejected_users"]: DATA["ejected_users"].append(u)
            if u in DATA["users"]: DATA["users"][u]["status"] = "ejected"
            add_staff_log(u, "EKRAJ SHOD")
        save_db({"action": "eject_user", "u": u})

    def show_staff_logs(self, x):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView(); grid = GridLayout(cols=1, spacing=8, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height')); scroll.add_widget(grid)
        with db_lock:
            for entry in DATA.get("staff_activity", []):
                c = BoxLayout(orientation='vertical', size_hint_y=None, height=85, padding=10)
                with c.canvas.before: Color(0.12, 0.15, 0.2, 1); RoundedRectangle(pos=c.pos, size=c.size, radius=[8,])
                c.add_widget(Label(text=f"Staff: {entry['staff']} | Target: {entry['target']}", bold=True, font_size='12sp'))
                c.add_widget(Label(text=f"Action: {entry['action']} | Time: {entry['time']}", font_size='10sp', color=(0.6,0.6,0.6,1)))
                grid.add_widget(c)
        box.add_widget(scroll); pop = Popup(title="Staff Logs", content=box, size_hint=(0.95, 0.9)); pop.open()

    def show_tools_popup(self, x):
        box = BoxLayout(orientation='vertical', padding=15, spacing=10)
        not_inp = ModernInput(hint_text="Global Notice..."); not_inp.text = DATA.get("global_notice", "")
        box.add_widget(not_inp)
        bl_inp = ModernInput(hint_text="ID for Blacklist..."); box.add_widget(bl_inp)
        def save_tools(instance):
            with db_lock:
                DATA["global_notice"] = not_inp.text
                if bl_inp.text and bl_inp.text not in DATA["blacklist"]: DATA["blacklist"].append(bl_inp.text)
            save_db({"action": "update_tools", "notice": not_inp.text, "bl": bl_inp.text})
            pop.dismiss()
        box.add_widget(ModernButton(text="SABT", bg_color=(0.1, 0.4, 0.2, 1), on_press=save_tools))
        pop = Popup(title="Admin Tools", content=box, size_hint=(0.8, 0.6)); pop.open()

class AdminVerifyScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=60, spacing=20)
        l.add_widget(Label(text="ADMIN VERIFY", bold=True, font_size='24sp'))
        self.c = ModernInput(hint_text="Master Key", password=True); l.add_widget(self.c)
        l.add_widget(ModernButton(text="VOROOOD", height=60, on_press=self.verify))
        l.add_widget(ModernButton(text="BACK", height=50, bg_color=(0.2,0.2,0.2,1), on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        self.add_widget(l)
    def verify(self, x):
        if self.c.text == "MAHDI@#25#": 
            self.c.text = ""; self.manager.current = 'admin_panel'
        else: self.c.text = "WRONG KEY"

class TeamNezaratApp(App):
    def build(self):
        self.session_user = "Guest"; load_db()
        from kivy.core.window import Window
        Window.clearcolor = (0.05, 0.05, 0.08, 1)
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(EntryScreen(name='entry'))
        sm.add_widget(AdminVerifyScreen(name='admin_verify'))
        sm.add_widget(AdminPanel(name='admin_panel'))
        sm.add_widget(BannedScreen(name='banned_list'))
        sm.add_widget(StatusScreen(name='status'))
        sm.add_widget(BlacklistScreen(name='blacklist_view'))
        Clock.schedule_interval(self.auto_tasks, 60); return sm
    def auto_tasks(self, dt):
        threading.Thread(target=sync_time_offset, daemon=True).start(); check_auto_unban()

if __name__ == '__main__':
    try: TeamNezaratApp().run()
    except Exception as e: print(f"FATAL ERROR: {e}")
