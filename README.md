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

ui_text = ui.read_text(encoding="utf-8")
sh_text = script.read_text(encoding="utf-8")

# ---- UI: replace Adw.ToolbarView ----
replacements = [
    (
        '''        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()''',
        '''        root = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0
        )
        header = Adw.HeaderBar()''',
        "Toolbar initialization",
    ),
    (
        "        toolbar.add_top_bar(header)",
        "        root.append(header)",
        "Header attachment",
    ),
    (
        '''        toolbar.set_content(self.content)
        self.window.set_content(toolbar)''',
        '''        root.append(self.content)
        self.window.set_content(root)''',
        "Main content attachment",
    ),
]

for old, new, label in replacements:
    if old in ui_text:
        ui_text = ui_text.replace(old, new, 1)
    elif new not in ui_text:
        raise SystemExit(f"[ERROR] {label} block not found.")

# ---- UI: use a GTK 4.8-compatible folder chooser ----
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

ui_text, count = re.subn(
    folder_pattern, folder_replacement, ui_text,
    count=1, flags=re.S
)
if count != 1:
    raise SystemExit("[ERROR] Folder chooser methods not found.")

# ---- Shell: select the correct recording backend ----
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

if old_geometry in sh_text:
    sh_text = sh_text.replace(old_geometry, new_geometry, 1)
elif 'BACKEND="x11"' not in sh_text or 'BACKEND="wayland"' not in sh_text:
    raise SystemExit("[ERROR] Recording backend selection block not found.")

# ---- Shell: use FFmpeg on X11 and wf-recorder on Wayland ----
old_recorder = '''    wf-recorder \\
        --geometry "$GEOM" \\
        --file "$FILE" \\
        --audio=alsa_output.pci-0000_0d_00.6.analog-stereo.monitor \\
        > /dev/null 2>&1 &

    PID=$!'''

new_recorder = '''    if [ "$BACKEND" = "x11" ]; then
        if ! command -v ffmpeg >/dev/null 2>&1; then
            echo "ffmpeg is not installed" >&2
            exit 1
        fi

        ffmpeg -hide_banner -nostdin -loglevel warning \\
            -f x11grab -framerate 30 -i "$DISPLAY" \\
            -c:v libx264 -preset ultrafast -crf 23 \\
            -pix_fmt yuv420p -movflags +faststart "$FILE" \\
            > "$CACHE_DIR/ffmpeg.log" 2>&1 &
    else
        wf-recorder \\
            --geometry "$GEOM" \\
            --file "$FILE" \\
            --audio=alsa_output.pci-0000_0d_00.6.analog-stereo.monitor \\
            > "$CACHE_DIR/wf-recorder.log" 2>&1 &
    fi

    PID=$!'''

if old_recorder in sh_text:
    sh_text = sh_text.replace(old_recorder, new_recorder, 1)
elif 'ffmpeg -hide_banner -nostdin -loglevel warning' not in sh_text:
    raise SystemExit("[ERROR] Recorder launch block not found.")

# Back up both files before writing.
shutil.copy2(ui, ui.with_suffix(".py.bak"))
shutil.copy2(script, script.with_suffix(".sh.bak"))

ui.write_text(ui_text, encoding="utf-8")
script.write_text(sh_text, encoding="utf-8")
script.chmod(0o755)

print("[OK] UI and recording backend updated.")
print("[BACKUP]", ui.with_suffix(".py.bak"))
print("[BACKUP]", script.with_suffix(".sh.bak"))
PY

python3 -m py_compile ~/.config/screenrec/screenrec-ui.py &&
bash -n ~/.config/screenrec/screenrec.sh &&
echo "[OK] Both files passed syntax checks." &&
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
