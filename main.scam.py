def extract_gateway(text: str) -> str:
    GATEWAY_KEYWORDS = [
        'BRAINTREE', 'STRIPE', 'ADYEN', 'PAYPAL', 'SHOPIFY', 'ZAREK',
        'PAYFLOW', 'EAGLE', 'CHECKOUT', 'AUTH', 'GATEWAY', 'CHECKER',
        'CHK', 'PLUG', 'VITAL', 'AUTHORIZE', 'AUTHORIZED', 'ATREUS',
        '2CHECKOUT', 'PAYMENTWALL', 'PAYSAFE', 'SKRILL', 'NETELLER',
        'WEBMONEY', 'PERFECT MONEY', 'PAYONEER', 'WORLDPAY', 'SAGE PAY',
        'REALEX', 'NMI', 'BLUE SNAP', 'VERIFONE', 'FIRST DATA',
        'ELAVON', 'PAYMENT DEPOT', 'DURANGO', 'BAMBORA', 'PROCESSOR',
        'PASARELA', 'CHECKOUT', 'PAYMENT', 'GATE', 'RIN'
    ]
    
    gate = get_field_flexible(text, ["GATEWAY", "GATE", "PASARELA", "𝑮𝑨𝑻𝑬", "𝐆𝐚𝐭𝐞", "𝗚𝗮𝘁𝗲"])
    type_field = get_field_flexible(text, ["TYPE", "TIPO"])
    
    if gate != "Not Found":
        gate = clean_text(gate).upper()
        if re.search(r'\d{14,16}', gate):
            gate = "Not Found"
    
    if gate != "Not Found":
        # SIEMPRE combinar con TYPE si existe (sin importar qué sea)
        if type_field != "Not Found":
            type_clean = clean_text(type_field).strip().upper()
            # Evitar combinar si el TYPE es basura o muy largo
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
