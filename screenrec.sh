#!/bin/bash

CONFIG_DIR="$HOME/.config/screenrec"
CONFIG_FILE="$CONFIG_DIR/config.json"
CACHE_DIR="$HOME/.cache/screenrec"
RECORDINGS_DIR="$CACHE_DIR/recordings"

mkdir -p "$CONFIG_DIR" "$CACHE_DIR" "$RECORDINGS_DIR"

get_config() {
    python3 - "$CONFIG_FILE" "$1" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    value = data.get(sys.argv[2], "")
    if isinstance(value, bool):
        print("1" if value else "0")
    else:
        print(value)
except Exception:
    print("")
PY
}

LANGUAGE="$(get_config language)"
[ "$LANGUAGE" = "tr" ] || LANGUAGE="en"

if [ "$LANGUAGE" = "tr" ]; then
    MSG_STARTED="Kayıt başladı"
    MSG_STOPPED="Kayıt durduruldu"
    MSG_DELAY_TITLE="Ekran Kaydı"
else
    MSG_STARTED="Recording started"
    MSG_STOPPED="Recording stopped"
    MSG_DELAY_TITLE="Screen Recorder"
fi

OUTPUT_DIR="$(get_config output_dir)"
[ -n "$OUTPUT_DIR" ] || OUTPUT_DIR="$HOME/Resimler"
mkdir -p "$OUTPUT_DIR"

STOP_KEY="$(get_config stop_key)"
DELAY_ENABLED="$(get_config starting_delay_enabled)"
DELAY="$(get_config starting_delay)"
[ -n "$DELAY" ] || DELAY=5

# --------------------------------------------------
# LIST
# --------------------------------------------------
if [ "$1" = "list" ]; then
    for meta in "$RECORDINGS_DIR"/*.meta; do
        [ -e "$meta" ] || continue

        PID="$(python3 - "$meta" <<'PY'
import json,sys
try:
    print(json.load(open(sys.argv[1], encoding="utf-8"))["pid"])
except Exception:
    print("")
PY
)"

        if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
            cat "$meta"
            echo
        else
            rm -f "$meta"
        fi
    done
    exit 0
fi

# --------------------------------------------------
# STOP PID
# --------------------------------------------------
if [ "$1" = "stop" ]; then
    PID="$2"

    if ! [[ "$PID" =~ ^[0-9]+$ ]]; then
        exit 1
    fi

    META="$RECORDINGS_DIR/$PID.meta"

    if kill -0 "$PID" 2>/dev/null; then
        kill -INT "$PID" 2>/dev/null
    fi

    # Give wf-recorder a moment to finalize the MP4.
    for _ in {1..50}; do
        if ! kill -0 "$PID" 2>/dev/null; then
            break
        fi
        sleep 0.1
    done

    rm -f "$META"
    rm -f "$CACHE_DIR/stop-request"

    notify-send \
        "Screen Recorder" \
        "$MSG_STOPPED"

    exit 0
fi

# --------------------------------------------------
# CANCEL STARTING COUNTDOWN
# --------------------------------------------------
if [ "$1" = "cancel-start" ]; then
    LAUNCHER_PID="$2"

    if ! [[ "$LAUNCHER_PID" =~ ^[0-9]+$ ]]; then
        exit 1
    fi

    META="$RECORDINGS_DIR/start-$LAUNCHER_PID.meta"

    if kill -0 "$LAUNCHER_PID" 2>/dev/null; then
        kill -TERM "$LAUNCHER_PID" 2>/dev/null
    fi

    rm -f "$META"
    rm -f "$CACHE_DIR/stop-request"
    exit 0
fi

# --------------------------------------------------
# START
# --------------------------------------------------
if [ "$1" = "start" ]; then

    GEOM="$(slurp -o -f "%x,%y %wx%h" 2>/dev/null)" || exit 0

    FILE="$OUTPUT_DIR/screen_capture_$(date +%Y%m%d-%H%M%S).mp4"

    # Create the pending-start record BEFORE the countdown notification.
    # This makes the start button aware of the countdown immediately.
    LAUNCHER_PID=$$
    META="$RECORDINGS_DIR/start-$LAUNCHER_PID.meta"

    python3 - "$META" "$LAUNCHER_PID" "$FILE" "$DELAY" <<'PY'
import json, sys, datetime
data = {
    "status": "starting",
    "launcher_pid": int(sys.argv[2]),
    "recorder_pid": None,
    "pid": int(sys.argv[2]),
    "file": sys.argv[3],
    "delay": int(sys.argv[4]),
    "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
PY

    # Temporary stop-key listener. It starts immediately after the recording
    # entry is created, so it also works during the countdown. The listener
    # asks the GTK UI to handle the stop action instead of stopping directly.
    # This lets the UI show the selection dialog when multiple recordings
    # or countdowns are active.
    if [ -n "$STOP_KEY" ]; then
        STOP_KEY_ENV="$STOP_KEY" LAUNCHER_PID_ENV="$LAUNCHER_PID" \
        STOP_REQUEST_FILE_ENV="$CACHE_DIR/stop-request" \
        python3 - <<'PY' &
import os
import time
from pathlib import Path
from evdev import InputDevice, list_devices, ecodes

wanted = os.environ.get("STOP_KEY_ENV", "")
launcher_pid = int(os.environ["LAUNCHER_PID_ENV"])
request_file = Path(os.environ["STOP_REQUEST_FILE_ENV"])

devices = []

for path in list_devices():
    try:
        d = InputDevice(path)
        if ecodes.EV_KEY in d.capabilities():
            devices.append(d)
    except Exception:
        pass

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

try:
    while True:
        try:
            os.kill(launcher_pid, 0)
        except (ProcessLookupError, OSError):
            break
        except Exception:
            break

        # Wait until the UI consumes the previous request.
        if not request_file.exists():
            for device in devices:
                try:
                    events = list(device.read())
                except BlockingIOError:
                    continue
                except Exception:
                    continue

                for event in events:
                    if event.type != ecodes.EV_KEY or event.value != 1:
                        continue

                    if event.code in mouse_codes:
                        candidate = "mouse:" + mouse_codes[event.code]
                    else:
                        name = ecodes.KEY.get(event.code)
                        if isinstance(name, list):
                            name = name[0]
                        if not name:
                            continue
                        candidate = "keyboard:" + name

                    if candidate == wanted:
                        try:
                            request_file.parent.mkdir(parents=True, exist_ok=True)
                            fd = os.open(
                                request_file,
                                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                                0o600,
                            )
                            with os.fdopen(fd, "w") as f:
                                f.write("stop")
                        except FileExistsError:
                            pass
                        except Exception:
                            pass
                        break

        time.sleep(0.01)
finally:
    for device in devices:
        try:
            device.close()
        except Exception:
            pass
PY
    fi

    if [ "$DELAY_ENABLED" = "1" ] && [ "$DELAY" -gt 0 ]; then
        if [ "$LANGUAGE" = "tr" ]; then
            notify-send \
                "$MSG_DELAY_TITLE" \
                "Ekran kaydına $DELAY saniye"
        else
            notify-send \
                "$MSG_DELAY_TITLE" \
                "$DELAY seconds to screen recording"
        fi

        sleep "$DELAY"
    fi

    # The countdown may have been cancelled while sleeping.
    if [ ! -f "$META" ]; then
        exit 0
    fi

    wf-recorder \
        --geometry "$GEOM" \
        --file "$FILE" \
        --audio=alsa_output.pci-0000_0d_00.6.analog-stereo.monitor \
        > /dev/null 2>&1 &

    PID=$!

    # Convert the pending entry into an active recorder entry while keeping
    # the launcher PID so the UI can still identify this start.
    python3 - "$META" "$PID" "$LAUNCHER_PID" <<'PY'
import json, sys

with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)

data["status"] = "recording"
data["recorder_pid"] = int(sys.argv[2])
data["pid"] = int(sys.argv[2])
data["launcher_pid"] = int(sys.argv[3])

with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
PY

    notify-send \
        "Screen Recorder" \
        "$MSG_STARTED"

    wait "$PID" 2>/dev/null
    rm -f "$META"

    exit 0
fi

# No arguments: compatibility fallback.
if [ -f "$CACHE_DIR/legacy.pid" ]; then
    PID="$(cat "$CACHE_DIR/legacy.pid" 2>/dev/null)"
    "$0" stop "$PID"
    rm -f "$CACHE_DIR/legacy.pid"
else
    "$0" start
fi
