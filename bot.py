import requests
import json
import os
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# ========== НАСТРОЙКИ ==========
# Сначала пытаемся взять токен из переменной окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Если не нашлось — пробуем прочитать из файла .env
if not BOT_TOKEN:
    try:
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("BOT_TOKEN="):
                    BOT_TOKEN = line.strip().split("=", 1)[1]
                    break
    except:
        pass

# Если всё равно нет — вставляем токен прямо здесь (временно!)
if not BOT_TOKEN:
    BOT_TOKEN = "8784207665:AAFWCkHSD1p2qKEJj76sknIUOPKYw8sXo3E"  # <-- ВСТАВЬ СВОЙ ТОКЕН СЮДА

ADMIN_ID = 8296841503

if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден")
    exit(1)
# ================================

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
    orders = load_orders()
    if str(oid) in orders:
        del orders[str(oid)]
        with open(orders_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
        return True
    return False

def clear_all_orders():
    with open(orders_file, 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = keyboard
    requests.post(f"{API_URL}/sendMessage", json=data)

user_states = {}

def process_update(update):
    global last_update_id
    last_update_id = update['update_id']

    if 'message' in update:
        msg = update['message']
        chat_id = msg['chat']['id']
        text = msg.get('text', '')

        # Команды админа
        if chat_id == ADMIN_ID and text.startswith('/'):
            if text == '/list_orders':
                orders = load_orders()
                if not orders:
                    send_message(chat_id, "📭 Список заказов пуст.")
                    return
                recent = list(orders.keys())[-10:]
                result = "📋 Последние заказы:\n\n"
                for oid in reversed(recent):
                    order = orders[oid]
                    result += f"🔹 Заказ №{oid}\n   Клиент: {order.get('user_name', '-')}\n   Создан: {order.get('created', '-')[:16]}\n\n"
                send_message(chat_id, result)
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
                except ValueError:
                    send_message(chat_id, "❌ Номер должен быть числом.")
                return
            
            elif text == '/clear_orders':
                clear_all_orders()
                send_message(chat_id, "🗑️ Все заказы удалены.")
                return
            
            elif text == '/start':
                send_message(chat_id, "👋 Привет, админ! Доступные команды:\n/list_orders - список заказов\n/delete_order N - удалить заказ №N\n/clear_orders - удалить все заказы")
                return

        # Обработка клиентов
        if text == '/start':
            keyboard = {"inline_keyboard": [[{"text": "🛒 Новый заказ", "callback_data": "new"}]]}
            send_message(chat_id, "👋 Бот готов!\nНажмите «Новый заказ»:", keyboard)
            user_states.pop(chat_id, None)
            return

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
                'link': state['link'],
                'name': state['name'],
                'address': state['address'],
                'phone': text,
                'status': 'Принят',
                'created': datetime.now().isoformat()
            }
            save_order(num, order)
            send_message(chat_id, f"✅ Заказ №{num} принят!\nСпасибо, администратор свяжется с вами.")
            admin_text = f"🛒 НОВЫЙ ЗАКАЗ №{num}\n\nКлиент: {msg['chat'].get('first_name', '')}\nСсылка: {state['link']}\nИмя: {state['name']}\nАдрес: {state['address']}\nТелефон: {text}"
            requests.post(f"{API_URL}/sendMessage", json={"chat_id": ADMIN_ID, "text": admin_text})
            user_states.pop(chat_id, None)

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
    while True:
        try:
            response = requests.get(f"{API_URL}/getUpdates", params={"offset": last_update_id + 1, "timeout": 30})
            updates = response.json().get('result', [])
            for update in updates:
                process_update(update)
        except Exception as e:
            print(f"Ошибка: {e}")
        time.sleep(1)

f __name__ == "__main__":
    # Запускаем Flask в отдельном потоке, чтобы Render видел порт
    def run_flask():
        app.run(host='0.0.0.0', port=8080)
    
    Thread(target=run_flask).start()
    
    # Запускаем основного бота
    main()
