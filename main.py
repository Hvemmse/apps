#!/usr/bin/env python3
"""
SysMon — Theme Edition
Features:
- Dark / Light / Auto theme (detects from system)
- Persistent config (~/.config/sysmon_dark.cfg)
- Hostname + Uptime
- Zoom (Ctrl + / Ctrl - / Ctrl 0)
- Update interval (menu, Alt +/-)
- CPU total + per-core, RAM, SWAP, Disk, Processes
"""
import os, sys, time, psutil, platform, shutil, subprocess, socket, tkinter as tk
from tkinter import ttk
from configparser import ConfigParser
from datetime import timedelta

# ---------- THEMES ----------
THEMES = {
    "dark": {
        "bg": "#121212",
        "panel": "#1e1e1e",
        "fg": "#e0e0e0",
        "accent": "#4caf50",
        "warn": "#ff9800",
        "crit": "#f44336",
        "disk": "#03a9f4",
        "swap": "#9c27b0",
        "status": "#888888"
    },
    "light": {
        "bg": "#f5f5f5",
        "panel": "#e0e0e0",
        "fg": "#202020",
        "accent": "#388e3c",
        "warn": "#f57c00",
        "crit": "#d32f2f",
        "disk": "#0288d1",
        "swap": "#7b1fa2",
        "status": "#555555"
    }
}
FONT_BASE = "JetBrains Mono"

# ---------- UTILITIES ----------
def bytes2human(n):
    for u in ["B", "K", "M", "G", "T"]:
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}P"

def color_for_load(pct, colors):
    if pct < 50: return colors["accent"]
    if pct < 75: return colors["warn"]
    return colors["crit"]

def get_os_name():
    try:
        out = subprocess.check_output(["lsb_release", "-d"], text=True)
        return out.split(":", 1)[1].strip()
    except Exception:
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except: pass
    return platform.system()

def get_cpu_model():
    try:
        out = subprocess.check_output(["lscpu"], text=True, errors="ignore")
        for line in out.splitlines():
            if "Model name" in line or "Modelnavn" in line:
                return line.split(":", 1)[1].strip()
    except Exception: pass
    return platform.processor() or "Unknown CPU"

def get_gpu_list():
    try:
        out = subprocess.check_output(["lspci"], text=True, errors="ignore")
        return [l.split(":", 2)[-1].strip()
                for l in out.splitlines()
                if ("VGA" in l or "3D controller" in l)]
    except Exception: return []

def format_uptime():
    boot = psutil.boot_time()
    delta = timedelta(seconds=int(time.time() - boot))
    days = delta.days
    rest = str(delta - timedelta(days=days))
    return f"{days} day{'s' if days!=1 else ''} {rest}" if days else rest

def detect_system_theme():
    """Try detect desktop color-scheme (GNOME first), fallback to dark."""
    try:
        out = subprocess.check_output(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            text=True
        ).strip().lower()
        if "dark" in out: return "dark"
        if "light" in out: return "light"
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            ["xdg-settings", "get", "org.gnome.desktop.interface.color-scheme"],
            text=True
        ).strip().lower()
        if "dark" in out: return "dark"
        if "light" in out: return "light"
    except Exception:
        pass
    return "dark"

# ---------- CONFIG ----------
def cfg_path():
    base = os.path.join(os.path.expanduser("~"), ".config")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "sysmon_dark.cfg")

def load_settings():
    cfg = ConfigParser()
    cfg.read(cfg_path())
    fs = cfg.getint("ui", "font_size", fallback=10)
    interval = cfg.getint("ui", "update_interval_ms", fallback=1000)
    theme_mode = cfg.get("ui", "theme_mode", fallback="auto")
    return fs, interval, theme_mode

def save_settings(fs, interval, theme_mode):
    cfg = ConfigParser()
    cfg["ui"] = {
        "font_size": str(fs),
        "update_interval_ms": str(interval),
        "theme_mode": theme_mode
    }
    with open(cfg_path(), "w") as f:
        cfg.write(f)

# ---------- APP ----------
class SysMon(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SysMon — Theme Edition")
        self.geometry("1100x770")
        self.minsize(860, 520)

        self.font_size, self.update_interval, self.theme_mode = load_settings()
        self.colors = THEMES[self._resolve_theme()]
        self.configure(bg=self.colors["bg"])

        self._sort_column = ("%CPU", True)

        self._create_menu()
        self._create_top_info()
        self._create_cpu_panel()
        self._create_mem_swap_disk_panel()
        self._create_proc_table()
        self._create_statusbar()
        self._bind_shortcuts()

        self._update_all()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- THEME ----------
    def _resolve_theme(self):
        if self.theme_mode == "auto":
            return detect_system_theme()
        return self.theme_mode if self.theme_mode in THEMES else "dark"

    def _apply_theme(self):
        self.colors = THEMES[self._resolve_theme()]
        self.configure(bg=self.colors["bg"])
        for widget in self.winfo_children():
            self._recolor(widget)

    def _recolor(self, w):
        try:
            if isinstance(w, (tk.Frame, tk.LabelFrame)):
                w.configure(bg=self.colors["panel"], fg=self.colors["fg"])
            elif isinstance(w, tk.Label):
                # top labels/status are on panel by design
                if getattr(w, "_is_status", False):
                    w.configure(bg=self.colors["bg"], fg=self.colors["status"])
                else:
                    w.configure(bg=self.colors["panel"], fg=self.colors["fg"])
            elif isinstance(w, tk.Canvas):
                w.configure(bg=self.colors["bg"])
        except tk.TclError:
            pass
        for c in w.winfo_children():
            self._recolor(c)

    # ---------- MENU ----------
    def _create_menu(self):
        m = tk.Menu(self)
        self.config(menu=m)

        # Update Interval
        m_interval = tk.Menu(m, tearoff=0)
        for sec in [0.5, 1, 2, 5]:
            m_interval.add_command(label=f"{sec:.1f} sec", command=lambda s=sec: self._set_interval(s))
        m.add_cascade(label="Update Interval", menu=m_interval)

        # View
        m_view = tk.Menu(m, tearoff=0)
        m_theme = tk.Menu(m_view, tearoff=0)
        for mode in ["auto", "dark", "light"]:
            m_theme.add_command(label=mode.capitalize(), command=lambda md=mode: self._set_theme(md))
        m_view.add_cascade(label="Theme", menu=m_theme)
        m_view.add_separator()
        m_view.add_command(label="Zoom in (Ctrl +)", command=self._zoom_in)
        m_view.add_command(label="Zoom out (Ctrl -)", command=self._zoom_out)
        m_view.add_command(label="Reset zoom (Ctrl 0)", command=self._zoom_reset)
        m.add_cascade(label="View", menu=m_view)

        # Settings
        m_settings = tk.Menu(m, tearoff=0)
        m_settings.add_command(label="Save settings (Ctrl S)", command=self._save_settings_now)
        m.add_cascade(label="Settings", menu=m_settings)

    def _set_theme(self, mode):
        self.theme_mode = mode
        self._apply_theme()
        self.status.config(text=f"Theme set to {mode} (saved on exit)")

    def _set_interval(self, sec):
        self.update_interval = int(sec * 1000)
        self.status.config(text=f"Interval {sec:.1f}s (saved on exit)")

    # ---------- SHORTCUTS ----------
    def _bind_shortcuts(self):
        # zoom
        self.bind("<Control-plus>", self._zoom_in)
        self.bind("<Control-minus>", self._zoom_out)
        self.bind("<Control-KP_Add>", self._zoom_in)
        self.bind("<Control-KP_Subtract>", self._zoom_out)
        self.bind("<Control-0>", self._zoom_reset)
        # interval
        self.bind("<Alt-plus>", self._increase_interval)
        self.bind("<Alt-minus>", self._decrease_interval)
        self.bind("<Alt-KP_Add>", self._increase_interval)
        self.bind("<Alt-KP_Subtract>", self._decrease_interval)
        # save
        self.bind("<Control-s>", self._save_settings_now)

    def _increase_interval(self, e=None):
        self.update_interval = min(self.update_interval + 500, 10000)
        self.status.config(text=f"Interval: {self.update_interval/1000:.1f}s")

    def _decrease_interval(self, e=None):
        self.update_interval = max(self.update_interval - 500, 250)
        self.status.config(text=f"Interval: {self.update_interval/1000:.1f}s")

    # ---------- FONT ----------
    def _zoom_in(self, e=None):
        self.font_size += 1
        self._apply_font_size()
    def _zoom_out(self, e=None):
        if self.font_size > 6:
            self.font_size -= 1
            self._apply_font_size()
    def _zoom_reset(self, e=None):
        self.font_size = 10
        self._apply_font_size()
    def _apply_font_size(self):
        ft = (FONT_BASE, self.font_size)
        for w in self.winfo_children():
            self._apply_font_recursive(w, ft)
    def _apply_font_recursive(self, w, ft):
        try: w.configure(font=ft)
        except tk.TclError: pass
        for c in w.winfo_children():
            self._apply_font_recursive(c, ft)

    # ---------- SAVE ----------
    def _save_settings_now(self, e=None):
        save_settings(self.font_size, self.update_interval, self.theme_mode)
        self.status.config(text="Settings saved ✓")
    def _on_close(self):
        save_settings(self.font_size, self.update_interval, self.theme_mode)
        self.destroy()

    # ---------- PANELS ----------
    def _create_top_info(self):
        self.top_frame = tk.Frame(self, bg=self.colors["panel"])
        self.top_frame.pack(fill="x", padx=8, pady=6)
        self.top_labels = []
        for _ in range(7):  # Host, Uptime, OS, CPU, GPU1..N, Python
            lbl = tk.Label(self.top_frame, bg=self.colors["panel"], fg=self.colors["fg"], anchor="w")
            lbl.pack(anchor="w", padx=8)
            self.top_labels.append(lbl)
        self._update_top_info()

    def _update_top_info(self):
        host = socket.gethostname()
        boot = psutil.boot_time()
        uptime = format_uptime()
        os_info = get_os_name()
        cpu_info = get_cpu_model()
        gpus = get_gpu_list()
        py = f"Python {platform.python_version()}"

        lines = [f"Host: {host}",
                 f"Uptime: {uptime}",
                 f"OS: {os_info}",
                 f"CPU: {cpu_info}"]
        lines += [f"GPU{i+1}: {g}" for i, g in enumerate(gpus)] or ["GPU: (none detected)"]
        lines.append(py)

        # Ensure label list long enough
        for i in range(max(len(self.top_labels), len(lines)) - len(self.top_labels)):
            lbl = tk.Label(self.top_frame, bg=self.colors["panel"], fg=self.colors["fg"], anchor="w")
            lbl.pack(anchor="w", padx=8)
            self.top_labels.append(lbl)
        for lbl, txt in zip(self.top_labels, lines + [""]*(len(self.top_labels)-len(lines))):
            lbl.config(text=txt)

    def _create_cpu_panel(self):
        f = tk.LabelFrame(self, text="CPU Usage", fg=self.colors["fg"], bg=self.colors["panel"])
        f.pack(fill="x", padx=8, pady=4)

        # total bar
        self.total_canvas = tk.Canvas(f, height=18, bg=self.colors["bg"], highlightthickness=0)
        self.total_canvas.pack(fill="x", padx=6, pady=3)

        # per-core
        self.cpu_labels = []
        cols = 4
        n = psutil.cpu_count(logical=True)
        grid = tk.Frame(f, bg=self.colors["panel"])
        grid.pack(fill="x")
        for i in range(n):
            r, c = divmod(i, cols)
            cell = tk.Frame(grid, bg=self.colors["panel"])
            cell.grid(row=r, column=c, sticky="ew", padx=4, pady=2)
            lbl = tk.Label(cell, text=f"CPU{i}", bg=self.colors["panel"], fg=self.colors["fg"], width=6, anchor="w")
            lbl.pack(side="left")
            bar = tk.Canvas(cell, height=12, bg=self.colors["bg"], highlightthickness=0)
            bar.pack(side="left", fill="x", expand=True, padx=4)
            pct = tk.Label(cell, text="0%", bg=self.colors["panel"], fg=self.colors["fg"], width=5, anchor="e")
            pct.pack(side="left")
            self.cpu_labels.append((lbl, bar, pct))

    def _create_mem_swap_disk_panel(self):
        f = tk.LabelFrame(self, text="Memory / Swap / Disk", fg=self.colors["fg"], bg=self.colors["panel"])
        f.pack(fill="x", padx=8, pady=4)

        self.mem_label = tk.Label(f, bg=self.colors["panel"], fg=self.colors["fg"])
        self.mem_label.pack(fill="x", padx=8)
        self.mem_canvas = tk.Canvas(f, height=16, bg=self.colors["bg"], highlightthickness=0)
        self.mem_canvas.pack(fill="x", padx=8)

        self.swap_label = tk.Label(f, bg=self.colors["panel"], fg=self.colors["fg"])
        self.swap_label.pack(fill="x", padx=8, pady=(6, 0))
        self.swap_canvas = tk.Canvas(f, height=16, bg=self.colors["bg"], highlightthickness=0)
        self.swap_canvas.pack(fill="x", padx=8)

        self.disk_label = tk.Label(f, bg=self.colors["panel"], fg=self.colors["fg"])
        self.disk_label.pack(fill="x", padx=8, pady=(6, 0))
        self.disk_canvas = tk.Canvas(f, height=16, bg=self.colors["bg"], highlightthickness=0)
        self.disk_canvas.pack(fill="x", padx=8)

    def _create_proc_table(self):
        f = tk.Frame(self, bg=self.colors["bg"])
        f.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("PID","USER","%CPU","%MEM","VIRT","RES","TIME","CMD")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
            background=self.colors["bg"],
            foreground=self.colors["fg"],
            fieldbackground=self.colors["bg"],
            rowheight=22,
            font=(FONT_BASE, self.font_size))
        style.map("Treeview",
            background=[("selected", "#333333")],
            foreground=[("selected", self.colors["fg"])])

        self.tree = ttk.Treeview(f, columns=cols, show="headings")
        for c,w in zip(cols,[70,100,70,70,90,90,80,400]):
            self.tree.column(c,width=w,anchor="w")
            self.tree.heading(c,text=c,anchor="w")
        vsb = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _create_statusbar(self):
        self.status = tk.Label(self, text="", anchor="w",
                               bg=self.colors["bg"], fg=self.colors["status"])
        self.status._is_status = True
        self.status.pack(fill="x", side="bottom", padx=8, pady=4)

    # ---------- DRAW ----------
    def _draw_bar(self, canvas, pct, color):
        canvas.delete("all")
        w = canvas.winfo_width() or 100
        h = canvas.winfo_height() or 14
        canvas.create_rectangle(0,0,w,h,fill=self.colors["bg"],outline="")
        canvas.create_rectangle(0,0,int(w*pct/100),h,fill=color,outline="")
        canvas.create_text(w-25,h//2,text=f"{pct:.0f}%",fill=self.colors["fg"],
                           font=(FONT_BASE, max(7,self.font_size-2)))

    # ---------- UPDATE LOOP ----------
    def _update_all(self):
        try:
            self._update_cpu()
            self._update_mem_swap_disk()
            self._update_procs()
            self._update_top_info()
        except Exception as e:
            print("Update error:", e, file=sys.stderr)
        self.after(self.update_interval, self._update_all)

    def _update_cpu(self):
        total = psutil.cpu_percent(interval=None)
        self._draw_bar(self.total_canvas, total, color_for_load(total, self.colors))
        per = psutil.cpu_percent(percpu=True)
        for (lbl, bar, pct), p in zip(self.cpu_labels, per):
            pct.config(text=f"{p:.0f}%")
            self._draw_bar(bar, p, color_for_load(p, self.colors))

    def _update_mem_swap_disk(self):
        m = psutil.virtual_memory()
        s = psutil.swap_memory()
        d = shutil.disk_usage("/")
        self.mem_label.config(text=f"RAM: {bytes2human(m.used)}/{bytes2human(m.total)} ({m.percent:.1f}%)")
        self.swap_label.config(text=f"SWAP: {bytes2human(s.used)}/{bytes2human(s.total)} ({s.percent:.1f}%)")
        pct = (d.used/d.total)*100 if d.total else 0.0
        self.disk_label.config(text=f"Disk /: {bytes2human(d.used)}/{bytes2human(d.total)} ({pct:.1f}%)")
        self._draw_bar(self.mem_canvas, m.percent, color_for_load(m.percent, self.colors))
        self._draw_bar(self.swap_canvas, s.percent, self.colors["swap"])
        self._draw_bar(self.disk_canvas, pct, self.colors["disk"])

    def _update_procs(self):
        self.tree.delete(*self.tree.get_children())
        rows = []
        for p in psutil.process_iter(["pid","username","cpu_percent","memory_percent","memory_info","cmdline","create_time"]):
            try:
                i = p.info
                cmd = " ".join(i["cmdline"] or [p.name()])
                if len(cmd) > 100: cmd = cmd[:97] + "..."
                rows.append((
                    i["pid"],
                    i["username"] or "",
                    f"{i['cpu_percent']:.1f}",
                    f"{i['memory_percent']:.1f}",
                    bytes2human(i["memory_info"].vms),
                    bytes2human(i["memory_info"].rss),
                    time.strftime("%H:%M:%S", time.localtime(i["create_time"])),
                    cmd
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        rows.sort(key=lambda r: float(r[2]), reverse=True)
        for r in rows[:80]:
            self.tree.insert("", "end", values=r)
        self.status.config(text=f"Host: {socket.gethostname()} | Uptime: {format_uptime()} | "
                                f"Processes: {len(rows)} | Interval: {self.update_interval/1000:.1f}s | "
                                f"CPU: {psutil.cpu_percent():.1f}%")

# ---------- MAIN ----------
if __name__ == "__main__":
    try:
        import psutil  # ensure installed
    except ImportError:
        print("Please install psutil: pip install psutil")
        sys.exit(1)
    app = SysMon()
    app.mainloop()
