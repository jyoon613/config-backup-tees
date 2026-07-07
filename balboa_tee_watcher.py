"""
Balboa Park Tee Time Watcher (GitHub Actions edition)
------------------------------------------------------
Watches Balboa Park Golf Course's public tee-sheet for openings that match
your criteria (day/time window/players), and texts you the instant a match
appears — with a direct link so YOU click "book" yourself.

This script only reads publicly available availability data (the same data
your browser loads when you visit the booking page). It does not log in,
does not store any payment info, and does not submit a reservation for you.

This version runs ONCE per invocation (not in a loop) — GitHub Actions'
schedule handles the "check every N minutes" part, since each run happens
on GitHub's servers, not your computer. See SETUP.md in this repo for the
full walkthrough (GitHub account, secrets, workflow file).

Requires your foreUP account email/password (to view the tee sheet) set as
environment variables FOREUP_EMAIL / FOREUP_PASSWORD — never hardcode
these in the file itself. This only logs in to view availability; it never
submits a reservation or touches any payment info.
"""

import os
import time
import smtplib
import requests
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# ── CONFIG: edit these ──────────────────────────────────────────────
SCHEDULE_ID = "1470"
BOOKING_CLASS_ID = "929"

FACILITY_BOOKING_URL = "https://foreupsoftware.com/index.php/booking/19348/1470"
LOGIN_URL = "https://foreupsoftware.com/index.php/api/booking/users/login"
API_URL = "https://foreupsoftware.com/index.php/api/booking/times"

FOREUP_EMAIL = os.environ.get("FOREUP_EMAIL")
FOREUP_PASSWORD = os.environ.get("FOREUP_PASSWORD")

TARGET_WEEKDAY = 3          # Monday=0 ... Thursday=3 ... Sunday=6
TIME_WINDOW_START = "06:00"  # 24hr "HH:MM", early morning
TIME_WINDOW_END = "11:00"
PLAYERS = 1
DAYS_AHEAD_TO_CHECK = 14      # how far out to look each pass

# Your AT&T number -> AT&T's email-to-SMS gateway
PHONE_SMS_GATEWAY = "6307072366@txt.att.net"

SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

STATE_FILE = "seen.txt"  # lives in the repo; the workflow commits updates to it
# ─────────────────────────────────────────────────────────────────────


def load_seen():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())


def mark_seen(key):
    with open(STATE_FILE, "a") as f:
        f.write(key + "\n")


def send_text(message):
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        print("[!] SMTP_EMAIL / SMTP_APP_PASSWORD not set — printing instead of texting:")
        print(message)
        return
    msg = MIMEText(message)
    msg["From"] = SMTP_EMAIL
    msg["To"] = PHONE_SMS_GATEWAY
    msg["Subject"] = ""  # keep SMS gateways happy with no subject noise
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
            server.sendmail(SMTP_EMAIL, [PHONE_SMS_GATEWAY], msg.as_string())
        print(f"[✓] Text sent: {message}")
    except Exception as e:
        print(f"[!] Failed to send text: {e}")


def login():
    """Log in with your foreUP account and return an authenticated session."""
    session = requests.Session()

    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }

    # First load the booking page normally so the server hands us a session
    # cookie (PHPSESSID), same as a real browser visiting the page would.
    try:
        session.get(FACILITY_BOOKING_URL, headers=browser_headers, timeout=15)
    except Exception as e:
        print(f"[!] Could not load booking page before login: {e}")
        return None

    login_headers = dict(browser_headers)
    login_headers.update({
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "X-FU-Golfer-Location": "foreup",
        "Origin": "https://foreupsoftware.com",
        "Referer": FACILITY_BOOKING_URL,
    })

    payload = {
        "username": FOREUP_EMAIL,
        "password": FOREUP_PASSWORD,
        "api_key": "",
        "booking_class_id": "",
        "course_id": "19348",
    }
    try:
        resp = session.post(LOGIN_URL, data=payload, headers=login_headers, timeout=15)
        if resp.status_code != 200:
            print(f"[!] Login response status: {resp.status_code}")
            print(f"[!] Login response body: {resp.text[:1000]}")
        resp.raise_for_status()
        return session
    except Exception as e:
        print(f"[!] Login failed: {e}")
        return None


def check_date(session, date_str):
    """Query foreUP's availability API for a single date (MM-DD-YYYY), authenticated."""
    params = {
        "time": "all",
        "date": date_str,
        "holes": "all",
        "players": PLAYERS,
        "booking_class": BOOKING_CLASS_ID,
        "schedule_id": SCHEDULE_ID,
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = session.get(API_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[!] Error checking {date_str}: {e}")
        return []


def in_time_window(time_str):
    """time_str like '7:00 AM' -> check against TIME_WINDOW_START/END."""
    try:
        t = datetime.strptime(time_str.strip(), "%I:%M %p").time()
        start = datetime.strptime(TIME_WINDOW_START, "%H:%M").time()
        end = datetime.strptime(TIME_WINDOW_END, "%H:%M").time()
        return start <= t <= end
    except Exception:
        return False


def next_target_weekday_dates(count=3):
    """Return the next `count` upcoming dates matching TARGET_WEEKDAY, within DAYS_AHEAD_TO_CHECK."""
    dates = []
    today = datetime.now()
    for i in range(DAYS_AHEAD_TO_CHECK):
        d = today + timedelta(days=i)
        if d.weekday() == TARGET_WEEKDAY:
            dates.append(d)
        if len(dates) >= count:
            break
    return dates


def run_once(seen, session):
    for d in next_target_weekday_dates():
        date_str = d.strftime("%m-%d-%Y")
        slots = check_date(session, date_str)
        if not isinstance(slots, list):
            continue
        for slot in slots:
            slot_time = slot.get("time") or slot.get("teetime") or ""
            available = slot.get("available_spots", slot.get("spots", 0))
            if not slot_time or not in_time_window(slot_time):
                continue
            if available and int(available) >= PLAYERS:
                key = f"{date_str}_{slot_time}"
                if key in seen:
                    continue
                message = (
                    f"Balboa Park opening: {d.strftime('%a %m/%d')} at {slot_time} "
                    f"({available} spot(s)). Book now: {FACILITY_BOOKING_URL}"
                )
                send_text(message)
                mark_seen(key)
                seen.add(key)


def main():
    if SCHEDULE_ID == "REPLACE_ME" or BOOKING_CLASS_ID == "REPLACE_ME":
        print("!! You still need to set SCHEDULE_ID and BOOKING_CLASS_ID at the top of this file.")
        print("!! See SETUP.md for how to find them.")
        return
    if not FOREUP_EMAIL or not FOREUP_PASSWORD:
        print("!! FOREUP_EMAIL / FOREUP_PASSWORD environment variables are not set.")
        return

    print(f"Checking Balboa Park for Thursday tee times, {TIME_WINDOW_START}-{TIME_WINDOW_END}, "
          f"{PLAYERS} player(s). (single pass — GitHub Actions schedules the repeats)")

    session = login()
    if session is None:
        print("!!
