import requests
import json
import os
import time
import logging
from datetime import datetime
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# ========== ЗАГРУЗКА ПЕРЕМЕННЫХ ==========
load_dotenv()

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("Ошибка: BOT_TOKEN не установлен! Проверьте .env файл или переменные окружения")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "8296841503"))
except ValueError:
    raise Exception("ADMIN_ID должен быть числом!")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ========== ЛОГИРОВАНИЕ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== FLASK ДЛЯ ПИНГА ==========
app = Flask('')

@app.route('/')
def home():
    return "Бот для заказов работает!"

@app.route('/ping')
def ping():
    return "ok"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask, daemon=True).start()

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
last_update_id = 0
user_states = {}

# ========== ФУНКЦИИ ХРАНЕНИЯ ==========
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

# ========== ФУНКЦИИ ОТПРАВКИ ==========
def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        data["reply_markup"] = keyboard
    try:
        response = requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return None

def send_order_to_admin(order_data):
    items_text = ""
    for i, item in enumerate(order_data['items'], 1):
        items_text += f"\n{i}. Ссылка: {item['link']}"
        if item.get('characteristics'):
            items_text += f"\n   Характеристики: {item['characteristics']}"
    
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

# ========== ФОРМАТИРОВАНИЕ ==========
def format_orders_list(orders, limit=10):
    if not orders:
        return "📭 Список заказов пуст."
    
    sorted_orders = sorted(orders.items(), key=lambda x: int(x[0]), reverse=True)
    recent = sorted_orders[:limit]
    
    result = "📋 **Список заказов:**\n\n"
    for oid, order in recent:
        items_count = len(order.get('items', []))
        status_emoji = {
            'Новый': '🆕',
            'Принят': '✅',
            'Отклонён': '❌',
            'В обработке': '🔄',
            'Доставлен': '📦'
        }.get(order.get('status', 'Новый'), '📌')
        
        result += f"{status_emoji} **Заказ №{oid}** | {order.get('status', 'Новый')}\n"
        result += f"   👤 {order.get('name', '-')} | @{order.get('username', '-')}\n"
        result += f"   📦 {items_count} товар(ов)\n"
        result += f"   📅 {order.get('created', '-')[:16]}\n\n"
    return result

def format_order_details(order_id, order):
    items_text = ""
    for i, item in enumerate(order.get('items', []), 1):
        items_text += f"\n{i}. Ссылка: {item['link']}"
        if item.get('characteristics'):
            items_text += f"\n   Характеристики: {item['characteristics']}"
    
    text = f"""
📦 **ЗАКАЗ №{order_id}**

👤 **Клиент:** {order.get('name', '-')}
🆔 **Telegram:** @{order.get('username', '-')} (ID: {order.get('user_id', '-')})
📱 **Телефон:** {order.get('phone', '-')}
🏠 **Адрес:** {order.get('address', '-')}

📦 **Товары:**{items_text}

📅 **Создан:** {order.get('created', '-')}
📊 **Статус:** {order.get('status', 'Новый')}
"""
    return text

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========
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
        
        # АДМИН-КОМАНДЫ
        if chat_id == ADMIN_ID and text.startswith('/'):
            if text == '/start':
                send_message(chat_id, """
👋 **Админ-панель**

Доступные команды:
/list_orders - список заказов
/view_order N - детали заказа N
/delete_order N - удалить заказ N
/clear_orders - удалить все заказы
/status N СТАТУС - изменить статус заказа
/start - это сообщение
""")
                return
            
            elif text == '/list_orders':
                orders = load_orders()
                send_message(chat_id, format_orders_list(orders))
                return
            
            elif text.startswith('/view_order'):
                parts = text.split()
                if len(parts) != 2:
                    send_message(chat_id, "❌ Использование: /view_order НОМЕР")
                    return
                try:
                    order_id = int(parts[1])
                    orders = load_orders()
                    if str(order_id) in orders:
                        send_message(chat_id, format_order_details(order_id, orders[str(order_id)]))
                    else:
                        send_message(chat_id, f"❌ Заказ №{order_id} не найден")
                except ValueError:
                    send_message(chat_id, "❌ Номер должен быть числом")
                return
            
            elif text.startswith('/delete_order'):
                parts = text.split()
                if len(parts) != 2:
                    send_message(chat_id, "❌ Использование: /delete_order НОМЕР")
                    return
                try:
                    order_id = int(parts[1])
                    if delete_order(order_id):
                        send_message(chat_id, f"✅ Заказ №{order_id} удалён")
                    else:
                        send_message(chat_id, f"❌ Заказ №{order_id} не найден")
                except ValueError:
                    send_message(chat_id, "❌ Номер должен быть числом")
                return
            
            elif text == '/clear_orders':
                clear_all_orders()
                send_message(chat_id, "🗑️ Все заказы удалены!")
                return
            
            elif text.startswith('/status'):
                parts = text.split()
                if len(parts) < 3:
                    send_message(chat_id, "❌ Использование: /status НОМЕР СТАТУС")
                    return
                try:
                    order_id = int(parts[1])
                    status = ' '.join(parts[2:])
                    if update_order_status(order_id, status):
                        send_message(chat_id, f"✅ Статус заказа №{order_id} изменён на: {status}")
                        orders = load_orders()
                        if str(order_id) in orders:
                            user_id = orders[str(order_id)]['user_id']
                            send_message(user_id, f"📢 Статус вашего заказа №{order_id} изменён на: *{status}*")
                    else:
                        send_message(chat_id, f"❌ Заказ №{order_id} не найден")
                except ValueError:
                    send_message(chat_id, "❌ Номер должен быть числом")
                return
            
            return
        
        # ПОЛЬЗОВАТЕЛЬ
        if text == '/start':
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🛒 Новый заказ", "callback_data": "new_order"}]
                ]
            }
            send_message(chat_id, """
👋 **Добро пожаловать!**

Я помогу вам оформить заказ.
Нажмите кнопку «Новый заказ» чтобы начать.
""", keyboard)
            user_states.pop(chat_id, None)
            return
        
        state = user_states.get(chat_id)
        if not state:
            return
        
        step = state.get('step', 0)
        order_data = state.get('data', {})
        
        if step == 1:  # Имя
            if len(text.strip()) < 2:
                send_message(chat_id, "❌ Имя должно содержать минимум 2 символа. Попробуйте снова:")
                return
            order_data['name'] = text.strip()
            order_data['user_id'] = chat_id
            order_data['username'] = username
            state['step'] = 2
            user_states[chat_id] = state
            send_message(chat_id, "📱 Отправьте ваш номер телефона (только цифры):")
            
        elif step == 2:  # Телефон
            phone = ''.join(filter(str.isdigit, text))
            if len(phone) < 10:
                send_message(chat_id, "❌ Введите корректный номер телефона (минимум 10 цифр):")
                return
            order_data['phone'] = phone
            state['step'] = 3
            user_states[chat_id] = state
            send_message(chat_id, "🏠 Введите ваш адрес (город, улица, дом, квартира):")
            
        elif step == 3:  # Адрес
            if len(text.strip()) < 5:
                send_message(chat_id, "❌ Введите полный адрес (минимум 5 символов):")
                return
            order_data['address'] = text.strip()
            state['step'] = 4
            user_states[chat_id] = state
            send_message(chat_id, "🔗 Отправьте ссылку на товар:")
            
        elif step == 4:  # Ссылка
            if not text.startswith(('http://', 'https://')):
                send_message(chat_id, "❌ Это не похоже на ссылку. Отправьте корректную ссылку:")
                return
            if 'items' not in order_data:
                order_data['items'] = []
            order_data['items'].append({
                'link': text,
                'characteristics': ''
            })
            state['step'] = 5
            user_states[chat_id] = state
            send_message(chat_id, "📝 Опишите характеристики товара (размер, цвет, количество и т.д.):")
            
        elif step == 5:  # Характеристики
            if len(order_data['items']) > 0:
                order_data['items'][-1]['characteristics'] = text.strip()
            
            items_preview = ""
            for i, item in enumerate(order_data['items'], 1):
                items_preview += f"\n{i}. {item['link']}"
                if item.get('characteristics'):
                    items_preview += f"\n   📌 {item['characteristics']}"
            
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
        
        # АДМИН-КНОПКИ
        if chat_id == ADMIN_ID:
            if data.startswith('accept_') or data.startswith('reject_'):
                order_id = data.split('_')[1]
                status = "Принят" if data.startswith('accept_') else "Отклонён"
                if update_order_status(order_id, status):
                    orders = load_orders()
                    if str(order_id) in orders:
                        user_id = orders[str(order_id)]['user_id']
                        send_message(user_id, f"📢 Статус вашего заказа №{order_id} изменён на: *{status}*")
                    send_message(chat_id, f"✅ Заказ №{order_id} {status.lower()}")
                    orders = load_orders()
                    if str(order_id) in orders:
                        send_message(chat_id, format_order_details(order_id, orders[str(order_id)]))
                else:
                    send_message(chat_id, f"❌ Заказ №{order_id} не найден")
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
📞 **Контакты заказчика №{order_id}**

👤 Имя: {order.get('name', '-')}
🆔 Telegram: @{username} (ID: {user_id})
📱 Телефон: +{phone}

💡 Вы можете:
• Написать в Telegram: https://t.me/{username}
• Позвонить по телефону: +{phone}
"""
                    send_message(chat_id, text)
                else:
                    send_message(chat_id, f"❌ Заказ №{order_id} не найден")
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
        
        # ПОЛЬЗОВАТЕЛЬСКИЕ КНОПКИ
        if data == 'new_order':
            user_states[chat_id] = {
                'step': 1,
                'data': {}
            }
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
                order_data = state.get('data', {})
                
                if not order_data.get('items'):
                    send_message(chat_id, "❌ Нет добавленных товаров. Начните заказ заново.")
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
                    'status': 'Новый',
                    'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                save_order(order)
                
                items_summary = ""
                for i, item in enumerate(order['items'], 1):
                    items_summary += f"\n{i}. {item['link']}"
                    if item.get('characteristics'):
                        items_summary += f"\n   📌 {item['characteristics']}"
                
                send_message(chat_id, f"""
✅ **Заказ №{order_id} оформлен!**

📦 **Ваши товары:**{items_summary}

📞 **Контакты:**
👤 Имя: {order['name']}
📱 Телефон: +{order['phone']}
🏠 Адрес: {order['address']}

Спасибо! Администратор свяжется с вами в ближайшее время.
Номер заказа: **{order_id}**
""")
                
                send_order_to_admin(order)
                user_states.pop(chat_id, None)
                
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})

# ========== ОСНОВНОЙ ЦИКЛ ==========
def main():
    global last_update_id
    logger.info("Бот запущен!")
    send_message(ADMIN_ID, "Бот успешно запущен!")
    
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
                        logger.error(f"Ошибка обработки обновления: {e}")
            else:
                logger.error(f"Ошибка API: {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.warning("Таймаут запроса, продолжаем...")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    main()
