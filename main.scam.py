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
    """Convierte caracteres UNICODE a ASCII normal y sube a mayúsculas"""
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

def extract_field(text: str, field_names: list, default="Not Found") -> str:
    """Extrae un campo del texto con múltiples nombres y separadores"""
    separators = r'[:|»➸↠\-–—]'
    pattern = r'(?:' + '|'.join(field_names) + r')\s*' + separators + r'\s*([^\n\r]+)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return clean_text(match.group(1).strip())
    return default

def extract_gateway(text: str, text_norm: str) -> str:
    """
    Extrae el gateway de forma inteligente.
    SOLO acepta palabras conocidas, NUNCA números.
    """
    # Lista de gateways válidos (SOLO letras)
    VALID_GATEWAYS = [
        'BRAINTREE', 'STRIPE', 'ADYEN', 'PAYFLOW', 'EAGLE', 
        'CHECKOUT', 'AUTH', 'GATEWAY', 'CHECKER', 'CHK', 
        'PLUG', 'VITAL', 'SHOPIFY', 'ZAREK', 'PAYPAL',
        'AUTHORIZE', 'AUTHORIZED', 'STRIPE V2', 'STRIPE V3',
        'BRAINTREE AUTH', 'SHOPIFY PAYMENTS'
    ]
    
    # 1. Buscar campo etiquetado
    gateway_field = extract_field(text, ['GATEWAY', 'GATE', 'PASARELA', 'GW'])
    if gateway_field != "Not Found":
        # Limpiar y verificar que NO sea un número
        cleaned = clean_text(gateway_field)
        # Si tiene números de tarjeta (14-16 dígitos), ignorar
        if re.search(r'\d{14,16}', cleaned):
            print(f"⚠️ Gateway ignorado (parece número de tarjeta): {cleaned}")
        # Si tiene #BIN seguido de números, ignorar
        elif re.search(r'#\d{6}', cleaned):
            print(f"⚠️ Gateway ignorado (parece BIN): {cleaned}")
        # Si tiene solo números (o principalmente números), ignorar
        elif re.search(r'^\d+$', cleaned.replace(' ', '')):
            print(f"⚠️ Gateway ignorado (solo números): {cleaned}")
        else:
            # Verificar que contenga al menos una palabra válida
            for gw in VALID_GATEWAYS:
                if gw in cleaned.upper():
                    return cleaned
            # Si no contiene ninguna palabra válida, pero es texto, devolverlo
            # (puede ser un gateway no listado)
            if len(cleaned) > 1 and not re.search(r'^\d+$', cleaned.replace(' ', '')):
                return cleaned
    
    # 2. Buscar palabras clave en el texto normalizado
    found = []
    for gw in VALID_GATEWAYS:
        if gw in text_norm:
            found.append(gw)
    
    if found:
        # Eliminar duplicados manteniendo orden
        seen = set()
        unique = [gw for gw in found if not (gw in seen or seen.add(gw))]
        return ' | '.join(unique)
    
    # 3. Buscar en campos de "Bin Info" o similar
    bin_section = re.search(r'(?:BIN INFO|BIN|INFO)(?:[:|»➸↠\-–—])\s*([^\n\r]+)', text, re.IGNORECASE)
    if bin_section:
        bin_text = bin_section.group(1).strip()
        for gw in VALID_GATEWAYS:
            if gw in bin_text.upper():
                return gw
    
    return "Not Found"

def extract_card_info(text: str) -> dict | None:
    print("\n" + "="*60)
    print("📨 PROCESANDO MENSAJE:")
    print(text[:500] + "..." if len(text) > 500 else text)
    print("="*60)
    
    # ---------- EXTRAER TARJETA ----------
    text_clean = re.sub(r'\|\|([^|]+)\|\|', r'\1', text)
    
    card_patterns = [
        r'(\d{14,16})\s*[|:]\s*(\d{1,2})\s*[|:]\s*(\d{2,4})\s*[|:]\s*(\d{3,4})',
        r'(?:CC|CARD)\s*[↠»➸:]\s*(\d{14,16})\s*[|:]\s*(\d{1,2})\s*[|:]\s*(\d{2,4})\s*[|:]\s*(\d{3,4})',
        r'(\d{14,16})\s*-\s*(\d{1,2})\s*-\s*(\d{2,4})\s*-\s*(\d{3,4})',
        r'(\d{14,16})\s*/\s*(\d{1,2})\s*/\s*(\d{2,4})\s*/\s*(\d{3,4})',
    ]
    
    match_cc = None
    for pattern in card_patterns:
        match_cc = re.search(pattern, text_clean, re.IGNORECASE)
        if match_cc:
            print(f"✅ CC ENCONTRADO")
            break
    
    if not match_cc:
        print("❌ No se encontró tarjeta")
        return None
    
    cc, month, year, cvv = match_cc.groups()
    card_info = f"{cc}|{month}|{year}|{cvv}"
    bin_num = cc[:6]
    print(f"💳 Tarjeta: {card_info}")

    # ---------- NORMALIZAR TEXTO ----------
    text_norm = normalize_text(text_clean)

    # ---------- EXTRACCIÓN DE STATUS Y RESULT ----------
    status_field = extract_field(text_clean, ['STATUS', 'ESTADO', 'STAT', 'ESTATUS'])
    result_field = extract_field(text_clean, ['RESULT', 'RESPONSE', 'MESSAGE', 'MSG', 'REPLY'])
    
    if result_field == "Not Found":
        result_match = re.search(r'Result\s*[↠»➸]\s*([^\n\r]+)', text_clean, re.IGNORECASE)
        if result_match:
            result_field = clean_text(result_match.group(1).strip())
    
    print(f"📊 Status extraído: {status_field}")
    print(f"📝 Result extraído: {result_field}")

    # ---------- FILTRADO DE APROBACIÓN ----------
    success_words = ['APPROVED', 'APROBADA', 'LIVE', 'CHARGED', 'CHARGE', 
                     'AUTH', 'AUTHORIZED', 'ADDED', 'SUCCESSFUL', 'EXITOSA',
                     'COMPLETED', 'ACCEPTED', 'OK', 'VALID', 'ACTIVE']
    
    reject_words = ['DEAD', 'DENIED', 'REJECTED', 'ERROR', 'INCORRECT', 
                    'TIMEOUT', 'DECLINED', 'EXPIRED', 'FAILED', 'INSUFFICIENT',
                    'CANCELED', 'CANCELLED', 'INVALID', 'BLOCKED']
    
    has_success = False
    has_reject = False
    
    if status_field != "Not Found":
        status_upper = status_field.upper()
        has_success = any(word in status_upper for word in success_words)
        has_reject = any(word in status_upper for word in reject_words)
    
    if status_field == "Not Found":
        has_success = any(word in text_norm for word in success_words)
    
    if has_reject:
        print("❌ Mensaje RECHAZADO (Status contiene rechazo)")
        return None
    
    if not has_success:
        print("❌ Mensaje IGNORADO (Status no tiene éxito)")
        return None
    
    print("✅ MENSAJE APROBADO!")

    # ---------- ASIGNAR STATUS ----------
    if status_field != "Not Found":
        status = status_field
    elif 'LIVE' in text_norm:
        status = "Live ✓"
    else:
        status = "Approved ✓"
    
    print(f"📊 Status final: {status}")

    # ---------- ASIGNAR RESPONSE ----------
    response = result_field if result_field != "Not Found" else "Not Found"
    if response != "Not Found":
        response = re.sub(r'^\d+\s*[:|»➸]\s*', '', response).strip()
    
    print(f"📝 Response final: {response}")

    # ---------- EXTRACCIÓN DE GATEWAY (MEJORADA) ----------
    gateway = extract_gateway(text_clean, text_norm)
    print(f"🚪 Gateway: {gateway}")

    # ---------- EXTRACCIÓN DE BANK ----------
    bank = "Not Found"
    bank_field = extract_field(text_clean, ['BANK', 'BANCO', 'ISSUER'])
    if bank_field != "Not Found":
        bank = bank_field
    else:
        bin_section = re.search(r'(?:BIN INFO|BIN|INFO)(?:[:|»➸↠\-–—])\s*([^\n\r]+)', text_clean, re.IGNORECASE)
        if bin_section:
            bin_text = bin_section.group(1).strip()
            bank_match = re.search(r'Bank\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
            if bank_match:
                bank = clean_text(bank_match.group(1).strip())
    
    print(f"🏦 Bank: {bank}")

    # ---------- EXTRACCIÓN DE COUNTRY ----------
    country = "Not Found"
    flag = "❓"
    country_field = extract_field(text_clean, ['COUNTRY', 'PAIS'])
    if country_field != "Not Found":
        country = country_field
        flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
        if flag_match:
            flag = flag_match.group(1)
            country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()
    else:
        bin_section = re.search(r'(?:BIN INFO|BIN|INFO)(?:[:|»➸↠\-–—])\s*([^\n\r]+)', text_clean, re.IGNORECASE)
        if bin_section:
            bin_text = bin_section.group(1).strip()
            country_match = re.search(r'Country\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
            if country_match:
                country = clean_text(country_match.group(1).strip())
                flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
                if flag_match:
                    flag = flag_match.group(1)
                    country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()
    
    print(f"🌍 Country: {country} {flag}")

    # ---------- EXTRACCIÓN DE BRAND, TYPE, LEVEL ----------
    brand = "Unknown"
    card_type = "Unknown"
    level = "Unknown"
    
    bin_section = re.search(r'(?:BIN INFO|BIN|INFO)(?:[:|»➸↠\-–—])\s*([^\n\r]+)', text_clean, re.IGNORECASE)
    if bin_section:
        bin_text = bin_section.group(1).strip()
        
        brand_match = re.search(r'Brand\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
        if brand_match:
            brand = clean_text(brand_match.group(1).strip())
        else:
            for kw in ['VISA', 'MASTERCARD', 'AMEX', 'DISCOVER']:
                if kw in bin_text.upper():
                    brand = kw
                    break
        
        type_match = re.search(r'Type\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
        if type_match:
            card_type = clean_text(type_match.group(1).strip())
        
        level_match = re.search(r'Level\s*[↠»➸]\s*([^\n\r]+)', bin_text, re.IGNORECASE)
        if level_match:
            level = clean_text(level_match.group(1).strip())
    
    print(f"🏷️ Brand: {brand}, Type: {card_type}, Level: {level}")

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
        print(f"⏭️ Tarjeta {card_clean} ya procesada")
        return
    if card_clean in cards_in_progress:
        print(f"⏳ Tarjeta {card_clean} en proceso")
        return

    cards_in_progress.add(card_clean)
    print(f"🔄 Procesando tarjeta: {card_clean}")

    try:
        bin_info = await get_bin_info(card_data['bin_number'])
        if bin_info.get('brand') and bin_info['brand'] != 'N/A':
            card_data['brand'] = clean_text(bin_info['brand'])
        if bin_info.get('type') and bin_info['type'] != 'N/A':
            card_data['type'] = clean_text(bin_info['type'])
        if bin_info.get('level') and bin_info['level'] != 'N/A':
            card_data['level'] = clean_text(bin_info['level'])
        if bin_info.get('bank') and bin_info['bank'] != 'N/A':
            card_data['bank'] = clean_text(bin_info['bank'])
        if bin_info.get('country_name') and bin_info['country_name'] != 'N/A':
            card_data['country'] = clean_text(bin_info['country_name'])
        if bin_info.get('country_flag') and bin_info['country_flag'] != '❓':
            card_data['flag'] = bin_info['country_flag']

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
                print(f"✅ Mensaje ENVIADO para tarjeta {card_clean}")
                processed_cards.add(card_clean)
                break
            except telebot.apihelper.ApiException as e:
                if 'Too Many Requests' in str(e):
                    print(f"⏳ Rate limit, esperando 5s... (intento {attempt+1}/3)")
                    await asyncio.sleep(5)
                elif attempt < 2:
                    await asyncio.sleep(3)
                else:
                    print(f"❌ Fallo después de 3 intentos: {e}")
            except Exception as e:
                print(f"❌ Error al enviar: {e}")
                break
    finally:
        cards_in_progress.discard(card_clean)

# ------------------- ARRANQUE -------------------
async def main():
    print("🚀 Iniciando cliente de Telegram...")
    await client.start()
    print("✅ ¡Bot en ejecución! Esperando mensajes...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
