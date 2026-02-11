# -*- coding: utf-8 -*-
import json, os, datetime, time, threading, requests, urllib3, socket, uuid
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.utils import platform

# غیرفعال کردن اخطارهای امنیتی برای پایداری در شبکه ایران
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CURRENT_VERSION = "1.2" 
IRAN_BRIDGE_URL = "https://devconnect-123.ir"
API_SECRET_KEY = "MAHDI_SECURE_TOKEN_2024"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Mobile)',
    'Content-Type': 'application/json',
    'X-API-KEY': API_SECRET_KEY,
    'Cache-Control': 'no-cache'
}

# قفل‌های سیستمی برای مدیریت ۱۵۰ فعالیت همزمان بدون تداخل حافظه
db_lock = threading.RLock()
_is_syncing = False
_NET_STATUS = False 
_PING_VALUE = "0"
TIME_OFFSET = 0 
SYNC_QUEUE = [] 

def get_storage_path():
    """تعیین مسیر ذخیره‌سازی فایل‌ها هماهنگ با اندروید و ویندوز"""
    if platform == 'android':
        try:
            from android.storage import app_storage_path
            return app_storage_path()
        except: pass
        return "/sdcard/Documents/MafiaGuard"
    return os.getcwd()

STORAGE_DIR = get_storage_path()
if not os.path.exists(STORAGE_DIR): os.makedirs(STORAGE_DIR, exist_ok=True)

DB_FILE = os.path.join(STORAGE_DIR, "mafia_guard_v32.json")
LOCAL_CONFIG_FILE = os.path.join(STORAGE_DIR, "user_private_config.json")

# دیتای پیش‌فرض با ساختار اصلاح شده برای جلوگیری از خطای AttributeError
DATA = {
    "version": CURRENT_VERSION,
    "users": {"admin": {"pass": "MAHDI@#25#", "status": "approved", "device": ""}}, 
    "permissions": [], "game_db": {}, "pending_requests": {}, 
    "blacklist": [], "banned_list": {}, "global_notice": "خوش آمدید", 
    "staff_activity": [], "ejected_users": []
}

LOCAL_SETTINGS = {"saved_creds": {"u": "", "p": "", "auto_login": False}}

def gregorian_to_jalali(gy, gm, gd):
    """فرمول دقیق تبدیل تاریخ میلادی به شمسی بدون باگ اعدادی"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0):
        if gm > 2: gd += 1
    g_day_no = 365 * (gy - 1600) + (gy - 1597) // 4 - (gy - 1501) // 100 + (gy - 1501) // 400 + g_d_m[gm - 1] + gd - 79
    j_np = g_day_no // 12053
    g_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (g_day_no // 1461)
    g_day_no %= 1461
    if g_day_no >= 366:
        jy += (g_day_no - 1) // 365
        g_day_no = (g_day_no - 1) % 365
    for i in range(11):
        if g_day_no < [31, 62, 93, 124, 155, 186, 216, 246, 276, 306, 336][i]:
            jm = i + 1
            jd = g_day_no - (0 if i == 0 else [31, 62, 93, 124, 155, 186, 216, 246, 276, 306, 336][i-1]) + 1
            return f"{jy}/{jm:02d}/{jd:02d}"
    return f"{jy}/12/{(g_day_no - 336 + 1):02d}"

def sync_time_offset():
    """هماهنگی زمان موبایل با سرور جهت ابطال بن‌های غیرمجاز"""
    global TIME_OFFSET, _NET_STATUS, _PING_VALUE
    try:
        st = time.time()
        r = requests.get(f"{IRAN_BRIDGE_URL}?ping=1&v={time.time()}", headers=HEADERS, timeout=4, verify=False)
        _PING_VALUE = str(int((time.time() - st) * 1000))
        if r.status_code == 200:
            _NET_STATUS = True
            server_ts = r.json().get('t', time.time())
            TIME_OFFSET = server_ts - time.time()
        else:
            _NET_STATUS = False
    except: 
        _NET_STATUS = False; _PING_VALUE = "999"

def get_accurate_now():
    """محاسبه زمان دقیق بدون توجه به تغییرات ساعت گوشی توسط کاربر"""
    return time.time() + TIME_OFFSET

def get_full_time_ir():
    """خروجی زمان دقیق شمسی برای ثبت در دیتابیس MySQL"""
    now = datetime.datetime.fromtimestamp(get_accurate_now())
    shamsi_date = gregorian_to_jalali(now.year, now.month, now.day)
    return f"{shamsi_date} {now.strftime('%H:%M:%S')}"
def save_local_settings():
    """ذخیره تنظیمات خصوصی ناظر در فایل لوکال گوشی"""
    try:
        with open(LOCAL_CONFIG_FILE, "w", encoding='utf-8') as f:
            json.dump(LOCAL_SETTINGS, f, indent=4, ensure_ascii=False)
    except: 
        pass
def save_db(change_data=None):
    """ثبت تغییرات در صف و ذخیره آنی در حافظه گوشی با آیدی منحصر‌به‌فرد"""
    global DATA, SYNC_QUEUE
    with db_lock:
        if change_data:
            # ایجاد UUID برای هر تغییر جهت جلوگیری از ثبت تکراری در SQL
            change_data["change_id"] = str(uuid.uuid4())
            change_data["staff_name"] = getattr(App.get_running_app(), 'session_user', 'System')
            change_data["report_time"] = get_full_time_ir()
            if change_data not in SYNC_QUEUE:
                SYNC_QUEUE.append(change_data)
        
        try:
            # ذخیره امن: ابتدا در فایل موقت و سپس جایگزینی (جلوگیری از فساد فایل)
            temp_file = DB_FILE + ".tmp"
            with open(temp_file, "w", encoding='utf-8') as f:
                json.dump(DATA, f, indent=4, ensure_ascii=False)
            if os.path.exists(temp_file):
                if os.path.exists(DB_FILE): os.remove(DB_FILE)
                os.rename(temp_file, DB_FILE)
        except: 
            pass
    
    # بیدار کردن خودکار موتور همگام‌سازی
    if not _is_syncing and _NET_STATUS:
        threading.Thread(target=smart_sync_engine, daemon=True).start()
def smart_sync_engine():
    """ارسال تراکنش‌های محلی به هاست هماهنگ با ۵۰۰ ناظر همزمان"""
    global _is_syncing, _NET_STATUS, SYNC_QUEUE
    if not SYNC_QUEUE or _is_syncing: return
    _is_syncing = True
    
    try:
        with db_lock:
            current_batch = list(SYNC_QUEUE)
            clean_data = {k: v for k, v in DATA.items() if k != "saved_creds"}
            payload = {
                "full_data": clean_data,
                "changes": current_batch,
                "timestamp": get_accurate_now(),
                "app_version": CURRENT_VERSION
            }

        r = requests.post(IRAN_BRIDGE_URL, json=payload, headers=HEADERS, timeout=12, verify=False)
        
        if r.status_code == 200 and "OK_SUCCESS" in r.text:
            _NET_STATUS = True
            with db_lock:
                for item in current_batch:
                    if item in SYNC_QUEUE: SYNC_QUEUE.remove(item)
            # دریافت دیتای جدید بلافاصله پس از ارسال موفق
            threading.Thread(target=fetch_cloud_engine, daemon=True).start()
        else:
            _NET_STATUS = False
    except:
        _NET_STATUS = False
    finally:
        _is_syncing = False

def fetch_cloud_engine(on_complete=None):
    """دریافت دیتا از سرور و رفع باگ AttributeError با اجبار به نوع داده صحیح"""
    global _NET_STATUS, DATA
    try:
        r = requests.get(f"{IRAN_BRIDGE_URL}?v={time.time()}", headers=HEADERS, timeout=10, verify=False)
        if r.status_code == 200:
            _NET_STATUS = True
            cloud = r.json()
            if cloud and isinstance(cloud, dict):
                with db_lock:
                    # ذخیره تنظیمات لاگین محلی
                    saved_local = dict(DATA.get("saved_creds", {}))
                    
                    # اصلاح ارشد: اجبار به دیکشنری یا لیست برای جلوگیری از کرش در ترافیک بالا
                    DATA["game_db"] = dict(cloud.get("game_db", {}))
                    DATA["users"] = dict(cloud.get("users", {}))
                    DATA["banned_list"] = dict(cloud.get("banned_list", {}))
                    DATA["pending_requests"] = dict(cloud.get("pending_requests", {}))
                    
                    DATA["blacklist"] = list(cloud.get("blacklist", []))
                    DATA["permissions"] = list(cloud.get("permissions", []))
                    DATA["ejected_users"] = list(cloud.get("ejected_users", []))
                    DATA["staff_activity"] = list(cloud.get("staff_activity", []))
                    DATA["global_notice"] = str(cloud.get("global_notice", "نظارت فعال"))
                    
                    DATA["saved_creds"] = saved_local
                
                check_auto_unban()
                if on_complete: Clock.schedule_once(lambda dt: on_complete(True))
                return
        if on_complete: Clock.schedule_once(lambda dt: on_complete(False))
    except:
        if on_complete: Clock.schedule_once(lambda dt: on_complete(False))
def check_auto_unban():
    """بررسی آزادکردن خودکار با زمان هماهنگ شده سرور (جلوگیری از تقلب ساعتی)"""
    now = get_accurate_now()
    changed = False
    with db_lock:
        if not isinstance(DATA.get("banned_list"), dict): DATA["banned_list"] = {}
        keys = list(DATA["banned_list"].keys())
        for uid in keys:
            expiry = DATA["banned_list"][uid].get("expiry", 0)
            if now >= expiry:
                DATA["banned_list"].pop(uid, None)
                changed = True
    if changed: 
        save_db({"action": "auto_unban_sync"})
def load_db():
    """بارگذاری اولیه دیتا با تفکیک دقیق تنظیمات محلی و دیتای کلود"""
    global DATA, LOCAL_SETTINGS
    if os.path.exists(LOCAL_CONFIG_FILE):
        try:
            with open(LOCAL_CONFIG_FILE, "r", encoding='utf-8') as f:
                ls = json.load(f)
                if isinstance(ls, dict): LOCAL_SETTINGS.update(ls)
        except: pass

    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding='utf-8') as f:
                with db_lock: 
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict):
                        for k, v in loaded_data.items():
                            if k != "saved_creds": DATA[k] = v
        except: pass
    
    ess_keys = ["staff_activity", "ejected_users", "banned_list", "game_db", "permissions", "pending_requests", "blacklist"]
    for key in ess_keys:
        if key not in DATA:
            DATA[key] = [] if key in ["staff_activity", "ejected_users", "permissions", "blacklist"] else {}
    check_auto_unban()

class ConnectionLight(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'; self.size_hint = (None, None); self.size = (100, 25); self.spacing = 5
        self.led = Label(size_hint=(None, None), size=(12, 12))
        self.ping_lbl = Label(text="...", font_size='10sp', color=(0.8, 0.8, 0.8, 1))
        self.add_widget(self.led); self.add_widget(self.ping_lbl)
        Clock.schedule_once(self.update_status, 0.1)
        Clock.schedule_interval(self.update_status, 5)

    def update_status(self, dt):
        threading.Thread(target=sync_time_offset, daemon=True).start()
        self.ping_lbl.text = f"{_PING_VALUE}ms"
        self.led.canvas.before.clear()
        with self.led.canvas.before:
            if not _NET_STATUS: Color(0.8, 0.2, 0.2, 1)
            elif int(_PING_VALUE) < 150: Color(0.2, 0.8, 0.2, 1)
            else: Color(0.8, 0.8, 0.2, 1)
            self._rect = RoundedRectangle(pos=self.led.pos, size=self.led.size, radius=[6,])
        self.led.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        if hasattr(self, '_rect'):
            self._rect.pos = self.led.pos
            self._rect.size = self.led.size

class ModernButton(Button):
    def __init__(self, bg_color=(0.18, 0.22, 0.3, 1), radius=[12,], **kwargs):
        super().__init__(**kwargs); self.background_normal = ""; self.background_color = (0,0,0,0)
        self.bg_color = bg_color; self.radius = radius; self.bind(pos=self._upd, size=self._upd)
    def _upd(self, *args):
        self.canvas.before.clear()
        with self.canvas.before: 
            Color(*self.bg_color); RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)

class DynamicBlinkingInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.readonly = True; self.halign = 'center'
        self.background_normal = ""; self.background_color = (0.1, 0.12, 0.16, 1)
        self.foreground_color = (0.9, 0.9, 0.9, 1); self.is_blinking = False
        self._blink_ev = None
    def start_ban_blink(self, reason_text):
        if self._blink_ev: Clock.unschedule(self._blink_ev)
        self.is_blinking = True; self.text = f"!!! BAN {reason_text} !!!"
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
        self.foreground_color = (0.9, 0.9, 0.9, 1); self.padding = [10, 10]; self.multiline = False

def add_staff_log(target_id, action):
    staff = getattr(App.get_running_app(), 'session_user', 'System')
    full_time = get_full_time_ir()
    entry = {"staff": staff, "target": target_id, "action": action, "time": full_time}
    with db_lock:
        if "staff_activity" not in DATA or not isinstance(DATA["staff_activity"], list):
            DATA["staff_activity"] = []
        DATA["staff_activity"].insert(0, entry)
class LoginScreen(Screen):
    def on_enter(self): 
        threading.Thread(target=sync_time_offset, daemon=True).start()
        with db_lock:
            creds = LOCAL_SETTINGS.get("saved_creds", {})
            u, p, auto = creds.get("u", ""), creds.get("p", ""), creds.get("auto_login", False)
        
        if u and p and auto:
            self.u.text, self.p.text = u, p
            Clock.schedule_once(lambda dt: self.login(), 0.5)

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
        if not self.u.text.strip(): return
        self.u.hint_text = "VASYB BE TUNEL..."
        threading.Thread(target=fetch_cloud_engine, args=(self.execute_login,), daemon=True).start()

    def execute_login(self, success):
        Clock.schedule_once(lambda dt: self._final_login_check(success))

    def _final_login_check(self, net_success):
        if not net_success: 
            self.u.text = "KHATAYE SHABAKE!"; return
        
        u, p = self.u.text.strip(), self.p.text.strip()
        
        if platform == 'android':
            try:
                from jnius import autoclass
                Secure = autoclass('android.provider.Settings$Secure')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                ctx = PythonActivity.mActivity
                dev_id = Secure.getString(ctx.getContentResolver(), Secure.ANDROID_ID)
            except: dev_id = socket.gethostname() + "_android_v4"
        else: dev_id = socket.gethostname() + "_pc"
        
        with db_lock:
            if u == "admin" and p == "MAHDI@#25#":
                App.get_running_app().session_user = u
                LOCAL_SETTINGS["saved_creds"] = {"u": u, "p": p, "auto_login": True}
                save_local_settings(); self.manager.current = 'entry'; return

            users_db = DATA.get("users", {})
            if u in users_db and users_db[u]["pass"] == p:
                user_info = users_db[u]
                if user_info.get("status") == "approved":
                    if not user_info.get("device"): 
                        user_info["device"] = dev_id
                        save_db({"action": "device_lock", "u": u, "dev": dev_id})
                    if user_info["device"] == dev_id:
                        App.get_running_app().session_user = u
                        LOCAL_SETTINGS["saved_creds"] = {"u": u, "p": p, "auto_login": True}
                        save_local_settings(); self.manager.current = 'entry'
                    else:
                        self.u.text = "GOSHI MOJAZ NIST!"
                        LOCAL_SETTINGS["saved_creds"]["auto_login"] = False; save_local_settings()
                else:
                    self.u.text = "NAZER TAYID NASHOD"
                    LOCAL_SETTINGS["saved_creds"]["auto_login"] = False; save_local_settings()
            else:
                self.u.text = "USER YA PASS GHALAT"
                LOCAL_SETTINGS["saved_creds"]["auto_login"] = False; save_local_settings()

    def req(self, x):
        u, p = self.u.text.strip(), self.p.text.strip()
        if u and p: 
            with db_lock:
                if not isinstance(DATA.get("pending_requests"), dict): DATA["pending_requests"] = {}
                DATA["pending_requests"][u] = p
            save_db({"action": "request_join", "u": u, "p": p}); self.u.text = "ERSAL SHOD."
BAN_DAYS_MAP = {"ETLAGH": 1, "USER/NAME": 2, "FAHASHI": 3, "TABANI": 5, "BI EHTARAMI": 4, "RADE SANI": 7}

class EntryScreen(Screen):
    def on_enter(self):
        self.monitor_ev = Clock.schedule_interval(self.check_ejection, 15)
        self.update_notice_display()

    def update_notice_display(self):
        self.notice_lbl.text = str(DATA.get("global_notice", "نظارت آنلاین فعال است"))

    def check_ejection(self, dt):
        u = getattr(App.get_running_app(), 'session_user', '')
        with db_lock:
            ej_list = DATA.get("ejected_users", [])
            if not isinstance(ej_list, list): ej_list = []
            if u in ej_list:
                Clock.unschedule(self.monitor_ev); self.logout(None)

    def __init__(self, **kw):
        super().__init__(**kw); self.taps = 0; self.last_tap = 0
        l = BoxLayout(orientation='vertical', padding=20, spacing=12)
        h = BoxLayout(size_hint_y=0.05); h.add_widget(ConnectionLight()); h.add_widget(Label()); l.add_widget(h)
        self.notice_lbl = Label(text="", size_hint_y=0.05, color=(1, 0.8, 0.2, 1), bold=True)
        l.add_widget(self.notice_lbl)
        l.add_widget(Label(text="PANELE NEZARAT", bold=True, size_hint_y=0.08, font_size='20sp'))
        self.p_id = ModernInput(hint_text="ID Karbar", size_hint_y=0.1)
        l.add_widget(self.p_id)
        self.reason_box = DynamicBlinkingInput(hint_text="ENTEKHABE KHALAF", size_hint_y=0.08)
        l.add_widget(self.reason_box)
        grid = GridLayout(cols=2, spacing=10, size_hint_y=0.28)
        self.v_list = list(BAN_DAYS_MAP.keys())
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
        self.reason_box.stop_blink(name); uid = self.p_id.text.strip()
        with db_lock:
            g_db = DATA.get("game_db", {})
            if not isinstance(g_db, dict): g_db = {}
            db_copy = g_db.get(uid, {})
            if not isinstance(db_copy, dict): db_copy = {}
            if uid and db_copy.get(name, 0) >= 10: self.reason_box.start_ban_blink(name)

    def logout(self, x):
        with db_lock: 
            if "saved_creds" in LOCAL_SETTINGS: LOCAL_SETTINGS["saved_creds"]["auto_login"] = False
        save_local_settings(); self.manager.current = 'login'

    def submit(self, x):
        uid, vt = self.p_id.text.strip(), self.reason_box.text.strip()
        if not uid or vt not in self.v_list: return
        with db_lock:
            if not isinstance(DATA["game_db"], dict): DATA["game_db"] = {}
            if uid not in DATA["game_db"]: DATA["game_db"][uid] = {}
            if vt not in DATA["game_db"][uid]: DATA["game_db"][uid][vt] = 0
            
            DATA["game_db"][uid][vt] += 1
            count = DATA["game_db"][uid][vt]
            add_staff_log(uid, f"GozARESH: {vt} ({count})")
            if count >= 10:
                if uid in DATA["game_db"] and vt in DATA["game_db"][uid]:
                    DATA["game_db"][uid].pop(vt)
                expiry = get_accurate_now() + (BAN_DAYS_MAP[vt] * 86400)
                ban_entry = {"reason": vt, "date": get_full_time_ir(), "expiry": expiry}
                if not isinstance(DATA["banned_list"], dict): DATA["banned_list"] = {}
                DATA["banned_list"][uid] = ban_entry
                self.reason_box.start_ban_blink(vt); save_db({"action": "auto_ban", "uid": uid, "info": ban_entry})
            else: 
                save_db({"action": "report", "uid": uid, "khalaf": vt, "new_count": count})
        self.p_id.text = ""; self.reason_box.text = ""

    def on_touch_down(self, t):
        if t.y > self.height * 0.9 and getattr(App.get_running_app(), 'session_user', '') == "admin":
            self.taps = self.taps + 1 if time.time() - self.last_tap < 1.5 else 1
            self.last_tap = time.time()
            if self.taps >= 5: self.manager.current = 'admin_verify'; self.taps = 0
            return True
        return super().on_touch_down(t)
class StatusScreen(Screen):
    def on_enter(self): self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=15, spacing=18)
        l.add_widget(Label(text="DETAILED REPORTS", bold=True, size_hint_y=0.08, color=(0.4, 0.7, 0.9, 1)))
        self.search = ModernInput(hint_text="Search Player ID...", size_hint_y=0.1)
        self.search.bind(text=self.refresh); l.add_widget(self.search)
        self.scroll = ScrollView(size_hint_y=0.6); self.grid = GridLayout(cols=1, spacing=25, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height')); self.scroll.add_widget(self.grid); l.add_widget(self.scroll)
        l.add_widget(ModernButton(text="LISTE SIAH", size_hint_y=0.08, bg_color=(0.5, 0.1, 0.1, 1), on_press=lambda x: setattr(self.manager, 'current', 'blacklist_view')))
        self.adm_key = ModernInput(hint_text="Pass", password=True, size_hint_y=0.08); l.add_widget(self.adm_key)
        l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=0.08, on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        self.add_widget(l)

    def refresh(self, *args):
        self.grid.clear_widgets(); q = self.search.text.strip().lower()
        with db_lock: 
            g_db = DATA.get("game_db", {})
            if not isinstance(g_db, dict): g_db = {}
            items = list(g_db.items())
        for uid, reps in items:
            if not isinstance(reps, dict): continue
            if q and q not in uid.lower(): continue
            active = [f"{k}: {v}" for k, v in reps.items() if v > 0]
            if active:
                card = BoxLayout(orientation='vertical', size_hint_y=None, height=185, padding=18, spacing=10)
                with card.canvas.before: Color(0.15, 0.17, 0.22, 1); r = RoundedRectangle(pos=card.pos, size=card.size, radius=[12,])
                card.bind(pos=lambda ins,v,r=r: setattr(r,'pos',ins.pos), size=lambda ins,v,r=r: setattr(r,'size',ins.size))
                row1 = BoxLayout(size_hint_y=0.3); row1.add_widget(Label(text=f"ID: {uid}", bold=True, font_size='18sp'))
                row1.add_widget(ModernButton(text="RESET", size_hint_x=0.3, bg_color=(0.5, 0.2, 0.2, 1), on_press=lambda x, i=uid: self.quick_unb(i)))
                card.add_widget(row1); ig = GridLayout(cols=2, size_hint_y=0.7, spacing=10)
                for r_t in active: ig.add_widget(Label(text=r_t, font_size='12sp', color=(0.8, 0.8, 0.9, 1)))
                card.add_widget(ig); self.grid.add_widget(card)

    def quick_unb(self, uid):
        u = getattr(App.get_running_app(), 'session_user', '')
        perm_list = DATA.get("permissions", [])
        if not isinstance(perm_list, list): perm_list = []
        if u == "admin" or u in perm_list or self.adm_key.text == "MAHDI@#25#":
            with db_lock: 
                if isinstance(DATA.get("game_db"), dict): DATA["game_db"].pop(uid, None)
            save_db({"action": "reset_player", "uid": uid}); self.adm_key.text = ""; self.refresh()

class BannedScreen(Screen):
    def on_enter(self): check_auto_unban(); self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=15)
        l.add_widget(Label(text="LISTE BANNED (MOGHATI)", bold=True, size_hint_y=0.1, color=(0.8, 0.4, 0.4, 1)))
        self.key = ModernInput(hint_text="Pass", password=True, size_hint_y=0.1); l.add_widget(self.key)
        self.scroll = ScrollView(size_hint_y=0.7); self.grid = GridLayout(cols=1, spacing=15, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height')); self.scroll.add_widget(self.grid)
        l.add_widget(self.scroll); l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=0.1, on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        self.add_widget(l)

    def refresh(self, *args):
        self.grid.clear_widgets(); now = get_accurate_now()
        with db_lock:
            b_list = DATA.get("banned_list", {})
            if not isinstance(b_list, dict): b_list = {}
            items = list(b_list.items())
        for uid, info in items:
            if not isinstance(info, dict): continue
            rem_h = max(0, int((info.get('expiry', 0) - now) / 3600))
            c = BoxLayout(orientation='vertical', size_hint_y=None, height=115, padding=10, spacing=5)
            with c.canvas.before: Color(0.2, 0.1, 0.14, 1); RoundedRectangle(pos=c.pos, size=c.size, radius=[12,])
            c.add_widget(Label(text=f"ID: {uid} | Khalaf: {info.get('reason')}", bold=True, font_size='14sp'))
            c.add_widget(Label(text=f"Time Left: {rem_h}h", font_size='11sp', color=(0.7,0.7,0.7,1)))
            c.add_widget(ModernButton(text="UNBAN", size_hint_y=None, height=35, on_press=lambda x, i=uid: self.secure_unb(i)))
            self.grid.add_widget(c)

    def secure_unb(self, uid):
        u = getattr(App.get_running_app(), 'session_user', '')
        if u == "admin" or self.key.text == "MAHDI@#25#":
            with db_lock: 
                if isinstance(DATA.get("banned_list"), dict): DATA["banned_list"].pop(uid, None)
            save_db({"action": "unban_player", "uid": uid}); self.key.text = ""; self.refresh()

class BlacklistScreen(Screen):
    def on_enter(self): self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=10)
        l.add_widget(Label(text="PERMANENT BLACKLIST", bold=True, size_hint_y=0.1, color=(1, 0.2, 0.2, 1)))
        self.scroll = ScrollView(); self.grid = GridLayout(cols=1, spacing=12, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height')); self.scroll.add_widget(self.grid)
        l.add_widget(self.scroll); self.key = ModernInput(hint_text="Pass", password=True, size_hint_y=0.1)
        l.add_widget(self.key); l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=0.1, on_press=lambda x: setattr(self.manager, 'current', 'status')))
        self.add_widget(l)

    def refresh(self):
        self.grid.clear_widgets()
        with db_lock: 
            bl_list = DATA.get("blacklist", [])
            if not isinstance(bl_list, list): bl_list = []
        for uid in bl_list:
            c = BoxLayout(size_hint_y=None, height=65, padding=10)
            with c.canvas.before: Color(0.1, 0.1, 0.1, 1); RoundedRectangle(pos=c.pos, size=c.size, radius=[8,])
            c.add_widget(Label(text=f"BANNED ID: {uid}", bold=True, color=(1, 0.4, 0.4, 1)))
            c.add_widget(ModernButton(text="REMOVE", size_hint_x=0.3, bg_color=(0.2, 0.4, 0.2, 1), on_press=lambda x, i=uid: self.un_blacklist(i)))
            self.grid.add_widget(c)

    def un_blacklist(self, uid):
        u = getattr(App.get_running_app(), 'session_user', '')
        if u == "admin" or self.key.text == "MAHDI@#25#":
            with db_lock:
                bl = DATA.get("blacklist", [])
                if isinstance(bl, list) and uid in bl: bl.remove(uid)
            save_db({"action": "remove_blacklist", "uid": uid}); self.key.text = ""; self.refresh()
class AdminPanel(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=25, spacing=15)
        l.add_widget(Label(text="OWNER DASHBOARD (v1.2)", bold=True, size_hint_y=0.1, font_size='22sp'))
        bg = GridLayout(cols=1, spacing=12, size_hint_y=0.7)
        bg.add_widget(ModernButton(text="TAYIDE NAZERIN", bg_color=(0.1, 0.4, 0.4, 1), on_press=self.show_req_popup))
        bg.add_widget(ModernButton(text="EKRAJE NAZERIN", bg_color=(0.2, 0.3, 0.5, 1), on_press=self.show_staff_mgmt))
        bg.add_widget(ModernButton(text="LOGS & PERFORMANCE", bg_color=(0.5, 0.3, 0.1, 1), on_press=self.show_staff_logs))
        bg.add_widget(ModernButton(text="NOTICE & BLACKLIST", bg_color=(0.4, 0.1, 0.1, 1), on_press=self.show_tools_popup))
        bg.add_widget(ModernButton(text="MODIRIYATE DASTRESI", bg_color=(0.3, 0.3, 0.3, 1), on_press=self.show_perm_mgmt))
        l.add_widget(bg); l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=0.15, bg_color=(0.2, 0.2, 0.2, 1), on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        self.add_widget(l)

    def show_req_popup(self, x):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10); scroll = ScrollView(); grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height')); scroll.add_widget(grid)
        with db_lock:
            pending_db = DATA.get("pending_requests", {})
            if not isinstance(pending_db, dict): pending_db = {}
            pending = list(pending_db.items())
        for u, p in pending:
            row = BoxLayout(size_hint_y=None, height=50, spacing=5); row.add_widget(Label(text=f"User: {u}", font_size='13sp'))
            row.add_widget(ModernButton(text="OK", bg_color=(0,0.5,0,1), on_press=lambda x, user=u, pas=p: self.approve(user, pas))); grid.add_widget(row)
        box.add_widget(scroll); Popup(title="New Requests", content=box, size_hint=(0.9, 0.8)).open()

    def approve(self, u, p):
        with db_lock:
            ej = DATA.get("ejected_users", [])
            if isinstance(ej, list) and u in ej: ej.remove(u)
            if not isinstance(DATA.get("users"), dict): DATA["users"] = {}
            DATA["users"][u] = {"pass": p, "status": "approved", "device": ""}
            if isinstance(DATA.get("pending_requests"), dict): DATA["pending_requests"].pop(u, None)
        save_db({"action": "approve_user", "u": u, "p": p})

    def show_staff_mgmt(self, x):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10); scroll = ScrollView(); grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height')); scroll.add_widget(grid)
        with db_lock: 
            users_db = DATA.get("users", {})
            if not isinstance(users_db, dict): users_db = {}
            users = list(users_db.items())
        for u, info in users:
            if isinstance(info, dict) and info.get("status") == "approved" and u != "admin":
                row = BoxLayout(size_hint_y=None, height=55, padding=5, spacing=5); row.add_widget(Label(text=f"Nazer: {u}", bold=True))
                row.add_widget(ModernButton(text="EKRAJ", bg_color=(0.6, 0.1, 0.1, 1), on_press=lambda x, user=u: self.eject(user))); grid.add_widget(row)
        box.add_widget(scroll); Popup(title="Staff Management", content=box, size_hint=(0.95, 0.85)).open()

    def eject(self, u):
        with db_lock:
            perms = DATA.get("permissions", [])
            if isinstance(perms, list) and u in perms: perms.remove(u)
            ej = DATA.get("ejected_users", [])
            if isinstance(ej, list) and u not in ej: ej.append(u)
            u_db = DATA.get("users", {})
            if isinstance(u_db, dict) and u in u_db: u_db[u]["status"] = "ejected"
        save_db({"action": "eject_user", "u": u})
    def show_staff_logs(self, x):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10); scroll = ScrollView(); grid = GridLayout(cols=1, spacing=8, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height')); scroll.add_widget(grid)
        with db_lock: 
            logs = DATA.get("staff_activity", [])
            if not isinstance(logs, list): logs = []
        for entry in logs:
            if not isinstance(entry, dict): continue
            c = BoxLayout(orientation='vertical', size_hint_y=None, height=85, padding=10)
            with c.canvas.before: Color(0.12, 0.15, 0.2, 1); RoundedRectangle(pos=c.pos, size=c.size, radius=[8,])
            c.add_widget(Label(text=f"Staff: {entry.get('staff')} | Target: {entry.get('target')}", bold=True, font_size='12sp'))
            c.add_widget(Label(text=f"Action: {entry.get('action')} | Time: {entry.get('time')}", font_size='10sp', color=(0.6,0.6,0.6,1)))
            grid.add_widget(c)
        box.add_widget(scroll); Popup(title="Staff Logs", content=box, size_hint=(0.95, 0.9)).open()

    def show_tools_popup(self, x):
        box = BoxLayout(orientation='vertical', padding=15, spacing=10); not_inp = ModernInput(hint_text="Global Notice..."); not_inp.text = str(DATA.get("global_notice", ""))
        box.add_widget(not_inp); bl_inp = ModernInput(hint_text="ID for Blacklist..."); box.add_widget(bl_inp)
        def save_tools(instance):
            with db_lock:
                DATA["global_notice"] = not_inp.text
                bl = DATA.get("blacklist", [])
                if not isinstance(bl, list): DATA["blacklist"] = []
                if bl_inp.text and bl_inp.text not in DATA["blacklist"]: DATA["blacklist"].append(bl_inp.text)
            save_db({"action": "update_tools", "notice": not_inp.text, "bl": bl_inp.text})
        box.add_widget(ModernButton(text="SABT", bg_color=(0.1, 0.4, 0.2, 1), on_press=save_tools))
        Popup(title="Admin Tools", content=box, size_hint=(0.8, 0.6)).open()

    def show_perm_mgmt(self, x):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10); scroll = ScrollView(); grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height')); scroll.add_widget(grid)
        with db_lock: 
            u_db = DATA.get("users", {})
            if not isinstance(u_db, dict): u_db = {}
            staff = list(u_db.keys())
        for u in staff:
            if u == "admin" or DATA["users"][u].get("status") != "approved": continue
            row = BoxLayout(size_hint_y=None, height=50, spacing=10)
            perms = DATA.get("permissions", [])
            if not isinstance(perms, list): perms = []
            is_granted = u in perms
            row.add_widget(Label(text=u)); row.add_widget(ModernButton(text="Laghv" if is_granted else "Ete", bg_color=(0.4,0.2,0.2,1) if is_granted else (0.2,0.4,0.2,1), on_press=lambda x, user=u: self.toggle_perm(user)))
            grid.add_widget(row)
        box.add_widget(scroll); Popup(title="Permissions", content=box, size_hint=(0.9, 0.8)).open()

    def toggle_perm(self, u):
        with db_lock:
            if "permissions" not in DATA or not isinstance(DATA["permissions"], list): DATA["permissions"] = []
            if u in DATA["permissions"]: DATA["permissions"].remove(u)
            else: DATA["permissions"].append(u)
        save_db({"action": "toggle_permission", "u": u})

class AdminVerifyScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=60, spacing=20)
        l.add_widget(Label(text="ADMIN VERIFY", bold=True, font_size='24sp'))
        self.c = ModernInput(hint_text="Master Key", password=True); l.add_widget(self.c)
        l.add_widget(ModernButton(text="VOROOOD", height=60, on_press=lambda x: self.verify()))
        l.add_widget(ModernButton(text="BACK", height=50, bg_color=(0.2,0.2,0.2,1), on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        self.add_widget(l)
    def verify(self):
        if self.c.text == "MAHDI@#25#": self.c.text = ""; self.manager.current = 'admin_panel'
        else: self.c.text = "WRONG KEY"

class TeamNezaratApp(App):
    def build(self):
        self.session_user = "Guest"; load_db()
        from kivy.core.window import Window
        Window.clearcolor = (0.05, 0.05, 0.08, 1)
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(LoginScreen(name='login')); sm.add_widget(EntryScreen(name='entry'))
        sm.add_widget(StatusScreen(name='status')); sm.add_widget(BannedScreen(name='banned_list'))
        sm.add_widget(BlacklistScreen(name='blacklist_view')); sm.add_widget(AdminVerifyScreen(name='admin_verify'))
        sm.add_widget(AdminPanel(name='admin_panel')); return sm

if __name__ == '__main__':
    TeamNezaratApp().run()
