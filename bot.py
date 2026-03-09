#!/usr/bin/env python3
"""
Bot de Telegram Ultra Mejorado - Descarga de múltiples plataformas
Soporta: Instagram, TikTok, YouTube, Twitter, Facebook, Pinterest, Reddit, Threads
"""
import os
import logging
import re
import tempfile
import shutil
import subprocess
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, List, Tuple
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ChatAction

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
COOKIES_FILE = 'cookies.txt'
DB_FILE = 'bot_stats.db'

# Plataformas soportadas
PLATAFORMAS = {
    'instagram': {
        'patron': r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[^\s]+',
        'nombre': '📸 Instagram',
        'icono': '📸'
    },
    'tiktok': {
        'patron': r'(?:https?://)?(?:www\.|vm\.)?tiktok\.com/[^\s]+',
        'nombre': '🎵 TikTok',
        'icono': '🎵'
    },
    'youtube': {
        'patron': r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[^\s]+',
        'nombre': '▶️ YouTube',
        'icono': '▶️'
    },
    'twitter': {
        'patron': r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[^\s]+/status/[0-9]+',
        'nombre': '🐦 Twitter/X',
        'icono': '🐦'
    },
    'facebook': {
        'patron': r'(?:https?://)?(?:www\.)?(?:facebook\.com|fb\.watch)/[^\s]+',
        'nombre': '📘 Facebook',
        'icono': '📘'
    },
    'pinterest': {
        'patron': r'(?:https?://)?(?:www\.)?pinterest\.com/pin/[^\s]+',
        'nombre': '📌 Pinterest',
        'icono': '📌'
    },
    'reddit': {
        'patron': r'(?:https?://)?(?:www\.)?reddit\.com/r/[^/]+/comments/[^\s]+',
        'nombre': '👽 Reddit',
        'icono': '👽'
    },
    'threads': {
        'patron': r'(?:https?://)?(?:www\.)?threads\.net/@[^/]+/post/[^\s]+',
        'nombre': '🧵 Threads',
        'icono': '🧵'
    }
}

# Calidades disponibles
CALIDADES = {
    'best': {'ytdlp': 'best[ext=mp4]/best', 'nombre': '🎬 Mejor calidad'},
    '1080': {'ytdlp': 'best[height<=1080][ext=mp4]/best', 'nombre': '🎬 1080p'},
    '720': {'ytdlp': 'best[height<=720][ext=mp4]/best', 'nombre': '🎬 720p'},
    '480': {'ytdlp': 'best[height<=480][ext=mp4]/best', 'nombre': '🎬 480p'},
    '360': {'ytdlp': 'best[height<=360][ext=mp4]/best', 'nombre': '🎬 360p'},
    'audio': {'ytdlp': 'bestaudio/best', 'nombre': '🎵 Solo Audio (MP3)'}
}

class Database:
    """Maneja la base de datos SQLite"""
    
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        """Inicializa las tablas de la base de datos"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        # Tabla de usuarios
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      first_seen TIMESTAMP,
                      last_seen TIMESTAMP,
                      quality TEXT DEFAULT 'best',
                      total_downloads INTEGER DEFAULT 0)''')
        
        # Tabla de descargas
        c.execute('''CREATE TABLE IF NOT EXISTS downloads
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      platform TEXT,
                      url TEXT,
                      success BOOLEAN,
                      filesize INTEGER,
                      duration INTEGER,
                      timestamp TIMESTAMP,
                      FOREIGN KEY(user_id) REFERENCES users(user_id))''')
        
        # Tabla de estadísticas diarias
        c.execute('''CREATE TABLE IF NOT EXISTS daily_stats
                     (date TEXT PRIMARY KEY,
                      downloads INTEGER DEFAULT 0,
                      users_active INTEGER DEFAULT 0,
                      bytes_downloaded INTEGER DEFAULT 0)''')
        
        conn.commit()
        conn.close()
    
    def get_or_create_user(self, user_id, username, first_name, last_name):
        """Obtiene o crea un usuario"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        now = datetime.now().isoformat()
        
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        
        if user:
            c.execute('''UPDATE users SET 
                        last_seen = ?,
                        username = ?,
                        first_name = ?,
                        last_name = ?
                        WHERE user_id = ?''',
                     (now, username, first_name, last_name, user_id))
        else:
            c.execute('''INSERT INTO users 
                        (user_id, username, first_name, last_name, first_seen, last_seen, quality)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (user_id, username, first_name, last_name, now, now, 'best'))
        
        conn.commit()
        
        # Obtener calidad del usuario
        c.execute('SELECT quality FROM users WHERE user_id = ?', (user_id,))
        quality = c.fetchone()[0]
        
        conn.close()
        return quality
    
    def get_user_quality(self, user_id):
        """Obtiene la calidad preferida del usuario"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('SELECT quality FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 'best'
    
    def set_user_quality(self, user_id, quality):
        """Establece la calidad preferida del usuario"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('UPDATE users SET quality = ? WHERE user_id = ?', (quality, user_id))
        conn.commit()
        conn.close()
    
    def register_download(self, user_id, platform, url, success, filesize=0, duration=0):
        """Registra una descarga"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        now = datetime.now().isoformat()
        date = datetime.now().strftime('%Y-%m-%d')
        
        # Registrar descarga
        c.execute('''INSERT INTO downloads 
                    (user_id, platform, url, success, filesize, duration, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (user_id, platform, url, success, filesize, duration, now))
        
        # Actualizar contador de usuario
        c.execute('UPDATE users SET total_downloads = total_downloads + 1 WHERE user_id = ?', (user_id,))
        
        # Actualizar estadísticas diarias
        c.execute('''INSERT INTO daily_stats (date, downloads, users_active, bytes_downloaded)
                    VALUES (?, 1, 1, ?)
                    ON CONFLICT(date) DO UPDATE SET
                    downloads = downloads + 1,
                    users_active = users_active + 1,
                    bytes_downloaded = bytes_downloaded + ?''',
                 (date, filesize, filesize))
        
        conn.commit()
        conn.close()
    
    def get_stats(self, user_id=None):
        """Obtiene estadísticas generales o de usuario"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        if user_id:
            # Estadísticas de usuario
            c.execute('''SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as exitosas,
                        platform,
                        quality
                        FROM downloads d
                        JOIN users u ON d.user_id = u.user_id
                        WHERE d.user_id = ?
                        GROUP BY platform''', (user_id,))
        else:
            # Estadísticas globales
            c.execute('''SELECT 
                        COUNT(DISTINCT user_id) as total_users,
                        COUNT(*) as total_downloads,
                        SUM(filesize) as total_bytes,
                        AVG(duration) as avg_duration
                        FROM downloads
                        WHERE success = 1''')
        
        stats = c.fetchall()
        conn.close()
        return stats

class DownloadManager:
    """Maneja las descargas con yt-dlp"""
    
    def __init__(self, cookies_file):
        self.cookies_file = cookies_file
        self.active_downloads = {}
        self.download_queue = asyncio.Queue()
        self.user_qualities = {}
    
    def detect_platform(self, url):
        """Detecta la plataforma de la URL"""
        for platform, config in PLATAFORMAS.items():
            if re.search(config['patron'], url, re.IGNORECASE):
                return platform, config
        return None, None
    
    async def download(self, url: str, quality: str = 'best', user_id: int = None) -> Tuple[Optional[str], Optional[str], Optional[str], Dict]:
        """Descarga un video/audio usando yt-dlp"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Detectar plataforma
            platform, config = self.detect_platform(url)
            platform_name = config['nombre'] if config else 'Desconocida'
            
            logger.info(f"Descargando [{platform_name}]: {url[:50]}...")
            
            # Configurar opciones de yt-dlp
            quality_config = CALIDADES.get(quality, CALIDADES['best'])
            
            # Comando base
            cmd = [
                'yt-dlp',
                '--no-warnings',
                '--no-playlist',
                '--restrict-filenames',
                '-o', os.path.join(temp_dir, '%(title)s.%(ext)s')
            ]
            
            # Añadir cookies si existen
            if os.path.exists(self.cookies_file):
                cmd.extend(['--cookies', self.cookies_file])
            
            # Configurar según calidad
            if quality == 'audio':
                cmd.extend([
                    '-x', '--audio-format', 'mp3',
                    '--audio-quality', '0',
                    '-f', 'bestaudio'
                ])
            else:
                cmd.extend(['-f', quality_config['ytdlp']])
            
            # Añadir URL
            cmd.append(url)
            
            # Ejecutar descarga
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Error en yt-dlp: {stderr.decode()}")
                return None, None, None, {}
            
            # Buscar archivo descargado
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path):
                    # Obtener información del archivo
                    filesize = os.path.getsize(file_path)
                    
                    # Obtener metadata con yt-dlp
                    info_cmd = ['yt-dlp', '--dump-json', url]
                    info_process = await asyncio.create_subprocess_exec(
                        *info_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    info_stdout, _ = await info_process.communicate()
                    
                    metadata = {}
                    if info_stdout:
                        try:
                            metadata = json.loads(info_stdout)
                        except:
                            pass
                    
                    # Determinar tipo de archivo
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext in ['.mp3', '.m4a', '.ogg']:
                        file_type = 'audio'
                    elif file_ext in ['.mp4', '.mov', '.mkv', '.webm']:
                        file_type = 'video'
                    else:
                        file_type = 'document'
                    
                    return file_path, file_type, platform_name, {
                        'title': metadata.get('title', 'Video'),
                        'uploader': metadata.get('uploader', 'Desconocido'),
                        'duration': metadata.get('duration', 0),
                        'filesize': filesize,
                        'platform': platform_name
                    }
            
            return None, None, None, {}
            
        except Exception as e:
            logger.error(f"Error en descarga: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None, None, None, {}
    
    def cleanup(self, temp_dir):
        """Limpia archivos temporales"""
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

# Inicializar componentes
db = Database(DB_FILE)
downloader = DownloadManager(COOKIES_FILE)

# Handlers de Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Mensaje de bienvenida"""
    user = update.effective_user
    quality = db.get_or_create_user(
        user.id, user.username, user.first_name, user.last_name
    )
    
    welcome_text = f"""
🤖 <b>¡Bienvenido {user.first_name}!</b>

📥 <b>Bot Multi-Downloader</b>
Descarga videos de múltiples plataformas:

{chr(10).join([f"{p['icono']} {p['nombre']}" for p in PLATAFORMAS.values()])}

<b>Comandos disponibles:</b>
/start - Este mensaje
/help - Ayuda detallada
/quality - Configurar calidad
/stats - Ver estadísticas
/info [URL] - Info sin descargar
/audio [URL] - Solo audio MP3
/batch [URL1] [URL2]... - Descarga múltiple

<i>Calidad actual: {CALIDADES[quality]['nombre']}</i>
"""
    await update.message.reply_text(welcome_text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - Ayuda detallada"""
    help_text = """
📖 <b>AYUDA - Bot Multi-Downloader</b>

<b>📱 Plataformas soportadas:</b>
• Instagram (Reels, Posts, Stories)
• TikTok (Videos, Slideshows)
• YouTube (Videos, Shorts)
• Twitter/X (Videos, GIFs)
• Facebook (Videos, Reels)
• Pinterest (Pins, Videos)
• Reddit (Videos, GIFs)
• Threads (Posts)

<b>🎚️ Calidades disponibles:</b>
• Mejor calidad (automático)
• 1080p / 720p / 480p / 360p
• Solo Audio MP3

<b>📝 Cómo usar:</b>
1. Envía cualquier enlace
2. Elige calidad con /quality
3. ¡Disfruta tu descarga!

<b>📊 Estadísticas:</b>
/stats - Ver uso del bot
/info [URL] - Info del video
/batch [URLs] - Hasta 5 videos

<i>¿Sugerencias? ¡Escríbeme!</i>
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

async def quality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /quality - Configurar calidad"""
    keyboard = []
    row = []
    
    for i, (key, config) in enumerate(CALIDADES.items()):
        button = InlineKeyboardButton(config['nombre'], callback_data=f'quality_{key}')
        row.append(button)
        if len(row) == 2 or i == len(CALIDADES) - 1:
            keyboard.append(row)
            row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎚️ <b>Selecciona la calidad por defecto:</b>\n"
        "(Puedes cambiarla en cualquier momento)",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats - Ver estadísticas"""
    user = update.effective_user
    
    # Estadísticas globales
    global_stats = db.get_stats()
    
    # Estadísticas del usuario
    user_stats = db.get_stats(user.id)
    
    stats_text = f"""
📊 <b>Estadísticas del Bot</b>

<b>👤 Tus estadísticas:</b>
• Descargas totales: {sum([s[0] for s in user_stats]) if user_stats else 0}
• Calidad preferida: {CALIDADES[db.get_user_quality(user.id)]['nombre']}

<b>🌍 Estadísticas globales:</b>
• Usuarios totales: {global_stats[0][0] if global_stats else 0}
• Descargas totales: {global_stats[0][1] if global_stats else 0}
• Datos transferidos: {global_stats[0][2] / (1024*1024):.2f} MB
• Duración promedio: {global_stats[0][3] if global_stats else 0:.1f} seg

<b>📈 Por plataforma:</b>
"""
    
    # Añadir estadísticas por plataforma
    for platform in PLATAFORMAS.values():
        platform_downloads = sum([s[1] for s in user_stats if s[2] == platform['nombre']]) if user_stats else 0
        if platform_downloads > 0:
            stats_text += f"{platform['icono']} {platform['nombre']}: {platform_downloads}\n"
    
    await update.message.reply_text(stats_text, parse_mode='HTML')

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /info - Información del video sin descargar"""
    if not context.args:
        await update.message.reply_text("❌ Uso: /info [URL]")
        return
    
    url = context.args[0]
    await update.message.reply_text("🔄 Obteniendo información...")
    
    try:
        cmd = ['yt-dlp', '--dump-json', url]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0 and stdout:
            info = json.loads(stdout)
            
            # Detectar plataforma
            platform, _ = downloader.detect_platform(url)
            
            duration = info.get('duration', 0)
            duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Desconocida"
            
            info_text = f"""
📋 <b>Información del Video</b>

<b>Título:</b> {info.get('title', 'N/A')[:100]}
<b>Plataforma:</b> {PLATAFORMAS.get(platform, {}).get('nombre', 'Desconocida')}
<b>Autor:</b> {info.get('uploader', 'Desconocido')}
<b>Duración:</b> {duration_str}
<b>Vistas:</b> {info.get('view_count', 0):,}
<b>Likes:</b> {info.get('like_count', 0):,}
<b>Fecha:</b> {info.get('upload_date', 'Desconocida')}
"""
            await update.message.reply_text(info_text, parse_mode='HTML')
        else:
            await update.message.reply_text("❌ No se pudo obtener información")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /audio - Descargar solo audio MP3"""
    if not context.args:
        await update.message.reply_text("❌ Uso: /audio [URL]")
        return
    
    url = context.args[0]
    await update.message.reply_text("🔄 Procesando audio...")
    
    # Descargar audio
    file_path, file_type, platform_name, metadata = await downloader.download(
        url, quality='audio', user_id=update.effective_user.id
    )
    
    if file_path and file_type == 'audio':
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.UPLOAD_AUDIO
        )
        
        caption = f"🎵 {metadata['title'][:100]}\n📱 {platform_name}"
        
        with open(file_path, 'rb') as f:
            await update.message.reply_audio(
                audio=f,
                caption=caption,
                title=metadata['title'][:50],
                performer=metadata['uploader'][:50],
                duration=metadata['duration']
            )
        
        # Registrar descarga exitosa
        db.register_download(
            update.effective_user.id,
            platform_name,
            url,
            True,
            metadata['filesize'],
            metadata['duration']
        )
        
        downloader.cleanup(os.path.dirname(file_path))
    else:
        await update.message.reply_text("❌ No se pudo extraer el audio")
        db.register_download(update.effective_user.id, 'Desconocida', url, False)

async def batch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /batch - Descargar múltiples URLs"""
    if not context.args:
        await update.message.reply_text("❌ Uso: /batch [URL1] [URL2] ... (máx 5)")
        return
    
    urls = context.args[:5]  # Máximo 5 URLs
    await update.message.reply_text(f"🔄 Procesando {len(urls)} URLs...")
    
    for i, url in enumerate(urls, 1):
        await update.message.reply_text(f"📥 Descargando {i}/{len(urls)}...")
        
        quality = db.get_user_quality(update.effective_user.id)
        file_path, file_type, platform_name, metadata = await downloader.download(
            url, quality=quality, user_id=update.effective_user.id
        )
        
        if file_path:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_VIDEO if file_type == 'video' else ChatAction.UPLOAD_DOCUMENT
            )
            
            caption = f"📥 {metadata['title'][:100]}\n📱 {platform_name}"
            
            with open(file_path, 'rb') as f:
                if file_type == 'video':
                    await update.message.reply_video(video=f, caption=caption)
                elif file_type == 'audio':
                    await update.message.reply_audio(audio=f, caption=caption)
                else:
                    await update.message.reply_document(document=f, caption=caption)
            
            db.register_download(
                update.effective_user.id,
                platform_name,
                url,
                True,
                metadata['filesize'],
                metadata['duration']
            )
            
            downloader.cleanup(os.path.dirname(file_path))
        else:
            await update.message.reply_text(f"❌ Falló URL {i}: {url[:50]}...")
            db.register_download(update.effective_user.id, 'Desconocida', url, False)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes con URLs"""
    text = update.message.text
    
    # Buscar URLs en el mensaje
    url_encontrada = None
    plataforma_encontrada = None
    
    for platform, config in PLATAFORMAS.items():
        if re.search(config['patron'], text, re.IGNORECASE):
            match = re.search(config['patron'], text, re.IGNORECASE)
            url_encontrada = match.group(0)
            plataforma_encontrada = config
            break
    
    if url_encontrada:
        await update.message.reply_text(f"🔄 Procesando {plataforma_encontrada['icono']}...")
        
        # Obtener calidad del usuario
        quality = db.get_user_quality(update.effective_user.id)
        
        # Enviar acción de escritura
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )
        
        # Descargar
        file_path, file_type, platform_name, metadata = await downloader.download(
            url_encontrada, quality=quality, user_id=update.effective_user.id
        )
        
        if file_path:
            # Enviar acción de subida
            action = ChatAction.UPLOAD_VIDEO if file_type == 'video' else ChatAction.UPLOAD_DOCUMENT
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=action
            )
            
            # Preparar caption
            caption = f"📥 {metadata['title'][:100]}\n📱 {platform_name}"
            if metadata.get('uploader'):
                caption += f"\n👤 {metadata['uploader']}"
            
            # Enviar archivo según tipo
            with open(file_path, 'rb') as f:
                if file_type == 'video':
                    await update.message.reply_video(
                        video=f,
                        caption=caption,
                        supports_streaming=True
                    )
                elif file_type == 'audio':
                    await update.message.reply_audio(
                        audio=f,
                        caption=caption,
                        title=metadata['title'][:50],
                        performer=metadata.get('uploader', 'Desconocido')[:50],
                        duration=metadata.get('duration', 0)
                    )
                else:
                    await update.message.reply_document(
                        document=f,
                        caption=caption
                    )
            
            # Registrar descarga exitosa
            db.register_download(
                update.effective_user.id,
                platform_name,
                url_encontrada,
                True,
                metadata['filesize'],
                metadata.get('duration', 0)
            )
            
            # Limpiar
            downloader.cleanup(os.path.dirname(file_path))
            
        else:
            await update.message.reply_text(
                f"❌ No pude descargar el contenido.\n"
                f"Posibles causas:\n"
                f"• URL no válida\n"
                f"• Contenido privado\n"
                f"• Plataforma no soportada\n"
                f"• Las cookies expiraron (solo Instagram)"
            )
            db.register_download(
                update.effective_user.id,
                plataforma_encontrada['nombre'] if plataforma_encontrada else 'Desconocida',
                url_encontrada,
                False
            )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones de callback"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('quality_'):
        quality = query.data.replace('quality_', '')
        user_id = query.from_user.id
        
        # Guardar calidad
        db.set_user_quality(user_id, quality)
        
        await query.edit_message_text(
            f"✅ Calidad configurada: {CALIDADES[quality]['nombre']}\n\n"
            f"Ahora puedes enviar enlaces y se descargarán en esta calidad.\n"
            f"Usa /quality para cambiarla cuando quieras."
        )

def main():
    """Función principal"""
    if not TELEGRAM_TOKEN:
        logger.error("❌ No se encontró TELEGRAM_BOT_TOKEN")
        return
    
    # Verificar cookies
    if os.path.exists(COOKIES_FILE):
        logger.info(f"✅ Cookies cargadas: {COOKIES_FILE}")
    else:
        logger.warning("⚠️ No hay cookies. Instagram puede fallar")
    
    # Crear aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Añadir handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("quality", quality_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("audio", audio_command))
    app.add_handler(CommandHandler("batch", batch_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🚀 Bot Multi-Downloader iniciado!")
    logger.info(f"📱 Plataformas soportadas: {len(PLATAFORMAS)}")
    logger.info(f"🎚️ Calidades disponibles: {len(CALIDADES)}")
    
    app.run_polling()

if __name__ == "__main__":
    main()