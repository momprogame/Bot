# Bot
Bot de tg
# Telegram Bot Simple con GitHub Actions

Un bot simple de Telegram que se ejecuta usando GitHub Actions.

## Comandos
- `/start` - Mensaje de bienvenida
- `/time` - Muestra la hora actual
- `/echo [mensaje]` - Repite tu mensaje

## Configuración
1. Habla con [@BotFather](https://t.me/botfather) para obtener un token
2. Añade el token como secret en GitHub con nombre `TELEGRAM_BOT_TOKEN`
3. El bot se ejecutará automáticamente con cada push

## Nota
El bot funciona mientras GitHub Actions lo ejecuta. 
Se ejecuta por 25 minutos cada 30 minutos gracias al cron job configurado.
