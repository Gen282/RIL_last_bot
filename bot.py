import requests
import json
import os
import time
import logging
from datetime import datetime
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN not set")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "8296841503"))
except ValueError:
    raise Exception("ADMIN_ID must be a number")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask('')

@app.route('/')
def home():
    return "Bot is working"

@app.route('/ping')
def ping():
    return "ok"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask, daemon=True).start()

last_update_id = 0
user_states = {}

def get_next_order_number():
    counter_file = "counter.txt"
    if os.path.exists(counter_file):
        with open(counter_file, 'r') as f:
            num = int(f.read().strip())
    else:
        num = 100
    num += 1
    with open(counter_file, 'w') as f:
        f.write(str(num))
    return num

def load_orders():
    orders_file = "orders.json"
    if os.path.exists(orders_file):
        with open(orders_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_order(order_data):
    orders_file = "orders.json"
    orders = load_orders()
    order_id = str(order_data['id'])
    orders[order_id] = order_data
    with open(orders_file, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)
    return order_id

def delete_order(order_id):
    orders_file = "orders.json"
    orders = load_orders()
    if str(order_id) in orders:
        del orders[str(order_id)]
        with open(orders_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
        return True
    return False

def clear_all_orders():
    orders_file = "orders.json"
    with open(orders_file, 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

def update_order_status(order_id, status):
    orders_file = "orders.json"
    orders = load_orders()
    if str(order_id) in orders:
        orders[str(order_id)]['status'] = status
        with open(orders_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
        return True
    return False

def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        data["reply_markup"] = keyboard
    try:
        response = requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Send error: {e}")
        return None

def send_order_to_admin(order_data):
    items_text = ""
    for i, item in enumerate(order_data['items'], 1):
        items_text += f"\n{i}. Link: {item['link']}"
        if item.get('characteristics'):
            items_text += f"\n   Characteristics: {item['characteristics']}"
    
    text = f"""
NEW ORDER #{order_data['id']}

Client: {order_data['name']}
Telegram: @{order_data['username']} (ID: {order_data['user_id']})
Phone: {order_data['phone']}
Address: {order_data['address']}

Items:{items_text}

Created: {order_data['created']}
Status: {order_data['status']}
"""
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "Accept", "callback_data": f"accept_{order_data['id']}"}],
            [{"text": "Reject", "callback_data": f"reject_{order_data['id']}"}],
            [{"text": "Contact", "callback_data": f"contact_{order_data['id']}"}]
        ]
    }
    
    send_message(ADMIN_ID, text, keyboard)

def format_orders_list(orders, limit=10):
    if not orders:
        return "Order list is empty."
    
    sorted_orders = sorted(orders.items(), key=lambda x: int(x[0]), reverse=True)
    recent = sorted_orders[:limit]
    
    result = "Order List:\n\n"
    for oid, order in recent:
        items_count = len(order.get('items', []))
        result += f"Order #{oid} | {order.get('status', 'New')}\n"
        result += f"   {order.get('name', '-')} | @{order.get('username', '-')}\n"
        result += f"   {items_count} item(s)\n"
        result += f"   {order.get('created', '-')[:16]}\n\n"
    return result

def format_order_details(order_id, order):
    items_text = ""
    for i, item in enumerate(order.get('items', []), 1):
        items_text += f"\n{i}. Link: {item['link']}"
        if item.get('characteristics'):
            items_text += f"\n   Characteristics: {item['characteristics']}"
    
    text = f"""
ORDER #{order_id}

Client: {order.get('name', '-')}
Telegram: @{order.get('username', '-')} (ID: {order.get('user_id', '-')})
Phone: {order.get('phone', '-')}
Address: {order.get('address', '-')}

Items:{items_text}

Created: {order.get('created', '-')}
Status: {order.get('status', 'New')}
"""
    return text

def process_update(update):
    global last_update_id
    
    update_id = update.get('update_id', 0)
    if update_id <= last_update_id:
        return
    last_update_id = update_id
    
    if 'message' in update:
        msg = update['message']
        chat_id = msg['chat']['id']
        text = msg.get('text', '')
        
        username = msg['chat'].get('username', '')
        if not username:
            username = msg['chat'].get('first_name', '').replace(' ', '_')
        
        if chat_id == ADMIN_ID and text.startswith('/'):
            if text == '/start':
                send_message(chat_id, """
Admin Panel:

Commands:
/list_orders - list all orders
/view_order N - view order N
/delete_order N - delete order N
/clear_orders - delete all orders
/status N STATUS - change order status
/start - this message
""")
                return
            
            elif text == '/list_orders':
                orders = load_orders()
                send_message(chat_id, format_orders_list(orders))
                return
            
            elif text.startswith('/view_order'):
                parts = text.split()
                if len(parts) != 2:
                    send_message(chat_id, "Usage: /view_order NUMBER")
                    return
                try:
                    order_id = int(parts[1])
                    orders = load_orders()
                    if str(order_id) in orders:
                        send_message(chat_id, format_order_details(order_id, orders[str(order_id)]))
                    else:
                        send_message(chat_id, f"Order #{order_id} not found")
                except ValueError:
                    send_message(chat_id, "Number must be integer")
                return
            
            elif text.startswith('/delete_order'):
                parts = text.split()
                if len(parts) != 2:
                    send_message(chat_id, "Usage: /delete_order NUMBER")
                    return
                try:
                    order_id = int(parts[1])
                    if delete_order(order_id):
                        send_message(chat_id, f"Order #{order_id} deleted")
                    else:
                        send_message(chat_id, f"Order #{order_id} not found")
                except ValueError:
                    send_message(chat_id, "Number must be integer")
                return
            
            elif text == '/clear_orders':
                clear_all_orders()
                send_message(chat_id, "All orders deleted!")
                return
            
            elif text.startswith('/status'):
                parts = text.split()
                if len(parts) < 3:
                    send_message(chat_id, "Usage: /status NUMBER STATUS")
                    return
                try:
                    order_id = int(parts[1])
                    status = ' '.join(parts[2:])
                    if update_order_status(order_id, status):
                        send_message(chat_id, f"Order #{order_id} status changed to: {status}")
                        orders = load_orders()
                        if str(order_id) in orders:
                            user_id = orders[str(order_id)]['user_id']
                            send_message(user_id, f"Your order #{order_id} status changed to: {status}")
                    else:
                        send_message(chat_id, f"Order #{order_id} not found")
                except ValueError:
                    send_message(chat_id, "Number must be integer")
                return
            
            return
        
        if text == '/start':
            keyboard = {
                "inline_keyboard": [
                    [{"text": "New Order", "callback_data": "new_order"}]
                ]
            }
            send_message(chat_id, """
Welcome!

Press "New Order" to start.
""", keyboard)
            user_states.pop(chat_id, None)
            return
        
        state = user_states.get(chat_id)
        if not state:
            return
        
        step = state.get('step', 0)
        order_data = state.get('data', {})
        
        if step == 1:
            if len(text.strip()) < 2:
                send_message(chat_id, "Name must be at least 2 characters. Try again:")
                return
            order_data['name'] = text.strip()
            order_data['user_id'] = chat_id
            order_data['username'] = username
            state['step'] = 2
            user_states[chat_id] = state
            send_message(chat_id, "Send your phone number (digits only):")
            
        elif step == 2:
            phone = ''.join(filter(str.isdigit, text))
            if len(phone) < 10:
                send_message(chat_id, "Enter valid phone number (at least 10 digits):")
                return
            order_data['phone'] = phone
            state['step'] = 3
            user_states[chat_id] = state
            send_message(chat_id, "Enter your address (city, street, house, apartment):")
            
        elif step == 3:
            if len(text.strip()) < 5:
                send_message(chat_id, "Enter full address (at least 5 characters):")
                return
            order_data['address'] = text.strip()
            state['step'] = 4
            user_states[chat_id] = state
            send_message(chat_id, "Send product link:")
            
        elif step == 4:
            if not text.startswith(('http://', 'https://')):
                send_message(chat_id, "This is not a valid link. Send correct link:")
                return
            if 'items' not in order_data:
                order_data['items'] = []
            order_data['items'].append({
                'link': text,
                'characteristics': ''
            })
            state['step'] = 5
            user_states[chat_id] = state
            send_message(chat_id, "Describe product characteristics (size, color, quantity, etc.):")
            
        elif step == 5:
            if len(order_data['items']) > 0:
                order_data['items'][-1]['characteristics'] = text.strip()
            
            items_preview = ""
            for i, item in enumerate(order_data['items'], 1):
                items_preview += f"\n{i}. {item['link']}"
                if item.get('characteristics'):
                    items_preview += f"\n   {item['characteristics']}"
            
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Add more items", "callback_data": "add_item"}],
                    [{"text": "Finish order", "callback_data": "finish_order"}]
                ]
            }
            state['step'] = 6
            user_states[chat_id] = state
            send_message(chat_id, f"""
Item added!

Your items:{items_preview}

What next?
""", keyboard)
    
    elif 'callback_query' in update:
        cb = update['callback_query']
        chat_id = cb['message']['chat']['id']
        data = cb['data']
        
        if chat_id == ADMIN_ID:
            if data.startswith('accept_') or data.startswith('reject_'):
                order_id = data.split('_')[1]
                status = "Accepted" if data.startswith('accept_') else "Rejected"
                if update_order_status(order_id, status):
                    orders = load_orders()
                    if str(order_id) in orders:
                        user_id = orders[str(order_id)]['user_id']
                        send_message(user_id, f"Your order #{order_id} status changed to: {status}")
                    send_message(chat_id, f"Order #{order_id} {status.lower()}")
                    orders = load_orders()
                    if str(order_id) in orders:
                        send_message(chat_id, format_order_details(order_id, orders[str(order_id)]))
                else:
                    send_message(chat_id, f"Order #{order_id} not found")
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            elif data.startswith('contact_'):
                order_id = data.split('_')[1]
                orders = load_orders()
                if str(order_id) in orders:
                    order = orders[str(order_id)]
                    user_id = order['user_id']
                    username = order.get('username', '')
                    phone = order.get('phone', '')
                    
                    text = f"""
Customer contacts #{order_id}

Name: {order.get('name', '-')}
Telegram: @{username} (ID: {user_id})
Phone: +{phone}

You can:
• Write in Telegram: https://t.me/{username}
• Call: +{phone}
"""
                    send_message(chat_id, text)
                else:
                    send_message(chat_id, f"Order #{order_id} not found")
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
        
        if data == 'new_order':
            user_states[chat_id] = {
                'step': 1,
                'data': {}
            }
            send_message(chat_id, "Enter your name:")
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
            
        elif data == 'add_item':
            state = user_states.get(chat_id, {})
            if state and state.get('step') == 6:
                state['step'] = 4
                user_states[chat_id] = state
                send_message(chat_id, "Send next product link:")
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
            
        elif data == 'finish_order':
            state = user_states.get(chat_id)
            if state and state.get('step') == 6:
                order_data = state.get('data', {})
                
                if not order_data.get('items'):
                    send_message(chat_id, "No items added. Start over.")
                    user_states.pop(chat_id, None)
                    requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                    return
                
                order_id = get_next_order_number()
                order = {
                    'id': order_id,
                    'user_id': order_data['user_id'],
                    'username': order_data['username'],
                    'name': order_data['name'],
                    'phone': order_data['phone'],
                    'address': order_data['address'],
                    'items': order_data['items'],
                    'status': 'New',
                    'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                save_order(order)
                
                items_summary = ""
                for i, item in enumerate(order['items'], 1):
                    items_summary += f"\n{i}. {item['link']}"
                    if item.get('characteristics'):
                        items_summary += f"\n   {item['characteristics']}"
                
                send_message(chat_id, f"""
Order #{order_id} confirmed!

Your items:{items_summary}

Contacts:
Name: {order['name']}
Phone: +{order['phone']}
Address: {order['address']}

Thank you! Admin will contact you soon.
Order number: {order_id}
""")
                
                send_order_to_admin(order)
                user_states.pop(chat_id, None)
                
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})

def main():
    global last_update_id
    logger.info("Bot started!")
    send_message(ADMIN_ID, "Bot started successfully!")
    
    while True:
        try:
            response = requests.get(
                f"{API_URL}/getUpdates",
                params={"offset": last_update_id + 1, "timeout": 30},
                timeout=35
            )
            
            if response.status_code == 200:
                updates = response.json().get('result', [])
                for update in updates:
                    try:
                        process_update(update)
                    except Exception as e:
                        logger.error(f"Update error: {e}")
            else:
                logger.error(f"API error: {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.warning("Timeout, continuing...")
        except Exception as e:
            logger.error(f"Critical error: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    main()
