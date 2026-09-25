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

COUNTRY_FLAGS = {
    'ESP': '🇪🇸', 'SPAIN': '🇪🇸',
    'USA': '🇺🇸', 'US': '🇺🇸', 'UNITED STATES': '🇺🇸',
    'MEX': '🇲🇽', 'MEXICO': '🇲🇽',
    'ARG': '🇦🇷', 'ARGENTINA': '🇦🇷',
    'BRA': '🇧🇷', 'BRAZIL': '🇧🇷',
    'COL': '🇨🇴', 'COLOMBIA': '🇨🇴',
    'CHL': '🇨🇱', 'CHILE': '🇨🇱',
    'PER': '🇵🇪', 'PERU': '🇵🇪',
    'GBR': '🇬🇧', 'UK': '🇬🇧', 'UNITED KINGDOM': '🇬🇧',
    'FRA': '🇫🇷', 'FRANCE': '🇫🇷',
    'DEU': '🇩🇪', 'GERMANY': '🇩🇪',
    'ITA': '🇮🇹', 'ITALY': '🇮🇹',
    'JPN': '🇯🇵', 'JAPAN': '🇯🇵',
    'CHN': '🇨🇳', 'CHINA': '🇨🇳',
    'CAN': '🇨🇦', 'CANADA': '🇨🇦',
    'AUS': '🇦🇺', 'AUSTRALIA': '🇦🇺',
    'IND': '🇮🇳', 'INDIA': '🇮🇳',
    'RUS': '🇷🇺', 'RUSSIA': '🇷🇺',
    'LKA': '🇱🇰', 'SRI LANKA': '🇱🇰',
    'SGP': '🇸🇬', 'SINGAPORE': '🇸🇬',
    'HKG': '🇭🇰', 'HONG KONG': '🇭🇰',
    'NLD': '🇳🇱', 'NETHERLANDS': '🇳🇱',
    'CHE': '🇨🇭', 'SWITZERLAND': '🇨🇭',
    'SWE': '🇸🇪', 'SWEDEN': '🇸🇪',
    'NOR': '🇳🇴', 'NORWAY': '🇳🇴',
    'DNK': '🇩🇰', 'DENMARK': '🇩🇰',
    'POL': '🇵🇱', 'POLAND': '🇵🇱',
    'PRT': '🇵🇹', 'PORTUGAL': '🇵🇹',
    'IRL': '🇮🇪', 'IRELAND': '🇮🇪',
    'ZAF': '🇿🇦', 'SOUTH AFRICA': '🇿🇦',
    'NZL': '🇳🇿', 'NEW ZEALAND': '🇳🇿',
    'KOR': '🇰🇷', 'SOUTH KOREA': '🇰🇷',
    'THA': '🇹🇭', 'THAILAND': '🇹🇭',
    'MYS': '🇲🇾', 'MALAYSIA': '🇲🇾',
    'IDN': '🇮🇩', 'INDONESIA': '🇮🇩',
    'PHL': '🇵🇭', 'PHILIPPINES': '🇵🇭',
    'VNM': '🇻🇳', 'VIETNAM': '🇻🇳',
    'ARE': '🇦🇪', 'UAE': '🇦🇪',
    'SAU': '🇸🇦', 'SAUDI ARABIA': '🇸🇦',
    'ISR': '🇮🇱', 'ISRAEL': '🇮🇱',
    'TUR': '🇹🇷', 'TURKEY': '🇹🇷',
    'UKR': '🇺🇦', 'UKRAINE': '🇺🇦',
    'ROU': '🇷🇴', 'ROMANIA': '🇷🇴',
    'GRC': '🇬🇷', 'GREECE': '🇬🇷',
    'HUN': '🇭🇺', 'HUNGARY': '🇭🇺',
    'CZE': '🇨🇿', 'CZECH REPUBLIC': '🇨🇿',
    'AUT': '🇦🇹', 'AUSTRIA': '🇦🇹',
    'BEL': '🇧🇪', 'BELGIUM': '🇧🇪',
    'FIN': '🇫🇮', 'FINLAND': '🇫🇮',
}

def clean_text(text: str) -> str:
    if not text:
        return "Not Found"
    cleaned = re.sub(r'__\s*', '', text)
    cleaned = re.sub(r'[\*\`"\']', '', cleaned)
    cleaned = re.sub(r'[⚡💳✅✓♻️⚜️〄⪼]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ASCII', 'ignore').decode('ASCII')
    return text

def get_flag_for_country(country: str) -> str:
    if not country:
        return "❓"
    country_upper = country.upper().strip()
    for key, flag in COUNTRY_FLAGS.items():
        if key in country_upper:
            return flag
    return "❓"

def get_field_flexible(text: str, field_names: list) -> str:
    separators = r'[:|»➸↠\-–—┊⌁]'
    text_norm = normalize_text(text)
    
    for field_name in field_names:
        patterns = [
            rf'{field_name}\s*{separators}\s*([^\n\r]+)',
            rf'{field_name}\s*:\s*([^\n\r]+)',
            rf'{field_name}\s*[-»┊⌁]\s*([^\n\r]+)',
            rf'\|\s*{field_name}\s*{separators}\s*([^\n\r]+)',
            rf'⚜️\s*{field_name}\s*{separators}\s*([^\n\r]+)',
            rf'⚡\s*{field_name}\s*{separators}\s*([^\n\r]+)',
            rf'〄\s*{field_name}\s*{separators}\s*([^\n\r]+)',
            rf'⪼\s*{field_name}\s*{separators}\s*([^\n\r]+)',
            rf'🔐\s*{field_name}\s*{separators}\s*([^\n\r]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result = clean_text(match.group(1).strip())
                if result and len(result) > 0:
                    return result
        
        for pattern in patterns:
            match = re.search(pattern, text_norm, re.IGNORECASE)
            if match:
                result = clean_text(match.group(1).strip())
                if result and len(result) > 0:
                    return result
    
    return "Not Found"

def extract_response(text: str) -> str:
    response_names = [
        "R2", "RESPONSE", "RESULT", "MESSAGE", "MSG", "REPLY",
        "RESPUESTA", "RESULTADO", "MENSAJE", "R1"
    ]
    
    text_norm = normalize_text(text)
    separators = r'[:|»➸↠\-–—┊⌁]'
    
    for name in response_names:
        patterns = [
            rf'{name}\s*{separators}\s*([^\n\r]+)',
            rf'{name}\s*:\s*([^\n\r]+)',
            rf'{name}\s*[-»┊⌁]\s*([^\n\r]+)',
            rf'⚜️\s*{name}\s*{separators}\s*([^\n\r]+)',
            rf'⚡\s*{name}\s*{separators}\s*([^\n\r]+)',
            rf'〄\s*{name}\s*{separators}\s*([^\n\r]+)',
            rf'⪼\s*{name}\s*{separators}\s*([^\n\r]+)',
            rf'🔐\s*{name}\s*{separators}\s*([^\n\r]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result = clean_text(match.group(1).strip())
                if result and len(result) > 0 and result != "$0.0":
                    return result
        
        for pattern in patterns:
            match = re.search(pattern, text_norm, re.IGNORECASE)
            if match:
                result = clean_text(match.group(1).strip())
                if result and len(result) > 0 and result != "$0.0":
                    return result
    
    return "Not Found"

def extract_gateway(text: str) -> str:
    GATEWAY_KEYWORDS = [
        'BRAINTREE', 'STRIPE', 'ADYEN', 'PAYPAL', 'SHOPIFY', 'ZAREK',
        'PAYFLOW', 'EAGLE', 'CHECKOUT', 'AUTH', 'CHECKER',
        'CHK', 'PLUG', 'VITAL', 'AUTHORIZE', 'AUTHORIZED', 'ATREUS',
        '2CHECKOUT', 'PAYMENTWALL', 'PAYSAFE', 'SKRILL', 'NETELLER',
        'WEBMONEY', 'PERFECT MONEY', 'PAYONEER', 'WORLDPAY', 'SAGE PAY',
        'REALEX', 'NMI', 'BLUE SNAP', 'VERIFONE', 'FIRST DATA',
        'ELAVON', 'PAYMENT DEPOT', 'DURANGO', 'BAMBORA', 'PROCESSOR',
        'PASARELA', 'PAYMENT', 'RIN'
    ]
    
    gate = get_field_flexible(text, ["GATEWAY", "GATE", "PASARELA", "𝑮𝑨𝑻𝑬", "𝐆𝐚𝐭𝐞", "𝗚𝗮𝘁𝗲"])
    type_field = get_field_flexible(text, ["TYPE", "TIPO"])
    
    if gate != "Not Found":
        gate = clean_text(gate).upper()
        if re.search(r'\d{14,16}', gate):
            gate = "Not Found"
    
    if gate != "Not Found":
        if type_field != "Not Found":
            type_clean = clean_text(type_field).strip().upper()
            type_clean = re.split(r'\s*[|]\s*|\s+GATE\s*[:|]|\s+GATEWAY\s*[:|]', type_clean)[0].strip()
            if type_clean and len(type_clean) < 20 and not re.search(r'\d{14,16}', type_clean):
                return f"{gate} {type_clean}"
        return gate
    
    first_line = text.split('\n')[0] if text else ""
    for gw in GATEWAY_KEYWORDS:
        if gw in first_line.upper():
            match = re.search(r'#([A-Za-z]+)\s*~\s*([A-Za-z]+)', first_line, re.IGNORECASE)
            if match:
                return f"{match.group(1).strip()} {match.group(2).strip()}".upper()
            return gw.upper()
    
    text_upper = text.upper()
    text_norm = normalize_text(text).upper()
    found_gateways = []
    for gw in GATEWAY_KEYWORDS:
        if gw in text_upper or gw in text_norm:
            if gw not in found_gateways:
                found_gateways.append(gw)
    
    if found_gateways:
        return (' | '.join(found_gateways) if len(found_gateways) > 1 else found_gateways[0]).upper()
    
    return "Not Found"

def extract_mass_cards(text: str) -> list:
    """Extrae TODAS las tarjetas APPROVED de un mensaje MASS."""
    mass_cards = []
    
    pattern = r'\[[\U0001F1E6-\U0001F1FF]+\]\s*(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})\s*\n\s*\[([✅❌])\]\s*([^\n\r]+)'
    matches = re.findall(pattern, text)
    
    if not matches:
        pattern2 = r'(\d{14,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})\s*\n\s*\[([✅❌])\]\s*([^\n\r]+)'
        matches = re.findall(pattern2, text)
    
    for match in matches:
        cc = match[0]
        month = match[1]
        year = match[2]
        cvv = match[3]
        emoji = match[4]
        response = clean_text(match[5].strip())
        
        if emoji == '✅':
            mass_cards.append({
                "cc": cc,
                "month": month,
                "year": year,
                "cvv": cvv,
                "response": response,
                "card_info": f"{cc}|{month}|{year}|{cvv}",
                "bin_number": cc[:6]
            })
    
    return mass_cards

def extract_card_info(text: str) -> dict | None:
    print("\n" + "="*60)
    print("📨 PROCESANDO MENSAJE:")
    print(text[:500] + "..." if len(text) > 500 else text)
    print("="*60)
    
    text_clean = re.sub(r'\|\|([^|]+)\|\|', r'\1', text)
    
    card_patterns = [
        r'(\d{14,16})\s*[|:]\s*(\d{1,2})\s*[|:]\s*(\d{2,4})\s*[|:]\s*(\d{3,4})',
        r'(?:CC|CARD|Tarjeta|QUERY|IN)\s*[-»:┊⌁]\s*(\d{14,16})\s*[|:]\s*(\d{1,2})\s*[|:]\s*(\d{2,4})\s*[|:]\s*(\d{3,4})',
        r'〄\s*Card\s*[┊⌁:]\s*(\d{14,16})\s*[|:]\s*(\d{1,2})\s*[|:]\s*(\d{2,4})\s*[|:]\s*(\d{3,4})',
        r'⪼\s*Tarjeta\s*[┊⌁:]\s*(\d{14,16})\s*[|:]\s*(\d{1,2})\s*[|:]\s*(\d{2,4})\s*[|:]\s*(\d{3,4})',
        r'⚜️\s*CC\s*[-»:]\s*(\d{14,16})\s*[|:]\s*(\d{1,2})\s*[|:]\s*(\d{2,4})\s*[|:]\s*(\d{3,4})',
        r'🔐\s*QUERY\s*[-»:]\s*(\d{14,16})\s*[|:]\s*(\d{1,2})\s*[|:]\s*(\d{2,4})\s*[|:]\s*(\d{3,4})',
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

    status = get_field_flexible(text_clean, ["S1", "STATUS", "ESTADO", "ESTATUS", "STAT", "R1", "𝑺𝒕𝒂𝒕𝒖𝒔", "𝐒𝐭𝐚𝐭𝐮𝐬", "𝗦𝘁𝗮𝘁𝘂𝘀", "Estado"])
    
    if status != "Not Found":
        status_upper = status.upper()
        success_words = ['APPROVED', 'APROBADA', 'LIVE', 'CHARGED', 'CHARGE', 'AUTH', 'AUTHORIZED', 'OK', 'VALID', 'ACTIVE']
        reject_words = [
            'DECLINED', 'DENIED', 'REJECTED', 'ERROR', 'FAILED', 'EXPIRED',
            'INVALID', 'BANNED', 'BLOCKED', 'RETRY', 'RETAIN', 'TRY AGAIN',
            'TIMEOUT', 'CANCELED', 'CANCELLED', 'UNABLE', 'INCORRECT',
            'INCORRECT_CVV', 'INCORRECT CVV', 'CALL', 'REFER', 'STOLEN',
            'LOST', 'RESTRICTED', 'FRAUD', 'PICKUP', 'HOLD', 'SUSPENDED',
            'NOT_PERMITTED', 'NOT PERMITTED', 'DO_NOT_HONOR', 'DO NOT HONOR'
        ]
        
        has_success = any(word in status_upper for word in success_words)
        has_reject = any(word in status_upper for word in reject_words)
        
        if has_reject:
            print(f"❌ MENSAJE RECHAZADO - Status contiene rechazo: {status}")
            return None
        
        if has_success:
            print(f"✅ MENSAJE APROBADO - Status: {status}")
        else:
            if "LIVE" not in text_clean.upper() and "APPROVED" not in text_clean.upper():
                print("❌ No se encontró LIVE/APPROVED en el texto")
                return None
    else:
        text_upper = text_clean.upper()
        if "LIVE" in text_upper or "APPROVED" in text_upper:
            print("✅ LIVE/APPROVED encontrado en el texto")
            status = "Live ✓" if "LIVE" in text_upper else "Approved ✓"
        else:
            print("❌ No se encontró LIVE ni APPROVED")
            return None
    
    print(f"📊 Status final: {status}")

    response = extract_response(text_clean)
    print(f"📝 Response final: {response}")

    gateway = extract_gateway(text_clean)
    print(f"🚪 Gateway final: {gateway}")

    bank = get_field_flexible(text_clean, ["BANK", "BANCO", "Banco", "𝑩𝒂𝒏𝒌", "𝐁𝐚𝐧𝐤", "𝗕𝗮𝗻𝗸"])
    if bank != "Not Found":
        bank = bank.upper()
    print(f"🏦 Bank: {bank}")

    country = get_field_flexible(text_clean, ["COUNTRY", "PAIS", "Pais", "𝑪𝒐𝒖𝒏𝒕𝒓𝒚", "𝐂𝐨𝐮𝐧𝐭𝐫𝐲", "𝗖𝗼𝘂𝗻𝘁𝗿𝘆"])
    flag = "❓"
    if country != "Not Found":
        flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
        if flag_match:
            flag = flag_match.group(1)
            country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()
        
        country = re.sub(r'\s*-\s*[A-Z]{2,3}\s*$', '', country).strip()
        country = country.upper()
        
        if flag == "❓":
            flag = get_flag_for_country(country)
    print(f"🌍 Country: {country} {flag}")

    info_field = get_field_flexible(text_clean, ["BIN INFO", "INFO", "Data", "Info", "𝑰𝒏𝒇𝒐", "𝐈𝐧𝐟𝐨", "𝗜𝗻𝗳𝗼"])
    
    if info_field != "Not Found":
        info_field = info_field.upper().strip()
    else:
        info_field = "Not Found"
    
    print(f"💳 Card Info: {info_field}")

    return {
        "card_info": card_info,
        "bin_number": bin_num,
        "status": status,
        "response": response,
        "gateway": gateway,
        "card_info_field": info_field,
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

async def send_card_message(card_data: dict, response_override: str = None):
    """Función auxiliar para enviar un mensaje de tarjeta al canal."""
    try:
        bin_info = await get_bin_info(card_data['bin_number'])
        
        if card_data.get('card_info_field', "Not Found") == "Not Found":
            brand = clean_text(bin_info.get('brand', 'Unknown')).upper()
            type_api = clean_text(bin_info.get('type', 'Unknown')).upper()
            level_api = clean_text(bin_info.get('level', 'Unknown')).upper()
            card_data['card_info_field'] = f"{brand} - {type_api} - {level_api}"
        
        if card_data.get('bank', "Not Found") == "Not Found":
            if bin_info.get('bank') and bin_info['bank'] != 'N/A':
                card_data['bank'] = clean_text(bin_info['bank']).upper()
        
        if card_data.get('country', "Not Found") == "Not Found" or not card_data.get('country'):
            if bin_info.get('country_name') and bin_info['country_name'] != 'N/A':
                card_data['country'] = clean_text(bin_info['country_name']).upper()
        
        if card_data.get('flag', "❓") == "❓":
            if bin_info.get('country_flag') and bin_info['country_flag'] != '❓':
                card_data['flag'] = bin_info['country_flag']
            else:
                card_data['flag'] = get_flag_for_country(card_data.get('country', ''))

        ext1, ext2, ext3 = generate_extrapolated(card_data['card_info'])
        bin_short = card_data['bin_number'].lstrip('0')
        
        response_final = response_override if response_override else card_data.get('response', 'Not Found')
        
        custom_message = f"""
✸  𝗖𝗛𝗘𝗥𝗥𝗬'𝗦  𝗦𝗖𝗔𝗠  — [#B{bin_short}]

✦  |  𝗖𝗖 →  <code>{card_data['card_info']}</code>  
✦  |  𝗦𝗧𝗔𝗧𝗨𝗦 → {card_data.get('status', 'Approved ✓')}
✦  |  𝗚𝗔𝗧𝗘𝗪𝗔𝗬 → {card_data.get('gateway', 'Not Found')}    
✦  |  𝗦𝗖𝗔𝗠 𝗗𝗔𝗧𝗘 → {time.strftime('%d - %m - %Y')}

︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶
⊹    |  𝗥𝗘𝗦𝗣𝗢𝗡𝗦𝗘 → {response_final}
 ᨭ⠀ 𝗜𝗡𝗙𝗢   →  {card_data['card_info_field']}
 ᨭ⠀ 𝗕𝗔𝗡𝗞  →  {card_data['bank']}
 ᨭ⠀ 𝗖𝗢𝗨𝗡𝗧𝗥𝗬  →  {card_data['country']} {card_data['flag']}
 
︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶︶

 𐔌    ．⠀𝖣𝖠𝖳𝖠 𝖡𝖠𝖲𝖤 𝖤𝖷𝗧𝗥𝗔𝗦

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
                print(f"✅ Mensaje ENVIADO para tarjeta {card_data['card_info']}")
                return True
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
        return False
    except Exception as e:
        print(f"❌ Error en send_card_message: {e}")
        return False

# ------------------- MANEJADOR -------------------
@client.on(events.NewMessage())
@client.on(events.MessageEdited())
async def handler(event):
    global processed_cards, cards_in_progress

    msg: Message = event.message
    if not msg.text:
        return

    # ---------- DETECTAR SI ES MASS ----------
    text_upper = msg.text.upper()
    is_mass = 'MASS' in text_upper and ('[✅]' in msg.text or '[❌]' in msg.text)
    
    if is_mass:
        print("\n" + "="*60)
        print("📦 MASS DETECTADO - Procesando TODAS las tarjetas approved...")
        print("="*60)
        
        gateway = extract_gateway(msg.text)
        country = get_field_flexible(msg.text, ["COUNTRY", "PAIS", "Pais"])
        flag = "❓"
        if country != "Not Found":
            flag_match = re.search(r'([\U0001F1E6-\U0001F1FF]+)', country)
            if flag_match:
                flag = flag_match.group(1)
                country = re.sub(r'[\U0001F1E6-\U0001F1FF]+', '', country).strip()
            country = country.upper()
        
        bank = get_field_flexible(msg.text, ["BANK", "BANCO", "Banco"])
        if bank != "Not Found":
            bank = bank.upper()
        
        info_field = get_field_flexible(msg.text, ["BIN INFO", "INFO", "Data", "Info"])
        if info_field != "Not Found":
            info_field = info_field.upper().strip()
        
        mass_cards = extract_mass_cards(msg.text)
        print(f"🔍 Tarjetas APPROVED encontradas: {len(mass_cards)}")
        
        for card in mass_cards:
            card_clean = re.sub(r'[\s|-]', '', card['card_info'])
            
            if card_clean in processed_cards:
                print(f"⏭️ Tarjeta {card_clean} ya procesada")
                continue
            if card_clean in cards_in_progress:
                print(f"⏳ Tarjeta {card_clean} en proceso")
                continue
            
            cards_in_progress.add(card_clean)
            
            card_data = {
                "card_info": card['card_info'],
                "bin_number": card['bin_number'],
                "status": "Approved ✓",
                "response": card['response'],
                "gateway": gateway,
                "card_info_field": info_field if info_field != "Not Found" else "Not Found",
                "bank": bank if bank != "Not Found" else "Not Found",
                "country": country if country != "Not Found" else "Not Found",
                "flag": flag,
            }
            
            success = await send_card_message(card_data, response_override=card['response'])
            
            if success:
                processed_cards.add(card_clean)
            
            cards_in_progress.discard(card_clean)
            await asyncio.sleep(1.5)
        
        return
    
    # ---------- MODO NORMAL (1 tarjeta) ----------
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

    try:
        success = await send_card_message(card_data)
        if success:
            processed_cards.add(card_clean)
    finally:
        cards_in_progress.discard(card_clean)

# ------------------- ARRANQUE CON RECONEXIÓN AUTOMÁTICA -------------------
async def main():
    while True:  # BUCLE INFINITO
        try:
            print("🚀 Iniciando cliente de Telegram...")
            
            if not client.is_connected():
                await client.connect()
            
            if not await client.is_user_authorized():
                print("⚠️ Sesión no autorizada, iniciando...")
                await client.start()
            
            print("✅ ¡Bot en ejecución! Escuchando mensajes...")
            
            await client.run_until_disconnected()
            
            print("⚠️ Cliente desconectado, reconectando...")
            
        except KeyboardInterrupt:
            print("🛑 Bot detenido manualmente")
            break
        except asyncio.CancelledError:
            print("🛑 Tarea cancelada")
            break
        except Exception as e:
            print(f"❌ ERROR: {e}")
            print("🔄 Reconectando en 10 segundos...")
            await asyncio.sleep(10)
            continue


if __name__ == "__main__":
    while True:  # BUCLE INFINITO EXTERNO
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("🛑 Bot detenido manualmente")
            break
        except Exception as e:
            print(f"❌ ERROR CRÍTICO:
