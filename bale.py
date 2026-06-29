import requests
import time
import sqlite3

BALE_TOKEN = "541921468:x4wRmb4Wuu_98kDELv_xeiqfkmLOzEpfwOU"
OPENROUTER_KEY = "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"

BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

AVAILABLE_MODELS = {
    "gpt4o": "openai/gpt-4o-mini",
    "deepseek": "deepseek/deepseek-chat",
    "mistral": "mistralai/mistral-7b-instruct",
    "llama": "meta-llama/llama-3-8b-instruct"
}

# دیتابیس
db = sqlite3.connect("memory.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS memory(
user_id INTEGER,
role TEXT,
content TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS model(
user_id INTEGER PRIMARY KEY,
model TEXT
)
""")

db.commit()

last_request = {}

def get_model(user_id):

    cur.execute("SELECT model FROM model WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    if row:
        return row[0]

    return AVAILABLE_MODELS["gpt4o"]


def set_model(user_id, model):

    cur.execute(
        "INSERT OR REPLACE INTO model(user_id,model) VALUES(?,?)",
        (user_id, model)
    )
    db.commit()


def load_memory(user_id):

    cur.execute(
        "SELECT role,content FROM memory WHERE user_id=? ORDER BY rowid DESC LIMIT 10",
        (user_id,)
    )

    rows = cur.fetchall()

    messages = []

    for r in reversed(rows):
        messages.append({"role": r[0], "content": r[1]})

    return messages


def save_message(user_id, role, content):

    cur.execute(
        "INSERT INTO memory VALUES(?,?,?)",
        (user_id, role, content)
    )

    db.commit()


def reset_memory(user_id):

    cur.execute("DELETE FROM memory WHERE user_id=?", (user_id,))
    db.commit()


def ask_ai(user_id, text):

    messages = load_memory(user_id)

    messages.append({
        "role": "user",
        "content": text
    })

    payload = {
        "model": get_model(user_id),
        "messages": messages
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }

    try:

        r = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=40
        )

        data = r.json()

        reply = data["choices"][0]["message"]["content"]

    except Exception as e:

        print("AI error:", e)

        return "هوش مصنوعی در دسترس نیست 😵"

    save_message(user_id, "user", text)
    save_message(user_id, "assistant", reply)

    return reply


def send_message(chat_id, text):

    try:
        requests.post(
            f"{BALE_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15
        )
    except:
        pass


offset = 0

print("✅ Bale AI Pro Bot started")

while True:

    try:

        r = requests.get(
            f"{BALE_API}/getUpdates",
            params={"offset": offset, "timeout": 30},
            timeout=35
        )

        data = r.json()

    except:
        time.sleep(3)
        continue

    if not data.get("ok"):
        continue

    for update in data["result"]:

        offset = update["update_id"] + 1

        message = update.get("message")

        if not message:
            continue

        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        text = message.get("text")

        if not text:
            continue

        # rate limit
        now = time.time()

        if user_id in last_request:
            if now - last_request[user_id] < 3:
                send_message(chat_id, "آروم‌تر موری 😅")
                continue

        last_request[user_id] = now

        # commands
        if text == "/reset":
            reset_memory(user_id)
            send_message(chat_id, "حافظه پاک شد ✅")
            continue

        if text.startswith("/model"):

            parts = text.split()

            if len(parts) < 2:
                send_message(chat_id, "مدل‌ها: gpt4o deepseek mistral llama")
                continue

            key = parts[1]

            if key in AVAILABLE_MODELS:
                set_model(user_id, AVAILABLE_MODELS[key])
                send_message(chat_id, f"مدل تغییر کرد به {key}")
            else:
                send_message(chat_id, "مدل پیدا نشد")

            continue

        send_message(chat_id, "دارم فکر می‌کنم...")

        reply = ask_ai(user_id, text)

        send_message(chat_id, reply)
