import cv2
import os
import csv
import time
import threading
import win32com.client
from datetime import datetime
from ultralytics import YOLO

# ==========================================
# FOLDERS & LOGGING
# ==========================================

os.makedirs("violations", exist_ok=True)

if not os.path.exists("intrusion_log.csv"):
    with open("intrusion_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Time", "Zone", "Event"])

# ==========================================
# WINDOWS VOICE
# ==========================================

speaker = win32com.client.Dispatch("SAPI.SpVoice")
speaker.Volume = 100
speaker.Rate = 0

import win32com.client

speaker = win32com.client.Dispatch("SAPI.SpVoice")
speaker.Volume = 100
speaker.Speak("Warning. Restricted area entered.")

warning_active = False

def warning_loop():
    global warning_active

    local_speaker = win32com.client.Dispatch("SAPI.SpVoice")
    local_speaker.Volume = 100
    local_speaker.Rate = 0

    while warning_active:
        local_speaker.Speak(
            "Warning. you are not allowed here, get out from here."
        )
        time.sleep(2)

# ==========================================
# YOLO
# ==========================================

model = YOLO("yolov8n.pt")

# ==========================================
# CAMERA
# ==========================================

cap = cv2.VideoCapture(0)

window = "AI INDUSTRIAL SAFETY SYSTEM"

cv2.namedWindow(window, cv2.WINDOW_NORMAL)

cv2.setWindowProperty(
    window,
    cv2.WND_PROP_FULLSCREEN,
    cv2.WINDOW_FULLSCREEN
)

# ==========================================
# ZONES
# ==========================================

zones = [

    {
        "name": "CNC MACHINE",
        "x1": 50,
        "y1": 100,
        "x2": 300,
        "y2": 300
    },

    {
        "name": "CRANE WORKING ZONE",
        "x1": 350,
        "y1": 100,
        "x2": 650,
        "y2": 300
    }

]

selected_zone = None
mode = None

# ==========================================
# COUNTERS
# ==========================================

intrusion_count = 0
already_inside = False

# ==========================================
# MOUSE
# ==========================================

def mouse_event(event, x, y, flags, param):

    global selected_zone
    global mode

    if event == cv2.EVENT_LBUTTONDOWN:

        for i, z in enumerate(zones):

            # resize handle

            if (
                abs(x - z["x2"]) < 15
                and
                abs(y - z["y2"]) < 15
            ):
                selected_zone = i
                mode = "resize"
                return

            # move zone

            if (
                z["x1"] <= x <= z["x2"]
                and
                z["y1"] <= y <= z["y2"]
            ):

                selected_zone = i
                mode = "move"

                z["offset_x"] = x - z["x1"]
                z["offset_y"] = y - z["y1"]

                return

    elif event == cv2.EVENT_MOUSEMOVE:

        if selected_zone is None:
            return

        z = zones[selected_zone]

        if mode == "move":

            width = z["x2"] - z["x1"]
            height = z["y2"] - z["y1"]

            z["x1"] = x - z["offset_x"]
            z["y1"] = y - z["offset_y"]

            z["x2"] = z["x1"] + width
            z["y2"] = z["y1"] + height

        elif mode == "resize":

            z["x2"] = max(z["x1"] + 60, x)
            z["y2"] = max(z["y1"] + 60, y)

    elif event == cv2.EVENT_LBUTTONUP:

        selected_zone = None
        mode = None

cv2.setMouseCallback(window, mouse_event)

# ==========================================
# MAIN LOOP
# ==========================================

while True:

    ret, frame = cap.read()

    if not ret:
        break

    frame = cv2.flip(frame, 1)

    danger = False
    active_zone = ""

    # ==========================================
    # STABLE HUMAN TRACKING
    # ==========================================

    results = model.track(
        frame,
        persist=True,
        classes=[0],
        verbose=False
    )

    for result in results:

        if result.boxes is None:
            continue

        for box in result.boxes:

            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0]
            )

            # HUMAN BOX

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            cv2.circle(
                frame,
                (cx, cy),
                4,
                (0, 255, 0),
                -1
            )

            cv2.putText(
                frame,
                "HUMAN",
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1
            )

            # ==================================
            # OVERLAP DETECTION
            # ==================================

            for z in zones:

                overlap_x = max(
                    0,
                    min(x2, z["x2"]) - max(x1, z["x1"])
                )

                overlap_y = max(
                    0,
                    min(y2, z["y2"]) - max(y1, z["y1"])
                )

                if overlap_x * overlap_y > 0:

                    danger = True
                    active_zone = z["name"]

    # ==========================================
    # WARNING ACTIONS
    # ==========================================

    if danger:

        if not warning_active:

            warning_active = True

            threading.Thread(
                target=warning_loop,
                daemon=True
            ).start()

        if not already_inside:

            intrusion_count += 1

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            img_name = (
                f"violations/{timestamp}.jpg"
            )

            cv2.imwrite(
                img_name,
                frame
            )

            with open(
                "intrusion_log.csv",
                "a",
                newline=""
            ) as f:

                writer = csv.writer(f)

                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d"),
                    datetime.now().strftime("%H:%M:%S"),
                    active_zone,
                    "Intrusion"
                ])

        already_inside = True

    else:

        warning_active = False
        already_inside = False

    # ==========================================
    # DRAW ZONES
    # ==========================================

    for z in zones:

        color = (0, 255, 0)

        if z["name"] == active_zone:
            color = (0, 0, 255)

        cv2.rectangle(
            frame,
            (z["x1"], z["y1"]),
            (z["x2"], z["y2"]),
            color,
            2
        )

        # resize handle

        cv2.rectangle(
            frame,
            (z["x2"] - 8, z["y2"] - 8),
            (z["x2"] + 8, z["y2"] + 8),
            color,
            -1
        )

        cv2.putText(
            frame,
            z["name"],
            (z["x1"], z["y1"] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            1
        )

    # ==========================================
    # WARNING BANNER
    # ==========================================

    if danger:

        screen_w = frame.shape[1]

        cv2.rectangle(
            frame,
            (0, 0),
            (screen_w, 60),
            (0, 0, 255),
            -1
        )

        cv2.putText(
            frame,
            f"WARNING : HUMAN DETECTED IN {active_zone}",
            (40, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2
        )

    # Intrusion Counter

    cv2.putText(
        frame,
        f"INTRUSIONS : {intrusion_count}",
        (20, frame.shape[0] - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2
    )

    cv2.imshow(window, frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

warning_active = False

cap.release()
cv2.destroyAllWindows()