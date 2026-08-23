# ScamCherrys Bot

Bot de Telegram que monitorea canales/grupos en busca de tarjetas de crédito aprobadas y las reenvía formateadas a un canal de destino.

## Configuración

1. **Obtén tus credenciales**:
   - `API_ID` y `API_HASH` desde [my.telegram.org](https://my.telegram.org)
   - `BOT_TOKEN` de [@BotFather](https://t.me/BotFather)
   - `PHONE_NUMBER` de la cuenta de usuario que usará Telethon.

2. **Genera la sesión de Telethon** localmente:
   ```bash
   python -c "from telethon.sync import TelegramClient; client = TelegramClient('scam_session', API_ID, API_HASH); client.start(phone='TU_NUMERO'); client.disconnect()"
