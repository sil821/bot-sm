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

# ------------------- FUNCIONES -------------------
def clean_text(text: str) -> str:
    if not text:
        return "Not Found"
    # Solo limpiar caracteres molestos, sin eliminar información
    cleaned = re.sub(r'[\*\`]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def get_field(text: str, field_name: str) -> str:
    """
    EXTRAE LO QUE SALE DESPUÉS DE UN CAMPO.
    Ej: "Response: Charged 1$" -> "Charged 1$"
    """
    # Buscar el campo con diferentes separadores
    patterns = [
        rf'{field_name}\s*[:|»➸↠\-–—]\s*([^\n\r]+)',
        rf'⚜️\s*{field_name}\s*[-»:]\s*([^\n\r]+)',
        rf'⚡\s*{field_name}\s*[-»:]\s*([^\n\r]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_text(match.group(1).strip())
    
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
        r'(?:CC|CARD)\s*[-»:]\s*(\d{14,16})\s*[|:]\s*(\d{1,2})\s*[|:]\s*(\d{2,4})\s*[|:]\s*(\d{3,4})',
        r'(\d{14,16})\s*-\s*(\d{1,2})\s*-\s*(\d{2,4})\s*-\s*(\d{3,4})',
        r'(\d{14,16})\s*/\s*(\d{1,2})\s*/\s*(\d{2,4})\s*/\s*(\d{3,4})',
    ]
    
    match_cc = None
    for pattern in card_patterns:
        match_cc = re.search(pattern, text_clean, re.IGNORECASE)
        if match_cc:
            break
    
    if not match_cc:
        print("❌ No se encontró tarjeta")
        return None
    
    cc, month, year, cvv = match_cc.groups()
    card_info = f"{cc}|{month}|{year}|{cvv}"
    bin_num = cc[:6]
    print(f"💳 Tarjeta: {card_info}")

    # ---------- EXTRAER STATUS ----------
    status = get_field(text_clean, "STATUS")
    if status == "Not Found":
        status = get_field(text_clean, "ESTADO")
    if status == "Not Found":
        status = get_field(text_clean, "STAT")
    if status == "Not Found":
        status = "Approved ✓"  # Por defecto si no encuentra

    print(f"📊 Status: {status}")

    # ---------- EXTRAER RESPONSE ----------
    response = get_field(text_clean, "RESPONSE")
    if response == "Not Found":
        response = get_field(text_clean, "RESULT")
    if response == "Not Found":
        response = get_field(text_clean, "MESSAGE")
    
    print(f"📝 Response: {response}")

    # ---------- EXTRAER GATEWAY ----------
    gateway = get_field(text_clean, "GATEWAY")
    if gateway == "Not Found":
        gateway = get_field(text_clean, "GATE")
    if gateway == "Not Found":
        gateway = get_field(text_clean, "PASARELA")
    
    print(f"🚪 Gateway: {gateway}")

    # ---------- EXTRAER BANK ----------
    bank = get_field(text_clean, "BANK")
    if bank == "Not Found":
        bank = get_field(text_clean, "BANCO")
    
    print(f"🏦 Bank: {bank}")

    # ---------- EXTRAER COUNTRY ----------
    country = get_field(text_clean, "COUNTRY")
    if country == "Not Found":
        country = get_field(text_clean, "PAIS")
    
    flag = "❓"
    if country != "Not Found":
        flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
        if flag_match:
            flag = flag_match.group(1)
            country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()
    
    print(f"🌍 Country: {country} {flag}")

    # ---------- EXTRAER BRAND, TYPE, LEVEL ----------
    brand = "Unknown"
    card_type = "Unknown"
    level = "Unknown"
    
    bin_info = get_field(text_clean, "BIN INFO")
    if bin_info == "Not Found":
        bin_info = get_field(text_clean, "INFO")
    
    if bin_info != "Not Found":
        parts = [p.strip() for p in bin_info.split('-') if p.strip()]
        if len(parts) >= 3:
            card_type = clean_text(parts[0])
            brand = clean_text(parts[1])
            level = clean_text(parts[2])
        elif len(parts) >= 2:
            card_type = clean_text(parts[0])
            brand = clean_text(parts[1])
    
    if brand == "Unknown":
        brand_field = get_field(text_clean, "BRAND")
        if brand_field != "Not Found":
            brand = brand_field
    
    if card_type == "Unknown":
        type_field = get_field(text_clean, "TYPE")
        if type_field != "Not Found":
            card_type = type_field
    
    if level == "Unknown":
        level_field = get_field(text_clean, "LEVEL")
        if level_field != "Not Found":
            level = level_field
    
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
        return
    if card_clean in cards_in_progress:
        return

    cards_in_progress.add(card_clean)

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
    print("🚀 Iniciando cliente de Telegram...")
    await client.start()
    print("✅ ¡Bot en ejecución!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
