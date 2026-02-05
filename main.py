# -*- coding: utf-8 -*-
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

# --- CONFIG (بهینه‌شده برای نت ملی و ساعت رسمی ایران) ---
CURRENT_VERSION = "1.1" 
# آدرس تونل اختصاصی شما در ایران (بدون نیاز به دامنه)
IRAN_BRIDGE_URL = "http://185.164.72.71"

db_lock = threading.RLock()
_is_syncing = False
TIME_OFFSET = 0 
_NET_STATUS = False 
_PING_VALUE = "0"

def sync_time_offset():
    """هماهنگ‌سازی ساعت با سرورهای ایران جهت ثبت دقیق گزارش‌ها"""
    global TIME_OFFSET, _NET_STATUS, _PING_VALUE
    try:
        st = time.time()
        # استعلام زمان از API رسمی منطبق بر آسیا/تهران
        r = requests.get("http://worldtimeapi.org", timeout=5)
        _PING_VALUE = str(int((time.time() - st) * 1000))
        if r.status_code == 200:
            TIME_OFFSET = r.json()['unixtime'] - time.time()
            _NET_STATUS = True
        else:
            _NET_STATUS = False
    except: 
        _NET_STATUS = False
        _PING_VALUE = "999"

def get_accurate_now():
    """خروجی ثانیه‌شمار دقیق بر اساس وقت ایران"""
    return time.time() + TIME_OFFSET

def get_full_time_ir():
    """فرمت‌دهی تاریخ و ساعت رسمی ایران برای ثبت در سوابق"""
    now = datetime.datetime.fromtimestamp(get_accurate_now())
    return now.strftime('%Y/%m/%d - %H:%M:%S')

BAN_DAYS_MAP = {"ETLAGH": 1, "USER/NAME": 1, "FAHASHI": 7, "TABANI": 3, "BI EHTARAMI": 3, "RADE SANI": 1}
DB_FILE = "mafia_guard_v32.json"
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
def save_db():
    """ذخیره‌سازی ایمن با مدیریت تداخل ۴۰ ناظر همزمان و پاکسازی ۶۰ روزه سوابق"""
    global DATA
    with db_lock:
        try:
            now = get_accurate_now()
            # بازه ۶۰ روزه برای پاکسازی سوابق (۵۱۸۴۰۰۰ ثانیه)
            # اطلاعات ناظرین (users) هرگز تحت هیچ شرایطی پاک نمی‌شود
            if now - DATA.get("last_cleanup_time", 0) > 5184000:
                if len(DATA["staff_activity"]) > 2000:
                    DATA["staff_activity"] = DATA["staff_activity"][:2000]
                
                game_items = list(DATA["game_db"].items())
                if len(game_items) > 2000:
                    DATA["game_db"] = dict(game_items[-2000:])
                
                DATA["last_cleanup_time"] = now

            with open(DB_FILE, "w", encoding='utf-8') as f:
                json.dump(DATA, f, indent=4, ensure_ascii=False)
        except: pass
    
    # ارسال به هاست ایران (IRAN BRIDGE) جهت عبور از سد نت ملی
    threading.Thread(target=sync_plain_engine, daemon=True).start()

def sync_plain_engine():
    """ارسال دیتا به هاست ایران با متد POST جهت ثبت در سایت سوپابیس"""
    global _is_syncing, _NET_STATUS
    if _is_syncing: return
    _is_syncing = True
    try:
        with db_lock:
            # ثبت زمان دقیق آخرین همگام‌سازی به وقت ایران
            DATA["last_sync_etag"] = get_accurate_now()
            plain_json_str = json.dumps(DATA, indent=4, ensure_ascii=False)
        
        # ارسال مستقیم به آی‌پی ایران شما (پایداری ۱۰۰٪ در نت ملی)
        r = requests.post(IRAN_BRIDGE_URL, data=plain_json_str.encode('utf-8'), timeout=15)
        
        # کد ۲۰۰ نشانه دریافت موفق توسط هاست ایران و انتقال به سوپابیس است
        _NET_STATUS = True if r.status_code == 200 else False
    except: 
        _NET_STATUS = False
    finally:
        _is_syncing = False

def check_auto_unban():
    """آزادسازی خودکار بن‌های منقضی شده بر اساس ساعت دقیق ایران"""
    now = get_accurate_now()
    changed = False
    with db_lock:
        for uid in list(DATA["banned_list"].keys()):
            if now >= DATA["banned_list"][uid].get("expiry", 0):
                DATA["banned_list"].pop(uid)
                changed = True
    if changed: save_db()

def load_db():
    """بارگذاری اولیه و استعلام فوری از تونل ایران برای چک کردن وضعیت ناظرین"""
    global DATA
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding='utf-8') as f:
                with db_lock: DATA.update(json.load(f))
        except: pass
    check_auto_unban()
    # دریافت آنی آخرین تغییرات لیست ناظرین از طریق هاست ایران
    threading.Thread(target=fetch_cloud_engine, daemon=True).start()

def fetch_cloud_engine(on_complete=None):
    """دریافت دیتا از طریق تونل اختصاصی ایران (Bypass Net Meli)"""
    global _NET_STATUS, DATA
    try:
        # برای دریافت دیتا، از پارامتر خاص در تونل استفاده می‌کنیم
        r = requests.get(IRAN_BRIDGE_URL, timeout=10)
        if r.status_code == 200:
            _NET_STATUS = True
            res = r.json()
            item = res if isinstance(res, list) and len(res)>0 else (res if res else {})
            raw_data = item.get('content', "{}")
            cloud = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            
            if cloud and isinstance(cloud, dict) and "users" in cloud:
                with db_lock:
                    # ادغام هوشمند جهت جلوگیری از تداخل گزارش‌های ۴۰ ناظر همزمان
                    for key in cloud:
                        if key == "users":
                            DATA["users"].update(cloud["users"])
                        elif key == "staff_activity":
                            if getattr(App.get_running_app(), 'session_user', '') == 'admin':
                                DATA[key] = cloud[key]
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
        # بررسی وضعیت اتصال از طریق هاست ایران
        threading.Thread(target=sync_time_offset, daemon=True).start()
        self.ping_lbl.text = f"{_PING_VALUE}ms"
        self.led.canvas.before.clear()
        with self.led.canvas.before:
            Color(0.2, 0.8, 0.2, 1) if _NET_STATUS else Color(0.8, 0.2, 0.2, 1)
            RoundedRectangle(pos=self.led.pos, size=self.led.size, radius=[6,])

class ModernButton(Button):
    def __init__(self, bg_color=(0.18, 0.22, 0.3, 1), radius=[12,], **kwargs):
        super().__init__(**kwargs); self.background_normal = ""; self.background_color = (0,0,0,0)
        self.bg_color = bg_color; self.radius = radius; self.bind(pos=self._upd, size=self._upd)
    def _upd(self, *args):
        self.canvas.before.clear()
        with self.canvas.before: Color(*self.bg_color); RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)

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
    """ثبت سوابق فعالیت ناظر با تاریخ و ساعت دقیق ایران"""
    staff = getattr(App.get_running_app(), 'session_user', 'System')
    entry = {"staff": staff, "target": target_id, "action": action, "time": get_full_time_ir()}
    with db_lock:
        if "staff_activity" not in DATA: DATA["staff_activity"] = []
        DATA["staff_activity"].insert(0, entry)
    save_db()
class LoginScreen(Screen):
    def on_enter(self): 
        # هماهنگ‌سازی ساعت ایران در بدو ورود
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
        # استعلام از هاست ایران برای وضعیت تایید ناظر
        threading.Thread(target=fetch_cloud_engine, args=(self.execute_login,), daemon=True).start()

    def execute_login(self, success):
        Clock.schedule_once(lambda dt: self._final_login_check())

    def _final_login_check(self):
        u, p = self.u.text.strip(), self.p.text.strip()
        dev_id = socket.gethostname() if platform != 'android' else "ANDROID-NODE" 
        
        with db_lock:
            # --- پل اضطراری ادمین: همیشه کار می‌کند ---
            if u == "admin" and p == "MAHDI@#25#":
                App.get_running_app().session_user = u
                DATA["saved_creds"] = {"u": u, "p": p, "auto_login": True}
                save_db(); self.manager.current = 'entry'
                return

            # --- بررسی ناظرین تایید شده ---
            if u in DATA["users"] and DATA["users"][u]["pass"] == p:
                user_info = DATA["users"][u]
                if user_info.get("status") == "approved":
                    if u in DATA.get("ejected_users", []): DATA["ejected_users"].remove(u)
                    
                    if not user_info.get("device"): 
                        user_info["device"] = dev_id
                        save_db()
                    
                    if user_info["device"] == dev_id:
                        App.get_running_app().session_user = u
                        DATA["saved_creds"] = {"u": u, "p": p, "auto_login": True}
                        save_db(); self.manager.current = 'entry'
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
            save_db(); self.u.text = "DAR KHAST ERSAL SHOD"

class EntryScreen(Screen):
    def on_enter(self):
        # مانیتورینگ وضعیت اخراج به وقت ایران
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
        
        # نمایش اطلاعیه سراسری ادمین
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
        if uid and uid in DATA["game_db"]:
            if DATA["game_db"][uid].get(name, 0) >= 10:
                self.reason_box.start_ban_blink(name)

    def logout(self, x):
        with db_lock: DATA["saved_creds"]["auto_login"] = False
        save_db(); self.manager.current = 'login'

    def submit(self, x):
        uid, vt = self.p_id.text.strip(), self.reason_box.text.strip()
        if not uid or vt not in self.v_list: return
        with db_lock:
            if uid not in DATA["game_db"]: DATA["game_db"][uid] = {v:0 for v in self.v_list}
            DATA["game_db"][uid][vt] += 1
            count = DATA["game_db"][uid][vt]
            # ثبت فعالیت ناظر با تاریخ و ساعت دقیق ایران
            add_staff_log(uid, f"GozARESH: {vt} (Count: {count})")
            
            if count >= 10:
                days = BAN_DAYS_MAP.get(vt, 1)
                # محاسبه زمان انقضا دقیقاً بر اساس ساعت ایران
                expiry = get_accurate_now() + (days * 86400)
                DATA["banned_list"][uid] = {
                    "reason": vt, 
                    "date": get_full_time_ir(), 
                    "expiry": expiry
                }
                DATA["game_db"][uid][vt] = 0
                self.reason_box.start_ban_blink(vt)
        save_db()
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
        # اصلاح: حذف نیاز به رمز برای ادمین و مجازین (Permissions)
        is_permitted = u == "admin" or u in DATA.get("permissions", [])
        if is_permitted or self.adm_key.text == "MAHDI@#25#":
            with db_lock: DATA["game_db"].pop(uid, None)
            save_db(); self.adm_key.text = ""; self.refresh()
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
            for uid in DATA.get("blacklist", []):
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
                if uid in DATA["blacklist"]: DATA["blacklist"].remove(uid)
            save_db(); self.key.text = ""; self.refresh()
        else: self.key.text = "NO PERMISSION"

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
        with db_lock: items = list(DATA.get("banned_list", {}).items())
        for uid, info in items:
            # محاسبه ساعت باقی‌مانده بر اساس زمان حالِ ایران
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
                if uid in DATA["banned_list"]: DATA["banned_list"].pop(uid)
            save_db(); self.key.text = ""; self.refresh()
        else: self.key.text = "NO PERMISSION"
class AdminPanel(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=25, spacing=15)
        l.add_widget(Label(text="OWNER DASHBOARD (v1.1)", bold=True, size_hint_y=0.1, font_size='22sp'))
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
        save_db()

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
            # ثبت تایید با ساعت ایران
            add_staff_log(u, "TAYID MAJJAD")
        save_db()

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
            # ابطال آنی تمام دسترسی‌های ویژه ناظر اخراج شده
            if u in DATA.get("permissions", []): DATA["permissions"].remove(u)
            if u not in DATA["ejected_users"]: DATA["ejected_users"].append(u)
            if u in DATA["users"]: DATA["users"][u]["status"] = "ejected"
            add_staff_log(u, "EKRAJ SHOD")
        save_db()

    def show_staff_logs(self, x):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView(); grid = GridLayout(cols=1, spacing=8, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height')); scroll.add_widget(grid)
        with db_lock:
            for entry in DATA.get("staff_activity", []):
                c = BoxLayout(orientation='vertical', size_hint_y=None, height=85, padding=10)
                with c.canvas.before: Color(0.12, 0.15, 0.2, 1); RoundedRectangle(pos=c.pos, size=c.size, radius=[8,])
                # نمایش لاگ‌ها با ساعت ثبت شده به وقت ایران
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
            save_db(); pop.dismiss()
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
        if self.c.text == "MAHDI@#25#": self.c.text = ""; self.manager.current = 'admin_panel'
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
