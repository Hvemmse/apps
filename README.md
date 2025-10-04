# 🖥️ SysMon — Theme Edition

A modern **Python + Tkinter system monitor**, inspired by `htop` and `btop++`,  
featuring **dark/light/auto theme**, persistent settings, and live performance stats.

---

## 🚀 Features

✅ Dark / Light / Auto theme (auto-detects from system)  
✅ Hostname & Uptime display  
✅ Real-time CPU load (total + per-core)  
✅ Memory (RAM), Swap, and Disk usage bars  
✅ Live process list (CPU%, MEM%, PID, user, etc.)  
✅ Adjustable update interval (menu or `Alt +/-`)  
✅ Zoomable interface (`Ctrl +`, `Ctrl -`, `Ctrl 0`)  
✅ Persistent config (`~/.config/sysmon_dark.cfg`)  
✅ Cross-platform (Linux, *BSD, macOS partial, WSL)

---

## 🧩 Requirements

- Python **3.10+**
- `psutil`
- `tkinter` (usually preinstalled)
- Optional for auto theme detection:
  - `gsettings` *(GNOME)* or  
  - `xdg-settings` *(XDG standard)*

Install dependencies:

```bash
sudo apt install python3-tk lsb-release pciutils gsettings-desktop-schemas
pip install psutil
