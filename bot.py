#!/usr/bin/env python3
"""
Bot de Telegram que descarga videos de Instagram
Usa yt-dlp para la descarga (soporta Reels, Posts, IGTV)
"""
import os
import logging
import requests
import time
import re
import asyncio
from datetime import datetime
from yt_dlp import YoutubeDL
import tempfile
import shutil

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class InstagramDownloaderBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
        
        # Configuración de yt-dlp para Instagram
        self.ydl_opts = {
            'format': 'best[ext=mp4]/best',  # Mejor calidad MP4
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': True,
            'no_color': True,
            'cookiefile': None,  # Opcional: archivo con cookies para contenido privado
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
    
    def is_instagram_url(self, text):
        """Verifica si el texto contiene una URL de Instagram"""
        instagram_patterns = [
            r'https?://(www\.)?instagram\.com/(p|reel|tv)/[\w-]+',
            r'https?://(www\.)?instagram\.com/stories/[\w-]+/[\d]+',
            r'https?://instagr\.am/(p|reel|tv)/[\w-]+'
        ]
        
        for pattern in instagram_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def extract_url(self, text):
        """Extrae la primera URL de Instagram del texto"""
        instagram_pattern = r'(https?://(?:www\.)?(?:instagram\.com|instagr\.am)/(?:p|reel|tv|stories)/[^\s]+)'
        match = re.search(instagram_pattern, text, re.IGNORECASE)
        return match.group(1) if match else None
    
    def download_instagram_video(self, url):
        """Descarga un video de Instagram usando yt-dlp"""
        temp_dir = tempfile.mkdtemp()
        try:
            logger.info(f"Descargando: {url}")
            
            # Configurar opciones para esta descarga
            ydl_opts = self.ydl_opts.copy()
            ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')
            
            with YoutubeDL(ydl_opts) as ydl:
                # Extraer información
                info = ydl.extract_info(url, download=True)
                
                if info and 'entries' in info:
                    # Es una colección (varios videos)
                    info = info['entries'][0]
                
                # Buscar el archivo descargado
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        logger.info(f"Video descargado: {file}")
                        return file_path, info.get('title', 'video')
                
                return None, None
                
        except Exception as e:
            logger.error(f"Error descargando video: {e}")
            return None, None
    
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
        except requests.exceptions.HTTPError as e:
            if response.status_code == 409:
                logger.warning("Conflicto detectado - esperando 30 segundos...")
                time.sleep(30)
                return []
            logger.error(f"Error getting updates: {e}")
            return []
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
    
    def send_video(self, chat_id, video_path, caption=""):
        """Envía un video a Telegram"""
        url = f"{self.base_url}/sendVideo"
        
        try:
            with open(video_path, 'rb') as video_file:
                files = {'video': video_file}
                data = {'chat_id': chat_id, 'caption': caption}
                response = requests.post(url, data=data, files=files)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending video: {e}")
            return False
    
    def send_action(self, chat_id, action):
        """Envía una acción (typing, upload_video, etc)"""
        url = f"{self.base_url}/sendChatAction"
        payload = {'chat_id': chat_id, 'action': action}
        try:
            requests.post(url, json=payload)
        except:
            pass
    
    def handle_message(self, message):
        """Procesa los mensajes recibidos"""
        chat_id = message['chat']['id']
        text = message.get('text', '')
        first_name = message['from'].get('first_name', 'Usuario')
        
        # Comandos básicos
        if text.startswith('/start'):
            welcome = f"""👋 ¡Hola {first_name}!

Soy un bot que descarga videos de Instagram.

📱 <b>Qué puedo descargar:</b>
• Reels
• Posts con video
• IGTV
• Stories (si tienes cookies)

<b>Cómo usar:</b>
Simplemente envíame cualquier enlace de Instagram y yo descargaré el video.

<b>Ejemplos:</b>
• instagram.com/reel/ABC123/
• instagram.com/p/XYZ789/
• instagram.com/tv/DEF456/

<i>Nota: Solo funcionan videos públicos</i>"""
            self.send_message(chat_id, welcome)
            
        elif text.startswith('/help'):
            help_text = """📖 <b>Ayuda</b>

<b>Comandos:</b>
/start - Mensaje de bienvenida
/help - Esta ayuda
/time - Hora actual

<b>Para descargar:</b>
Envía cualquier enlace de Instagram y automáticamente procesaré el video.

<b>Problemas comunes:</b>
• Asegúrate que el video sea público
• Espera mientras descargo (puede tomar unos segundos)
• Si falla, intenta con otro enlace"""
            self.send_message(chat_id, help_text)
            
        elif text.startswith('/time'):
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.send_message(chat_id, f"🕐 Hora actual: {current_time}")
            
        # Procesar URLs de Instagram
        elif self.is_instagram_url(text):
            url = self.extract_url(text)
            if url:
                # Indicar que está procesando
                self.send_action(chat_id, 'typing')
                self.send_message(chat_id, "🔄 Procesando enlace de Instagram...")
                
                # Indicar que está subiendo video
                self.send_action(chat_id, 'upload_video')
                
                # Descargar el video
                video_path, title = self.download_instagram_video(url)
                
                if video_path and os.path.exists(video_path):
                    # Enviar el video
                    caption = f"📥 Descargado de Instagram\n🔗 {url}"
                    if title:
                        caption = f"📹 {title}\n{caption}"
                    
                    success = self.send_video(chat_id, video_path, caption)
                    
                    if success:
                        logger.info(f"Video enviado a {chat_id}")
                    else:
                        self.send_message(chat_id, "❌ Error al enviar el video. Intenta de nuevo.")
                    
                    # Limpiar archivo temporal
                    try:
                        os.remove(video_path)
                        shutil.rmtree(os.path.dirname(video_path))
                    except:
                        pass
                else:
                    self.send_message(chat_id, "❌ No pude descargar el video. Asegúrate que:\n• El enlace sea válido\n• El video sea público\n• Instagram no haya bloqueado la descarga")
            else:
                self.send_message(chat_id, "❌ No reconocí un enlace válido de Instagram")
        
        elif text.startswith('/'):
            self.send_message(chat_id, "❌ Comando no reconocido. Usa /start para ver los comandos disponibles.")
        
        else:
            # Si no es comando ni URL de Instagram
            self.send_message(chat_id, "❌ Envíame un enlace de Instagram para descargar el video o usa /help para ayuda.")
    
    def run(self):
        """Bucle principal del bot"""
        logger.info("🚀 Bot de Instagram iniciado!")
        
        while True:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    if 'message' in update:
                        self.handle_message(update['message'])
                        self.offset = update['update_id'] + 1
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Bot detenido manualmente")
                break
            except Exception as e:
                logger.error(f"Error en el bucle principal: {e}")
                time.sleep(5)

if __name__ == "__main__":
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        logger.error("❌ No se encontró TELEGRAM_BOT_TOKEN en las variables de entorno")
        exit(1)
    
    bot = InstagramDownloaderBot(TOKEN)
    bot.run()
