#!/usr/bin/env python3

import json
import os
import subprocess
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib

try:
    from evdev import InputDevice, list_devices, ecodes
except ImportError:
    InputDevice = None
    list_devices = None
    ecodes = None


CONFIG_DIR = Path.home() / ".config" / "screenrec"
CONFIG_FILE = CONFIG_DIR / "config.json"
SCRIPT_FILE = CONFIG_DIR / "screenrec.sh"
STOP_REQUEST_FILE = Path.home() / ".cache" / "screenrec" / "stop-request"

DEFAULT_CONFIG = {
    "output_dir": str(Path.home() / "Resimler"),
    "stop_key": "",
    "language": "en",
    "dark_mode": True,
    "starting_delay": 5,
    "starting_delay_enabled": False
}


def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULT_CONFIG, **data}
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def key_name(code):
    if ecodes is None:
        return None

    # Mouse buttons live in ecodes.BTN on evdev. Some versions also expose
    # them through ecodes.KEY, but that is not guaranteed, so check BTN first.
    name = ecodes.BTN.get(code)
    if isinstance(name, list):
        name = name[0]
    if name:
        return name

    name = ecodes.KEY.get(code)
    if isinstance(name, list):
        name = name[0]

    return name if name else None


def key_id_from_event(code):
    name = key_name(code)

    if not name:
        return None

    # BTN_* is a mouse/button event. Do not rely on the KEY dictionary
    # containing BTN_* entries.
    if name.startswith("BTN_"):
        mouse_names = {
            "BTN_LEFT": "Mouse Left",
            "BTN_RIGHT": "Mouse Right",
            "BTN_MIDDLE": "Mouse Middle",
            "BTN_SIDE": "Mouse Side",
            "BTN_EXTRA": "Mouse Extra",
            "BTN_FORWARD": "Mouse Forward",
            "BTN_BACK": "Mouse Back",
            "BTN_TASK": "Mouse Task",
        }
        return f"mouse:{mouse_names.get(name, name.replace('BTN_', 'Mouse '))}"

    return f"keyboard:{name}"

def pretty_key(key_id):
    if not key_id:
        return "Not set"

    kind, _, name = key_id.partition(":")

    if kind == "mouse":
        labels = {
            "BTN_LEFT": "Mouse Left",
            "BTN_MIDDLE": "Mouse Middle",
            "BTN_RIGHT": "Mouse Right",
            "BTN_SIDE": "Mouse Side",
            "BTN_EXTRA": "Mouse Extra",
        }
        return labels.get(name, f"Mouse {name}")

    aliases = {
        "KEY_ESC": "Esc",
        "KEY_ENTER": "Enter",
        "KEY_SPACE": "Space",
        "KEY_TAB": "Tab",
        "KEY_BACKSPACE": "Backspace",
        "KEY_LEFT": "Left",
        "KEY_RIGHT": "Right",
        "KEY_UP": "Up",
        "KEY_DOWN": "Down",
        "KEY_LEFTCTRL": "Left Ctrl",
        "KEY_RIGHTCTRL": "Right Ctrl",
        "KEY_LEFTSHIFT": "Left Shift",
        "KEY_RIGHTSHIFT": "Right Shift",
        "KEY_LEFTALT": "Left Alt",
        "KEY_RIGHTALT": "Right Alt",
    }

    if name in aliases:
        return aliases[name]

    return name.removeprefix("KEY_")


class KeyCaptureWindow(Adw.Window):

    def tr_text(self, en, tr):
        return tr if self.language == "tr" else en

    def __init__(self, parent, callback, language):
        self._ignore_left_until = time.monotonic() + 0.35
        title = "Kapatma tuşu" if language == "tr" else "Stop key"

        super().__init__(
            transient_for=parent,
            modal=True,
            title=title
        )

        self.callback = callback
        self.devices = []
        self.finished = False
        self.language = language

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14
        )

        box.set_margin_top(25)
        box.set_margin_bottom(25)
        box.set_margin_start(25)
        box.set_margin_end(25)

        title_label = Gtk.Label(
            label="Bir klavye veya mouse tuşuna bas"
            if language == "tr"
            else "Press a keyboard or mouse button"
        )
        title_label.add_css_class("title-2")
        box.append(title_label)

        self.status = Gtk.Label()
        self.status.set_wrap(True)
        box.append(self.status)

        cancel = Gtk.Button(
            label="İptal" if language == "tr" else "Cancel"
        )
        cancel.connect("clicked", lambda *_: self.close())
        box.append(cancel)

        self.set_content(box)

        self.open_all_input_devices()

        if not self.devices:
            self.status.set_text(
                self.tr_text(
                    "No input devices are available for key capture.",
                    "Tuş yakalama için giriş cihazı bulunamadı."
                )
            )
        else:
            self.status.set_text(
                self.tr_text(
                    "Input devices are ready for key capture. Press a keyboard or mouse button.",
                    "Tuş yakalama için giriş cihazları hazır. Klavye veya mouse tuşuna bas."
                )
            )

        GLib.timeout_add(10, self.poll_keys)

    def open_all_input_devices(self):
        if list_devices is None or InputDevice is None:
            return

        for path in list_devices():
            try:
                device = InputDevice(path)

                if ecodes.EV_KEY not in device.capabilities():
                    device.close()
                    continue

                # InputDevice already uses a non-blocking fd.
                # Do not grab the device, so normal keyboard/mouse input remains intact.
                self.devices.append(device)

            except (PermissionError, OSError):
                continue
            except Exception:
                continue

    def poll_keys(self):
        if self.finished:
            return False

        for device in self.devices:
            try:
                while True:
                    try:
                        events = list(device.read())
                    except BlockingIOError:
                        break

                    if not events:
                        break

                    for event in events:
                        # The left click that opened the GTK capture
                        # window also reaches /dev/input/event*. Ignore only
                        # that initial click for a short period.
                        if (
                            event.type == ecodes.EV_KEY
                            and event.code == ecodes.BTN_LEFT
                            and event.value == 1
                            and time.monotonic() < self._ignore_left_until
                        ):
                            continue

                        if event.type != ecodes.EV_KEY:
                            continue

                        # 1 = key/button press
                        if event.value != 1:
                            continue

                        # Linux input uses fixed BTN_* codes. Handle the
                        # mouse buttons directly before doing name lookup.
                        mouse_codes = {
                            ecodes.BTN_LEFT: "BTN_LEFT",
                            ecodes.BTN_RIGHT: "BTN_RIGHT",
                            ecodes.BTN_MIDDLE: "BTN_MIDDLE",
                            ecodes.BTN_SIDE: "BTN_SIDE",
                            ecodes.BTN_EXTRA: "BTN_EXTRA",
                        }

                        if hasattr(ecodes, "BTN_FORWARD"):
                            mouse_codes[ecodes.BTN_FORWARD] = "BTN_FORWARD"
                        if hasattr(ecodes, "BTN_BACK"):
                            mouse_codes[ecodes.BTN_BACK] = "BTN_BACK"
                        if hasattr(ecodes, "BTN_TASK"):
                            mouse_codes[ecodes.BTN_TASK] = "BTN_TASK"

                        if event.code in mouse_codes:
                            key_id = f"mouse:{mouse_codes[event.code]}"
                        else:
                            key_id = key_id_from_event(event.code)

                        # Fallback for evdev versions where BTN_* is not
                        # present in ecodes.KEY/BTN dictionaries.
                        if not key_id and event.code in (
                            ecodes.BTN_LEFT,
                            ecodes.BTN_RIGHT,
                            ecodes.BTN_MIDDLE,
                            ecodes.BTN_SIDE,
                            ecodes.BTN_EXTRA,
                            getattr(ecodes, "BTN_FORWARD", -1),
                            getattr(ecodes, "BTN_BACK", -1),
                            getattr(ecodes, "BTN_TASK", -1),
                        ):
                            fallback_names = {
                                ecodes.BTN_LEFT: "Mouse Left",
                                ecodes.BTN_RIGHT: "Mouse Right",
                                ecodes.BTN_MIDDLE: "Mouse Middle",
                                ecodes.BTN_SIDE: "Mouse Side",
                                ecodes.BTN_EXTRA: "Mouse Extra",
                            }

                            if hasattr(ecodes, "BTN_FORWARD"):
                                fallback_names[ecodes.BTN_FORWARD] = "Mouse Forward"
                            if hasattr(ecodes, "BTN_BACK"):
                                fallback_names[ecodes.BTN_BACK] = "Mouse Back"
                            if hasattr(ecodes, "BTN_TASK"):
                                fallback_names[ecodes.BTN_TASK] = "Mouse Task"

                            key_id = f"mouse:{fallback_names[event.code]}"

                        if not key_id:
                            continue

                        self.finished = True
                        self.callback(key_id)
                        self.close()

                        return False

            except BlockingIOError:
                pass
            except OSError:
                pass
            except Exception:
                pass

        return True

    def close(self):
        for device in self.devices:
            try:
                device.close()
            except Exception:
                pass

        self.devices.clear()
        super().close()


class ScreenRecorderUI(Adw.Application):
    def tr_text(self, en, tr):
        return tr if self.config.get("language", "en") == "tr" else en



    def __init__(self):
        super().__init__(
            application_id="com.local.ScreenRecorder"
        )

        self.config = load_config()
        self.stop_dialog_open = False

        self.connect(
            "activate",
            self.on_activate
        )

    def on_activate(self, app):
        self.window = Adw.ApplicationWindow(
            application=app,
            title="Screen Recorder"
        )

        self.window.set_default_size(620, 500)

        self.setup_theme()

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()

        # ------------------------------
        # Language selector - top right
        # ------------------------------

        language_model = Gtk.StringList.new([
            "English",
            "Türkçe"
        ])

        self.language_dropdown = Gtk.DropDown(
            model=language_model
        )

        self.language_dropdown.set_selected(
            1 if self.config.get("language") == "tr" else 0
        )

        self.language_dropdown.connect(
            "notify::selected",
            self.language_changed
        )

        header.pack_end(self.language_dropdown)

        # ------------------------------
        # Dark mode switch
        # ------------------------------

        self.dark_switch = Gtk.Switch(
            active=self.config.get("dark_mode", True)
        )

        self.dark_switch.set_tooltip_text(
            "Dark mode"
        )

        self.dark_switch.connect(
            "notify::active",
            self.dark_mode_changed
        )

        header.pack_end(self.dark_switch)

        toolbar.add_top_bar(header)

        self.content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18
        )

        self.content.set_margin_top(25)
        self.content.set_margin_bottom(25)
        self.content.set_margin_start(25)
        self.content.set_margin_end(25)

        toolbar.set_content(self.content)
        self.window.set_content(toolbar)

        self.build_content()

        self.window.present()
        GLib.timeout_add(150, self.poll_stop_key_request)

    def poll_stop_key_request(self):
        try:
            if STOP_REQUEST_FILE.exists():
                # Always consume the request. If a stop-selection dialog is
                # already open, discard duplicate requests generated by the
                # other recording listeners for the same physical key press.
                STOP_REQUEST_FILE.unlink()

                if not self.stop_dialog_open:
                    self.stop_recording()
        except Exception:
            pass
        return True

    def setup_theme(self):
        style_manager = Adw.StyleManager.get_default()

        style_manager.set_color_scheme(
            Adw.ColorScheme.FORCE_DARK
            if self.config.get("dark_mode", True)
            else Adw.ColorScheme.FORCE_LIGHT
        )

    def language_changed(self, dropdown, _):
        selected = dropdown.get_selected()

        self.config["language"] = (
            "tr" if selected == 1 else "en"
        )

        save_config(self.config)

        self.build_content()

    def dark_mode_changed(self, switch, _):
        self.config["dark_mode"] = switch.get_active()
        save_config(self.config)
        self.setup_theme()

    def clear_content(self):
        child = self.content.get_first_child()

        while child:
            next_child = child.get_next_sibling()
            self.content.remove(child)
            child = next_child

    def build_content(self):
        self.clear_content()

        tr = self.config.get("language") == "tr"

        title = Gtk.Label(
            label="Ekran Kaydedici"
            if tr else
            "Screen Recorder"
        )
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        self.content.append(title)

        subtitle = Gtk.Label(
            label=(
                "Kayıt klasörünü ve kapatma tuşunu ayarla."
                if tr else
                "Configure the recording folder and stop key."
            )
        )
        subtitle.set_wrap(True)
        subtitle.set_halign(Gtk.Align.START)
        self.content.append(subtitle)

        # ------------------------------
        # Folder
        # ------------------------------

        folder_title = Gtk.Label(
            label="Kayıt yeri" if tr else "Recording location"
        )
        folder_title.add_css_class("heading")
        folder_title.set_halign(Gtk.Align.START)
        self.content.append(folder_title)

        folder_row = Gtk.Box(spacing=8)

        self.folder_entry = Gtk.Entry()
        self.folder_entry.set_hexpand(True)
        self.folder_entry.set_text(
            self.config.get(
                "output_dir",
                str(Path.home() / "Resimler")
            )
        )

        folder_row.append(self.folder_entry)

        browse = Gtk.Button(
            label="Gözat" if tr else "Browse"
        )
        browse.connect(
            "clicked",
            self.choose_folder
        )

        folder_row.append(browse)
        self.content.append(folder_row)

        # ------------------------------
        # Stop key
        # ------------------------------

        key_title = Gtk.Label(
            label="Kapatma tuşu" if tr else "Stop key"
        )
        key_title.add_css_class("heading")
        key_title.set_halign(Gtk.Align.START)
        self.content.append(key_title)

        key_row = Gtk.Box(spacing=8)

        self.key_entry = Gtk.Entry()
        self.key_entry.set_editable(False)
        self.key_entry.set_hexpand(True)
        self.key_entry.set_text(
            pretty_key(
                self.config.get("stop_key", "")
            )
        )

        key_row.append(self.key_entry)

        capture = Gtk.Button(
            label="Tuşu yakala" if tr else "Capture key"
        )
        capture.connect(
            "clicked",
            self.capture_key
        )
        key_row.append(capture)

        clear = Gtk.Button(
            label="Temizle" if tr else "Clear"
        )
        clear.connect(
            "clicked",
            self.clear_key
        )
        key_row.append(clear)

        self.content.append(key_row)

        hint = Gtk.Label(
            label=(
                "Herhangi bir klavye tuşu veya mouse butonu seçebilirsin."
                if tr else
                "You can select any keyboard key or mouse button."
            )
        )
        hint.add_css_class("dim-label")
        hint.set_halign(Gtk.Align.START)
        hint.set_wrap(True)
        self.content.append(hint)

        # ------------------------------
        # Save settings
        # ------------------------------

        save = Gtk.Button(
            label="Ayarları kaydet" if tr else "Save settings"
        )
        save.add_css_class("suggested-action")
        save.set_size_request(-1, 45)
        save.connect("clicked", self.save_settings)
        self.content.append(save)

        # ------------------------------
        # Starting delay
        # ------------------------------

        delay_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )

        delay_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )

        delay_label = Gtk.Label(
            label=self.tr_text("Starting delay", "Başlama gecikmesi"),
            xalign=0
        )
        delay_label.set_hexpand(True)

        self.starting_delay_switch = Gtk.Switch()
        self.starting_delay_switch.set_active(
            bool(self.config.get("starting_delay_enabled", False))
        )
        self.starting_delay_switch.connect(
            "notify::active",
            self.on_starting_delay_switch_changed
        )

        delay_row.append(delay_label)
        delay_row.append(self.starting_delay_switch)
        delay_box.append(delay_row)

        delay_value_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8
        )

        self.delay_value_label = Gtk.Label(
            label="",
            xalign=0
        )
        self.delay_value_label.set_hexpand(True)

        self.delay_spin = Gtk.SpinButton.new_with_range(0, 60, 1)
        self.delay_spin.set_value(
            float(self.config.get("starting_delay", 5))
        )
        self.delay_spin.set_numeric(True)
        self.delay_spin.connect(
            "value-changed",
            self.on_starting_delay_changed
        )

        delay_value_row.append(self.delay_value_label)
        delay_value_row.append(self.delay_spin)
        delay_box.append(delay_value_row)

        self.starting_delay_box = delay_box
        self.update_starting_delay_visuals()
        self.content.append(delay_box)

        # ------------------------------
        # Start / Stop buttons
        # ------------------------------

        action_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )
        action_box.set_homogeneous(True)

        self.start_button = Gtk.Button(
            label="Kaydı başlat" if tr else "Start recording"
        )
        self.start_button.set_size_request(-1, 50)
        self.start_button.connect("clicked", self.start_recording)

        self.stop_button = Gtk.Button(
            label="Kaydı durdur" if tr else "Stop recording"
        )
        self.stop_button.set_size_request(-1, 50)
        self.stop_button.connect("clicked", self.stop_recording)

        action_box.append(self.start_button)
        action_box.append(self.stop_button)
        self.content.append(action_box)

        # ------------------------------
        # Input status
        # ------------------------------

        devices_ready = self.input_devices_available()

        if tr:
            status_text = (
                "Tuş yakalama için giriş cihazları hazır. "
                "Klavye veya mouse tuşuna bas."
                if devices_ready else
                "Tuş yakalama için giriş cihazları kullanılamıyor. "
                "'Tuşu yakala' ile tekrar deneyebilirsin."
            )
        else:
            status_text = (
                "Input devices are ready for key capture. "
                "Press a keyboard or mouse button."
                if devices_ready else
                "Input devices are not available for key capture. "
                "Try 'Capture key' again."
            )

        input_status = Gtk.Label(label=status_text)

        input_status.add_css_class(
            "dim-label"
        )

        input_status.set_wrap(True)
        input_status.set_halign(Gtk.Align.START)

        self.content.append(input_status)

    def input_devices_available(self):
        if list_devices is None or InputDevice is None:
            return False

        for path in list_devices():
            try:
                device = InputDevice(path)

                if ecodes.EV_KEY in device.capabilities():
                    device.close()
                    return True

                device.close()

            except Exception:
                pass

        return False

    def choose_folder(self, *_):
        dialog = Gtk.FileDialog()

        dialog.set_title(
            "Kayıt klasörünü seç"
        )

        dialog.select_folder(
            self.window,
            None,
            self.folder_selected
        )

    def folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)

            if folder:
                self.folder_entry.set_text(
                    folder.get_path()
                )

        except Exception:
            pass

    def capture_key(self, *_):
        dialog = KeyCaptureWindow(
            self.window,
            self.key_captured,
            self.config.get("language", "en")
        )

        dialog.present()

    def key_captured(self, key_id):
        self.config["stop_key"] = key_id

        self.key_entry.set_text(
            pretty_key(key_id)
        )

        save_config(self.config)

    def clear_key(self, *_):
        self.config["stop_key"] = ""

        self.key_entry.set_text(
            "Not set"
            if self.config.get("language") != "tr"
            else
            "Ayarlanmadı"
        )

        save_config(self.config)

    def update_starting_delay_visuals(self):
        enabled = self.starting_delay_switch.get_active()
        value = int(self.delay_spin.get_value())

        self.delay_spin.set_sensitive(enabled)

        if self.config.get("language", "en") == "tr":
            self.delay_value_label.set_text(
                f"Başlama gecikmesi: {value} sn"
            )
        else:
            self.delay_value_label.set_text(
                f"Starting delay: {value} sec"
            )

        self.delay_value_label.set_opacity(
            1.0 if enabled else 0.35
        )
        self.delay_spin.set_opacity(
            1.0 if enabled else 0.35
        )

    def on_starting_delay_switch_changed(self, switch, _param):
        enabled = switch.get_active()
        self.config["starting_delay_enabled"] = enabled
        self.update_starting_delay_visuals()

    def on_starting_delay_changed(self, spin):
        value = int(spin.get_value())
        self.config["starting_delay"] = value

        if self.config.get("language", "en") == "tr":
            self.delay_value_label.set_text(f"Başlama gecikmesi: {value} sn")
        else:
            self.delay_value_label.set_text(f"Starting delay: {value} sec")

    def save_settings(self, *_):
        self.config["starting_delay_enabled"] = self.starting_delay_switch.get_active()
        self.config["starting_delay"] = int(self.delay_spin.get_value())
        output = self.folder_entry.get_text().strip()

        if not output:
            output = str(Path.home() / "Resimler")

        output = os.path.expanduser(output)

        try:
            Path(output).mkdir(
                parents=True,
                exist_ok=True
            )
        except Exception as e:
            self.notify(
                f"Folder error: {e}"
            )
            return

        self.config["output_dir"] = output

        save_config(self.config)

        self.install_script()

        self.notify(
            "Ayarlar kaydedildi"
            if self.config.get("language") == "tr"
            else
            "Settings saved"
        )

    def install_script(self):
        source = Path(__file__).with_name(
            "screenrec.sh"
        )

        if not source.exists():
            return

        CONFIG_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        try:
            SCRIPT_FILE.write_text(
                source.read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8"
            )

            SCRIPT_FILE.chmod(0o755)

        except Exception as e:
            self.notify(
                f"Script error: {e}"
            )

    def _persist_current_settings(self):
        self.config["starting_delay_enabled"] = (
            self.starting_delay_switch.get_active()
        )
        self.config["starting_delay"] = int(
            self.delay_spin.get_value()
        )

        output = self.folder_entry.get_text().strip()
        if not output:
            output = str(Path.home() / "Resimler")

        output = os.path.expanduser(output)
        Path(output).mkdir(parents=True, exist_ok=True)
        self.config["output_dir"] = output
        save_config(self.config)
        self.install_script()

    def start_recording(self, *_):
        try:
            self._persist_current_settings()
        except Exception as e:
            self.notify(
                f"Klasör hatası: {e}"
                if self.config.get("language") == "tr"
                else f"Folder error: {e}"
            )
            return

        active = self.get_active_recordings()

        if active:
            tr = self.config.get("language") == "tr"
            self.show_start_already_running_dialog(tr)
            return

        if not SCRIPT_FILE.exists():
            self.notify(
                "screenrec.sh bulunamadı"
                if self.config.get("language") == "tr"
                else "screenrec.sh not found"
            )
            return

        subprocess.Popen(
            [str(SCRIPT_FILE), "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def stop_recording(self, *_):
        active = self.get_active_recordings()
        tr = self.config.get("language") == "tr"

        if not active:
            self.notify(
                "Devam eden bir ekran kaydı yok."
                if tr
                else
                "There is no active screen recording."
            )
            return

        if len(active) == 1:
            self.stop_selected_recording(active[0])
            return

        if self.stop_dialog_open:
            return

        self.show_stop_recording_dialog(active, tr)

    def get_active_recordings(self):
        meta_dir = Path.home() / ".cache" / "screenrec" / "recordings"
        meta_dir.mkdir(parents=True, exist_ok=True)

        recordings = []

        for meta in meta_dir.glob("*.meta"):
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))

                # A countdown is considered an active recording start.
                status = data.get("status", "recording")
                check_pid = int(
                    data.get("launcher_pid")
                    if status == "starting"
                    else data.get("recorder_pid", data.get("pid"))
                )

                os.kill(check_pid, 0)

                data["_meta"] = str(meta)
                recordings.append(data)

            except (
                ProcessLookupError,
                ValueError,
                KeyError,
                OSError,
                json.JSONDecodeError,
                TypeError,
            ):
                try:
                    meta.unlink()
                except Exception:
                    pass

        recordings.sort(
            key=lambda x: x.get("started_at", ""),
            reverse=True
        )
        return recordings

    def stop_selected_recording(self, recording):
        if not SCRIPT_FILE.exists():
            return

        status = recording.get("status", "recording")

        if status == "starting":
            target = str(recording.get("launcher_pid", ""))
            command = [str(SCRIPT_FILE), "cancel-start", target]
        else:
            target = str(
                recording.get(
                    "recorder_pid",
                    recording.get("pid", "")
                )
            )
            command = [str(SCRIPT_FILE), "stop", target]

        if target.isdigit():
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    def show_start_already_running_dialog(self, tr):
        dialog = Gtk.Window(
            title="Ekran kaydı zaten çalışıyor"
            if tr
            else
            "Screen recording is already running",
            transient_for=self.window,
            modal=True
        )
        dialog.set_default_size(420, 180)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16
        )
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        label = Gtk.Label(
            label=(
                "Halihazırda çalışan bir ekran kaydı var.\n"
                "Yenisini başlatmak ister misin?"
                if tr
                else
                "There is already an active screen recording.\n"
                "Do you want to start a new one?"
            )
        )
        label.set_wrap(True)
        label.set_halign(Gtk.Align.START)
        box.append(label)

        buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )
        buttons.set_halign(Gtk.Align.END)

        cancel = Gtk.Button(
            label="Hayır" if tr else "No"
        )
        yes = Gtk.Button(
            label="Evet" if tr else "Yes"
        )
        yes.add_css_class("suggested-action")

        cancel.connect("clicked", lambda *_: dialog.close())

        def confirm_start(*_):
            dialog.close()
            subprocess.Popen(
                [str(SCRIPT_FILE), "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        yes.connect("clicked", confirm_start)

        buttons.append(cancel)
        buttons.append(yes)
        box.append(buttons)

        dialog.set_child(box)
        dialog.present()

    def show_stop_recording_dialog(self, recordings, tr):
        if self.stop_dialog_open:
            return

        self.stop_dialog_open = True

        dialog = Gtk.Window(
            title="Ekran kaydını durdur"
            if tr
            else
            "Stop screen recording",
            transient_for=self.window,
            modal=True
        )
        dialog.set_default_size(560, 360)

        outer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14
        )
        outer.set_margin_top(22)
        outer.set_margin_bottom(22)
        outer.set_margin_start(22)
        outer.set_margin_end(22)

        title = Gtk.Label(
            label=(
                "Durdurmak istediğin ekran kaydını seç:"
                if tr
                else
                "Select the screen recording you want to stop:"
            )
        )
        title.set_halign(Gtk.Align.START)
        title.add_css_class("heading")
        outer.append(title)

        group = None
        buttons = []

        for index, rec in enumerate(recordings):
            filename = Path(rec.get("file", "")).name
            pid = rec.get("pid", "?")
            started = rec.get("started_at", "")

            label = f"{filename}  (PID {pid})"
            if started:
                label += f" — {started}"

            radio = Gtk.CheckButton(label=label)

            if group is not None:
                radio.set_group(group)
            else:
                group = radio

            if index == 0:
                radio.set_active(True)

            buttons.append((radio, rec))
            outer.append(radio)

        action_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )
        action_box.set_halign(Gtk.Align.END)

        cancel = Gtk.Button(
            label="İptal" if tr else "Cancel"
        )
        confirm = Gtk.Button(
            label="Tamam" if tr else "OK"
        )
        confirm.add_css_class("suggested-action")

        def close_stop_dialog(*_):
            self.stop_dialog_open = False
            try:
                if STOP_REQUEST_FILE.exists():
                    STOP_REQUEST_FILE.unlink()
            except Exception:
                pass
            dialog.close()

        cancel.connect("clicked", close_stop_dialog)

        def confirm_stop(*_):
            selected = None
            for radio, rec in buttons:
                if radio.get_active():
                    selected = rec
                    break

            if selected:
                self.stop_selected_recording(selected)

            self.stop_dialog_open = False
            try:
                if STOP_REQUEST_FILE.exists():
                    STOP_REQUEST_FILE.unlink()
            except Exception:
                pass
            dialog.close()

        confirm.connect("clicked", confirm_stop)

        action_box.append(cancel)
        action_box.append(confirm)
        outer.append(action_box)

        dialog.set_child(outer)

        def on_dialog_close(_dialog):
            self.stop_dialog_open = False
            try:
                if STOP_REQUEST_FILE.exists():
                    STOP_REQUEST_FILE.unlink()
            except Exception:
                pass

        dialog.connect("close-request", on_dialog_close)
        dialog.present()


    def notify(self, message):
        try:
            subprocess.Popen(
                [
                    "notify-send",
                    "Screen Recorder",
                    message
                ]
            )
        except Exception:
            pass


app = ScreenRecorderUI()
app.run()
