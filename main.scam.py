import os
import re
import time
import random
import asyncio
import aiohttp
import telebot
from telethon.sync import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ------------------- CONFIGURACIÓN DESDE VARIABLES DE ENTORNO -------------------
API_ID = int(os.getenv("API_ID", "30861149"))
API_HASH = os.getenv("API_HASH", "8e41ffe6c0d5b5609bc5129628d1f3e4")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+584123889230")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8545721791:AAHAk78dr1-jMDR6M-Un_vjVPwmUxYTTl-A")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003363707812"))

# --- Session String (recomendado para Railway) ---
SESSION_STRING = os.getenv("SESSION_STRING", None)
SESSION_NAME = "scam_session" if not SESSION_STRING else None

IMAGES_URL = [
    'https://i.pinimg.com/736x/20/af/cf/20afcf4beeb219fb55e90ca19a8131c9.jpg',
    'https://i.pinimg.com/736x/0b/41/fd/0b41fdc1fac4dc91e4531c20e1046213.jpg',
    'https://i.pinimg.com/736x/7a/cd/cd/7acdcd93235fdf7f3fdc2263d203e921.jpg',
    'https://i.pinimg.com/736x/d2/fa/9b/d2fa9b36007562e3a3954810cc73dac4.jpg',
    'https://i.pinimg.com/736x/cc/b0/ae/ccb0aec3b037cd980f5947c2077a4647.jpg',
]

bot = telebot.TeleBot(BOT_TOKEN)
processed_cards = set()
cards_in_progress = set()

# ------------------- CLIENTE DE TELEGRAM -------------------
if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# ------------------- FUNCIONES AUXILIARES -------------------
async def get_bin_info(bin_number: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{bin_number}") as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"Error al consultar BIN: {e}")
    return {"brand": "N/A", "type": "N/A", "level": "N/A",
            "bank": "N/A", "country_name": "N/A", "country_flag": "❓"}

def clean_text(text: str) -> str:
    """Limpia caracteres no deseados como **, `, comillas, etc."""
    if not text or text == "Not Found":
        return text
    # Elimina **, __, `, comillas dobles/simples, y espacios extra
    cleaned = re.sub(r'[\*\`"\']', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def extract_card_info(text: str) -> dict | None:
    text_upper = text.upper()
    print("\n--- Procesando mensaje ---")
    print(text[:500] + "..." if len(text) > 500 else text)
    print("---")

    # ---------- PATRONES CC ----------
    card_patterns = [
        r'(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'(\d{14,16}):(\d{1,2}):(\d{2,4}):(\d{3,4})',
        r'Card\s*[⇾»➸-]\s*(\d{14,16})[|:](\d{1,2})[|:](\d{2,4})[|:](\d{3,4})',
        r'CC\s*[≠:]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'Tarjeta\s*➸\s*\[(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})\]',
        r'💳\s*[:|]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'[Cc][Cc]\s*[:|]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
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
    success_keywords = r'(?:APPROVED|APROBADA|LIVE|CHARGED|CHARGE|AUTH|AUTHORIZED)'
    reject_keywords = r'DEAD|DENIED|REJECTED|ERROR|INCORRECT|TIMEOUT|DECLINED|EXPIRED'

    has_success = re.search(success_keywords, text_upper, re.IGNORECASE)
    has_reject = re.search(reject_keywords, text_upper, re.IGNORECASE)

    if not has_success:
        print("No se encontró palabra de aprobación. Ignorando.")
        return None
    if has_reject:
        print("Se encontró indicador de rechazo. Ignorando.")
        return None

    # ---------- EXTRACCIÓN DE CAMPOS ----------
    def extract_field(keywords, default="Not Found"):
        pattern = r'.*?(?:' + keywords + r')\s*[:≠⇾↳ϟ༄➸⌁┊»-]\s*([^\n\r]*)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_text(match.group(1).strip())
        return default

    # GATEWAY
    gateway = extract_field(r'GATEWAY|GATE|PASARELA|𝙂𝙖𝙩𝙚𝙬𝙖𝙮|𝗚𝗮𝘁𝗲|𝐆𝐚𝐭𝐞𝐰𝐚𝐲')
    if gateway == "Not Found":
        first_line = text.split('\n')[0].strip()
        gateway_candidates = re.findall(r'\b(BRAINTREE|STRIPE|PAYFLOW|AUTH|EAGLE|CHECKER|CHK|GATEWAY)\b', first_line, re.IGNORECASE)
        if gateway_candidates:
            gateway = ' '.join(gateway_candidates).strip()
        else:
            match = re.search(r'[/\-]\s*([a-zA-Z0-9\s]+)', first_line)
            if match:
                gateway = clean_text(match.group(1).strip())
            else:
                gw_match = re.search(r'\b(GATEWAY|GATE)\s*[:|»]\s*([^\n\r]+)', text, re.IGNORECASE)
                if gw_match:
                    gateway = clean_text(gw_match.group(2).strip())
    # Limpieza extra
    gateway = re.sub(r'\s*\(.*?\)', '', gateway).strip()
    gateway = re.sub(r'^#', '', gateway).strip()
    gateway = re.sub(r'\s*-\s*/ti', '', gateway, flags=re.IGNORECASE).strip()
    gateway = clean_text(gateway)

    # STATUS
    status = extract_field(r'STATUS|RESULT|ESTADO|𝙎𝙩𝙖𝙩𝙪𝙨|𝗦𝘁𝗮𝘁𝘂𝘀|𝐒𝐭𝐚𝐭𝐮𝐬|𝐑𝐞𝐬𝐮𝐥𝐭')
    if status == "Not Found" or status == "":
        if re.search(r'\b(APPROVED|LIVE|CHARGED|AUTH)\b', text_upper):
            status = "Approved ✓"
        else:
            status = "Approved ✓"
    else:
        status = clean_text(status)

    # RESPONSE
    response = extract_field(r'RESPONSE|RESULT|MESSAGE|𝙍𝙚𝙨𝙪𝙡𝙩|𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲|𝐌𝐞𝐬𝐬𝐚𝐠𝐞')
    if response != "Not Found":
        response = re.sub(r'^\d+\s*:\s*', '', response).strip()
        if response.upper() == "(ADDED) APPROVED":
            response = "Approved"
        response = clean_text(response)

    # BANK
    bank = extract_field(r'BANK|ISSUING BANK|BANCO|𝘽𝗮𝗻𝗸|𝗜𝘀𝘀𝘂𝗲𝗿|𝐁𝐚𝐧𝐤')
    bank = clean_text(bank)

    # COUNTRY
    country = extract_field(r'COUNTRY|PAIS|𝘾𝙤𝙪𝙣𝙩𝙧𝙮|𝗖𝗼𝘂𝗻𝘁𝗿𝘆|𝐂𝐨𝐮𝐧𝐭𝐫𝐲')
    flag = "❓"
    if country != "Not Found" and country:
        flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
        if flag_match:
            flag = flag_match.group(1)
            country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()
        country = clean_text(country)

    # BIN INFO (brand, type, level)
    bin_info = extract_field(r'BIN|𝘽𝗶𝗻|INFO|DATA|INFORMACION|𝗕𝗶𝗻|𝗧𝘆𝗽𝗲|𝐁𝐢𝐧 𝐈𝐧𝐟𝐨')
    brand = "Unknown"
    card_type = "Unknown"
    level = "Unknown"
    if bin_info != "Not Found" and bin_info:
        bin_info = re.sub(r'^\[\d{6}\]\s*', '', bin_info).strip()
        bin_info = re.sub(r'^\s*\(|\)\s*$', '', bin_info).strip()
        parts = [p.strip() for p in re.split(r'[-|]', bin_info) if p.strip()]
        if parts:
            if parts[0].upper() in ['VISA', 'MASTERCARD', 'AMEX', 'DISCOVER']:
                brand = clean_text(parts.pop(0))
            if parts:
                card_type = clean_text(parts.pop(0))
            if parts:
                level = clean_text(parts.pop(0))
            if parts:
                rest = ' '.join(parts)
                if bank == "Not Found" or bank == "":
                    bank = clean_text(rest)
                if country == "Not Found" or country == "":
                    country = clean_text(rest)
        flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', bin_info)
        if flag_match:
            flag = flag_match.group(1)

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
    cc, month, year, cvv = card_info.split('|')
    cc1 = cc[:12] + 'xxxx'
    ext1 = f"{cc1}|{month}|{year}|rnd"
    rand_digit = random.randint(0, 9)
    cc2 = cc[:11] + str(rand_digit) + 'xxxx'
    ext2 = f"{cc2}|{month}|{year}|rnd"
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
        bin_info_api = await get_bin_info(card_data['bin_number'])
        if bin_info_api.get('brand') and bin_info_api['brand'] != 'N/A':
            card_data['brand'] = clean_text(bin_info_api['brand'])
        if bin_info_api.get('type') and bin_info_api['type'] != 'N/A':
            card_data['type'] = clean_text(bin_info_api['type'])
        if bin_info_api.get('level') and bin_info_api['level'] != 'N/A':
            card_data['level'] = clean_text(bin_info_api['level'])
        if bin_info_api.get('bank') and bin_info_api['bank'] != 'N/A':
            card_data['bank'] = clean_text(bin_info_api['bank'])
        if bin_info_api.get('country_name') and bin_info_api['country_name'] != 'N/A':
            card_data['country'] = clean_text(bin_info_api['country_name'])
        if bin_info_api.get('country_flag') and bin_info_api['country_flag'] != '❓':
            card_data['flag'] = bin_info_api['country_flag']

        ext1, ext2, ext3 = generate_extrapolated(card_full)

        # Plantilla exacta (con espacios y líneas como pediste)
        custom_message = f"""
✸  𝗖𝗛𝗘𝗥𝗥𝗬'𝗦  𝗦𝗖𝗔𝗠  — [#BIN{card_data['bin_number']}]

✦  |  𝗖𝗖 →  <code>{card_data['card_info']}</code>  
✦  |  𝗦𝗧𝗔𝗧𝗨𝗦 → {card_data['status']}
✦  |  𝗚𝗔𝗧𝗘𝗪𝗔𝗬 → {card_data['gateway']}    
✦  |  𝗦𝗖𝗔𝗠 𝗗𝗔𝗧𝗘 → {time.strftime('%d - %m - %Y')}

︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶
⊹    |  𝗥𝗘𝗦𝗣𝗢𝗡𝗦𝗘 → {card_data['response']}
⊹    |  𝗖𝗔𝗥𝗗 𝗜𝗡𝗙𝗢 → {card_data['bank']}
⊹    |  𝗕𝗔𝗡𝗞 → {card_data['brand']}
⊹    |  𝗖𝗢𝗨𝗡𝗧𝗥𝗬 → {card_data['country']} [{card_data['flag']}]
 
︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶

 𐔌    ．⠀𝖣𝖠𝖳𝖠 𝖡𝖠𝖲𝖤 𝖤𝖷𝖳𝖱𝖠𝖲

⇢ <code>{ext1}</code>  
⇢ <code>{ext2}</code>   
⇢ <code>{ext3}</code> 
"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("𖥻 INFO", url="https://t.me/infocherrys"),
             InlineKeyboardButton("𖥻 REFES", url="https://t.me/+oS0yU_A2yGxjMjQ0")],
        ])

        image_url = random.choice(IMAGES_URL)

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
    if SESSION_STRING:
        await client.start()
    else:
        await client.start(phone=PHONE_NUMBER)
    print("¡Bot en ejecución! Esperando mensajes...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
