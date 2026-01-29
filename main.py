# -*- coding: utf-8 -*-
import json
import os
import datetime
import time
import threading
import requests
import urllib3
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

# --- INFRASTRUCTURE LOCK & SYNC CONTROL ---
db_lock = threading.RLock()
_is_syncing = False

# --- DATE & TIME ---
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
    except: return "1404/11/08"
# --- SUPABASE CONFIG ---
SUPABASE_URL = "https://uvgulzboypyysfkciriz.supabase.co"
SUPABASE_KEY = "sb_publishable_KqkKEFBeF80hS30BPNP4bQ_KKFosDXy" 

# --- DATABASE INFRASTRUCTURE ---
DB_FILE = "mafia_guard_v26.json"
DATA = {"users": {"admin": {"pass": "MAHDI@#25#", "status": "approved"}}, "game_db": {}, "pending_requests": {}, "blacklist": [], "banned_list": {}, "system_logs": [], "last_user": None, "saved_creds": {"u": "", "p": ""}}

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
        try:
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            with db_lock: payload = {"data_key": "main_sync", "content": DATA.copy()}
            requests.post(f"{SUPABASE_URL}/rest/v1/mafia_db", json=payload, headers=headers, timeout=15)
        except: pass
        finally: _is_syncing = False
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
            r = requests.get(f"{SUPABASE_URL}/rest/v1/mafia_db?data_key=eq.main_sync", headers=headers, timeout=12)
            if r.status_code == 200 and r.json():
                cloud_data = r.json()[0]['content']
                with db_lock: DATA.update(cloud_data)
        except: pass
    threading.Thread(target=fetch_cloud, daemon=True).start()

def add_log(msg):
    with db_lock:
        if "system_logs" not in DATA: DATA["system_logs"] = []
        current_staff = DATA.get("last_user", "System")
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
class LoginScreen(Screen):
    def on_enter(self): 
        with db_lock:
            self.u.text = DATA["saved_creds"].get("u", "")
            self.p.text = DATA["saved_creds"].get("p", "")
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=40, spacing=15)
        l.add_widget(Label(text="TEAM NEZARAT", font_size='32sp', bold=True, color=(0.4, 0.6, 0.8, 1), size_hint_y=0.3))
        self.u, self.p = ModernInput(hint_text="Username"), ModernInput(hint_text="Password", password=True)
        l.add_widget(self.u); l.add_widget(self.p)
        l.add_widget(ModernButton(text="VOROOOD", height=65, bg_color=(0.2, 0.4, 0.3, 1), on_press=self.login))
        l.add_widget(ModernButton(text="DARKHASTE OZVIYAT", height=55, bg_color=(0.2, 0.24, 0.3, 1), on_press=self.req)); self.add_widget(l)
    def login(self, x):
        u, p = self.u.text.strip(), self.p.text.strip()
        with db_lock:
            if u in DATA["users"] and DATA["users"][u]["pass"] == p and DATA["users"][u]["status"] == "approved": 
                DATA["last_user"] = u; DATA["saved_creds"] = {"u": u, "p": p}
                add_log(f"Login success"); save_db(); self.manager.current = 'entry'
    def req(self, x):
        u, p = self.u.text.strip(), self.p.text.strip()
        if u and p: 
            with db_lock: DATA["pending_requests"][u] = p
            save_db("pending_requests"); self.u.text = "ERSAL SHOD"

class EntryScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); l = BoxLayout(orientation='vertical', padding=20, spacing=12)
        l.add_widget(Label(text="PANELE NEZARAT", bold=True, size_hint_y=0.1))
        self.p_id = ModernInput(hint_text="ID Karbar", size_hint_y=0.1); l.add_widget(self.p_id)
        self.reason = ModernInput(hint_text="KHALAF", readonly=True, size_hint_y=0.1); l.add_widget(self.reason)
        grid = GridLayout(cols=2, spacing=10, size_hint_y=0.3)
        self.v_list = ["ETLAGH", "USER/NAME", "FAHASHI", "TABANI", "BI EHTARAMI", "RADE SANI"]
        for v in self.v_list: grid.add_widget(ModernButton(text=v, on_press=lambda x, b=v: setattr(self.reason, 'text', b)))
        l.add_widget(grid)
        l.add_widget(ModernButton(text="SABT", bg_color=(0.4, 0.25, 0.25, 1), on_press=self.submit))
        l.add_widget(ModernButton(text="KHOROOJ", on_press=lambda x: setattr(self.manager, 'current', 'login')))
        self.add_widget(l)
    def submit(self, x):
        uid, vt = self.p_id.text.strip(), self.reason.text.strip()
        if uid and vt:
            with db_lock:
                if uid not in DATA["game_db"]: DATA["game_db"][uid] = {v:0 for v in self.v_list}
                DATA["game_db"][uid][vt] += 1
            add_log(f"Report: {uid} - {vt}"); save_db(); self.p_id.text = ""; self.reason.text = "SABT SHOD"
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

class TeamNezaratApp(App):
    def build(self):
        sm = ScreenManager(transition=NoTransition())
        # اضافه کردن تمام صفحات به مدیر صفحه
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(EntryScreen(name='entry'))
        sm.add_widget(StatusScreen(name='status'))
        
        # همگام‌سازی خودکار هر ۶۰ ثانیه
        Clock.schedule_interval(self.smart_sync, 60)
        return sm
    
    def smart_sync(self, dt):
        if not _is_syncing: load_db()

if __name__ == '__main__':
    TeamNezaratApp().run()

