print("Bot is starting...")

import requests
import os
import time
from flask import Flask
from threading import Thread

BOT_TOKEN = "8646996759:AAH1D-xXzOekPUs2G1hr-90jcxjX_D5BYwg"
ADMIN_ID = 8296841503

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
last_update_id = 0

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask).start()

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

print("Bot started! Send /start to test")

def main():
    global last_update_id
    while True:
        try:
            response = requests.get(f"{API_URL}/getUpdates", params={"offset": last_update_id + 1, "timeout": 10})
            updates = response.json().get('result', [])
            for update in updates:
                last_update_id = update['update_id']
                if 'message' in update:
                    msg = update['message']
                    chat_id = msg['chat']['id']
                    text = msg.get('text', '')
                    if text == '/start':
                        send_message(chat_id, "Hello! Bot is working!")
                    elif chat_id == ADMIN_ID:
                        send_message(chat_id, f"Received: {text}")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
