import requests
import json
import os
import time
from datetime import datetime
from flask import Flask
from threading import Thread

print("1. Бот начинает загрузку...")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не установлен!")
    raise Exception("Ошибка: переменная окружения BOT_TOKEN не установлена!")

print(f"2. Токен загружен: {BOT_TOKEN[:10]}...")

ADMIN_ID = int(os.getenv("ADMIN_ID", "8296841503"))
print(f"3. ADMIN_ID: {ADMIN_ID}")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
last_update_id = 0
user_states = {}

print("4. Создаю Flask приложение...")
app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

@app.route('/ping')
def ping():
    return "ok"

def run_flask():
    print("5. Запускаю Flask сервер...")
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask).start()
print("6. Flask сервер запущен в фоне")

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
    try:
        response = requests.post(f"{API_URL}/sendMessage", json=data)
        print(f"📤 Отправлено сообщение в {chat_id}")
        return response
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return None

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
    
    result = "📋 **Список заказов:**\n\n"
    for oid, order in recent:
        status_emoji = {
            'Новый': '🆕',
            'Принят': '✅',
            'Отклонён': '❌',
            'В обработке': '🔄',
            'Доставлен': '📦'
        }.get(order.get('status', 'Новый'), '📌')
        
        result += f"{status_emoji} **Заказ №{oid}** | {order.get('status', 'Новый')}\n"
        result += f"   👤 {order.get('name', '-')}\n"
        result += f"   📅 {order.get('created', '-')[:16]}\n\n"
    return result

def get_order_details(oid):
    orders = load_orders()
    if str(oid) not in orders:
        return f"❌ Заказ №{oid} не найден"
    
    order = orders[str(oid)]
    items_text = ""
    for i, item in enumerate(order.get('items', []), 1):
        items_text += f"\n{i}. Ссылка: {item['link']}"
        if item.get('characteristics'):
            items_text += f"\n   Характеристики: {item['characteristics']}"
    
    text = f"""
📦 **ЗАКАЗ №{oid}**

👤 **Клиент:** {order.get('name', '-')}
🆔 **Telegram:** @{order.get('username', '-')} (ID: {order.get('user_id', '-')})
📱 **Телефон:** {order.get('phone', '-')}
🏠 **Адрес:** {order.get('address', '-')}

📦 **Товары:**{items_text}

📅 **Создан:** {order.get('created', '-')}
📊 **Статус:** {order.get('status', 'Новый')}
"""
    return text

def admin_panel(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "📋 Список заказов", "callback_data": "admin_list"}],
            [{"text": "🔍 Посмотреть заказ", "callback_data": "admin_view"}],
            [{"text": "📊 Изменить статус", "callback_data": "admin_status"}],
            [{"text": "🗑️ Удалить заказ", "callback_data": "admin_delete"}],
            [{"text": "🧹 Очистить все заказы", "callback_data": "admin_clear"}]
        ]
    }
    send_message(chat_id, "👋 **Админ-панель**\n\nВыберите действие:", keyboard)

def process_update(update):
    global last_update_id
    update_id = update['update_id']
    if update_id <= last_update_id:
        return
    last_update_id = update_id

    print(f"📩 Получено обновление: {update_id}")

    # ===== ОБРАБОТКА CALLBACK_QUERY (КНОПКИ) =====
    if 'callback_query' in update:
        cb = update['callback_query']
        chat_id = cb['message']['chat']['id']
        data = cb['data']
        message_id = cb['message']['message_id']
        
        print(f"🔘 Кнопка от {chat_id}: {data}")

        # ===== АДМИН-ПАНЕЛЬ =====
        if chat_id == ADMIN_ID:
            
            # Кнопка "Список заказов"
            if data == 'admin_list':
                send_message(chat_id, get_orders_list())
                admin_panel(chat_id)
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            # Кнопка "Посмотреть заказ"
            elif data == 'admin_view':
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🔙 Назад", "callback_data": "admin_back"}]
                    ]
                }
                send_message(chat_id, "✏️ Введите номер заказа для просмотра:", keyboard)
                user_states[chat_id] = {'admin_action': 'view'}
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            # Кнопка "Изменить статус"
            elif data == 'admin_status':
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🆕 Новый", "callback_data": "status_new"}],
                        [{"text": "✅ Принят", "callback_data": "status_accepted"}],
                        [{"text": "🔄 В обработке", "callback_data": "status_processing"}],
                        [{"text": "📦 Доставлен", "callback_data": "status_delivered"}],
                        [{"text": "❌ Отклонён", "callback_data": "status_rejected"}],
                        [{"text": "🔙 Назад", "callback_data": "admin_back"}]
                    ]
                }
                send_message(chat_id, "📊 Выберите статус для заказа:\n\nСначала введите номер заказа", keyboard)
                user_states[chat_id] = {'admin_action': 'status'}
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            # Кнопка "Удалить заказ"
            elif data == 'admin_delete':
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🔙 Назад", "callback_data": "admin_back"}]
                    ]
                }
                send_message(chat_id, "🗑️ Введите номер заказа для удаления:", keyboard)
                user_states[chat_id] = {'admin_action': 'delete'}
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            # Кнопка "Очистить все заказы"
            elif data == 'admin_clear':
                clear_all_orders()
                send_message(chat_id, "🗑️ Все заказы удалены!")
                admin_panel(chat_id)
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            # Кнопка "Назад"
            elif data == 'admin_back':
                admin_panel(chat_id)
                user_states.pop(chat_id, None)
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            # Выбор статуса
            elif data.startswith('status_'):
                status_map = {
                    'new': 'Новый',
                    'accepted': 'Принят',
                    'processing': 'В обработке',
                    'delivered': 'Доставлен',
                    'rejected': 'Отклонён'
                }
                status = status_map.get(data.split('_')[1], 'Новый')
                
                # Сохраняем выбранный статус в состояние
                state = user_states.get(chat_id, {})
                state['admin_action'] = 'status'
                state['status_value'] = status
                user_states[chat_id] = state
                
                send_message(chat_id, f"✅ Выбран статус: {status}\n\n✏️ Введите номер заказа:")
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            # Обработка кнопок принятия/отклонения заказа
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
            
            # Кнопка "Связаться"
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

        # ===== ПОЛЬЗОВАТЕЛЬСКИЕ КНОПКИ =====
        if data == 'new':
            user_states[chat_id] = {'step': 1, 'data': {}}
            send_message(chat_id, "👤 Введите ваше имя:")
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
            return
        
        elif data == 'add_item':
            state = user_states.get(chat_id, {})
            if state and state.get('step') == 6:
                state['step'] = 4
                user_states[chat_id] = state
                send_message(chat_id, "🔗 Отправьте ссылку на следующий товар:")
            else:
                send_message(chat_id, "❌ Сначала добавьте товар")
            requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
            return
        
        elif data == 'finish_order':
            print("🔴 Нажата кнопка Завершить заказ!")
            state = user_states.get(chat_id)
            
            if not state:
                send_message(chat_id, "❌ У вас нет активного заказа. Напишите /start")
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            if state.get('step') != 6:
                send_message(chat_id, "❌ Сначала добавьте товар")
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            order_data = state.get('data', {})
            
            # Проверяем, есть ли данные
            if not order_data.get('name'):
                send_message(chat_id, "❌ Ошибка: не заполнены данные. Начните заново.")
                user_states.pop(chat_id, None)
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            if not order_data.get('items'):
                send_message(chat_id, "❌ Нет добавленных товаров. Начните заново.")
                user_states.pop(chat_id, None)
                requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": cb['id']})
                return
            
            # Создаём заказ
            num = get_num()
            order = {
                'id': num,
                'user_id': chat_id,
                'username': cb['message']['chat'].get('username', ''),
                'name': order_data.get('name', ''),
                'phone': order_data.get('phone', ''),
                'address': order_data.get('address', ''),
                'items': order_data.get('items', []),
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
            return

    # ===== ОБРАБОТКА СООБЩЕНИЙ =====
    if 'message' in update:
        msg = update['message']
        chat_id = msg['chat']['id']
        text = msg.get('text', '')
        
        print(f"💬 Сообщение от {chat_id}: {text}")
        print(f"🔍 ADMIN_ID: {ADMIN_ID}, chat_id: {chat_id}")

        # ===== ОБРАБОТКА /start ДЛЯ ВСЕХ =====
        if text == '/start':
            print("🆕 Команда /start получена!")
            
            # Проверяем, админ ли это
            if chat_id == ADMIN_ID:
                print("👑 Это админ! Показываю админ-панель")
                admin_panel(chat_id)
                user_states.pop(chat_id, None)
                return
            else:
                print("👤 Это пользователь! Показываю приветствие")
                keyboard = {"inline_keyboard": [[{"text": "🛒 Новый заказ", "callback_data": "new"}]]}
                send_message(chat_id, "👋 Бот готов!\nНажмите «Новый заказ», чтобы оформить заказ:", keyboard)
                user_states.pop(chat_id, None)
                return

        # ===== АДМИН-КОМАНДЫ (кроме /start) =====
        if chat_id == ADMIN_ID and text.startswith('/'):
            print("👑 Админ-команда:", text)
            
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
            elif text.startswith('/status'):
                parts = text.split()
                if len(parts) < 3:
                    send_message(chat_id, "❌ Использование: /status НОМЕР СТАТУС")
                    return
                try:
                    oid = int(parts[1])
                    status = ' '.join(parts[2:])
                    orders = load_orders()
                    if str(oid) in orders:
                        orders[str(oid)]['status'] = status
                        with open("orders.json", 'w', encoding='utf-8') as f:
                            json.dump(orders, f, ensure_ascii=False, indent=2)
                        send_message(chat_id, f"✅ Статус заказа №{oid} изменён на: {status}")
                        user_id = orders[str(oid)]['user_id']
                        send_message(user_id, f"📢 Статус вашего заказа №{oid} изменён на: *{status}*")
                    else:
                        send_message(chat_id, f"❌ Заказ №{oid} не найден")
                except:
                    send_message(chat_id, "❌ Номер должен быть числом.")
                return
            return

        # ===== ПРОЦЕСС ЗАКАЗА =====
        state = user_states.get(chat_id, {})
        step = state.get('step', 0)
        order_data = state.get('data', {})
        
        print(f"📋 Шаг: {step}, состояние: {state}")

        if step == 1:
            order_data['name'] = text
            state['step'] = 2
            state['data'] = order_data
            user_states[chat_id] = state
            send_message(chat_id, "📱 Отправьте ваш номер телефона (только цифры):")
        elif step == 2:
            phone = ''.join(filter(str.isdigit, text))
            if len(phone) < 10:
                send_message(chat_id, "❌ Введите корректный номер телефона (минимум 10 цифр):")
                return
            order_data['phone'] = phone
            state['step'] = 3
            state['data'] = order_data
            user_states[chat_id] = state
            send_message(chat_id, "🏠 Введите ваш адрес (город, улица, дом, квартира):")
        elif step == 3:
            order_data['address'] = text
            state['step'] = 4
            state['data'] = order_data
            user_states[chat_id] = state
            send_message(chat_id, "🔗 Отправьте ссылку на товар:")
        elif step == 4:
            if not text.startswith(('http://', 'https://')):
                send_message(chat_id, "❌ Это не похоже на ссылку. Отправьте корректную ссылку:")
                return
            if 'items' not in order_data:
                order_data['items'] = []
            order_data['items'].append({'link': text, 'characteristics': ''})
            state['step'] = 5
            state['data'] = order_data
            user_states[chat_id] = state
            send_message(chat_id, "📝 Опишите характеристики товара (размер, цвет, количество и т.д.):")
        elif step == 5:
            if len(order_data['items']) > 0:
                order_data['items'][-1]['characteristics'] = text
            
            items_preview = ""
            for i, item in enumerate(order_data['items'], 1):
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
            state['data'] = order_data
            user_states[chat_id] = state
            send_message(chat_id, f"""
✅ Товар добавлен!

📦 **Ваши товары:**{items_preview}

Что делаем дальше?
""", keyboard)
        else:
            # Если состояние не определено, но бот получил сообщение
            if text and text != '/start':
                send_message(chat_id, "❌ Неизвестная команда. Напишите /start чтобы начать.")
        
        # ===== ОБРАБОТКА ТЕКСТОВЫХ ВВОДОВ АДМИНА =====
        # Проверяем, есть ли у админа активное действие
        if chat_id == ADMIN_ID:
            state = user_states.get(chat_id, {})
            admin_action = state.get('admin_action')
            
            if admin_action == 'view':
                try:
                    oid = int(text.strip())
                    send_message(chat_id, get_order_details(oid))
                    user_states.pop(chat_id, None)
                    admin_panel(chat_id)
                except:
                    send_message(chat_id, "❌ Введите корректный номер заказа (только цифры)")
                return
            
            elif admin_action == 'delete':
                try:
                    oid = int(text.strip())
                    if delete_order(oid):
                        send_message(chat_id, f"✅ Заказ №{oid} удалён.")
                    else:
                        send_message(chat_id, f"❌ Заказ №{oid} не найден.")
                    user_states.pop(chat_id, None)
                    admin_panel(chat_id)
                except:
                    send_message(chat_id, "❌ Введите корректный номер заказа (только цифры)")
                return
            
            elif admin_action == 'status':
                try:
                    oid = int(text.strip())
                    orders = load_orders()
                    if str(oid) in orders:
                        status = state.get('status_value', 'Новый')
                        orders[str(oid)]['status'] = status
                        with open("orders.json", 'w', encoding='utf-8') as f:
                            json.dump(orders, f, ensure_ascii=False, indent=2)
                        user_id = orders[str(oid)]['user_id']
                        send_message(user_id, f"📢 Статус вашего заказа №{oid} изменён на: *{status}*")
                        send_message(chat_id, f"✅ Статус заказа №{oid} изменён на: {status}")
                    else:
                        send_message(chat_id, f"❌ Заказ №{oid} не найден")
                    user_states.pop(chat_id, None)
                    admin_panel(chat_id)
                except:
                    send_message(chat_id, "❌ Введите корректный номер заказа (только цифры)")
                return

def main():
    global last_update_id
    print("🚀 Бот запущен!")
    
    # Отправляем приветствие админу
    send_message(ADMIN_ID, "✅ Бот успешно запущен!")
    
    while True:
        try:
            response = requests.get(f"{API_URL}/getUpdates", params={"offset": last_update_id + 1, "timeout": 30})
            if response.status_code == 200:
                updates = response.json().get('result', [])
                if updates:
                    print(f"📨 Получено {len(updates)} обновлений")
                for update in updates:
                    process_update(update)
            else:
                print(f"❌ Ошибка API: {response.status_code}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()

