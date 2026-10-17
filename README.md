## 👀 screenrec Overview  
**ScreenRec** is a Linux screen recording utility that lets you record selected screen regions with configurable recording settings, a dedicated graphical interface, and keyboard or mouse controls for stopping recordings.

![screenrec Demo Video](https://github.com/FURK4NGG/screenrec/blob/main/%7B%7D/screenrec.gif)


![screenrec_install Demo Image](https://github.com/FURK4NGG/screenrec/blob/main/%7B%7D/screenrec_install.webp)

<br><br>

✅ Works On  
Wayland compositors (Hyprland)  

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
import sys

home = Path.home()

shell_files = [
    home / "screenrec/screenrec.sh",
    home / ".config/scripts/screenrec.sh",
    home / ".config/screenrec/screenrec.sh",
]

ui_files = [
    home / "screenrec/screenrec-ui.py",
    home / ".config/scripts/screenrec-ui.py",
]

old_ffmpeg = '''        ffmpeg -hide_banner -loglevel warning \\
            -f x11grab -framerate 30 -i "$DISPLAY" \\
            -c:v libx264 -preset ultrafast -crf 23 \\
            -pix_fmt yuv420p "$FILE" \\
            > "$CACHE_DIR/ffmpeg.log" 2>&1 &
'''

new_ffmpeg = '''        ffmpeg -hide_banner -nostdin -loglevel warning \\
            -f x11grab -framerate 30 -i "$DISPLAY" \\
            -c:v libx264 -preset ultrafast -crf 23 \\
            -pix_fmt yuv420p -movflags +faststart "$FILE" \\
            > "$CACHE_DIR/ffmpeg.log" 2>&1 &
'''

start_function = '''    def start_recording(self, *_):
        try:
            self._persist_current_settings()
        except Exception as e:
            self.notify(
                f"Folder error: {e}"
            )
            return

        active = self.get_active_recordings()

        if active:
            tr = self.config.get("language") == "tr"
            self.show_start_already_running_dialog(tr)
            return

        if not SCRIPT_FILE.exists():
            self.notify("screenrec.sh not found")
            return

        log_dir = Path.home() / ".cache" / "screenrec"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "launcher.log"

        try:
            with log_file.open("a", encoding="utf-8") as output:
                output.write("\\\\n--- Starting ScreenRec ---\\\\n")
                output.flush()
                subprocess.Popen(
                    [str(SCRIPT_FILE), "start"],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except Exception as e:
            self.notify(f"Failed to start recording: {e}")
'''

failed = False

for path in shell_files:
    if not path.exists():
        continue

    text = path.read_text(encoding="utf-8")

    if old_ffmpeg in text:
        updated = text.replace(old_ffmpeg, new_ffmpeg, 1)
    elif new_ffmpeg in text:
        print(f"[OK] FFmpeg already updated: {path}")
        continue
    else:
        print(f"[ERROR] FFmpeg block not found: {path}")
        failed = True
        continue

    backup = path.with_suffix(path.suffix + ".final-backup")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")

    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Updated recorder: {path}")

for path in ui_files:
    if not path.exists():
        continue

    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^    def start_recording\(self, \*_\):\n"
        r".*?(?=^    def stop_recording\(self, \*_\):)",
        re.M | re.S,
    )

    match = pattern.search(text)
    if not match:
        if "launcher.log" in text:
            print(f"[OK] Launcher logging already enabled: {path}")
        else:
            print(f"[ERROR] start_recording function not found: {path}")
            failed = True
        continue

    backup = path.with_suffix(path.suffix + ".final-backup")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")

    updated = text[:match.start()] + start_function + "\n" + text[match.end():]
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Updated UI: {path}")

if failed:
    sys.exit("Some files were not updated. Review the errors above.")

print("\\nFinished. Validate syntax before launching.")
PY

bash -n ~/.config/scripts/screenrec.sh
python3 -m py_compile ~/.config/scripts/screenrec-ui.py
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
python3 ~/.config/scripts/screenrec-ui.py
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
