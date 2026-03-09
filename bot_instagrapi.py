#!/usr/bin/env python3
"""
Bot de Telegram para descargar videos de Instagram usando cookies.txt
"""
import os
import logging
import requests
import tempfile
import shutil
import re
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Token de Telegram desde variable de entorno
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

class InstagramDownloader:
    def __init__(self):
        self.cookies_file = 'cookies.txt'
        self.ytdlp_path = 'yt-dlp'  # Asume que yt-dlp está en PATH
        
    def check_cookies(self):
        """Verifica si existe el archivo de cookies"""
        if os.path.exists(self.cookies_file):
            with open(self.cookies_file, 'r') as f:
                content = f.read()
                if 'sessionid' in content:
                    logger.info("✅ Cookies encontradas y válidas")
                    return True
        logger.warning("⚠️ No hay cookies válidas")
        return False
    
    def extract_instagram_url(self, text):
        """Extrae URL de Instagram del texto"""
        pattern = r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[^\s]+)'
        match = re.search(pattern, text)
        return match.group(1) if match else None
    
    def download_video(self, url):
        """Descarga video usando yt-dlp con cookies"""
        temp_dir = tempfile.mkdtemp()
        try:
            logger.info(f"Descargando: {url}")
            
            import subprocess
            
            # Comando yt-dlp para obtener info y descargar
            cmd = [
                'yt-dlp',
                '--cookies', self.cookies_file,
                '--no-warnings',
                '--no-playlist',
                '-f', 'best[ext=mp4]/best',
                '-o', os.path.join(temp_dir, '%(title)s.%(ext)s'),
                url
            ]
            
            # Ejecutar descarga
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                logger.error(f"Error en yt-dlp: {result.stderr}")
                return None, None, None
            
            # Buscar el archivo descargado
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and file_path.endswith(('.mp4', '.mov', '.mkv')):
                    logger.info(f"✅ Video descargado: {file}")
                    return file_path, "Video descargado de Instagram", temp_dir
            
            return None, None, None
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout en la descarga")
            return None, None, None
        except Exception as e:
            logger.error(f"Error descargando: {e}")
            return None, None, None
    
    def cleanup(self, temp_dir):
        """Limpia archivos temporales"""
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

# Instancia global
downloader = InstagramDownloader()

# Handlers de Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "🤖 <b>Bot Descargador de Instagram</b>\n\n"
        "📥 <b>Cómo usar:</b>\n"
        "Simplemente envíame cualquier enlace de Instagram y descargaré el video.\n\n"
        "📱 <b>Enlaces soportados:</b>\n"
        "• Reels: instagram.com/reel/...\n"
        "• Posts: instagram.com/p/...\n"
        "• IGTV: instagram.com/tv/...\n\n"
        "✅ <b>Estado de cookies:</b> " + ("✓ Activas" if downloader.check_cookies() else "✗ No configuradas"),
        parse_mode='HTML'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    help_text = """
📖 <b>AYUDA - Bot Instagram</b>

<b>Comandos:</b>
/start - Mensaje de bienvenida
/help - Esta ayuda
/status - Ver estado de las cookies
/time - Hora actual

<b>Para descargar:</b>
Envía cualquier enlace de Instagram y el bot procesará la descarga automáticamente.

<b>Ejemplos:</b>
• https://www.instagram.com/reel/CxGQxL7IU8U/
• https://instagram.com/p/CxGQxL7IU8U/

<b>Nota:</b> El bot usa cookies para acceder a videos públicos y privados (si tienes acceso)
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica estado de las cookies"""
    if downloader.check_cookies():
        await update.message.reply_text("✅ <b>Cookies activas</b>\nEl bot puede descargar videos sin problemas.", parse_mode='HTML')
    else:
        await update.message.reply_text(
            "❌ <b>Cookies no configuradas</b>\n"
            "Las descargas pueden fallar. Contacta al administrador.",
            parse_mode='HTML'
        )

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la hora actual"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"🕐 Hora actual: {current_time}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa mensajes con URLs"""
    text = update.message.text
    
    # Verificar si es URL de Instagram
    url = downloader.extract_instagram_url(text)
    
    if url:
        await update.message.reply_text("🔄 Procesando enlace...")
        
        # Verificar cookies primero
        if not downloader.check_cookies():
            await update.message.reply_text("⚠️ Cookies no configuradas. Intentando descarga sin cookies...")
        
        # Enviar acción "typing"
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        # Descargar video
        video_path, caption, temp_dir = downloader.download_video(url)
        
        if video_path:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_video')
            
            try:
                with open(video_path, 'rb') as f:
                    await update.message.reply_video(
                        video=f,
                        caption="📥 Video descargado de Instagram",
                        supports_streaming=True
                    )
                await update.message.reply_text("✅ ¡Descarga completada!")
            except Exception as e:
                logger.error(f"Error enviando video: {e}")
                await update.message.reply_text("❌ Error al enviar el video")
            
            # Limpiar
            downloader.cleanup(temp_dir)
        else:
            await update.message.reply_text(
                "❌ No pude descargar el video.\n"
                "Posibles causas:\n"
                "• El enlace no es válido\n"
                "• El video es privado\n"
                "• Las cookies expiraron"
            )
    else:
        # Si no es URL de Instagram, ignorar
        pass

def main():
    """Función principal"""
    if not TELEGRAM_TOKEN:
        logger.error("❌ No se encontró TELEGRAM_BOT_TOKEN")
        return
    
    # Verificar cookies al inicio
    if downloader.check_cookies():
        logger.info("✅ Cookies cargadas correctamente")
    else:
        logger.warning("⚠️ No hay cookies. Las descargas pueden fallar")
    
    # Crear aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Añadir handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Bot iniciado!")
    app.run_polling()

if __name__ == "__main__":
    main()
