import requests
import json
import os
import time
from datetime import datetime
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ERROR: BOT_TOKEN not set")
    exit(1)

ADMIN = int(os.getenv("ADMIN_ID", "8296841503"))

URL = f"https://api.telegram.org/bot{TOKEN}"
LAST_ID = 0
USERS = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "OK"

@app.route('/ping')
def ping():
    return "pong"

def run_server():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_server, daemon=True).start()

def get_num():
    fname = "counter.txt"
    if os.path.exists(fname):
        with open(fname, 'r') as f:
            n = int(f.read())
    else:
        n = 100
    n += 1
    with open(fname, 'w') as f:
        f.write(str(n))
    return n

def load_orders():
    fname = "orders.json"
    if os.path.exists(fname):
        with open(fname, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_order(data):
    fname = "orders.json"
    orders = load_orders()
    orders[str(data['id'])] = data
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

def delete_order(oid):
    fname = "orders.json"
    orders = load_orders()
    if str(oid) in orders:
        del orders[str(oid)]
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
        return True
    return False

def clear_orders():
    fname = "orders.json"
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

def send(chat_id, text, kb=None):
    data = {"chat_id": chat_id, "text": text}
    if kb:
        data["reply_markup"] = kb
    try:
        requests.post(f"{URL}/sendMessage", json=data, timeout=10)
    except:
        pass

def send_admin(order):
    items = ""
    for i, item in enumerate(order['items'], 1):
        items += f"\n{i}. {item['link']}"
        if item.get('char'):
            items += f"\n   {item['char']}"
    
    txt = f"NEW ORDER #{order['id']}\n\n"
    txt += f"Name: {order['name']}\n"
    txt += f"User: @{order['username']} (ID: {order['user_id']})\n"
    txt += f"Phone: {order['phone']}\n"
    txt += f"Address: {order['address']}\n"
    txt += f"Items:{items}\n"
    txt += f"Created: {order['created']}"
    
    kb = {
        "inline_keyboard": [
            [{"text": "Accept", "callback_data": f"acc_{order['id']}"}],
            [{"text": "Reject", "callback_data": f"rej_{order['id']}"}],
            [{"text": "Contact", "callback_data": f"con_{order['id']}"}]
        ]
    }
    send(ADMIN, txt, kb)

def list_orders(orders):
    if not orders:
        return "No orders"
    txt = "Orders:\n\n"
    for oid, o in list(orders.items())[-10:]:
        txt += f"#{oid} | {o.get('status', 'New')}\n"
        txt += f"  {o.get('name', '-')} | @{o.get('username', '-')}\n\n"
    return txt

def order_details(oid, order):
    items = ""
    for i, item in enumerate(order.get('items', []), 1):
        items += f"\n{i}. {item['link']}"
        if item.get('char'):
            items += f"\n   {item['char']}"
    
    txt = f"ORDER #{oid}\n\n"
    txt += f"Name: {order.get('name', '-')}\n"
    txt += f"User: @{order.get('username', '-')} (ID: {order.get('user_id', '-')})\n"
    txt += f"Phone: {order.get('phone', '-')}\n"
    txt += f"Address: {order.get('address', '-')}\n"
    txt += f"Items:{items}\n"
    txt += f"Status: {order.get('status', 'New')}\n"
    txt += f"Created: {order.get('created', '-')}"
    return txt

def process(update):
    global LAST_ID
    
    uid = update.get('update_id', 0)
    if uid <= LAST_ID:
        return
    LAST_ID = uid
    
    if 'message' in update:
        msg = update['message']
        chat = msg['chat']['id']
        text = msg.get('text', '')
        
        username = msg['chat'].get('username', '')
        if not username:
            username = msg['chat'].get('first_name', 'user')
        
        if chat == ADMIN and text.startswith('/'):
            if text == '/start':
                send(chat, "Admin panel:\n/list - list orders\n/view N - view order\n/del N - delete order\n/clear - clear all\n/status N TEXT - change status")
                return
            
            if text == '/list':
                send(chat, list_orders(load_orders()))
                return
            
            if text.startswith('/view'):
                parts = text.split()
                if len(parts) != 2:
                    send(chat, "Use: /view NUMBER")
                    return
                try:
                    oid = int(parts[1])
                    orders = load_orders()
                    if str(oid) in orders:
                        send(chat, order_details(oid, orders[str(oid)]))
                    else:
                        send(chat, f"Order #{oid} not found")
                except:
                    send(chat, "Invalid number")
                return
            
            if text.startswith('/del'):
                parts = text.split()
                if len(parts) != 2:
                    send(chat, "Use: /del NUMBER")
                    return
                try:
                    oid = int(parts[1])
                    if delete_order(oid):
                        send(chat, f"Order #{oid} deleted")
                    else:
                        send(chat, f"Order #{oid} not found")
                except:
                    send(chat, "Invalid number")
                return
            
            if text == '/clear':
                clear_orders()
                send(chat, "All orders cleared")
                return
            
            if text.startswith('/status'):
                parts = text.split()
                if len(parts) < 3:
                    send(chat, "Use: /status NUMBER STATUS")
                    return
                try:
                    oid = int(parts[1])
                    status = ' '.join(parts[2:])
                    orders = load_orders()
                    if str(oid) in orders:
                        orders[str(oid)]['status'] = status
                        with open("orders.json", 'w', encoding='utf-8') as f:
                            json.dump(orders, f, ensure_ascii=False, indent=2)
                        send(chat, f"Order #{oid} status: {status}")
                        user_id = orders[str(oid)]['user_id']
                        send(user_id, f"Your order #{oid} status: {status}")
                    else:
                        send(chat, f"Order #{oid} not found")
                except:
                    send(chat, "Invalid number")
                return
            
            return
        
        if text == '/start':
            kb = {"inline_keyboard": [[{"text": "New Order", "callback_data": "new"}]]}
            send(chat, "Welcome! Press 'New Order' to start", kb)
            USERS.pop(chat, None)
            return
        
        state = USERS.get(chat)
        if not state:
            return
        
        step = state.get('step', 0)
        data = state.get('data', {})
        
        if step == 1:
            if len(text.strip()) < 2:
                send(chat, "Name too short. Try again:")
                return
            data['name'] = text.strip()
            data['user_id'] = chat
            data['username'] = username
            state['step'] = 2
            USERS[chat] = state
            send(chat, "Send your phone (digits only):")
            
        elif step == 2:
            phone = ''.join(filter(str.isdigit, text))
            if len(phone) < 10:
                send(chat, "Invalid phone. Try again:")
                return
            data['phone'] = phone
            state['step'] = 3
            USERS[chat] = state
            send(chat, "Enter your address:")
            
        elif step == 3:
            if len(text.strip()) < 5:
                send(chat, "Address too short. Try again:")
                return
            data['address'] = text.strip()
            state['step'] = 4
            USERS[chat] = state
            send(chat, "Send product link:")
            
        elif step == 4:
            if not text.startswith(('http://', 'https://')):
                send(chat, "Invalid link. Try again:")
                return
            if 'items' not in data:
                data['items'] = []
            data['items'].append({'link': text, 'char': ''})
            state['step'] = 5
            USERS[chat] = state
            send(chat, "Describe product (size, color, etc.):")
            
        elif step == 5:
            if len(data['items']) > 0:
                data['items'][-1]['char'] = text.strip()
            
            preview = ""
            for i, item in enumerate(data['items'], 1):
                preview += f"\n{i}. {item['link']}"
                if item.get('char'):
                    preview += f"\n   {item['char']}"
            
            kb = {
                "inline_keyboard": [
                    [{"text": "Add more", "callback_data": "add"}],
                    [{"text": "Finish", "callback_data": "finish"}]
                ]
            }
            state['step'] = 6
            USERS[chat] = state
            send(chat, f"Item added! Your items:{preview}\n\nWhat next?", kb)
    
    elif 'callback_query' in update:
        cb = update['callback_query']
        chat = cb['message']['chat']['id']
        data = cb['data']
        
        if chat == ADMIN:
            if data.startswith('acc_') or data.startswith('rej_'):
                oid = data.split('_')[1]
                status = "Accepted" if data.startswith('acc_') else "Rejected"
                orders = load_orders()
                if str(oid) in orders:
                    orders[str(oid)]['status'] = status
                    with open("orders.json", 'w', encoding='utf-8') as f:
                        json.dump(orders, f, ensure_ascii=False, indent=2)
                    user_id = orders[str(oid)]['user_id']
                    send(user_id, f"Order #{oid} status: {status}")
                    send(chat, f"Order #{oid} {status.lower()}")
                else:
                    send(chat, f"Order #{oid} not found")
                requests.post(f"{URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            if data.startswith('con_'):
                oid = data.split('_')[1]
                orders = load_orders()
                if str(oid) in orders:
                    o = orders[str(oid)]
                    txt = f"Contact #{oid}\n\n"
                    txt += f"Name: {o.get('name', '-')}\n"
                    txt += f"User: @{o.get('username', '-')} (ID: {o.get('user_id', '-')})\n"
                    txt += f"Phone: +{o.get('phone', '-')}\n"
                    txt += f"Link: https://t.me/{o.get('username', '')}"
                    send(chat, txt)
                else:
                    send(chat, f"Order #{oid} not found")
                requests.post(f"{URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
        
        if data == 'new':
            USERS[chat] = {'step': 1, 'data': {}}
            send(chat, "Enter your name:")
            requests.post(f"{URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
            
        elif data == 'add':
            state = USERS.get(chat, {})
            if state and state.get('step') == 6:
                state['step'] = 4
                USERS[chat] = state
                send(chat, "Send next product link:")
            requests.post(f"{URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
            
        elif data == 'finish':
            state = USERS.get(chat)
            if state and state.get('step') == 6:
                data = state.get('data', {})
                
                if not data.get('items'):
                    send(chat, "No items. Start over.")
                    USERS.pop(chat, None)
                    requests.post(f"{URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                    return
                
                oid = get_num()
                order = {
                    'id': oid,
                    'user_id': data['user_id'],
                    'username': data['username'],
                    'name': data['name'],
                    'phone': data['phone'],
                    'address': data['address'],
                    'items': data['items'],
                    'status': 'New',
                    'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                save_order(order)
                
                items = ""
                for i, item in enumerate(order['items'], 1):
                    items += f"\n{i}. {item['link']}"
                    if item.get('char'):
                        items += f"\n   {item['char']}"
                
                send(chat, f"Order #{oid} confirmed!\n\nYour items:{items}\n\nName: {order['name']}\nPhone: +{order['phone']}\nAddress: {order['address']}\n\nThank you!")
                
                send_admin(order)
                USERS.pop(chat, None)
                
            requests.post(f"{URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})

def main():
    global LAST_ID
    print("Bot started")
    send(ADMIN, "Bot started")
    
    while True:
        try:
            r = requests.get(f"{URL}/getUpdates", params={"offset": LAST_ID + 1, "timeout": 30}, timeout=35)
            if r.status_code == 200:
                updates = r.json().get('result', [])
                for u in updates:
                    try:
                        process(u)
                    except Exception as e:
                        print(f"Error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
