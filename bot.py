import requests
import json
import os
import time
from datetime import datetime
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("Ошибка: переменная окружения BOT_TOKEN не установлена!")

ADMIN_ID = int(os.getenv("ADMIN_ID", "8296841503"))

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
last_update_id = 0
user_states = {}

app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

@app.route('/ping')
def ping():
    return "ok"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask).start()

def get_num():
    counter_file = "counter.txt"
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
    orders_file = "orders.json"
    if os.path.exists(orders_file):
        with open(orders_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_order(oid, data):
    orders = load_orders()
    orders[str(oid)] = data
    with open("orders.json", 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

def delete_order(oid):
    orders = load_orders()
    if str(oid) in orders:
        del orders[str(oid)]
        with open("orders.json", 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
        return True
    return False

def clear_all_orders():
    with open("orders.json", 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        data["reply_markup"] = keyboard
    requests.post(f"{API_URL}/sendMessage", json=data)

def send_order_to_admin(order_data):
    items_text = ""
    for i, item in enumerate(order_data['items'], 1):
        items_text += f"\n{i}. Ссылка: {item['link']}"
        if item.get('characteristics'):
            items_text += f"\n   Характеристики: {item['characteristics']}"
    
    text = f"""
🛒 **НОВЫЙ ЗАКАЗ №{order_data['id']}**

👤 **Клиент:** {order_data['name']}
🆔 **Telegram:** @{order_data['username']} (ID: {order_data['user_id']})
📱 **Телефон:** {order_data['phone']}
🏠 **Адрес:** {order_data['address']}

📦 **Товары:**{items_text}

📅 **Создан:** {order_data['created']}
📊 **Статус:** {order_data['status']}
"""
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "✅ Принять", "callback_data": f"accept_{order_data['id']}"}],
            [{"text": "❌ Отклонить", "callback_data": f"reject_{order_data['id']}"}],
            [{"text": "📞 Связаться", "callback_data": f"contact_{order_data['id']}"}]
        ]
    }
    
    send_message(ADMIN_ID, text, keyboard)

def get_orders_list():
    orders = load_orders()
    if not orders:
        return "📭 Список заказов пуст."
    
    sorted_orders = sorted(orders.items(), key=lambda x: int(x[0]), reverse=True)
    recent = sorted_orders[:10]
    
    result = "📋 **Последние заказы:**\n\n"
    for oid, order in recent:
        result += f"🔹 **Заказ №{oid}**\n"
        result += f"   👤 Клиент: {order.get('name', '-')}\n"
        result += f"   📅 Создан: {order.get('created', '-')[:16]}\n"
        result += f"   📞 Телефон: {order.get('phone', '-')}\n\n"
    return result

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
                send_message(chat_id, get_orders_list())
                return
            elif text.startswith('/delete_order'):
                parts = text.split()
                if len(parts) != 2:
                    send_message(chat_id, "❌ Использование: /delete_order НОМЕР")
                    return
                try:
                    oid = int(parts[1])
                    if delete_order(oid):
                        send_message(chat_id, f"✅ Заказ №{oid} удалён.")
                    else:
                        send_message(chat_id, f"❌ Заказ №{oid} не найден.")
                except:
                    send_message(chat_id, "❌ Номер должен быть числом.")
                return
            elif text == '/clear_orders':
                clear_all_orders()
                send_message(chat_id, "🗑️ Все заказы удалены!")
                return
            elif text == '/start':
                send_message(chat_id, "👋 Админ-панель: /list_orders, /delete_order N, /clear_orders")
                return

        if text == '/start':
            keyboard = {"inline_keyboard": [[{"text": "🛒 Новый заказ", "callback_data": "new"}]]}
            send_message(chat_id, "👋 Бот готов!\nНажмите «Новый заказ», чтобы оформить заказ:", keyboard)
            user_states.pop(chat_id, None)
            return

        state = user_states.get(chat_id, {})
        step = state.get('step', 0)

        if step == 1:
            state['name'] = text
            state['step'] = 2
            user_states[chat_id] = state
            send_message(chat_id, "📱 Отправьте ваш номер телефона (только цифры):")
        elif step == 2:
            phone = ''.join(filter(str.isdigit, text))
            if len(phone) < 10:
                send_message(chat_id, "❌ Введите корректный номер телефона (минимум 10 цифр):")
                return
            state['phone'] = phone
            state['step'] = 3
            user_states[chat_id] = state
            send_message(chat_id, "🏠 Введите ваш адрес (город, улица, дом, квартира):")
        elif step == 3:
            state['address'] = text
            state['step'] = 4
            user_states[chat_id] = state
            send_message(chat_id, "🔗 Отправьте ссылку на товар:")
        elif step == 4:
            if not text.startswith(('http://', 'https://')):
                send_message(chat_id, "❌ Это не похоже на ссылку. Отправьте корректную ссылку:")
                return
            if 'items' not in state:
                state['items'] = []
            state['items'].append({'link': text, 'characteristics': ''})
            state['step'] = 5
            user_states[chat_id] = state
            send_message(chat_id, "📝 Опишите характеристики товара (размер, цвет, количество и т.д.):")
        elif step == 5:
            if len(state['items']) > 0:
                state['items'][-1]['characteristics'] = text
            
            items_preview = ""
            for i, item in enumerate(state['items'], 1):
                items_preview += f"\n{i}. {item['link']}"
                if item.get('characteristics'):
                    items_preview += f"\n   📌 {item['characteristics']}"
            
            keyboard = {
                "inline_keyboard": [
                    [{"text": "➕ Добавить ещё товар", "callback_data": "add_item"}],
                    [{"text": "✅ Завершить заказ", "callback_data": "finish_order"}]
                ]
            }
            state['step'] = 6
            user_states[chat_id] = state
            send_message(chat_id, f"""
✅ Товар добавлен!

📦 **Ваши товары:**{items_preview}

Что делаем дальше?
""", keyboard)

    elif 'callback_query' in update:
        cb = update['callback_query']
        chat_id = cb['message']['chat']['id']
        data = cb['data']

        if chat_id == ADMIN_ID:
            if data.startswith('accept_') or data.startswith('reject_'):
                oid = data.split('_')[1]
                status = "Принят" if data.startswith('accept_') else "Отклонён"
                orders = load_orders()
                if str(oid) in orders:
                    orders[str(oid)]['status'] = status
                    with open("orders.json", 'w', encoding='utf-8') as f:
                        json.dump(orders, f, ensure_ascii=False, indent=2)
                    user_id = orders[str(oid)]['user_id']
                    send_message(user_id, f"📢 Статус вашего заказа №{oid} изменён на: *{status}*")
                    send_message(chat_id, f"✅ Заказ №{oid} {status.lower()}")
                else:
                    send_message(chat_id, f"❌ Заказ №{oid} не найден")
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            elif data.startswith('contact_'):
                oid = data.split('_')[1]
                orders = load_orders()
                if str(oid) in orders:
                    order = orders[str(oid)]
                    text = f"""
📞 **Контакты заказчика №{oid}**

👤 Имя: {order.get('name', '-')}
🆔 Telegram: @{order.get('username', '-')} (ID: {order.get('user_id', '-')})
📱 Телефон: +{order.get('phone', '-')}
🏠 Адрес: {order.get('address', '-')}

💡 Напишите ему: https://t.me/{order.get('username', '')}
"""
                    send_message(chat_id, text)
                else:
                    send_message(chat_id, f"❌ Заказ №{oid} не найден")
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return

        if data == 'new':
            user_states[chat_id] = {'step': 1}
            send_message(chat_id, "👤 Введите ваше имя:")
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
        
        elif data == 'add_item':
            state = user_states.get(chat_id, {})
            if state and state.get('step') == 6:
                state['step'] = 4
                user_states[chat_id] = state
                send_message(chat_id, "🔗 Отправьте ссылку на следующий товар:")
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
        
        elif data == 'finish_order':
            state = user_states.get(chat_id)
            if state and state.get('step') == 6:
                num = get_num()
                order = {
                    'id': num,
                    'user_id': chat_id,
                    'username': msg['chat'].get('username', ''),
                    'name': state.get('name', ''),
                    'phone': state.get('phone', ''),
                    'address': state.get('address', ''),
                    'items': state.get('items', []),
                    'status': 'Новый',
                    'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                save_order(num, order)
                
                items_summary = ""
                for i, item in enumerate(order['items'], 1):
                    items_summary += f"\n{i}. {item['link']}"
                    if item.get('characteristics'):
                        items_summary += f"\n   📌 {item['characteristics']}"
                
                send_message(chat_id, f"""
✅ **Заказ №{num} оформлен!**

📦 **Ваши товары:**{items_summary}

📞 **Контакты:**
👤 Имя: {order['name']}
📱 Телефон: +{order['phone']}
🏠 Адрес: {order['address']}

Спасибо! Администратор свяжется с вами.
Номер заказа: **{num}**
""")
                
                send_order_to_admin(order)
                user_states.pop(chat_id, None)
            
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

