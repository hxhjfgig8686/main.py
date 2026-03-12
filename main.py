# main.py

import time
import requests
import sqlite3
import json
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import telebot
import threading

# =====================
# إعدادات البوت
# =====================

BOT_TOKEN = "8325061391:AAESPAfQ93gf79feMa8YgRMCOgTSHxGnu40"
CHAT_IDS = ["-1003745034804"]

REFRESH_INTERVAL = 5
DB_PATH = "bot.db"

# =====================
# إعداد لوحة iVasms
# =====================

IVASMS = {
    "login_url": "https://ivas.tempnum.qzz.io/login",
    "base_url": "https://ivas.tempnum.qzz.io",
    "sms_api": "https://ivas.tempnum.qzz.io/portal/sms/received/getsms",
    "username": "asmeralselwi103@gmail.com",
    "password": "Mohammed Saeed 123",
    "session": requests.Session(),
    "csrf": None,
    "logged": False
}

# =====================
# Telegram
# =====================

bot = telebot.TeleBot(BOT_TOKEN)

# =====================
# Database
# =====================

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        assigned_number TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS otp_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT,
        otp TEXT,
        message TEXT,
        time TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# =====================
# OTP
# =====================

def extract_otp(msg):
    code = re.findall(r"\d{4,8}", msg)
    return code[0] if code else "N/A"

# =====================
# Login iVasms
# =====================

def login():
    try:

        s = IVASMS["session"]

        r = s.get(IVASMS["login_url"])
        soup = BeautifulSoup(r.text,"html.parser")

        token = soup.find("input",{"name":"_token"})
        token = token["value"] if token else None

        data = {
            "email":IVASMS["username"],
            "password":IVASMS["password"],
            "_token":token
        }

        r = s.post(IVASMS["login_url"],data=data)

        if "login" not in r.url:

            meta = BeautifulSoup(r.text,"html.parser").find("meta",{"name":"csrf-token"})
            if meta:
                IVASMS["csrf"] = meta["content"]

            IVASMS["logged"] = True
            print("Login success")
            return True

    except Exception as e:
        print("Login error",e)

    return False

# =====================
# Fetch SMS
# =====================

def fetch_sms():

    if not IVASMS["logged"]:
        if not login():
            return []

    try:

        s = IVASMS["session"]

        headers = {
            "X-Requested-With":"XMLHttpRequest"
        }

        today = datetime.utcnow()
        start = (today - timedelta(days=1)).strftime("%m/%d/%Y")
        end = today.strftime("%m/%d/%Y")

        data = {
            "from":start,
            "to":end,
            "_token":IVASMS["csrf"]
        }

        r = s.post(IVASMS["sms_api"],headers=headers,data=data)

        soup = BeautifulSoup(r.text,"html.parser")

        cards = soup.find_all("div",class_="card-body")

        messages = []

        for card in cards:

            txt = card.text.strip()

            phone = re.findall(r"\+\d+",txt)
            phone = phone[0] if phone else "000"

            msg = txt

            messages.append({
                "number":phone,
                "text":msg
            })

        return messages

    except Exception as e:

        print("fetch error",e)
        IVASMS["logged"]=False
        return []

# =====================
# Send Telegram
# =====================

def send_group(text,otp):

    keyboard = {
        "inline_keyboard":[
            [
                {
                    "text":f"Code: {otp}",
                    "callback_data":f"copy_{otp}"
                }
            ]
        ]
    }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    for chat in CHAT_IDS:

        requests.post(url,data={
            "chat_id":chat,
            "text":text,
            "reply_markup":json.dumps(keyboard)
        })

# =====================
# Loop
# =====================

sent=set()

def main_loop():

    while True:

        messages = fetch_sms()

        for m in messages:

            uid = m["number"]+m["text"][:20]

            if uid in sent:
                continue

            sent.add(uid)

            otp = extract_otp(m["text"])

            txt = f"""
OTP RECEIVED

Number : {m['number']}
Code : {otp}
"""

            send_group(txt,otp)

        time.sleep(REFRESH_INTERVAL)

# =====================
# Telegram Commands
# =====================

@bot.message_handler(commands=['start'])
def start(msg):

    bot.reply_to(msg,"Bot Running")

@bot.callback_query_handler(func=lambda c:c.data.startswith("copy_"))
def copy(c):

    code=c.data.split("_")[1]

    bot.answer_callback_query(c.id,f"Code : {code}",show_alert=True)

# =====================
# Run
# =====================

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":

    threading.Thread(target=run_bot).start()

    main_loop()