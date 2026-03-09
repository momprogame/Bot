#!/usr/bin/env python3
"""
Bot de Telegram simple para GitHub Actions
"""
import os
import logging
import requests
import time
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
        
    def get_updates(self):
        """Obtiene nuevos mensajes"""
        url = f"{self.base_url}/getUpdates"
        params = {
            'offset': self.offset,
            'timeout': 30,
            'allowed_updates': ['message']
        }
        
        try:
            response = requests.get(url, params=params, timeout=35)
            response.raise_for_status()
            return response.json().get('result', [])
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []
    
    def send_message(self, chat_id, text):
        """Envía un mensaje"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        try:
            requests.post(url, json=payload)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    def handle_message(self, message):
        """Procesa los mensajes recibidos"""
        chat_id = message['chat']['id']
        text = message.get('text', '')
        first_name = message['from'].get('first_name', 'Usuario')
        
        # Comandos disponibles
        if text.startswith('/start'):
            welcome = f"""👋 ¡Hola {first_name}!

Soy un bot simple ejecutándose en GitHub Actions.

Comandos disponibles:
/start - Mensaje de bienvenida
/time - Hora actual
/echo [mensaje] - Repite tu mensaje

¿En qué puedo ayudarte?"""
            self.send_message(chat_id, welcome)
            
        elif text.startswith('/time'):
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.send_message(chat_id, f"🕐 Hora actual: {current_time}")
            
        elif text.startswith('/echo'):
            # Extraer el mensaje después de /echo
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                echo_text = parts[1]
                self.send_message(chat_id, f"📢 Dijiste: {echo_text}")
            else:
                self.send_message(chat_id, "Por favor, escribe algo después de /echo")
                
        elif text.startswith('/'):
            self.send_message(chat_id, "❌ Comando no reconocido. Usa /start para ver los comandos disponibles.")
    
    def run(self):
        """Bucle principal del bot"""
        logger.info("Bot iniciado!")
        
        while True:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    if 'message' in update:
                        self.handle_message(update['message'])
                        self.offset = update['update_id'] + 1
                
                # Pequeña pausa para no saturar la API
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Bot detenido manualmente")
                break
            except Exception as e:
                logger.error(f"Error en el bucle principal: {e}")
                time.sleep(5)

if __name__ == "__main__":
    # Obtener token de variables de entorno
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        logger.error("No se encontró TELEGRAM_BOT_TOKEN en las variables de entorno")
        exit(1)
    
    # Iniciar bot
    bot = SimpleBot(TOKEN)
    bot.run()
