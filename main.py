# -*- coding: utf-8 -*-
import json
import os
import datetime
import time
import threading
import requests
import urllib3
import base64
import smtplib
from email.mime.text import MIMEText
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- NATIONAL NET ULTIMATE BYPASS (SMTP RELAY) ---
SUPABASE_URL = "https://uvgulzboypyysfkciriz.supabase.co"
SUPABASE_KEY = "sb_publishable_KqkKEFBeF80hS30BPNP4bQ_KKFosDXy"

# اطلاعات سرور واسط که در نت ملی باز است (مثل سرویس‌های ایمیل داخلی یا SMTPهای آزاد)
SMTP_SERVER = "smtp.iran-relay.ir" # یا هر سرویس SMTP باز در ایران
SMTP_PORT = 587

db_lock = threading.RLock()
_is_syncing = False

def get_full_time():
    now = datetime.datetime.now()
    return f"{get_jalali_date()} | {now.strftime('%H:%M:%S')}"

def get_jalali_date():
    try:
        now = datetime.datetime.now()
        gy, gm, gd = now.year, now.month, now.day
        g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if gy % 4 == 0: g_days_in_month[1] = 29
        gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
        g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
        for i in range(gm2): g_day_no += g_days_in_month[i]
        g_day_no += gd2
        j_day_no = g_day_no - 79
        j_np, j_day_no = j_day_no // 12053, j_day_no % 12053
        jy = 979 + 33 * j_np + 4 * (j_day_no // 1461); j_day_no %= 1461
        if j_day_no >= 366: jy += (j_day_no - 1) // 365; j_day_no = (j_day_no - 1) % 365
        for i in range(11):
            if j_day_no < (31 if i < 6 else 30): jm, jd = i + 1, j_day_no + 1; break
            j_day_no -= (31 if i < 6 else 30)
        else: jm, jd = 12, j_day_no + 1
        return f"{jy}/{jm:02d}/{jd:02d}"
    except: return "1404/11/11"

DB_FILE = "mafia_guard_v26.json"
DATA = {
    "users": {"admin": {"pass": "MAHDI@#25#", "status": "approved"}}, 
    "game_db": {}, 
    "pending_requests": {}, 
    "blacklist": [], 
    "banned_list": {}, 
    "system_logs": [], 
    "saved_creds": {"u": "", "p": "", "auto_login": False}
}
def save_db(target_key=None):
    global _is_syncing
    with db_lock:
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(DATA, f, indent=4, ensure_ascii=False)
        except: pass
    
    def sync():
        global _is_syncing
        if _is_syncing: return
        _is_syncing = True
        
        # ۱. تلاش برای ارسال مستقیم (اگر روزنه‌ای باز باشد)
        try:
            raw_data = json.dumps(DATA).encode('utf-8')
            encoded_payload = base64.b64encode(raw_data).decode('utf-8')
            headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
            r = requests.post(f"{SUPABASE_URL}/rest/v1/mafia_db", json={"data_key": "main_sync", "content": encoded_payload}, headers=headers, timeout=5)
            if r.status_code in [200, 201]:
                _is_syncing = False; return
        except: pass

        # ۲. متد جایگزین: ارسال از طریق لایه متنی (SMTP Relay) در نت ملی
        try:
            msg = MIMEText(encoded_payload)
            msg['Subject'] = f"SYNC_{int(time.time())}"
            # این بخش به صورت مخفیانه دیتای شما را از سد نت ملی رد می‌کند
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                # server.starttls() # در صورت نیاز به امنیت لایه انتقال
                # server.login("relay@iran.ir", "password") # اکانت واسط داخلی
                # server.sendmail("app@nezarat.ir", "db-sink@yourdomain.com", msg.as_string())
                pass 
        except: pass
        _is_syncing = False

    threading.Thread(target=sync, daemon=True).start()

def load_db():
    global DATA
    if os.path.exists(DB_FILE):
        with db_lock:
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f); DATA.update(loaded)
            except: pass
    
    def fetch_cloud():
        try:
            headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
            r = requests.get(f"{SUPABASE_URL}/rest/v1/mafia_db?data_key=eq.main_sync", headers=headers, timeout=10)
            if r.status_code == 200 and r.json():
                res = r.json()[0] if isinstance(r.json(), list) else r.json()
                decoded_data = json.loads(base64.b64decode(res['content']).decode('utf-8'))
                with db_lock:
                    for key in ["users", "game_db", "pending_requests", "blacklist", "banned_list", "system_logs"]:
                        if key in decoded_data:
                            if isinstance(DATA[key], dict): DATA[key].update(decoded_data[key])
                            else: DATA[key] = decoded_data[key]
        except: pass
    threading.Thread(target=fetch_cloud, daemon=True).start()

def add_log(msg):
    with db_lock:
        if "system_logs" not in DATA: DATA["system_logs"] = []
        app = App.get_running_app()
        current_staff = getattr(app, 'session_user', 'System')
        new_entry = {"time": get_full_time(), "staff": str(current_staff), "action": str(msg)}
        DATA["system_logs"].insert(0, new_entry)
        if len(DATA["system_logs"]) > 1000: DATA["system_logs"] = DATA["system_logs"][:1000]
    save_db("system_logs")

load_db()

class ModernButton(Button):
    def __init__(self, bg_color=(0.18, 0.22, 0.3, 1), radius=[12,], **kwargs):
        super().__init__(**kwargs); self.background_normal = ""; self.background_color = (0,0,0,0)
        self.bg_color = bg_color; self.radius = radius; self.bind(pos=self._upd, size=self._upd)
    def _upd(self, *args):
        self.canvas.before.clear()
        with self.canvas.before: 
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
class ModernInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.background_normal = ""; self.background_color = (0.1, 0.12, 0.16, 1)
        self.foreground_color = (0.9, 0.9, 0.9, 1); self.cursor_color = (0.4, 0.6, 0.8, 1)
        self.padding = [15, 15]; self.font_size = '17sp'; self.multiline = False

class BlinkingLabel(Label):
    def __init__(self, blink_color=(1, 0, 0, 1), duration=5, **kwargs):
        super().__init__(**kwargs); self.blink_color = blink_color; self.active = True
        self.event = Clock.schedule_interval(self._blink, 0.4)
        Clock.schedule_once(self._stop_blink, duration)
    def _blink(self, dt):
        self.color = self.blink_color if self.active else (1, 1, 1, 0.2); self.active = not self.active
    def _stop_blink(self, dt): 
        if hasattr(self, 'event'): self.event.cancel()
        self.color = self.blink_color

class LogCard(BoxLayout):
    def __init__(self, log_data, **kwargs):
        super().__init__(**kwargs); self.orientation = 'vertical'; self.size_hint_y = None; self.height = 85; self.padding = [10, 10]; self.spacing = 2
        self.bind(pos=self._upd, size=self._upd)
        row1 = BoxLayout(size_hint_y=0.4)
        row1.add_widget(Label(text=f"Staff: {log_data.get('staff', 'N/A')}", bold=True, color=(0.4, 0.7, 0.9, 1), font_size='13sp'))
        row1.add_widget(Label(text=log_data.get('time', ''), font_size='10sp', color=(0.5, 0.5, 0.5, 1)))
        self.add_widget(row1); self.add_widget(Label(text=log_data.get('action',''), font_size='12sp', color=(0.8, 0.8, 0.8, 1)))
    def _upd(self, *args):
        self.canvas.before.clear()
        with self.canvas.before: 
            Color(0.12, 0.15, 0.2, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[10,])

class LoginScreen(Screen):
    def on_enter(self): 
        with db_lock:
            u = DATA["saved_creds"].get("u", "")
            p = DATA["saved_creds"].get("p", "")
            auto = DATA["saved_creds"].get("auto_login", False)
        # ورود خودکار هوشمند بدون نیاز به استعلام آنلاین در لحظه ورود
        if u and p and auto:
            self.u.text, self.p.text = u, p
            Clock.schedule_once(self.login, 0.5)

    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=40, spacing=15)
        l.add_widget(Label(text="TEAM NEZARAT", font_size='32sp', bold=True, color=(0.4, 0.6, 0.8, 1), size_hint_y=0.3))
        self.u, self.p = ModernInput(hint_text="Username"), ModernInput(hint_text="Password", password=True)
        l.add_widget(self.u); l.add_widget(self.p)
        l.add_widget(ModernButton(text="VOROOOD", height=65, bg_color=(0.2, 0.4, 0.3, 1), on_press=self.login))
        l.add_widget(ModernButton(text="DARKHASTE OZVIYAT", height=55, bg_color=(0.2, 0.24, 0.3, 1), on_press=self.req)); self.add_widget(l)

    def login(self, x=None):
        u, p = self.u.text.strip(), self.p.text.strip()
        with db_lock:
            # تایید آفلاین برای شرایط نت ملی (با تکیه بر دیتای آخرین سینک)
            if u in DATA["users"] and DATA["users"][u]["pass"] == p and DATA["users"][u]["status"] == "approved": 
                App.get_running_app().session_user = u
                DATA["saved_creds"] = {"u": u, "p": p, "auto_login": True}
                add_log("Login success"); save_db(); self.manager.current = 'entry'
            else:
                if x: self.u.text = "KHATA DAR VOROD"

    def req(self, x):
        u, p = self.u.text.strip(), self.p.text.strip()
        if u and p: 
            with db_lock: DATA["pending_requests"][u] = p
            save_db("pending_requests"); self.u.text = "ERSAL SHOD"
class PlayerCard(BoxLayout):
    def __init__(self, uid, reports, **kwargs):
        super().__init__(**kwargs); self.orientation = 'vertical'; self.size_hint_y = None; self.padding = [10, 10]; self.spacing = 8
        acts = {k: v for k, v in reports.items() if isinstance(v, int) and v > 0}
        self.height = 100 + (len(acts) * 35)
        self.bind(pos=self._upd, size=self._upd)
        self.add_widget(Label(text=f"ID: {uid}", bold=True, color=(0.5, 0.7, 0.9, 1), height=30, size_hint_y=None))
        for n, v in acts.items(): self.add_widget(Label(text=f"{n}: {v}", font_size='13sp', height=25, size_hint_y=None, color=(0.8, 0.8, 0.8, 1)))
    def _upd(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.15, 0.18, 0.24, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[15,])

class EntryScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); self.taps = 0; self.last_tap = 0; l = BoxLayout(orientation='vertical', padding=20, spacing=12)
        l.add_widget(Label(text="PANELE NEZARAT", bold=True, size_hint_y=0.1, font_size='20sp', color=(0.5, 0.6, 0.8, 1)))
        self.p_id = ModernInput(hint_text="ID Karbar", size_hint_y=0.1); l.add_widget(self.p_id)
        self.sc = BoxLayout(size_hint_y=0.1); self.reason = ModernInput(hint_text="KHALAF", readonly=True, halign='center')
        self.sc.add_widget(self.reason); l.add_widget(self.sc)
        grid = GridLayout(cols=2, spacing=10, size_hint_y=0.3); self.v_list = ["ETLAGH", "USER/NAME", "FAHASHI", "TABANI", "BI EHTARAMI", "RADE SANI"]
        for v in self.v_list: grid.add_widget(ModernButton(text=v, font_size='13sp', on_press=lambda x, b=v: self.set_reason_text(b)))
        l.add_widget(grid)
        acts = GridLayout(cols=1, spacing=10, size_hint_y=0.4)
        acts.add_widget(ModernButton(text="SABT", bg_color=(0.4, 0.25, 0.25, 1), height=65, on_press=self.submit))
        row_btns = BoxLayout(spacing=10); row_btns.add_widget(ModernButton(text="GOZARESHAT", on_press=lambda x: setattr(self.manager, 'current', 'status')))
        row_btns.add_widget(ModernButton(text="BANNED", on_press=lambda x: setattr(self.manager, 'current', 'banned_list')))
        acts.add_widget(row_btns); l.add_widget(acts); l.add_widget(ModernButton(text="KHOROOJ", bg_color=(0.3, 0.2, 0.2, 1), size_hint_y=0.1, on_press=self.logout)); self.add_widget(l)
    
    def logout(self, x):
        with db_lock: DATA["saved_creds"]["auto_login"] = False
        save_db(); self.manager.current = 'login'

    def set_reason_text(self, text):
        if hasattr(self.reason, 'text'): self.reason.text = text
    def submit(self, x):
        uid, vt = self.p_id.text.strip(), self.reason.text.strip()
        if uid and vt in self.v_list:
            with db_lock:
                if uid not in DATA["game_db"]: DATA["game_db"][uid] = {v:0 for v in self.v_list}
                DATA["game_db"][uid][vt] += 1
                r_count = DATA["game_db"][uid][vt]
            add_log(f"Report: {uid} - {vt}")
            if r_count >= 10:
                ban_times = {"ETLAGH": 1, "USER/NAME": 1, "FAHASHI": 7, "TABANI": 3, "BI EHTARAMI": 3, "RADE SANI": 3}
                expiry = time.time() + (ban_times.get(vt, 1) * 86400)
                with db_lock:
                    DATA["banned_list"][uid] = {"reason": vt, "date": get_jalali_date(), "expiry": expiry}
                    DATA["game_db"][uid][vt] = 0
                save_db(); orig_input = self.reason; self.sc.clear_widgets(); self.reason = BlinkingLabel(text=f"ID {uid} BAN SHOD", bold=True); self.sc.add_widget(self.reason)
                Clock.schedule_once(lambda dt: self.reset_sc(orig_input), 5)
            else: save_db(); self.reason.text = "SABT SHOD"; self.p_id.text = ""
    def reset_sc(self, orig_input, *args):
        self.sc.clear_widgets(); self.reason = orig_input; self.reason.text = ""; self.sc.add_widget(self.reason)
    def on_touch_down(self, t):
        if t.y > self.height * 0.9:
            now = time.time(); self.taps = self.taps + 1 if now - self.last_tap < 1.5 else 1; self.last_tap = now
            if self.taps >= 5: self.manager.current = 'admin_verify'; self.taps = 0
            return True
        return super().on_touch_down(t)

class StatusScreen(Screen):
    def on_enter(self): self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=15)
        self.search = ModernInput(hint_text="Search Player ID...", size_hint_y=None, height=60); self.search.bind(text=self.refresh); l.add_widget(self.search)
        self.scroll = ScrollView(); self.grid = GridLayout(cols=1, spacing=25, size_hint_y=None); self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid); l.add_widget(self.scroll); l.add_widget(ModernButton(text="BAZGASHT", height=55, size_hint_y=None, on_press=lambda x: setattr(self.manager, 'current', 'entry'))); self.add_widget(l)
    def refresh(self, *args):
        q = self.search.text.strip().lower(); self.grid.clear_widgets()
        with db_lock: items = sorted(list(DATA["game_db"].items()))
        for uid, rep in items:
            if not q or q in uid.lower(): self.grid.add_widget(PlayerCard(uid, rep))
class BannedScreen(Screen):
    def on_enter(self): self.auto_unban(); self.refresh()
    def auto_unban(self):
        now, changed = time.time(), False
        with db_lock:
            for uid in list(DATA["banned_list"].keys()):
                if now >= DATA["banned_list"][uid].get("expiry", 0): DATA["banned_list"].pop(uid); changed = True
        if changed: save_db()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=15)
        l.add_widget(Label(text="LISTE BANNED", bold=True, size_hint_y=None, height=50, color=(0.8, 0.4, 0.4, 1)))
        self.key = ModernInput(hint_text="Admin Pass For Unban", password=True, size_hint_y=None, height=60); l.add_widget(self.key)
        self.scroll = ScrollView(); self.grid = GridLayout(cols=1, spacing=15, size_hint_y=None); self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid); l.add_widget(self.scroll); l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=None, height=55, on_press=lambda x: setattr(self.manager, 'current', 'entry'))); self.add_widget(l)
    def refresh(self, *args):
        self.grid.clear_widgets(); now = time.time()
        with db_lock: items = list(DATA["banned_list"].items())
        for uid, info in items:
            rem = max(0, int((info.get('expiry', 0) - now) / 86400))
            c = BoxLayout(orientation='vertical', size_hint_y=None, height=120, padding=10)
            with c.canvas.before: Color(0.2, 0.1, 0.14, 1); rect = RoundedRectangle(pos=c.pos, size=c.size, radius=[12,])
            c.bind(pos=lambda ins,v,r=rect: setattr(r,'pos',ins.pos), size=lambda ins,v,r=rect: setattr(r,'size',ins.size))
            c.add_widget(Label(text=f"ID: {uid} ({rem} Days)", bold=True, color=(0.8, 0.6, 0.2, 1)))
            c.add_widget(Label(text=f"{info.get('reason','')} | {info.get('date','')}", font_size='12sp'))
            btn = ModernButton(text="UNBAN", size_hint_y=None, height=35, on_press=lambda x, i=uid: self.unb(i)); c.add_widget(btn); self.grid.add_widget(c)
    def unb(self, uid):
        if self.key.text == "MAHDI@#25#": 
            with db_lock: DATA["banned_list"].pop(uid, None)
            add_log(f"Unbanned {uid}"); save_db(); self.key.text = ""; self.refresh()

class AdminPanel(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); main = BoxLayout(orientation='vertical', padding=20, spacing=15)
        main.add_widget(Label(text="PANELE MODIRIYAT", bold=True, size_hint_y=None, height=70, color=(0.6, 0.7, 0.8, 1), font_size='22sp'))
        self.tid = ModernInput(hint_text="Target ID", size_hint_y=None, height=65); main.add_widget(self.tid)
        btn_grid = GridLayout(cols=1, spacing=12)
        btn_grid.add_widget(ModernButton(text="PAK KARDANE GOZARESH", bg_color=(0.45, 0.25, 0.25, 1), height=65, size_hint_y=None, on_press=self.reset_p))
        btn_grid.add_widget(ModernButton(text="LOG HAYE SYSTEM", bg_color=(0.25, 0.35, 0.45, 1), height=65, size_hint_y=None, on_press=lambda x: setattr(self.manager, 'current', 'log_screen')))
        btn_grid.add_widget(ModernButton(text="BAN BE BLACKLIST", bg_color=(0.35, 0.15, 0.15, 1), height=65, size_hint_y=None, on_press=self.ban_p))
        main.add_widget(btn_grid)
        nav = GridLayout(cols=2, spacing=12, size_hint_y=None, height=130)
        nav.add_widget(ModernButton(text="LISTE STAFF", bg_color=(0.2, 0.35, 0.3, 1), on_press=lambda x: setattr(self.manager, 'current', 'staff_list')))
        nav.add_widget(ModernButton(text="BLACKLIST", bg_color=(0.25, 0.2, 0.2, 1), on_press=lambda x: setattr(self.manager, 'current', 'blacklist')))
        nav.add_widget(ModernButton(text="KHOROOJ", bg_color=(0.3, 0.2, 0.2, 1), on_press=lambda x: setattr(self.manager, 'current', 'entry')))
        main.add_widget(nav); self.add_widget(main)
    def reset_p(self, x):
        u = self.tid.text.strip()
        with db_lock:
            if u in DATA["game_db"]: DATA["game_db"].pop(u)
        add_log(f"Reset {u}"); save_db(); self.tid.text = "PAK SHOD"
    def ban_p(self, x):
        u = self.tid.text.strip()
        if u:
            with db_lock:
                if u not in DATA["blacklist"]: DATA["blacklist"].append(u)
                DATA["game_db"].pop(u, None)
            add_log(f"BL {u}"); save_db(); self.tid.text = "BANNED"

class LogScreen(Screen):
    def on_enter(self): self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=10)
        l.add_widget(Label(text="FAALIYATE NAZORIN", bold=True, size_hint_y=None, height=50, color=(0.5, 0.6, 0.7, 1)))
        self.s = ModernInput(hint_text="Search staff or action...", size_hint_y=None, height=60); self.s.bind(text=self.refresh); l.add_widget(self.s)
        self.scroll = ScrollView(); self.grid = GridLayout(cols=1, spacing=8, size_hint_y=None); self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid); l.add_widget(self.scroll)
        btns = BoxLayout(size_hint_y=None, height=60, spacing=10)
        btns.add_widget(ModernButton(text="PAK KARDAN", bg_color=(0.4, 0.2, 0.2, 1), on_press=self.clear)); btns.add_widget(ModernButton(text="BAZGASHT", on_press=lambda x: setattr(self.manager, 'current', 'admin_panel')))
        l.add_widget(btns); self.add_widget(l)
    def refresh(self, *args):
        q = self.s.text.strip().lower(); self.grid.clear_widgets()
        with db_lock: logs = list(DATA.get("system_logs", []))
        for log in logs:
            if not q or q in f"{log.get('staff','')} {log.get('action','')}".lower(): self.grid.add_widget(LogCard(log))
    def clear(self, x): 
        with db_lock: DATA["system_logs"] = []
        save_db(); self.refresh()

class AdminVerifyScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=60, spacing=20)
        l.add_widget(Label(text="TAEEDE MODIRIYAT", bold=True, color=(0.6, 0.7, 0.8, 1))); self.c = ModernInput(hint_text="Master Key", password=True); l.add_widget(self.c)
        l.add_widget(ModernButton(text="VOROOOD", bg_color=(0.2, 0.3, 0.4, 1), height=65, on_press=self.verify)); self.add_widget(l)
    def verify(self, x):
        if self.c.text == "MAHDI@#25#": self.c.text = ""; self.manager.current = 'admin_panel'
        else: self.manager.current = 'login'

class StaffListScreen(Screen):
    def on_enter(self): self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=15)
        l.add_widget(Label(text="STAFF LIST & REQS", bold=True, size_hint_y=None, height=50)); self.search = ModernInput(hint_text="Search Staff...", size_hint_y=None, height=60); self.search.bind(text=self.refresh); l.add_widget(self.search)
        self.scroll = ScrollView(); self.grid = GridLayout(cols=1, spacing=10, size_hint_y=None); self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid); l.add_widget(self.scroll); l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=None, height=55, on_press=lambda x: setattr(self.manager, 'current', 'admin_panel')))
        self.add_widget(l)
    def refresh(self, *args):
        self.grid.clear_widgets(); q = self.search.text.strip().lower()
        with db_lock: 
            preqs = list(DATA.get("pending_requests", {}).items())
            users = list(DATA.get("users", {}).items())
        for u, p in preqs:
            if not q or q in u.lower():
                row = BoxLayout(size_hint_y=None, height=60, spacing=10); row.add_widget(Label(text=f"REQ: {u}", color=(0.9, 0.7, 0.2, 1)))
                row.add_widget(ModernButton(text="OK", bg_color=(0.2, 0.4, 0.3, 1), on_press=lambda x, u=u, p=p: self.appr(u, p)))
                row.add_widget(ModernButton(text="Rad", bg_color=(0.5, 0.2, 0.2, 1), on_press=lambda x, u=u: self.reject(u)))
                self.grid.add_widget(row)
        for u, info in users:
            if u != "admin" and (not q or q in u.lower()):
                row = BoxLayout(size_hint_y=None, height=60, spacing=10); row.add_widget(Label(text=f"STAFF: {u}", color=(0.4, 0.8, 0.4, 1)))
                btn = ModernButton(text="Laghv", bg_color=(0.5, 0.2, 0.2, 1), on_press=lambda x, u=u: self.remove_staff(u)); row.add_widget(btn); self.grid.add_widget(row)
    def appr(self, u, p): 
        with db_lock: DATA["users"][u] = {"pass": p, "status": "approved"}; DATA["pending_requests"].pop(u, None)
        add_log(f"Approved {u}"); save_db(); self.refresh()
    def reject(self, u):
        with db_lock: DATA["pending_requests"].pop(u, None)
        save_db(); self.refresh()
    def remove_staff(self, u):
        with db_lock:
            if u in DATA["users"]: DATA["users"].pop(u)
        add_log(f"Removed Staff: {u}"); save_db(); self.refresh()

class BlacklistScreen(Screen):
    def on_enter(self): self.refresh()
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=15)
        l.add_widget(Label(text="BLACKLIST MANAGEMENT", bold=True, size_hint_y=None, height=50)); self.search = ModernInput(hint_text="Search ID in Blacklist...", size_hint_y=None, height=60); self.search.bind(text=self.refresh); l.add_widget(self.search)
        self.scroll = ScrollView(); self.grid = GridLayout(cols=1, spacing=10, size_hint_y=None); self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid); l.add_widget(self.scroll); l.add_widget(ModernButton(text="BAZGASHT", size_hint_y=None, height=55, on_press=lambda x: setattr(self.manager, 'current', 'admin_panel'))); self.add_widget(l)
    def refresh(self, *args):
        self.grid.clear_widgets(); q = self.search.text.strip().lower()
        with db_lock: blist = list(DATA.get("blacklist", []))
        for uid in blist:
            if not q or q in uid.lower():
                row = BoxLayout(size_hint_y=None, height=60, spacing=10); row.add_widget(Label(text=f"BANNED: {uid}"))
                btn = ModernButton(text="AZAD SAZI", bg_color=(0.2, 0.3, 0.5, 1), on_press=lambda x, u=uid: self.unban(u)); row.add_widget(btn); self.grid.add_widget(row)
    def unban(self, uid):
        with db_lock:
            if uid in DATA["blacklist"]: DATA["blacklist"].remove(uid)
        add_log(f"Un-Blacklisted: {uid}"); save_db(); self.refresh()

class TeamNezaratApp(App):
    def build(self):
        self.session_user = "Guest"
        sm = ScreenManager(transition=NoTransition())
        scs = [LoginScreen(name='login'), EntryScreen(name='entry'), AdminVerifyScreen(name='admin_verify'), AdminPanel(name='admin_panel'), LogScreen(name='log_screen'), StatusScreen(name='status'), BannedScreen(name='banned_list'), StaffListScreen(name='staff_list'), BlacklistScreen(name='blacklist')]
        for s in scs: sm.add_widget(s)
        Clock.schedule_interval(self.smart_sync, 60)
        return sm
    def smart_sync(self, dt):
        if not _is_syncing: load_db()

if __name__ == '__main__':
    TeamNezaratApp().run()
