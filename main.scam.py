import os
import re
import time
import random
import asyncio
import aiohttp
import telebot
from telethon.sync import TelegramClient, events
from telethon.tl.types import Message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ------------------- CONFIGURACIÓN DESDE VARIABLES DE ENTORNO -------------------
API_ID = int(os.getenv("API_ID", "30861149"))
API_HASH = os.getenv("API_HASH", "8e41ffe6c0d5b5609bc5129628d1f3e4")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+584123889230")   # tu número de Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "8545721791:AAHAk78dr1-jMDR6M-Un_vjVPwmUxYTTl-A")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003363707812"))  # ID del canal de destino
SESSION_NAME = "scam_session"  # nombre del archivo .session (se generará localmente)

IMAGES_URL = [
    'https://i.pinimg.com/736x/78/39/79/7839791ce7428f1cacae903e034bffc0.jpg',
    'https://i.pinimg.com/736x/8f/dc/d8/8fdcd87fccba7f4a969b33b04823560d.jpg',
    'https://i.pinimg.com/736x/c6/77/33/c6773365ea8c89a1670f14739f1af1b1.jpg',
    'https://i.pinimg.com/736x/1c/42/6e/1c426e05aedbf7aa8a685df6f9b6f7f6.jpg',
    'https://i.pinimg.com/736x/74/40/b7/7440b7d0bbb8b2500cb6969d138a7f6a.jpg',
]

bot = telebot.TeleBot(BOT_TOKEN)

# Conjuntos para evitar duplicados y procesamiento concurrente
processed_cards = set()
cards_in_progress = set()

# ------------------- CLIENTE DE TELEGRAM -------------------
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# ------------------- FUNCIONES AUXILIARES -------------------
async def get_bin_info(bin_number: str) -> dict:
    """Obtiene información del BIN desde la API pública."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{bin_number}") as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"Error al consultar BIN: {e}")
    return {"brand": "N/A", "type": "N/A", "level": "N/A",
            "bank": "N/A", "country_name": "N/A", "country_flag": "❓"}

def extract_card_info(text: str) -> dict | None:
    """
    Extrae la información de la tarjeta del mensaje.
    Retorna un diccionario con los campos o None si no es aprobada.
    """
    text_upper = text.upper()
    print("\n--- Procesando mensaje ---")
    print(text[:300] + "..." if len(text) > 300 else text)
    print("---")

    # Patrones para capturar CC|MM|YY|CVV (flexibles)
    card_patterns = [
        r'(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'(\d{14,16}):(\d{1,2}):(\d{2,4}):(\d{3,4})',
        r'Card\s*[⇾»➸-]\s*(\d{14,16})[|:](\d{1,2})[|:](\d{2,4})[|:](\d{3,4})',
        r'CC\s*[≠:]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'Tarjeta\s*➸\s*\[(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})\]',
        # ... puedes añadir más patrones según necesites
    ]
    match_cc = None
    for pat in card_patterns:
        match_cc = re.search(pat, text, re.IGNORECASE)
        if match_cc:
            break
    if not match_cc:
        return None

    cc, month, year, cvv = match_cc.groups()
    card_info = f"{cc}|{month}|{year}|{cvv}"
    bin_num = cc[:6]

    # ---------- FILTRADO DE APROBACIÓN ----------
    # Buscar indicadores de éxito (aprobado, live, charged) con emoji positivo
    success_pattern = r'[✅💎✓].*?(?:CHARGE|CHARGED|APPROVED|APROBADA|LIVE)'
    reject_pattern = r'DEAD|DENIED|REJECTED|ERROR|INCORRECT|TIMEOUT|DECLINED'

    if not re.search(success_pattern, text, re.IGNORECASE | re.DOTALL):
        print("No se encontró indicador de aprobación. Ignorando.")
        return None
    if re.search(reject_pattern, text_upper, re.IGNORECASE | re.DOTALL):
        print("Se encontró indicador de rechazo. Ignorando.")
        return None

    # ---------- EXTRACCIÓN DE CAMPOS ----------
    def extract_field(keywords, default="Not Found"):
        """Busca un campo etiquetado en el mensaje."""
        pattern = r'.*?(?:' + keywords + r')\s*[:≠⇾↳ϟ༄➸⌁┊»-]\s*([^\n\r]*)'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else default

    gateway = extract_field(r'GATEWAY|GATE|PASARELA|𝙂𝙖𝙩𝙚𝙬𝙖𝙮|𝗚𝗮𝘁𝗲|𝐆𝐚𝐭𝐞𝐰𝐚𝐲')
    # Limpiar gateway
    gateway = re.sub(r'\s*\(.*?\)', '', gateway).strip()
    gateway = re.sub(r'^#', '', gateway).strip()

    status = extract_field(r'STATUS|RESULT|ESTADO|𝙎𝙩𝙖𝙩𝙪𝙨|𝗦𝘁𝗮𝘁𝘂𝘀|𝐒𝐭𝐚𝐭𝐮𝐬|𝐑𝐞𝐬𝐮𝐥𝐭')
    # Limpiar emojis del status (solo para mostrar)
    status_clean = re.sub(r'[✅💎✓]', '', status).strip()
    if not status_clean:
        status = "Approved ✓"

    response = extract_field(r'RESPONSE|RESULT|MESSAGE|𝙍𝙚𝙨𝙪𝙡𝙩|𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲|𝐌𝐞𝐬𝐬𝐚𝐠𝐞')
    response = re.sub(r'^\d+\s*:\s*', '', response).strip()
    if response.upper() == "(ADDED) APPROVED":
        response = "Approved"

    bank = extract_field(r'BANK|ISSUING BANK|BANCO|𝘽𝗮𝗻𝗸|𝗜𝘀𝘀𝘂𝗲𝗿|𝐁𝐚𝐧𝐤')

    country = extract_field(r'COUNTRY|PAIS|𝘾𝙤𝙪𝙣𝙩𝙧𝙮|𝗖𝗼𝘂𝗻𝘁𝗿𝘆|𝐂𝐨𝐮𝐧𝐭𝐫𝐲')
    flag = "❓"
    if country:
        flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
        if flag_match:
            flag = flag_match.group(1)
            country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()

    # Intentar extraer brand/type/level desde el campo "BIN INFO"
    bin_info = extract_field(r'BIN|𝘽𝗶𝗻|INFO|DATA|INFORMACION|𝗕𝗶𝗻|𝗧𝘆𝗽𝗲|𝐁𝐢𝐧 𝐈𝐧𝐟𝐨')
    brand = "Unknown"
    card_type = "Unknown"
    level = "Unknown"
    if bin_info:
        # Limpiar y separar
        bin_info = re.sub(r'^\[\d{6}\]\s*', '', bin_info).strip()
        bin_info = re.sub(r'^\s*\(|\)\s*$', '', bin_info).strip()
        parts = [p.strip() for p in re.split(r'[-|]', bin_info) if p.strip()]
        if parts:
            # Primera parte puede ser la marca
            if parts[0].upper() in ['VISA', 'MASTERCARD', 'AMEX', 'DISCOVER']:
                brand = parts.pop(0)
            if parts:
                card_type = parts.pop(0)
            if parts:
                level = parts.pop(0)
            if parts:
                # el resto puede ser el banco o país
                rest = ' '.join(parts)
                # Si no hay bank, lo usamos
                if bank == "Not Found":
                    bank = rest
                # Si no hay country, lo usamos
                if country == "Not Found" or not country:
                    country = rest
        # Si hay una bandera al final, extraerla
        flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', bin_info)
        if flag_match:
            flag = flag_match.group(1)

    # Si la API da mejor info, la usamos (pero asíncrono se hará después)
    # Devolvemos los datos extraídos
    return {
        "card_info": card_info,
        "bin_number": bin_num,
        "status": status,
        "response": response,
        "gateway": gateway,
        "brand": brand,
        "type": card_type,
        "level": level,
        "bank": bank,
        "country": country,
        "flag": flag,
        "raw_bin_info": bin_info
    }

def generate_extrapolated(card_info: str) -> tuple:
    """Genera tres tarjetas extrapoladas."""
    cc, month, year, cvv = card_info.split('|')
    # Primera: ocultar últimos 4 dígitos
    cc1 = cc[:12] + 'xxxx'
    ext1 = f"{cc1}|{month}|{year}|rnd"

    # Segunda: cambiar un dígito aleatorio
    rand_digit = random.randint(0, 9)
    cc2 = cc[:11] + str(rand_digit) + 'xxxx'
    ext2 = f"{cc2}|{month}|{year}|rnd"

    # Tercera: cambiar dos dígitos
    rand_digits = random.randint(10, 99)
    cc3 = cc[:10] + str(rand_digits) + 'xxxx'
    ext3 = f"{cc3}|{month}|{year}|rnd"

    return ext1, ext2, ext3

# ------------------- MANEJADOR DE MENSAJES -------------------
@client.on(events.NewMessage())
@client.on(events.MessageEdited())
async def handler(event):
    global processed_cards, cards_in_progress

    msg: Message = event.message
    if not msg.text:
        return

    # Extraer información
    card_data = extract_card_info(msg.text)
    if not card_data:
        return

    card_full = card_data['card_info']
    card_clean = re.sub(r'[\s|-]', '', card_full)

    if card_clean in processed_cards:
        print(f"Tarjeta {card_clean} ya procesada.")
        return
    if card_clean in cards_in_progress:
        print(f"Tarjeta {card_clean} en proceso.")
        return

    cards_in_progress.add(card_clean)

    try:
        # Obtener información del BIN desde la API (asíncrono)
        bin_info_api = await get_bin_info(card_data['bin_number'])

        # Combinar datos: preferir API si tiene datos válidos
        if bin_info_api.get('brand') and bin_info_api['brand'] != 'N/A':
            card_data['brand'] = bin_info_api['brand']
        if bin_info_api.get('type') and bin_info_api['type'] != 'N/A':
            card_data['type'] = bin_info_api['type']
        if bin_info_api.get('level') and bin_info_api['level'] != 'N/A':
            card_data['level'] = bin_info_api['level']
        if bin_info_api.get('bank') and bin_info_api['bank'] != 'N/A':
            card_data['bank'] = bin_info_api['bank']
        if bin_info_api.get('country_name') and bin_info_api['country_name'] != 'N/A':
            card_data['country'] = bin_info_api['country_name']
        if bin_info_api.get('country_flag') and bin_info_api['country_flag'] != '❓':
            card_data['flag'] = bin_info_api['country_flag']

        # Generar extrapoladas
        ext1, ext2, ext3 = generate_extrapolated(card_full)

        # Construir mensaje
        custom_message = f"""
✸ 𝗖𝗛𝗘𝗥𝗥𝗬'𝗦  𝗦𝗖𝗔𝗠  — [#BIN{card_data['bin_number']}]

⋆.𐙚 | 𝗖𝗖 →  <code>{card_data['card_info']}</code>  
⋆.𐙚 | 𝗦𝗧𝗔𝗧𝗨𝗦 → {card_data['status']}
⋆.𐙚 | 𝗚𝗔𝗧𝗘𝗪𝗔𝗬 → {card_data['gateway']}   
⋆.𐙚 | 𝗦𝗖𝗔𝗠 𝗗𝗔𝗧𝗘 → {time.strftime('%d - %m - %Y')}

︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶
꒰ঌ ໒꒱ | 𝗥𝗘𝗦𝗣𝗢𝗡𝗦𝗘 → {card_data['response']}
꒰ঌ ໒꒱ | 𝗖𝗔𝗥𝗗 𝗜𝗡𝗙𝗢 → {card_data['bank']}
꒰ঌ ໒꒱ | 𝗕𝗔𝗡𝗞 → {card_data['brand']}
꒰ঌ ໒꒱ | 𝗖𝗢𝗨𝗡𝗧𝗥𝗬 → {card_data['country']} [{card_data['flag']}]
 
︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶

✿  —⠀𝖣𝖠𝖳𝖠 𝖡𝖠𝖲𝖤 𝖤𝖷𝖳𝖱𝖠𝖲

➜ <code>{ext1}</code>  
➜ <code>{ext2}</code>  
➜ <code>{ext3}</code> 
"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("𖥻 INFO", url="https://t.me/infocherrys"),
             InlineKeyboardButton("𖥻 REFES", url="https://t.me/+oS0yU_A2yGxjMjQ0")],
        ])

        image_url = random.choice(IMAGES_URL)

        # Enviar con retries
        for attempt in range(3):
            try:
                await asyncio.to_thread(
                    bot.send_photo,
                    CHANNEL_ID,
                    image_url,
                    caption=custom_message,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                print(f"Mensaje enviado para tarjeta {card_clean}")
                processed_cards.add(card_clean)
                break
            except telebot.apihelper.ApiException as e:
                if 'Too Many Requests' in str(e):
                    print(f"Rate limit, esperando 5s... (intento {attempt+1}/3)")
                    await asyncio.sleep(5)
                elif attempt < 2:
                    await asyncio.sleep(3)
                else:
                    print(f"Fallo después de 3 intentos: {e}")
            except Exception as e:
                print(f"Error al enviar: {e}")
                break
    finally:
        cards_in_progress.discard(card_clean)

# ------------------- ARRANQUE -------------------
async def main():
    print("Iniciando cliente de Telegram...")
    await client.start(phone=PHONE_NUMBER)   # Si la sesión ya existe, no pedirá código
    print("¡Bot en ejecución! Esperando mensajes...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())