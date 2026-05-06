import requests
import json
import os
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# ========== ТОКЕН ВСТАВЬ СВОЙ ==========
BOT_TOKEN = "8784207665:AAFWCkHSD1p2qKEJj76sknIUOPKYw8sXo3E"
ADMIN_ID = 8296841503
# ======================================

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

def load_orders():
    """Загружает все заказы из файла"""
    if os.path.exists(orders_file):
        with open(orders_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_order(oid, data):
    orders = load_orders()
    orders[str(oid)] = data
    with open(orders_file, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

def delete_order(oid):
    """Удаляет заказ по номеру"""
    orders = load_orders()
    if str(oid) in orders:
        del orders[str(oid)]
        with open(orders_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
        return True
    return False

def clear_all_orders():
    """Удаляет ВСЕ заказы"""
    with open(orders_file, 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

def get_orders_list():
    """Возвращает список последних 10 заказов для админа"""
    orders = load_orders()
    if not orders:
        return "📭 Список заказов пуст."
    
    # Сортируем по номеру заказа (по убыванию - новые сверху)
    sorted_orders = sorted(orders.items(), key=lambda x: int(x[0]), reverse=True)
    recent = sorted_orders[:10]
    
    result = "📋 **Последние заказы:**\n\n"
    for oid, order in recent:
        result += f"🔹 **Заказ №{oid}**\n"
        result += f"   👤 Клиент: {order.get('user_name', '-')}\n"
        result += f"   📅 Создан: {order.get('created', '-')[:16]}\n"
        result += f"   📞 Телефон: {order.get('phone', '-')}\n\n"
    return result

def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = keyboard
    requests.post(f"{API_URL}/sendMessage", json=data)

user_states = {}

# Множество для отслеживания обработанных update_id
processed_updates = set()

def process_update(update):
    global last_update_id
    
    update_id = update['update_id']
    
    # Если это обновление уже обработано - пропускаем
    if update_id in processed_updates:
        return
    
    # Добавляем в обработанные
    processed_updates.add(update_id)
    
    # Ограничиваем размер множества (оставляем последние 1000)
    if len(processed_updates) > 1000:
        to_remove = list(processed_updates)[:500]
        for uid in to_remove:
            processed_updates.discard(uid)
    
    last_update_id = update_id

    # Обработка обычных сообщений
    if 'message' in update:
        msg = update['message']
        chat_id = msg['chat']['id']
        text = msg.get('text', '')

        # ===== АДМИН-КОМАНДЫ =====
        if chat_id == ADMIN_ID and text.startswith('/'):
            if text == '/list_orders':
                result = get_orders_list()
                send_message(chat_id, result)
                return
            
            elif text.startswith('/delete_order'):
                parts = text.split()
                if len(parts) != 2:
                    send_message(chat_id, "❌ Использование: `/delete_order НОМЕР`")
                    return
                try:
                    oid = int(parts[1])
                    if delete_order(oid):
                        send_message(chat_id, f"✅ Заказ №{oid} удалён.")
                    else:
                        send_message(chat_id, f"❌ Заказ №{oid} не найден.")
                except ValueError:
                    send_message(chat_id, "❌ Номер должен быть числом.")
                return
            
            elif text == '/clear_orders':
                clear_all_orders()
                send_message(chat_id, "🗑️ **ВСЕ заказы удалены!**")
                return
            
            elif text == '/start':
                help_text = """👋 Привет, админ!

📋 **Доступные команды:**

`/list_orders` - список последних 10 заказов
`/delete_order N` - удалить заказ №N
`/clear_orders` - удалить ВСЕ заказы

📌 Пример: `/delete_order 101`"""
                send_message(chat_id, help_text)
                return

        # ===== КЛИЕНТСКИЕ КОМАНДЫ =====
        if text == '/start':
            keyboard = {"inline_keyboard": [[{"text": "🛒 Новый заказ", "callback_data": "new"}]]}
            send_message(chat_id, "👋 Бот готов!\nНажмите «Новый заказ», чтобы оформить заказ:", keyboard)
            user_states.pop(chat_id, None)
            return

        # Обработка шагов оформления заказа
        state = user_states.get(chat_id, {})
        step = state.get('step', 0)

        if step == 1:
            state['link'] = text
            state['step'] = 2
            user_states[chat_id] = state
            send_message(chat_id, "2️⃣ Напишите ваше имя:")
        elif step == 2:
            state['name'] = text
            state['step'] = 3
            user_states[chat_id] = state
            send_message(chat_id, "3️⃣ Укажите адрес доставки:")
        elif step == 3:
            state['address'] = text
            state['step'] = 4
            user_states[chat_id] = state
            send_message(chat_id, "4️⃣ Укажите номер телефона:")
        elif step == 4:
            state['phone'] = text
            num = get_num()
            order = {
                'id': num,
                'user_id': chat_id,
                'user_name': msg['chat'].get('first_name', ''),
                'user_username': msg['chat'].get('username', ''),
                'link': state['link'],
                'name': state['name'],
                'address': state['address'],
                'phone': text,
                'status': 'Принят',
                'created': datetime.now().isoformat()
            }
            save_order(num, order)
            send_message(chat_id, f"✅ **Заказ №{num} принят!**\n\nСпасибо, администратор свяжется с вами.")
            
            # Отправка админу
            admin_text = f"""🛒 **НОВЫЙ ЗАКАЗ №{num}**

👤 Клиент: {msg['chat'].get('first_name', '')}
🔗 Ссылка: {state['link']}
📝 Имя: {state['name']}
📍 Адрес: {state['address']}
📞 Телефон: {text}

📅 Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
            requests.post(f"{API_URL}/sendMessage", json={"chat_id": ADMIN_ID, "text": admin_text})
            user_states.pop(chat_id, None)

    # Обработка нажатий на кнопки
    elif 'callback_query' in update:
        cb = update['callback_query']
        chat_id = cb['message']['chat']['id']
        data = cb['data']

        if data == 'new':
            user_states[chat_id] = {'step': 1}
            send_message(chat_id, "1️⃣ Отправьте ссылку на товар:")
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})

def main():
    global last_update_id
    print("🚀 Бот запущен!")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("📋 Команды админа: /list_orders, /delete_order N, /clear_orders")
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
