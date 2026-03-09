#!/usr/bin/env python3
"""
Bot de Telegram con acceso completo a Instagram usando instagrapi
Permite descargar posts, reels, stories, highlights, perfiles completos
"""
import os
import logging
import asyncio
import tempfile
import shutil
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
INSTAGRAM_USERNAME = "iroennys_rivas"  # Tu usuario de Instagram
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')  # Contraseña en secrets

class InstagramBot:
    def __init__(self):
        self.cl = Client()
        self.user_id = None
        self.session_file = "instagram_session.json"
        
    async def login(self):
        """Inicia sesión en Instagram"""
        try:
            # Intentar cargar sesión guardada
            if os.path.exists(self.session_file):
                self.cl.load_settings(self.session_file)
                self.cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                logger.info("✅ Sesión de Instagram cargada")
            else:
                # Login con credenciales
                self.cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                self.cl.dump_settings(self.session_file)
                logger.info("✅ Login exitoso en Instagram")
            
            self.user_id = self.cl.user_id
            return True
        except Exception as e:
            logger.error(f"❌ Error en login: {e}")
            return False
    
    async def download_post(self, url):
        """Descarga un post de Instagram por URL"""
        try:
            # Obtener media ID desde URL
            media_pk = self.cl.media_pk_from_url(url)
            
            # Obtener información del media
            media = self.cl.media_info(media_pk)
            
            temp_dir = tempfile.mkdtemp()
            result = []
            
            # Determinar tipo de media
            if media.media_type == 1:  # Foto
                path = self.cl.photo_download(media_pk, folder=temp_dir)
                result.append(('photo', path, media.caption_text))
                
            elif media.media_type == 2:  # Video
                path = self.cl.video_download(media_pk, folder=temp_dir)
                result.append(('video', path, media.caption_text))
                
            elif media.media_type == 8:  # Álbum (múltiples)
                paths = self.cl.album_download(media_pk, folder=temp_dir)
                for i, path in enumerate(paths):
                    result.append(('album', path, f"{media.caption_text} (Parte {i+1})"))
            
            return result, temp_dir
            
        except Exception as e:
            logger.error(f"Error descargando post: {e}")
            return None, None
    
    async def download_profile(self, username, amount=10):
        """Descarga los últimos posts de un perfil"""
        try:
            # Obtener user_id del username
            user_id = self.cl.user_id_from_username(username)
            
            # Obtener medias del usuario
            medias = self.cl.user_medias(user_id, amount=amount)
            
            temp_dir = tempfile.mkdtemp()
            results = []
            
            for media in medias:
                if media.media_type == 1:
                    path = self.cl.photo_download(media.pk, folder=temp_dir)
                    results.append(('photo', path, f"Post de @{username}"))
                elif media.media_type == 2:
                    path = self.cl.video_download(media.pk, folder=temp_dir)
                    results.append(('video', path, f"Video de @{username}"))
                elif media.media_type == 8:
                    paths = self.cl.album_download(media.pk, folder=temp_dir)
                    for path in paths:
                        results.append(('album', path, f"Álbum de @{username}"))
            
            return results, temp_dir, len(medias)
            
        except Exception as e:
            logger.error(f"Error descargando perfil: {e}")
            return None, None, 0
    
    async def download_stories(self, username):
        """Descarga stories activas de un usuario"""
        try:
            user_id = self.cl.user_id_from_username(username)
            stories = self.cl.user_stories(user_id)
            
            if not stories:
                return None, None, 0
            
            temp_dir = tempfile.mkdtemp()
            results = []
            
            for story in stories:
                if story.media_type == 1:  # Foto
                    path = self.cl.photo_download(story.pk, folder=temp_dir)
                    results.append(('photo', path, f"Story de @{username}"))
                elif story.media_type == 2:  # Video
                    path = self.cl.video_download(story.pk, folder=temp_dir)
                    results.append(('video', path, f"Story de @{username}"))
            
            return results, temp_dir, len(stories)
            
        except Exception as e:
            logger.error(f"Error descargando stories: {e}")
            return None, None, 0
    
    async def download_highlights(self, username):
        """Descarga highlights de un usuario"""
        try:
            user_id = self.cl.user_id_from_username(username)
            highlights = self.cl.user_highlights(user_id)
            
            if not highlights:
                return None, None, 0
            
            temp_dir = tempfile.mkdtemp()
            results = []
            total = 0
            
            for highlight in highlights:
                stories = self.cl.highlight_stories(highlight.pk)
                for story in stories:
                    if story.media_type == 1:
                        path = self.cl.photo_download(story.pk, folder=temp_dir)
                        results.append(('photo', path, f"Highlight: {highlight.title}"))
                    elif story.media_type == 2:
                        path = self.cl.video_download(story.pk, folder=temp_dir)
                        results.append(('video', path, f"Highlight: {highlight.title}"))
                    total += 1
            
            return results, temp_dir, total
            
        except Exception as e:
            logger.error(f"Error descargando highlights: {e}")
            return None, None, 0
    
    def cleanup(self, temp_dir):
        """Limpia archivos temporales"""
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

# Instancia global del bot
insta_bot = InstagramBot()

# Handlers de Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "🤖 <b>Bot de Instagram con acceso a cuenta</b>\n\n"
        "Comandos disponibles:\n"
        "/login - Iniciar sesión en Instagram\n"
        "/post [URL] - Descargar post/reel por URL\n"
        "/profile [usuario] - Descargar últimos posts de un perfil\n"
        "/stories [usuario] - Descargar stories activas\n"
        "/highlights [usuario] - Descargar highlights\n"
        "/me - Tu información de perfil\n"
        "/help - Ayuda detallada",
        parse_mode='HTML'
    )

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia sesión en Instagram"""
    await update.message.reply_text("🔄 Iniciando sesión en Instagram...")
    
    if await insta_bot.login():
        user_info = insta_bot.cl.user_info(insta_bot.user_id)
        await update.message.reply_text(
            f"✅ <b>Login exitoso!</b>\n\n"
            f"Usuario: @{user_info.username}\n"
            f"Nombre: {user_info.full_name}\n"
            f"Posts: {user_info.media_count}\n"
            f"Seguidores: {user_info.follower_count}",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "❌ Error al iniciar sesión. Verifica que:\n"
            "• INSTAGRAM_PASSWORD esté configurado\n"
            "• Tus credenciales sean correctas\n"
            "• Instagram no bloqueó el acceso"
        )

async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descarga post por URL"""
    if not context.args:
        await update.message.reply_text("❌ Uso: /post [URL de Instagram]")
        return
    
    url = context.args[0]
    await update.message.reply_text(f"🔄 Procesando: {url[:50]}...")
    
    results, temp_dir = await insta_bot.download_post(url)
    
    if results:
        for media_type, path, caption in results:
            try:
                with open(path, 'rb') as f:
                    if media_type == 'photo':
                        await update.message.reply_photo(photo=f, caption=caption[:200])
                    elif media_type == 'video':
                        await update.message.reply_video(video=f, caption=caption[:200])
                    else:
                        await update.message.reply_document(document=f, caption=caption[:200])
            except Exception as e:
                await update.message.reply_text(f"Error enviando archivo: {e}")
        
        insta_bot.cleanup(temp_dir)
        await update.message.reply_text("✅ Descarga completada!")
    else:
        await update.message.reply_text("❌ No se pudo descargar. Verifica la URL.")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descarga perfil de usuario"""
    username = context.args[0] if context.args else INSTAGRAM_USERNAME
    amount = int(context.args[1]) if len(context.args) > 1 else 5
    
    await update.message.reply_text(f"🔄 Descargando {amount} posts de @{username}...")
    
    results, temp_dir, total = await insta_bot.download_profile(username, amount)
    
    if results:
        await update.message.reply_text(f"📥 Descargando {total} posts...")
        
        for i, (media_type, path, caption) in enumerate(results):
            try:
                with open(path, 'rb') as f:
                    caption = f"@{username} ({i+1}/{total})"
                    if media_type == 'photo':
                        await update.message.reply_photo(photo=f, caption=caption)
                    elif media_type == 'video':
                        await update.message.reply_video(video=f, caption=caption)
                    else:
                        await update.message.reply_document(document=f, caption=caption)
            except Exception as e:
                await update.message.reply_text(f"Error con archivo {i+1}: {e}")
        
        insta_bot.cleanup(temp_dir)
        await update.message.reply_text(f"✅ {total} posts de @{username} enviados!")
    else:
        await update.message.reply_text("❌ No se pudo descargar el perfil.")

async def stories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descarga stories"""
    username = context.args[0] if context.args else INSTAGRAM_USERNAME
    
    await update.message.reply_text(f"🔄 Buscando stories de @{username}...")
    
    results, temp_dir, total = await insta_bot.download_stories(username)
    
    if results:
        await update.message.reply_text(f"📥 Descargando {total} stories...")
        
        for i, (media_type, path, caption) in enumerate(results):
            with open(path, 'rb') as f:
                if media_type == 'photo':
                    await update.message.reply_photo(photo=f, caption=caption)
                else:
                    await update.message.reply_video(video=f, caption=caption)
        
        insta_bot.cleanup(temp_dir)
        await update.message.reply_text(f"✅ {total} stories de @{username} enviadas!")
    else:
        await update.message.reply_text(f"ℹ️ @{username} no tiene stories activas.")

async def highlights_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descarga highlights"""
    username = context.args[0] if context.args else INSTAGRAM_USERNAME
    
    await update.message.reply_text(f"🔄 Buscando highlights de @{username}...")
    
    results, temp_dir, total = await insta_bot.download_highlights(username)
    
    if results:
        await update.message.reply_text(f"📥 Descargando {total} items de highlights...")
        
        for i, (media_type, path, caption) in enumerate(results):
            with open(path, 'rb') as f:
                if media_type == 'photo':
                    await update.message.reply_photo(photo=f, caption=caption)
                else:
                    await update.message.reply_video(video=f, caption=caption)
        
        insta_bot.cleanup(temp_dir)
        await update.message.reply_text(f"✅ {total} items de highlights de @{username} enviados!")
    else:
        await update.message.reply_text(f"ℹ️ @{username} no tiene highlights.")

async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Información de mi cuenta"""
    try:
        user_info = insta_bot.cl.user_info(insta_bot.user_id)
        await update.message.reply_text(
            f"👤 <b>Tu perfil de Instagram</b>\n\n"
            f"Usuario: @{user_info.username}\n"
            f"Nombre: {user_info.full_name}\n"
            f"Bio: {user_info.biography}\n"
            f"Posts: {user_info.media_count}\n"
            f"Seguidores: {user_info.follower_count}\n"
            f"Siguiendo: {user_info.following_count}",
            parse_mode='HTML'
        )
    except:
        await update.message.reply_text("❌ No has iniciado sesión. Usa /login")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ayuda detallada"""
    help_text = """
📖 <b>AYUDA - Bot Instagram</b>

<b>Comandos principales:</b>
• /login - Iniciar sesión en Instagram
• /post [URL] - Descargar post/reel por URL
• /profile [usuario] [cantidad] - Descargar posts de un perfil
• /stories [usuario] - Descargar stories activas
• /highlights [usuario] - Descargar highlights
• /me - Tu información

<b>Ejemplos:</b>
/post https://www.instagram.com/reel/ABC123/
/profile iroennys_rivas 10
/stories iroennys_rivas
/highlights iroennys_rivas

<b>Nota:</b> El bot usa tu cuenta de Instagram para acceder
a todo el contenido. Las sesiones se guardan automáticamente.
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes con URLs de Instagram"""
    text = update.message.text
    
    if 'instagram.com' in text and not text.startswith('/'):
        # Extraer URL
        import re
        url_pattern = r'(https?://(?:www\.)?instagram\.com/[^\s]+)'
        match = re.search(url_pattern, text)
        
        if match:
            url = match.group(1)
            await update.message.reply_text(f"🔄 Detecté URL de Instagram. Procesando...")
            
            results, temp_dir = await insta_bot.download_post(url)
            
            if results:
                for media_type, path, caption in results:
                    with open(path, 'rb') as f:
                        if media_type == 'photo':
                            await update.message.reply_photo(photo=f, caption=caption[:200])
                        else:
                            await update.message.reply_video(video=f, caption=caption[:200])
                
                insta_bot.cleanup(temp_dir)
                await update.message.reply_text("✅ Descarga completada!")
            else:
                await update.message.reply_text("❌ No pude descargar ese contenido. Prueba con /post [URL]")

def main():
    """Función principal"""
    if not TELEGRAM_TOKEN:
        logger.error("❌ No se encontró TELEGRAM_BOT_TOKEN")
        return
    
    # Crear aplicación
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Añadir handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("post", post_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("stories", stories_command))
    app.add_handler(CommandHandler("highlights", highlights_command))
    app.add_handler(CommandHandler("me", me_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Bot iniciado!")
    app.run_polling()

if __name__ == "__main__":
    main()
