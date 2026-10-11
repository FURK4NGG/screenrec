## 👀 screenrec Overview  
**ScreenRec** is a Linux screen recording utility that lets you record selected screen regions with configurable recording settings, a dedicated graphical interface, and keyboard or mouse controls for stopping recordings.

![screenrec Demo Video](https://github.com/FURK4NGG/screenrec/blob/main/%7B%7D/screenrec.gif)

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
