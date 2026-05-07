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
    return "Bot works!"

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

def load_orders():
    if os.path.exists(orders_file):
        with open(orders_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_order(oid, data):
    orders = load_orders()
    orders[str(oid)] = data
    with open(orders_file, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

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

        if chat_id == ADMIN_ID and text.startswith('/'):
            if text == '/list_orders':
                orders = load_orders()
                if not orders:
                    send_message(chat_id, "No orders")
                return
            elif text.startswith('/delete_order'):
                parts = text.split()
                if len(parts) != 2:
                    send_message(chat_id, "Use: /delete_order NUMBER")
                    return
                try:
                    oid = int(parts[1])
                    orders = load_orders()
                    if str(oid) in orders:
                        del orders[str(oid)]
                        with open(orders_file, 'w') as f:
                            json.dump(orders, f)
                        send_message(chat_id, f"Order {oid} deleted")
                    else:
                        send_message(chat_id, f"Order {oid} not found")
                except:
                    send_message(chat_id, "Number please")
                return
            elif text == '/clear_orders':
                with open(orders_file, 'w') as f:
                    json.dump({}, f)
                send_message(chat_id, "All orders cleared")
                return

        if text == '/start':
            keyboard = {"inline_keyboard": [[{"text": "New Order", "callback_data": "new"}]]}
            send_message(chat_id, "Bot ready! Press 'New Order' to start:", keyboard)
            user_states.pop(chat_id, None)
            return

        state = user_states.get(chat_id, {})
        step = state.get('step', 0)

        if step == 1:
            state['link'] = text
            state['step'] = 2
            user_states[chat_id] = state
            send_message(chat_id, "2. Your name:")
        elif step == 2:
            state['name'] = text
            state['step'] = 3
            user_states[chat_id] = state
            send_message(chat_id, "3. Delivery address:")
        elif step == 3:
            state['address'] = text
            state['step'] = 4
            user_states[chat_id] = state
            send_message(chat_id, "4. Phone number:")
        elif step == 4:
            state['phone'] = text
            if os.path.exists(counter_file):
                with open(counter_file, 'r') as f:
                    n = int(f.read())
            else:
                n = 99
            n += 1
            with open(counter_file, 'w') as f:
                f.write(str(n))
            order = {
                'id': n,
                'user_id': chat_id,
                'user_name': msg['chat'].get('first_name', ''),
                'link': state['link'],
                'name': state['name'],
                'address': state['address'],
                'phone': text,
                'created': datetime.now().isoformat()
            }
            orders = load_orders()
            orders[str(n)] = order
            with open(orders_file, 'w', encoding='utf-8') as f:
                json.dump(orders, f, ensure_ascii=False, indent=2)
            send_message(chat_id, f"Order #{n} accepted! Admin will contact you.")
            admin_text = f"NEW ORDER #{n}\nClient: {msg['chat'].get('first_name', '')}\nLink: {state['link']}\nName: {state['name']}\nAddress: {state['address']}\nPhone: {text}"
            requests.post(f"{API_URL}/sendMessage", json={"chat_id": ADMIN_ID, "text": admin_text})
            user_states.pop(chat_id, None)

    elif 'callback_query' in update:
        cb = update['callback_query']
        chat_id = cb['message']['chat']['id']
        data = cb['data']

        if data == 'new':
            user_states[chat_id] = {'step': 1}
            send_message(chat_id, "1. Send product link:")
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})

def main():
    global last_update_id
    print("Bot started!")
    while True:
        try:
            response = requests.get(f"{API_URL}/getUpdates", params={"offset": last_update_id + 1, "timeout": 30})
            updates = response.json().get('result', [])
            for update in updates:
                process_update(update)
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
