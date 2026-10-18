## 👀 screenrec Overview  
**ScreenRec** is a Linux screen recording utility that lets you record selected screen regions with configurable recording settings, a dedicated graphical interface, and keyboard or mouse controls for stopping recordings.

![screenrec Demo Video](https://github.com/FURK4NGG/screenrec/blob/main/%7B%7D/screenrec.gif)


![screenrec_install Demo Image](https://github.com/FURK4NGG/screenrec/blob/main/%7B%7D/screenrec_install.webp)

<br><br>

✅ Works On  
- Linux distributions: Arch Linux, Debian, Fedora  
- Wayland compositors: Hyprland, Sway, and other wlroots-based compositors  

⚠️ Compatibility  
Other Wayland compositors and desktop environments have not been verified yet.
<br><br>

## 🚀 Features

- [x] Record a selected region of the screen
- [x] Start and stop recordings from the graphical interface
- [x] Configure the recording output directory
- [x] Set a custom keyboard key or mouse button to stop recording
- [x] Optional starting delay with a configurable countdown
- [x] Cancel a recording before the countdown finishes
- [x] Manage multiple active recordings
- [x] Choose which active recording to stop
- [x] English and Turkish interface languages
- [x] Dark and light appearance modes
- [x] Persistent settings stored in a JSON configuration file
- [x] Input event detection through `evdev`
- [x] Screen recording through `wf-recorder`
- [x] Region selection through `slurp`
- [x] Desktop notifications through `notify-send`

<br>

## 📦 Setup

Directory Structure  
~/.config/screenrec/  
├── install.sh  
├── config.json (This file is auto-generated)  
├── screenrec-ui.py  
└── screenrec.sh  
<br>


```
git clone https://github.com/FURK4NGG/screenrec.git
cd screenrec
mkdir -p ~/.config/screenrec
cp screenrec-ui.py \
   screenrec.sh \
   install.sh \
   LICENSE \
   README.md \
   ~/.config/screenrec/


chmod +x ~/.config/screenrec/screenrec-ui.py  
chmod +x ~/.config/screenrec/screenrec.sh  
chmod +x ~/.config/screenrec/install.sh  
```


Arch
```
sudo pacman -S git python python-gobject python-cairo python-evdev gtk4 libadwaita ffmpeg wf-recorder slurp libnotify jq
```
<br>

<details>
<summary>Debian / Ubuntu</summary>

```
sudo apt update
sudo apt install -y \
    python3 \
    python3-gi \
    python3-gi-cairo \
    python3-evdev \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    ffmpeg \
    wf-recorder \
    slurp \
    libnotify-bin \
    dbus-x11
```

```
python3 - <<'PY'
from pathlib import Path
import re
import shutil

base = Path.home() / ".config" / "screenrec"
ui = base / "screenrec-ui.py"
script = base / "screenrec.sh"

if not ui.is_file() or not script.is_file():
    raise SystemExit("[ERROR] ScreenRec UI or shell script not found.")

u = ui.read_text(encoding="utf-8")
s = script.read_text(encoding="utf-8")


def replace_once(text, old, new, label):
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise SystemExit(f"[ERROR] Could not locate {label}. No files changed.")


# --------------------------------------------------
# UI: Debian 12 / libadwaita compatibility
# --------------------------------------------------

u = replace_once(
    u,
    '''        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()''',
    '''        root = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0
        )
        header = Adw.HeaderBar()''',
    "ToolbarView initialization",
)

u = replace_once(
    u,
    "        toolbar.add_top_bar(header)",
    "        root.append(header)",
    "header attachment",
)

u = replace_once(
    u,
    '''        toolbar.set_content(self.content)
        self.window.set_content(toolbar)''',
    '''        root.append(self.content)
        self.window.set_content(root)''',
    "main content attachment",
)

# Replace Gtk.FileDialog with Gtk.FileChooserNative for GTK 4.8.
folder_pattern = (
    r'    def choose_folder\(self, \*_?\):.*?'
    r'(?=    def capture_key\()'
)

folder_replacement = '''    def choose_folder(self, *_):
        tr = self.config.get("language") == "tr"

        dialog = Gtk.FileChooserNative.new(
            "Kayıt klasörünü seç" if tr else "Select recording folder",
            self.window,
            Gtk.FileChooserAction.SELECT_FOLDER,
            "Seç" if tr else "Select",
            "İptal" if tr else "Cancel"
        )
        dialog.connect("response", self.folder_selected)
        dialog.show()

    def folder_selected(self, dialog, response):
        try:
            if response == Gtk.ResponseType.ACCEPT:
                folder = dialog.get_file()
                if folder:
                    self.folder_entry.set_text(folder.get_path())
        finally:
            dialog.destroy()

'''

u2, count = re.subn(
    folder_pattern,
    folder_replacement,
    u,
    count=1,
    flags=re.S,
)

if count == 1:
    u = u2
elif not re.search(
    r'    def choose_folder\(self, \*_?\):.*?'
    r'Gtk\.FileChooserNative\.new',
    u,
    flags=re.S,
):
    raise SystemExit("[ERROR] Folder chooser block not found. No files changed.")


# --------------------------------------------------
# Shell: choose the correct display backend
# --------------------------------------------------

old_geometry = '''    GEOM="$(slurp -o -f "%x,%y %wx%h" 2>/dev/null)" || exit 0'''

new_geometry = '''    BACKEND=""
    GEOM=""

    if [ -n "${WAYLAND_DISPLAY:-}" ]; then
        BACKEND="wayland"
        GEOM="$(slurp -o -f "%x,%y %wx%h" 2>/dev/null)" || exit 0
        [ -n "$GEOM" ] || exit 0
    elif [ -n "${DISPLAY:-}" ]; then
        BACKEND="x11"
    else
        echo "No graphical display available" >&2
        exit 1
    fi'''

if old_geometry in s:
    s = s.replace(old_geometry, new_geometry, 1)
elif not (
    'BACKEND="x11"' in s
    and 'BACKEND="wayland"' in s
):
    raise SystemExit("[ERROR] Display backend block not found. No files changed.")


# --------------------------------------------------
# Shell: preserve audio setup, replace only recorder
# --------------------------------------------------

recorder_pattern = (
    r'    if \[ -n "\$AUDIO_SOURCE" \]; then\n'
    r'.*?'
    r'\n    PID=\$\!'
)

recorder_replacement = '''    if [ "$BACKEND" = "x11" ]; then
        if ! command -v ffmpeg >/dev/null 2>&1; then
            echo "ffmpeg is not installed" >&2
            exit 1
        fi

        if [ -n "$AUDIO_SOURCE" ]; then
            ffmpeg -hide_banner -nostdin -loglevel warning \\
                -f x11grab -framerate 30 -i "$DISPLAY" \\
                -f pulse -i "$AUDIO_SOURCE" \\
                -map 0:v:0 -map 1:a:0 \\
                -c:v libx264 -preset ultrafast -crf 23 \\
                -pix_fmt yuv420p -c:a aac -b:a 192k \\
                -movflags +faststart "$FILE" \\
                > "$CACHE_DIR/ffmpeg.log" 2>&1 &
        else
            ffmpeg -hide_banner -nostdin -loglevel warning \\
                -f x11grab -framerate 30 -i "$DISPLAY" \\
                -c:v libx264 -preset ultrafast -crf 23 \\
                -pix_fmt yuv420p -movflags +faststart "$FILE" \\
                > "$CACHE_DIR/ffmpeg.log" 2>&1 &
        fi
    else
        if [ -n "$AUDIO_SOURCE" ]; then
            wf-recorder \\
                --geometry "$GEOM" \\
                --file "$FILE" \\
                --audio="$AUDIO_SOURCE" \\
                > "$CACHE_DIR/wf-recorder.log" 2>&1 &
        else
            wf-recorder \\
                --geometry "$GEOM" \\
                --file "$FILE" \\
                > "$CACHE_DIR/wf-recorder.log" 2>&1 &
        fi
    fi

    PID=$!'''

if re.search(r'if \[ -n "\$AUDIO_SOURCE" \]; then\n.*?\n    PID=\$\!', s, flags=re.S):
    s2, count = re.subn(
        recorder_pattern,
        lambda _: recorder_replacement,
        s,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise SystemExit("[ERROR] Recorder block replacement failed. No files changed.")
    s = s2
elif not (
    'if [ "$BACKEND" = "x11" ]; then' in s
    and "-f x11grab" in s
    and "wf-recorder" in s
):
    raise SystemExit("[ERROR] Recorder block not found. No files changed.")


# --------------------------------------------------
# Validate in memory before writing; back up originals
# --------------------------------------------------

if re.search(r'Adw\.ToolbarView|toolbar\.add_top_bar|Gtk\.FileDialog', u):
    raise SystemExit("[ERROR] Unsupported GTK components remain. No files changed.")

ui_backup = ui.with_name(ui.name + ".bak")
sh_backup = script.with_name(script.name + ".bak")

shutil.copy2(ui, ui_backup)
shutil.copy2(script, sh_backup)

ui.write_text(u, encoding="utf-8")
script.write_text(s, encoding="utf-8")
script.chmod(0o755)

print("[OK] UI compatibility updated.")
print("[OK] X11/Wayland recording backend updated.")
print("[OK] Existing microphone and system-audio setup preserved.")
print(f"[BACKUP] {ui_backup}")
print(f"[BACKUP] {sh_backup}")
PY

python3 -m py_compile ~/.config/screenrec/screenrec-ui.py &&
bash -n ~/.config/screenrec/screenrec.sh &&
echo "[OK] Syntax checks passed." &&
python3 ~/.config/screenrec/screenrec-ui.py
```
</details>
<br>

Fedora  
```
sudo dnf install -y git python3 python3-gobject python3-cairo python3-evdev gtk4 libadwaita ffmpeg wf-recorder slurp libnotify jq
```
<br><br>

## 🎉 Run
```
python3 ~/.config/screenrec/screenrec-ui.py
```
<br><br>

## ❓ HOW IT WORKS ❓

Screen / Region Selection  
&nbsp;&nbsp;&nbsp;│  
&nbsp;&nbsp;&nbsp;▼  
`slurp`  
&nbsp;&nbsp;&nbsp;│  
&nbsp;&nbsp;&nbsp;▼  
`screenrec.sh`  
&nbsp;&nbsp;&nbsp;│  
&nbsp;&nbsp;&nbsp;▼  
`wf-recorder` → Screen Recording  
&nbsp;&nbsp;&nbsp;│  
&nbsp;&nbsp;&nbsp;▼  
Output Video File  
<br><br><br>

`screenrec-ui.py`  
&nbsp;&nbsp;&nbsp;│  
&nbsp;&nbsp;&nbsp;▼  
`~/.config/screenrec/config.json`  
<br><br><br>

`screenrec.sh`  
&nbsp;&nbsp;&nbsp;│  
&nbsp;&nbsp;&nbsp;├── Recording management  
&nbsp;&nbsp;&nbsp;├── Region selection and countdown  
&nbsp;&nbsp;&nbsp;└── Stop / cancel controls  


## [`screenrec.sh`]

- Starts, stops, and manages screen recordings.  
  Ekran kayıtlarını başlatır, durdurur ve yönetir.

- Uses `wf-recorder` and `slurp` to record selected screen regions.  
  Seçilen ekran bölgelerini kaydetmek için `wf-recorder` ve `slurp` kullanır.

- Supports countdowns, cancellation, and recording tracking.  
  Geri sayımı, iptal işlemini ve kayıt takibini destekler.

- Sends desktop notifications.  
  Masaüstü bildirimleri gönderir.

## [`screenrec-ui.py`]

- Provides a graphical settings interface.  
  Grafiksel bir ayarlar arayüzü sunar.

- Configures the output folder and custom stop keys or mouse buttons.  
  Kayıt klasörünü ve özel durdurma tuşlarını veya fare düğmelerini ayarlar.

- Supports optional starting delay and separate start/stop buttons.  
  İsteğe bağlı başlama gecikmesini ve ayrı başlatma/durdurma düğmelerini destekler.

- Supports English, Turkish, dark mode, and light mode.  
  İngilizce, Türkçe, koyu mod ve açık mod desteği sunar.

- Saves settings and manages active recordings.  
  Ayarları kaydeder ve etkin kayıtları yönetir.

- Detects keyboard and mouse events using `evdev`.  
  `evdev` kullanarak klavye ve fare olaylarını algılar.

# Fast Installation  

sudo pacman -Syu git  
git clone https://github.com/FURK4NGG/screenrec.git  
cd screenrec  
chmod +x install.sh  
./install.sh  

## 🔒 License  
<h1 align="center">📜 GPL-3.0 License</h1>
