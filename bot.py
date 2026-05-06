import requests
import json
import os
import time
from datetime import datetime
from flask import Flask
from threading import Thread

BOT_TOKEN = "8646996759:AAH1D-xXzOekPUs2G1hr-90jcxjX_D5BYwg"
ADMIN_ID = 8296841503

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
last_update_id = 0
counter_file = "counter.txt"
orders_file = "orders.json"

app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask).start()

def get_num():
    if os.path.exists(counter_file):
        with open(counter_file, 'r') as f:
            n = int(f.read())
    else:
        n = 99
    n += 1
    with open(counter_file, 'w') as f:
        f.write(str(n))
    return n

def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = keyboard
    requests.post(f"{API_URL}/sendMessage", json=data)

user_states = {}

def process_update(update):
    global last_update_id
    
    update_id = update['update_id']
    if update_id <= last_update_id:
        return
    last_update_id = update_id

    if 'message' in update:
        msg = update['message']
        chat_id = msg['chat']['id']
        text = msg.get('text', '')

        if text == '/start':
            keyboard = {"inline_keyboard": [[{"text": "🛒 Новый заказ", "callback_data": "new"}]]}
            send_message(chat_id, "👋 Бот готов! Нажми «Новый заказ»:", keyboard)
            user_states.pop(chat_id, None)
            return

        state = user_states.get(chat_id, {})
        step = state.get('step', 0)

        if step == 1:
            state['link'] = text
            state['step'] = 2
            user_states[chat_id] = state
            send_message(chat_id, "2️⃣ Ваше имя:")
        elif step == 2:
            state['name'] = text
            state['step'] = 3
            user_states[chat_id] = state
            send_message(chat_id, "3️⃣ Адрес доставки:")
        elif step == 3:
            state['address'] = text
            state['step'] = 4
            user_states[chat_id] = state
            send_message(chat_id, "4️⃣ Номер телефона:")
        elif step == 4:
            state['phone'] = text
            num = get_num()
            send_message(chat_id, f"✅ Заказ №{num} принят!")
            admin_text = f"НОВЫЙ ЗАКАЗ №{num}\nКлиент: {msg['chat'].get('first_name', '')}\nСсылка: {state['link']}\nИмя: {state['name']}\nАдрес: {state['address']}\nТелефон: {text}"
            requests.post(f"{API_URL}/sendMessage", json={"chat_id": ADMIN_ID, "text": admin_text})
            user_states.pop(chat_id, None)

    elif 'callback_query' in update:
        cb = update['callback_query']
        chat_id = cb['message']['chat']['id']
        data = cb['data']

        if data == 'new':
            user_states[chat_id] = {'step': 1}
            send_message(chat_id, "1️⃣ Ссылка на товар:")
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})

def main():
    global last_update_id
    print("🚀 Бот запущен!")
    while True:
        try:
            response = requests.get(f"{API_URL}/getUpdates", params={"offset": last_update_id + 1, "timeout": 30})
            updates = response.json().get('result', [])
            for update in updates:
                process_update(update)
        except Exception as e:
            print(f"Ошибка: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
