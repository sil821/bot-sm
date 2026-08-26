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

# ------------------- CONFIGURACIÓN -------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
SESSION_STRING = os.getenv("SESSION_STRING")

if not all([API_ID, API_HASH, BOT_TOKEN, CHANNEL_ID, SESSION_STRING]):
    raise ValueError("Faltan variables de entorno")

IMAGES_URL = [
    'https://i.pinimg.com/736x/38/5a/2f/385a2f9f39beb724959faa4c46a0ebbf.jpg',
    'https://i.pinimg.com/736x/4d/34/a4/4d34a4c55bdc990cb93be3197ed59d05.jpg',
    'https://i.pinimg.com/736x/b7/14/f0/b714f0ba6f3c087c5a1a3073d8f62f45.jpg',
    'https://i.pinimg.com/736x/eb/e7/01/ebe70174388848d7f0f6eb458624a660.jpg',
    'https://i.pinimg.com/736x/59/c5/9f/59c59f3baf4f0a66709d66556612aeea.jpg',
]

bot = telebot.TeleBot(BOT_TOKEN)
processed_cards = set()
cards_in_progress = set()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ------------------- FUNCIONES AUXILIARES -------------------
async def get_bin_info(bin_number: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{bin_number}") as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"Error BIN: {e}")
    return {"brand": "N/A", "type": "N/A", "level": "N/A",
            "bank": "N/A", "country_name": "N/A", "country_flag": "❓"}

def clean_text(text: str) -> str:
    if not text or text == "Not Found":
        return text
    cleaned = re.sub(r'[\*\`"\']', '', text)
    cleaned = re.sub(r'[⚡💳✅✓]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def remove_spoiler(text: str) -> str:
    return re.sub(r'\|\|([^|]+)\|\|', r'\1', text)

def extract_card_info(text: str) -> dict | None:
    text_clean = remove_spoiler(text)
    text_upper = text_clean.upper()
    
    print("\n--- Procesando mensaje ---")
    print(text_clean[:500] + "..." if len(text_clean) > 500 else text_clean)
    print("---")

    # ---------- PATRONES CC ----------
    card_patterns = [
        r'(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'(\d{14,16}):(\d{1,2}):(\d{2,4}):(\d{3,4})',
        r'[Cc][Cc]\s*[:|]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'[Cc]ard\s*[:|]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'(\d{14,16})\s*[|]\s*(\d{1,2})\s*[|]\s*(\d{2,4})\s*[|]\s*(\d{3,4})',
        r'💳\s*[:|]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'⚡\s*[Cc][Cc]\s*[:|]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'(\d{14,16})-(\d{1,2})-(\d{2,4})-(\d{3,4})',
    ]
    
    match_cc = None
    for pat in card_patterns:
        match_cc = re.search(pat, text_clean, re.IGNORECASE)
        if match_cc:
            break
    
    if not match_cc:
        print("No se encontró tarjeta")
        return None

    cc, month, year, cvv = match_cc.groups()
    card_info = f"{cc}|{month}|{year}|{cvv}"
    bin_num = cc[:6]

    # ---------- FILTRADO DE APROBACIÓN (MEJORADO) ----------
    # Palabras de éxito - AHORA INCLUYE "LIVE" explícitamente
    success_keywords = r'(?:APPROVED|APROBADA|LIVE|LIVE ✅|CHARGED|CHARGE|AUTH|AUTHORIZED|ADDED|SUCCESSFUL|EXITOSA|COMPLETED|ACCEPTED|CCN LIVE|CARD LIVE|CVV LIVE)'
    # Palabras de rechazo
    reject_keywords = r'DEAD|DENIED|REJECTED|ERROR|INCORRECT|TIMEOUT|DECLINED|EXPIRED|FAILED|INSUFFICIENT'

    has_success = re.search(success_keywords, text_upper, re.IGNORECASE)
    has_reject = re.search(reject_keywords, text_upper, re.IGNORECASE)

    # Si NO hay éxito O hay rechazo, ignorar
    if not has_success:
        print("No se encontró aprobación o LIVE")
        return None
    if has_reject:
        print("Se encontró rechazo")
        return None

    # ---------- EXTRACCIÓN DE GATEWAY ----------
    gateway = "Not Found"
    # AÑADIDO SHOPIFY y más gateways
    gateway_keywords = r'(?:BRAINTREE|STRIPE|ADYEN|PAYFLOW|EAGLE|CHECKOUT|AUTH|GATEWAY|CHECKER|CHK|PLUG|VITAL|AUTHORIZE|AUTHORIZED|SHOPIFY|SHOPIFY PAYMENTS|SHOPIFY CHECKOUT)'
    
    gateway_patterns = [
        r'(?:GATEWAY|GATE|PASARELA|𝙂𝙖𝙩𝙚𝙬𝙖𝙮|𝗚𝗮𝘁𝗲|𝐆𝐚𝐭𝐞𝐰𝐚𝐲)\s*[:|»➸-]\s*([^\n\r]+)',
        r'⚡\s*Gat[ée]\s*[:|»➸-]\s*([^\n\r]+)',
        r'⚡\s*Gate[wy]?\s*[:|»➸-]\s*([^\n\r]+)',
        r'#([A-Za-z0-9_\s]+)',
    ]
    
    for pattern in gateway_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            gateway = clean_text(match.group(1).strip())
            if re.search(r'\d{14,16}', gateway):
                continue
            break
    
    # Si no se encontró, buscar palabras clave en todo el texto
    if gateway == "Not Found":
        keywords = re.findall(gateway_keywords, text_clean, re.IGNORECASE)
        if keywords:
            seen = set()
            unique = [kw for kw in keywords if not (kw in seen or seen.add(kw))]
            gateway = ' | '.join(unique)
            gateway = clean_text(gateway)
    
    print(f"Gateway detectado: {gateway}")

    # ---------- EXTRACCIÓN DE STATUS ----------
    status = "Approved ✓"
    status_patterns = [
        r'(?:STATUS|RESULT|ESTADO|𝙎𝙩𝙖𝙩𝙪𝙨|𝗦𝘁𝗮𝘁𝘂𝘀|𝐒𝐭𝐚𝐭𝐮𝐬|𝐑𝐞𝐬𝐮𝐥𝐭)\s*[:|»➸-]\s*([^\n\r]+)',
        r'⚡\s*Status\s*[:|»➸-]\s*([^\n\r]+)',
    ]
    for pattern in status_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            status = clean_text(match.group(1).strip())
            break
    
    # Si el mensaje tiene "LIVE" en el título, poner status "Live ✓"
    if re.search(r'\bLIVE\b', text_upper):
        status = "Live ✓"

    # ---------- EXTRACCIÓN DE RESPONSE ----------
    response = "Not Found"
    response_patterns = [
        r'(?:RESPONSE|RESULT|MESSAGE|𝙍𝙚𝙨𝙪𝙡𝙩|𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲|𝐌𝐞𝐬𝐬𝐚𝐠𝐞)\s*[:|»➸-]\s*([^\n\r]+)',
        r'⚡\s*Response\s*[:|»➸-]\s*([^\n\r]+)',
    ]
    for pattern in response_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            response = clean_text(match.group(1).strip())
            response = re.sub(r'^\d+\s*:\s*', '', response).strip()
            break

    # ---------- EXTRACCIÓN DE BANK ----------
    bank = "Not Found"
    bank_patterns = [
        r'(?:BANK|ISSUING BANK|BANCO|𝘽𝗮𝗻𝗸|𝗜𝘀𝘀𝘂𝗲𝗿|𝐁𝐚𝐧𝐤)\s*[:|»➸-]\s*([^\n\r]+)',
        r'⚡\s*Bank\s*[:|»➸-]\s*([^\n\r]+)',
    ]
    for pattern in bank_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            bank = clean_text(match.group(1).strip())
            break

    # ---------- EXTRACCIÓN DE COUNTRY ----------
    country = "Not Found"
    flag = "❓"
    country_patterns = [
        r'(?:COUNTRY|PAIS|𝘾𝙤𝙪𝙣𝙩𝙧𝙮|𝗖𝗼𝘂𝗻𝘁𝗿𝘆|𝐂𝐨𝐮𝐧𝐭𝐫𝐲)\s*[:|»➸-]\s*([^\n\r]+)',
        r'⚡\s*Country\s*[:|»➸-]\s*([^\n\r]+)',
    ]
    for pattern in country_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            country = clean_text(match.group(1).strip())
            flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
            if flag_match:
                flag = flag_match.group(1)
                country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()
            break

    # ---------- EXTRACCIÓN DE BIN INFO ----------
    brand = "Unknown"
    card_type = "Unknown"
    level = "Unknown"
    
    bin_info_match = re.search(r'(?:BIN|INFO|DATA|INFORMACION|𝗕𝗶𝗻|𝗧𝘆𝗽𝗲|𝐁𝐢𝐧 𝐈𝐧𝐟𝐨)\s*[:|»➸-]\s*([^\n\r]+)', text_clean, re.IGNORECASE)
    bin_info = bin_info_match.group(1).strip() if bin_info_match else ""
    
    if bin_info:
        # Buscar Brand
        brand_match = re.search(r'Brand\s*[:|»➸-]\s*([^\n\r]+)', bin_info, re.IGNORECASE)
        if brand_match:
            brand = clean_text(brand_match.group(1).strip())
        else:
            parts = re.split(r'[|]', bin_info)
            if parts and len(parts) > 0:
                if 'VISA' in parts[0].upper() or 'MASTERCARD' in parts[0].upper() or 'AMEX' in parts[0].upper():
                    brand = clean_text(parts[0].strip())
        
        type_match = re.search(r'Type\s*[:|»➸-]\s*([^\n\r]+)', bin_info, re.IGNORECASE)
        if type_match:
            card_type = clean_text(type_match.group(1).strip())
        
        level_match = re.search(r'Level\s*[:|»➸-]\s*([^\n\r]+)', bin_info, re.IGNORECASE)
        if level_match:
            level = clean_text(level_match.group(1).strip())

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

# ------------------- MANEJADOR -------------------
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
        print(f"Tarjeta {card_clean} ya procesada")
        return
    if card_clean in cards_in_progress:
        print(f"Tarjeta {card_clean} en proceso")
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
                    print(f"Fallo: {e}")
            except Exception as e:
                print(f"Error: {e}")
                break
    finally:
        cards_in_progress.discard(card_clean)

# ------------------- ARRANQUE -------------------
async def main():
    print("Iniciando cliente...")
    await client.start()
    print("¡Bot en ejecución!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
