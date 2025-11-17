# love.py — PART 
import braintree
import os
import re
import csv
import io
import time
import json
import pytz
import hashlib
import aiohttp 
import secrets
import random
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed, .env will not load.")

# --- Load config from .env ---
BOT_TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))

BRAINTREE_MERCHANT_ID = os.getenv("BRAINTREE_MERCHANT_ID")
BRAINTREE_PUBLIC_KEY = os.getenv("BRAINTREE_PUBLIC_KEY")
BRAINTREE_PRIVATE_KEY = os.getenv("BRAINTREE_PRIVATE_KEY")

DATA_PATH = "./"
USERDATA_FILE = os.path.join(DATA_PATH, "users.json")
CACHE_FILE = os.path.join(DATA_PATH, "cache.json")
KEYS_FILE = os.path.join(DATA_PATH, "premium_keys.json")
PROMO_DB_FILE = os.path.join(DATA_PATH, "promo_db.json")

 # for async BIN lookup (if not already imported)

VBV_LOADING_FRAMES = [
    "🟦 [■□□□□] ꜱᴄᴀɴɴɪɴɢ ᴠʙᴠ...",
    "🟦 [■■□□□] ᴄʀᴏꜱꜱɪɴɢ ɢᴀᴛᴇ...",
    "🟦 [■■■□□] ɢᴇᴛᴛɪɴɢ ʙᴀɴᴋ ꜱᴛᴀᴛᴜꜱ...",
    "🟦 [■■■■□] ᴠᴇʀɪꜰʏɪɴɢ ᴄᴀʀᴅ 3ᴅ...",
    "🟦 [■■■■■] ᴇxᴛʀᴀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ!",
]

# Place these at the top of your file with your other animation/format definitions:
CHK_LOADING_FRAMES = [
    "🟩 [■□□□□] ꜱᴄᴀɴɴɪɴɢ ᴄᴀʀᴅ...",
    "🟩 [■■□□□] ᴠᴇʀɪꜰʏɪɴɢ ɢᴀᴛᴇᴡᴀʏ...",
    "🟩 [■■■□□] ʙᴀɴᴋ ʀᴇꜱᴘᴏɴꜱᴇ...",
    "🟩 [■■■■□] ᴀɴᴀʟʏᴢɪɴɢ ꜱᴛᴀᴛᴜꜱ...",
    "🟩 [■■■■■] ǫᴜᴀɴᴛᴜᴍ ᴘᴀꜱꜱ ᴀᴄᴛɪᴠᴇ!",
]

MASS_LOADING_TEXTS = [
    "⏳ ᴍᴀꜱꜱ ᴄʜᴇᴄᴋɪɴɢ ᴄᴀʀᴅꜱ...",
    "⏳ ꜱᴛɪʟʟ ᴡᴏʀᴋɪɴɢ...",
    "⏳ ᴀʟᴍᴏꜱᴛ ᴅᴏɴᴇ...",
    "⏳ ꜰɪɴᴀʟɪᴢɪɴɢ ʀᴇꜱᴜʟᴛꜱ...",
    "✔️ ᴄᴏᴍᴘʟᴇᴛᴇ!"
]

ALL_LOADING_TEXTS = [
    "⏳ ᴍᴜʟᴛɪ-ᴀᴜᴛʜ ᴄʜᴇᴄᴋɪɴɢ...",
    "⏳ ꜱᴄᴀɴɴɪɴɢ ᴀʟʟ ᴄᴀʀᴅꜱ...",
    "⏳ ᴍᴜʟᴛɪ-ᴀᴜᴛʜ ᴀɴᴀʟʏᴢɪɴɢ...",
    "⏳ ᴡᴀɪᴛɪɴɢ ꜰᴏʀ ʀᴇꜱᴜʟᴛꜱ...",
    "✔️ ᴍᴜʟᴛɪ-ᴀᴜᴛʜ ᴄᴏᴍᴘʟᴇᴛᴇ!"
]

# --- Utilities ---
def to_small_caps(text: str) -> str:
    table = str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ" * 2,
    )
    return text.translate(table)

def get_user_display_name(user):
    if user.username:
        return f"@{user.username}"
    name = (user.first_name or "") + " " + (user.last_name or "")
    return name.strip() or f"{user.id}"

def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def pretty_time(dt):
    return dt.strftime("%d-%m-%Y %I:%M %p")

def deterministic_rng(key):
    # Always same cards for same key
    seed = int.from_bytes(key.encode(), "little") % (2**32)
    return random.Random(seed)

def smart_mm_yy_cvv(mm, yy, cvv):
    # Fallbacks for any missing
    mm = mm if mm and mm.isdigit() else f"{random.randint(1,12):02d}"
    yy = yy if yy and yy.isdigit() else f"{random.randint(now_ist().year%100, (now_ist().year+7)%100):02d}"
    cvv = cvv if cvv and cvv.isdigit() else f"{random.randint(100,999)}"
    return mm, yy, cvv

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
        
def deterministic_rng(card, check_type="chk"):
    seed = hashlib.sha256(f"{check_type}:{card}".encode()).hexdigest()
    return random.Random(int(seed, 16))

def format_card_number(number):
    return " ".join([number[i:i+4] for i in range(0, len(number), 4)])

def extract_cards_from_text(text):
    lines = text.replace(",", "\n").splitlines()
    return [line.strip() for line in lines if "|" in line]

async def get_bin_details(bin_code):
    bin_apis = [
        f"https://bins.su/lookup/{bin_code}",
        f"https://lookup.binlist.net/{bin_code}",
        f"https://api.bintable.com/v1/{bin_code}"
    ]
    brand = issuer = country = flag = "unknown"
    for api_url in bin_apis:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "Mozilla/5.0"}
                async with session.get(api_url, headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "bins.su" in api_url:
                            brand = data.get("brand") or data.get("scheme", "unknown")
                            issuer = data.get("type", "unknown")
                            country = data.get("country_name", "unknown")
                            flag = data.get("country_emoji") or ""
                        elif "binlist.net" in api_url:
                            brand = data.get("scheme", "unknown")
                            issuer = data.get("bank", {}).get("name", "unknown")
                            country = data.get("country", {}).get("name", "unknown")
                            flag = data.get("country", {}).get("emoji", "")
                        elif "bintable.com" in api_url:
                            brand = data.get("card_brand", "unknown")
                            issuer = data.get("bank", "unknown")
                            country = data.get("country", "unknown")
                            flag = ""
                        if flag and country != "unknown":
                            country = f"{country} {flag}"
                        break
        except Exception:
            continue
    return brand, issuer, country

def send_premium_denied(update):
    return update.message.reply_text(
        to_small_caps("❌ ᴘʀᴇᴍɪᴜᴍ ᴏɴʟʏ.\nᴘʟᴇᴀꜱᴇ ʀᴇᴅᴇᴇᴍ ᴀ ᴋᴇʏ ꜰɪʀꜱᴛ."),
        parse_mode="HTML"
    )

# --- Storage Classes ---
class UserStore:
    def __init__(self, file):
        self.file = file
        self.data = load_json(file)
        self.default_role = "free"

    def save(self):
        save_json(self.file, self.data)

    def get(self, user_id):
        user_id = str(user_id)
        if user_id not in self.data:
            self.data[user_id] = {
                "credits": 25,
                "role": self.default_role,
                "joined": int(time.time()),
                "last_daily": 0,
            }
        return self.data[user_id]

    def set_role(self, user_id, role):
        self.get(user_id)["role"] = role
        self.save()

    def get_role(self, user_id):
        return self.get(user_id).get("role", self.default_role)

    def add_credits(self, user_id, amt):
        rec = self.get(user_id)
        rec["credits"] = max(0, rec.get("credits", 0) + amt)
        self.save()

    def get_credits(self, user_id):
        return self.get(user_id).get("credits", 0)

    def can_claim_daily(self, user_id):
        rec = self.get(user_id)
        today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
        last = datetime.fromtimestamp(rec["last_daily"], pytz.timezone("Asia/Kolkata")).date() if rec["last_daily"] else None
        return last != today

    def claim_daily(self, user_id):
        rec = self.get(user_id)
        rec["last_daily"] = int(time.time())
        rec["credits"] = rec.get("credits", 0) + 25
        self.save()

user_store = UserStore(USERDATA_FILE)

class CheckedCache:
    def __init__(self, file):
        self.file = file
        self.data = load_json(file)

    def save(self):
        save_json(self.file, self.data)

checked_cache = CheckedCache(CACHE_FILE)

premium_keys = load_json(KEYS_FILE)


PROMO_DB = load_json(PROMO_DB_FILE)




def set_role(user_id, role):
    user_store.set_role(user_id, role)

def change_credits(user_id, amount):
    """Add or subtract credits from user"""
    data = user_store.get(user_id) or {}
    current = data.get("credits", 0)
    data["credits"] = max(0, current + amount)  # Don't allow negative credits
    user_store.save()

def get_credits(user_id):
    """Get user's current credit balance"""
    data = user_store.get(user_id) or {}
    return data.get("credits", 0)
    
# Killed cards storage (card_number: killer_username)
KILLED_CARDS = {}

def save_killed_cards():
    try:
        with open("killed_cards.txt", "w") as f:
            for card, killer in KILLED_CARDS.items():
                f.write(f"{card}:{killer}\n")
    except Exception as e:
        print(f"Error saving killed cards: {e}")

def load_killed_cards():
    try:
        with open("killed_cards.txt", "r") as f:
            d = {}
            for line in f:
                if ":" in line:
                    card, killer = line.strip().split(":", 1)
                    d[card] = killer
            return d
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading killed cards: {e}")
        return {}

# Load killed cards at startup
KILLED_CARDS = load_killed_cards()



# love.py — PART 2/4

def is_premium(user_id):
    return user_store.get_role(user_id) == "premium"

def require_premium(handler_func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not is_premium(user_id):
            return await send_premium_denied(update)
        return await handler_func(update, context)
    return wrapper

def print_startup_box():
    print("\n" + "="*46)
    print("★━━ ᴄᴄ ᴄʜᴇᴄᴋᴇʀ ᴘʀᴇᴍɪᴜᴍ ━━★".center(46))
    print("ʙᴏᴛ ɪꜱ ʟɪᴠᴇ ᴀɴᴅ ᴡᴀɪᴛɪɴɢ ꜰᴏʀ ᴄᴏᴍᴍᴀɴᴅꜱ!".center(46))
    print("ᴜꜱᴇ .ʜᴇʟᴘ ꜰᴏʀ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅꜱ.".center(46))
    print("ᴊᴏɪɴ ᴜꜱᴇʀꜱ: @ccheckerpremium".center(46))
    print("="*46 + "\n")

STARTED_BOX = """
★━━ ᴄᴄ ᴄʜᴇᴄᴋᴇʀ ᴘʀᴇᴍɪᴜᴍ ━━★
ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ᴍᴏꜱᴛ ᴀᴅᴠᴀɴᴄᴇᴅ ᴄʀᴇᴅɪᴛ ᴄᴀʀᴅ ᴄʜᴇᴄᴋᴇʀ ᴏɴ ᴛᴇʟᴇɢʀᴀᴍ!
ᴜꜱᴇ .ʜᴇʟᴘ ꜰᴏʀ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅꜱ.
★━━━━━━━━━━━━━━━━━━━━━━━━★
"""

@require_premium
async def cmd_mass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cards = [c.strip() for c in context.args if "|" in c]
    total = len(cards)
    if not is_premium(user_id):
        return await send_premium_denied(update)
    if total == 0:
        return await update.message.reply_text(to_small_caps("❌ ᴜꜱᴀɢᴇ: .mass 4111|01|23|123 ..."), parse_mode="HTML")
    if get_credits(user_id) < 2 * total:
        return await update.message.reply_text(to_small_caps(f"❌ ɴᴇᴇᴅ {2*total} ᴄʀᴇᴅɪᴛꜱ ꜰᴏʀ {total} ᴄᴀʀᴅꜱ!"), parse_mode="HTML")

    # Premium single animated message (classic old style)
    anim_msg = await update.message.reply_text(to_small_caps(MASS_LOADING_TEXTS[0]), parse_mode="HTML")
    for txt in MASS_LOADING_TEXTS[1:]:
        await asyncio.sleep(1)
        await anim_msg.edit_text(to_small_caps(txt), parse_mode="HTML")
    await asyncio.sleep(0.5)

    # Deterministic which cards are approved
    rng = deterministic_rng("MASS:" + "|".join(cards))
    approved_idxs = set(rng.sample(range(total), k=min(2, total)))

    results = []
    for idx, card in enumerate(cards):
        status = "approved" if idx in approved_idxs else "declined"
        icon = "✅" if idx in approved_idxs else "❌"
        results.append(f"{icon} <code>{card}</code> — {status}")

    user = get_user_display_name(update.effective_user)
    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%I:%M:%S %p IST")

    box = (
        "★━━ ᴍᴀꜱꜱ ᴄʜᴇᴄᴋ ʀᴇꜱᴜʟᴛꜱ ━━★\n"
        f"{chr(10).join(results)}\n"
        f"\nᴜꜱᴇʀ: {user}\nᴛɪᴍᴇ: {now}\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )

    # Deduct credits
    change_credits(user_id, -2 * total)

    await anim_msg.edit_text(box, parse_mode="HTML")

@require_premium
async def cmd_vbv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id

    if not is_premium(user_id):
        return await send_premium_denied(update)

    if not args or "|" not in args[0]:
        await update.message.reply_text(to_small_caps("❌ ᴜꜱᴀɢᴇ: .vbv 4111111111111111|12|28|123"))
        return

    card = args[0].strip()
    
    # Credit check
    if get_credits(user_id) < 3:
        await update.message.reply_text(to_small_caps("❌ ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴄʀᴇᴅɪᴛꜱ!"))
        return

    # REMOVE CACHING - This was causing same results
    # key = f"VBV:{card}"
    # if key in checked_cache.data:
    #     await update.message.reply_text(checked_cache.data[key], parse_mode="HTML")
    #     return

    # Enhanced loading frames
    VBV_LOADING_FRAMES = [
        "🔍 ɪɴɪᴛɪᴀʟɪᴢɪɴɢ 3ᴅ ꜱᴇᴄᴜʀᴇ...",
        "🌐 ᴄᴏɴɴᴇᴄᴛɪɴɢ ᴛᴏ ᴠɪꜱᴀ ɴᴇᴛᴡᴏʀᴋ...",
        "🔐 ᴠᴇʀɪꜰʏɪɴɢ ᴄᴀʀᴅʜᴏʟᴅᴇʀ ᴀᴜᴛʜ...",
        "⚡ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ᴠʙᴠ ᴄʜᴇᴄᴋ...",
        "✨ ꜰɪɴᴀʟɪᴢɪɴɢ ʀᴇꜱᴜʟᴛꜱ..."
    ]

    # 5s animated loading
    loading_msg = await update.message.reply_text(to_small_caps(VBV_LOADING_FRAMES[0]), parse_mode="HTML")
    for frame in VBV_LOADING_FRAMES[1:]:
        await asyncio.sleep(1)
        await loading_msg.edit_text(to_small_caps(frame), parse_mode="HTML")
    await asyncio.sleep(0.5)

    # Parse card/BIN
    try:
        number, mm, yy, cvv = card.split("|")
        bin_code = number[:6]
    except Exception:
        await loading_msg.edit_text(to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ᴄᴀʀᴅ ꜰᴏʀᴍᴀᴛ"), parse_mode="HTML")
        return

    # Live BIN lookup with multiple APIs
    brand = issuer = country = "unknown"
    
    bin_apis = [
        f"https://bins.su/lookup/{bin_code}",
        f"https://lookup.binlist.net/{bin_code}",
        f"https://api.bintable.com/v1/{bin_code}"
    ]
    
    for api_url in bin_apis:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                async with session.get(api_url, headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if "bins.su" in api_url:
                            brand = data.get("brand") or data.get("scheme", "unknown")
                            issuer = data.get("type", "unknown")
                            country = data.get("country_name", "unknown")
                            flag = data.get("country_emoji") or ""
                        elif "binlist.net" in api_url:
                            brand = data.get("scheme", "unknown")
                            issuer = data.get("bank", {}).get("name", "unknown")
                            country = data.get("country", {}).get("name", "unknown")
                            flag = data.get("country", {}).get("emoji", "")
                        elif "bintable.com" in api_url:
                            brand = data.get("card_brand", "unknown")
                            issuer = data.get("bank", "unknown")
                            country = data.get("country", "unknown")
                            flag = ""
                        
                        if flag and country != "unknown":
                            country = f"{country} {flag}"
                        break
        except Exception:
            continue

    # RANDOM RESULT WITH 30% PASS RATE (not deterministic)
    import random
    import time
    
    # Use current timestamp + user_id for true randomness each time
    random.seed(int(time.time() * 1000) + hash(card + str(user_id)))
    
    # 30% pass rate as requested
    approved = random.randint(1, 100) <= 30
    
    # Random gateway selection from real providers
    gateways = [
        "Stripe 3D Secure [1$]",
        "Braintree VBV [0.5$]", 
        "PayPal 3DS [1$]",
        "Adyen 3D Secure [0.8$]",
        "Worldpay VBV [1.2$]",
        "Authorize.net 3DS [0.7$]"
    ]
    
    gateway = random.choice(gateways)
    
    # Enhanced response messages based on result
    if approved:
        status = "vbv passed"
        status_emoji = "🟦"
        vbv_responses = [
            "3D Secure authentication successful",
            "Cardholder verified successfully", 
            "VBV authentication completed",
            "3DS challenge passed",
            "Verified by Visa approved",
            "Authentication successful"
        ]
        
        # 3DS success details
        auth_details = [
            f"ACS Response: Y",
            f"ECI: 05",
            f"CAVV: {random.choice(['AAIBBJFgEghQVyIAAQAAAAAAAAA=', 'AAABCZEhcQAAAABZlyFxAAAAAAA='])}",
            f"XID: {random.choice(['MDAwMDAwMDAwMDAwMDAwMzIyNzY=', 'MDAwMDAwMDAwMDAwMDAwMzIyNzc='])}"
        ]
    else:
        status = "vbv failed"
        status_emoji = "⬛"
        vbv_responses = [
            "3D Secure authentication failed",
            "Cardholder verification declined",
            "VBV authentication rejected",
            "3DS challenge failed",
            "Authentication timeout",
            "Card not enrolled for 3DS",
            "Issuer declined authentication",
            "3D Secure not supported",
            "Authentication server unavailable",
            "Cardholder cancelled authentication",
            "Invalid authentication response",
            "3DS verification failed"
        ]
        
        # 3DS failure details
        auth_details = [
            f"ACS Response: N",
            f"ECI: 07",
            f"Status: Authentication Failed",
            f"Reason: {random.choice(['Card not enrolled', 'Timeout', 'User cancelled', 'System error'])}"
        ]
    
    vbv_response = random.choice(vbv_responses)

    user = get_user_display_name(update.effective_user)
    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%I:%M:%S %p IST")

    # Enhanced response format
    box = (
        "┏━━━━━━━⍟\n"
        f"┃ {to_small_caps(status.title())} {status_emoji}\n"
        "┗━━━━━━━━━━━⊛\n\n"
        f"⌯ {to_small_caps('ᴄᴀʀᴅ')}\n"
        f" ↳ `{card}`\n"
        f"⌯ {to_small_caps('ɢᴀᴛᴇᴡᴀʏ')} ➳ {gateway}\n"
        f"⌯ {to_small_caps('ʀᴇꜱᴘᴏɴꜱᴇ')} ➳ {vbv_response}\n\n"
        f"⌯ {to_small_caps('3ᴅ ꜱᴇᴄᴜʀᴇ ᴅᴇᴛᴀɪʟꜱ')}\n"
        f" ↳ {chr(10).join([f'   {detail}' for detail in auth_details])}\n\n"
        f"⌯ {to_small_caps('ɪɴꜰᴏ')} ➳ {brand}\n"
        f"⌯ {to_small_caps('ɪꜱꜱᴜᴇʀ')} ➳ {issuer}\n"
        f"⌯ {to_small_caps('ᴄᴏᴜɴᴛʀʏ')} ➳ {country}\n\n"
        f"ʀᴇQ ʙʏ ➳ {user}\n"
        f"{now}"
    )

    # DON'T CACHE RESULTS - This allows different results each time
    # checked_cache.data[key] = box
    # checked_cache.save()
    
    change_credits(user_id, -3)
    await loading_msg.edit_text(box, parse_mode="HTML")



async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_store.get(user.id)  # auto-register
    await update.message.reply_text(to_small_caps(STARTED_BOX), parse_mode="HTML")

RADAR_SWEEP = [
    "🟢 [■□□□□] ꜱᴄᴀɴɴɪɴɢ ᴜꜱᴇʀ...",
    "🟢 [■■□□□] ᴠᴇʀɪꜰʏɪɴɢ ᴘʀᴏꜰɪʟᴇ...",
    "🟢 [■■■□□] ᴄᴏʟʟᴇᴄᴛɪɴɢ ᴅᴀᴛᴀ...",
    "🟢 [■■■■□] ꜱʏɴᴄɪɴɢ ᴄᴏɴꜱᴏʟᴇ...",
    "🟢 [■■■■■] ǫᴜᴀɴᴛᴜᴍ ɢᴀᴛᴇ ᴀᴄᴛɪᴠᴇ!",
]

QUANTUM_BOX = """
┏━━ ✦ ǫᴜᴀɴᴛᴜᴍ ɢᴀᴛᴇ ✦ ━━┓

ꜰʀᴇᴇ ᴄᴏᴍᴍᴀɴᴅꜱ

• .chk ----> ᴄʜᴇᴄᴋ ᴄᴀʀᴅ
• .gen ----> ɢᴇɴᴇʀᴀᴛᴏʀ
• .daily ----> ᴅᴀɪʟʏ ᴄʀᴇᴅɪᴛ
• .info ----> ᴜꜱᴇʀ ɪɴꜰᴏ
• .plans ----> ᴘʟᴀɴꜱ
• .fake ----> ɪᴅ ɢᴇɴ
• .help ----> ʙᴏᴛ ʜᴇʟᴘ

━━━━━━━━━━━━━━━━━━━━━━━

ᴘʀᴇᴍɪᴜᴍ ᴄᴏᴍᴍᴀɴᴅꜱ

• .mass ----> ᴍᴀꜱꜱ ᴄʜᴇᴄᴋ
• .mchk ----> ᴍᴀꜱꜱ ᴄᴀʀᴅ ᴄʜᴇᴄᴋ
• .kill    ---->ᴋɪʟʟ ᴀ ᴄᴀʀᴅ
• .vbv   ----> ɪᴄᴇ ʙʀᴇᴀᴋᴇʀ
• .bin    ----> ᴅᴇᴇᴘ ʟᴏᴏᴋᴜᴘ
• .analytics ----> ᴀɴᴀʟʏᴛɪᴄꜱ
• .proxy    ---->ᴘʀᴏxʏ
• .sʟғ    ----> ᴄʜᴋ ᴄʀᴇᴅɪᴛꜱ

|━━━━━━━━━━━━━━━|
✧ ᴅᴇᴠ ʙʏ ~ Mustu ⚡
|━━━━━━━━━━━━━━━|
"""

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Radar sweep loading animation
    loading_msg = await update.message.reply_text(
        to_small_caps(RADAR_SWEEP[0])
    )
    for frame in RADAR_SWEEP[1:]:
        await asyncio.sleep(0.42)
        try:
            await loading_msg.edit_text(to_small_caps(frame))
        except:
            pass
    await asyncio.sleep(0.6)
    try:
        await loading_msg.delete()
    except:
        pass

    # Send quantum help box
    await update.message.reply_text(
        to_small_caps(QUANTUM_BOX),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = user_store.get(user.id) or {}
    role = data.get("role", "free")
    credits = data.get("credits", 0)
    joined = pretty_time(datetime.fromtimestamp(data.get("joined", int(time.time()))))
    last_daily = data.get("last_daily", 0)
    last_daily_str = pretty_time(datetime.fromtimestamp(last_daily)) if last_daily else "never"
    redeemed = data.get("redeemed_key", "None")
    
    # Get username properly without small caps
    username = f"@{user.username}" if user.username else "No Username"
    full_name = get_user_display_name(user)  # This gets first + last name

    msg = (
        "★━━ ᴜꜱᴇʀ ɪɴꜰᴏ ━━★\n"
        f"ɪᴅ: `{user.id}`\n"
        f"ɴᴀᴍᴇ: {full_name}\n"  # No small caps for name
        f"ᴜꜱᴇʀɴᴀᴍᴇ: {username}\n"  # No small caps for username
        f"ʀᴏʟᴇ: {to_small_caps(role)}\n"
        f"ᴄʀᴇᴅɪᴛꜱ: `{credits}`\n"  # Fixed: was using 'redeemed'
        f"ʀᴇᴅᴇᴇᴍᴇᴅ: {redeemed}\n"
        f"ʟᴀꜱᴛ ᴅᴀɪʟʏ: {last_daily_str}\n"
        f"ᴊᴏɪɴᴇᴅ: {joined}\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )

    await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")
    
DAILY_CREDITS = 25  # Set your daily credit amount

async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Daily reward command - gives users 25 free credits every 24 hours"""
    user_id = update.effective_user.id
    user_data = user_store.get(user_id) or {}
    
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    last_daily = user_data.get("last_daily")
    
    can_claim = False
    
    if last_daily:
        try:
            # Parse ISO string to datetime
            last_daily_dt = datetime.fromisoformat(last_daily)
            # Check if 24 hours have passed
            if now - last_daily_dt >= timedelta(hours=24):
                can_claim = True
        except Exception:
            # If date parsing fails, allow claim
            can_claim = True
    else:
        # First time claiming
        can_claim = True
    
    if can_claim:
        # Add credits and update last claim time
        change_credits(user_id, DAILY_CREDITS)
        user_data["last_daily"] = now.isoformat()
        user_store.save()
        
        # Get updated credit balance
        current_credits = get_credits(user_id)
        
        msg = (
            "★━━ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ ━━★\n"
            f"✅ ᴄʀᴇᴅɪᴛꜱ ᴀᴅᴅᴇᴅ: `{DAILY_CREDITS}`\n"
            f"💰 ᴛᴏᴛᴀʟ ᴄʀᴇᴅɪᴛꜱ: `{current_credits}`\n"
            f"⏰ ɴᴇxᴛ ᴄʟᴀɪᴍ: 24 ʜᴏᴜʀꜱ\n\n"
            "💡 ᴛɪᴘ: ᴜꜱᴇ .cr ᴛᴏ ᴄʜᴇᴄᴋ ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ!\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        
        await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")
    else:
        # Calculate time remaining until next claim
        last_daily_dt = datetime.fromisoformat(last_daily)
        time_until_next = timedelta(hours=24) - (now - last_daily_dt)
        
        hours = int(time_until_next.total_seconds() // 3600)
        minutes = int((time_until_next.total_seconds() % 3600) // 60)
        
        msg = (
            "★━━ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ ━━★\n"
            "❌ ᴀʟʀᴇᴀᴅʏ ᴄʟᴀɪᴍᴇᴅ!\n\n"
            f"⏰ ɴᴇxᴛ ᴄʟᴀɪᴍ ɪɴ: {hours}ʜ {minutes}ᴍ\n"
            f"💰 ᴄᴜʀʀᴇɴᴛ ᴄʀᴇᴅɪᴛꜱ: `{get_credits(user_id)}`\n\n"
            "💡 ᴄᴏᴍᴇ ʙᴀᴄᴋ ᴛᴏᴍᴏʀʀᴏᴡ ꜰᴏʀ ᴍᴏʀᴇ!\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        
        await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")


import string
import random

async def cmd_genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate premium keys command - Admin only"""
    user_id = update.effective_user.id
    
    # Only admin can generate keys
    if user_id != ADMIN_ID:
        return await update.message.reply_text(
            to_small_caps("❌ ᴏɴʟʏ ᴀᴅᴍɪɴ ᴄᴀɴ ɢᴇɴᴇʀᴀᴛᴇ ᴋᴇʏꜱ!"),
            parse_mode="HTML"
        )
    
    # Check usage
    if not context.args or len(context.args) < 3:
        usage_msg = (
            "★━━ ᴋᴇʏ ɢᴇɴᴇʀᴀᴛᴏʀ ━━★\n\n"
            "ᴜꜱᴀɢᴇ: .genkey [role] [credits] [count]\n\n"
            "ᴇxᴀᴍᴘʟᴇꜱ:\n"
            "• .genkey premium 100 5\n"
            "• .genkey free 25 10\n\n"
            "ʀᴏʟᴇꜱ: free, premium\n"
            "ᴍᴀx ᴄᴏᴜɴᴛ: 20 ᴋᴇʏꜱ\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        return await update.message.reply_text(to_small_caps(usage_msg), parse_mode="HTML")
    
    # Parse arguments
    try:
        role = context.args[0].lower()
        credits = int(context.args[1])
        count = int(context.args[2])
    except ValueError:
        return await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ꜰᴏʀᴍᴀᴛ"),
            parse_mode="HTML"
        )
    
    # Validate inputs
    if role not in ["free", "premium"]:
        return await update.message.reply_text(
            to_small_caps("❌ ʀᴏʟᴇ ᴍᴜꜱᴛ ʙᴇ 'free' ᴏʀ 'premium'"),
            parse_mode="HTML"
        )
    
    if credits < 0 or credits > 10000:
        return await update.message.reply_text(
            to_small_caps("❌ ᴄʀᴇᴅɪᴛꜱ ᴍᴜꜱᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 0-10000"),
            parse_mode="HTML"
        )
    
    if count < 1 or count > 20:
        return await update.message.reply_text(
            to_small_caps("❌ ᴄᴏᴜɴᴛ ᴍᴜꜱᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 1-20"),
            parse_mode="HTML"
        )
    
    # Loading animation
    loading_msg = await update.message.reply_text(
        to_small_caps("⏳ ɢᴇɴᴇʀᴀᴛɪɴɢ ᴋᴇʏꜱ..."),
        parse_mode="HTML"
    )
    
    await asyncio.sleep(1)
    
    # Generate keys
    generated_keys = []
    for _ in range(count):
        # Generate 12-character key: ABC123DEF456
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        
        # Store in premium_keys database
        premium_keys[key] = {
            "role": role,
            "credits": credits,
            "used": False,
            "created": datetime.now(pytz.timezone("Asia/Kolkata")).isoformat(),
            "created_by": user_id
        }
        
        # Also store in PROMO_DB for compatibility
        PROMO_DB[key] = {
            "role": role,
            "credits": credits,
            "used": False
        }
        
        generated_keys.append(key)
    
    # Save to files
    save_keys(premium_keys)
    save_promos(PROMO_DB)
    
    # Format response - keys without small caps so they can be copied
    key_list = "\n\n".join([f"<code>.redeem {key}</code>" for key in generated_keys])
    
    msg = (
    f"{to_small_caps('★━━ ᴋᴇʏꜱ ɢᴇɴᴇʀᴀᴛᴇᴅ ━━★')}\n\n"
    f"{to_small_caps('ʀᴏʟᴇ:')} {role.upper()}\n"
    f"{to_small_caps('ᴄʀᴇᴅɪᴛꜱ:')} {credits}\n"
    f"{to_small_caps('ᴄᴏᴜɴᴛ:')} {count}\n\n"
    f"{to_small_caps('ɢᴇɴᴇʀᴀᴛᴇᴅ ᴋᴇʏꜱ:')}\n\n"
    f"{key_list}\n\n"
    f"{to_small_caps('💡 ᴜꜱᴇʀꜱ ᴄᴀɴ ʀᴇᴅᴇᴇᴍ ᴡɪᴛʜ:')} .redeem KEY\n"
        f"{to_small_caps('★━━━━━━━━━━━━━━━━━━━━━━━━★')}"
    )
    
    await loading_msg.edit_text(msg, parse_mode="HTML")

# Helper functions for key management
def save_keys(keys_dict):
    """Save keys to file"""
    try:
        with open("premium_keys.json", "w") as f:
            json.dump(keys_dict, f, indent=2)
    except Exception as e:
        print(f"Error saving keys: {e}")

def load_keys():
    """Load keys from file"""
    try:
        with open("premium_keys.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading keys: {e}")
        return {}

def save_promos(promo_dict):
    """Save promos to file"""
    try:
        with open("promo_codes.json", "w") as f:
            json.dump(promo_dict, f, indent=2)
    except Exception as e:
        print(f"Error saving promos: {e}")

def isvalidpromo(code):
    """Check if promo code is valid and unused"""
    if code in PROMO_DB:
        return not PROMO_DB[code].get("used", False)
    if code in premium_keys:
        return not premium_keys[code].get("used", False)
    return False

# Initialize key storage at startup
premium_keys = load_keys()

async def cmd_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(to_small_caps("ᴜꜱᴀɢᴇ: .redeem CODE"), parse_mode="HTML")

    code = context.args[0].strip()
    uid = update.effective_user.id
    user_data = user_store.get(uid) or {}
    
    # Check daily redemption limit
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    last_redeem = user_data.get("last_redeem")
    
    can_redeem = False
    if last_redeem:
        try:
            last_redeem_dt = datetime.fromisoformat(last_redeem)
            if now - last_redeem_dt >= timedelta(hours=24):
                can_redeem = True
        except Exception:
            can_redeem = True
    else:
        can_redeem = True
    
    if not can_redeem:
        # Calculate time remaining
        last_redeem_dt = datetime.fromisoformat(last_redeem)
        time_until_next = timedelta(hours=24) - (now - last_redeem_dt)
        hours = int(time_until_next.total_seconds() // 3600)
        minutes = int((time_until_next.total_seconds() % 3600) // 60)
        
        return await update.message.reply_text(
            to_small_caps(f"❌ ᴀʟʀᴇᴀᴅʏ ʀᴇᴅᴇᴇᴍᴇᴅ ᴛᴏᴅᴀʏ!\n⏰ ɴᴇxᴛ ʀᴇᴅᴇᴇᴍ ɪɴ: {hours}ʜ {minutes}ᴍ"),
            parse_mode="HTML"
        )

    # Validate key
    if not isvalidpromo(code):
        return await update.message.reply_text(to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ᴄᴏᴅᴇ ᴏʀ ᴀʟʀᴇᴀᴅʏ ᴜꜱᴇᴅ."), parse_mode="HTML")

    # Process redemption
    grant = PROMO_DB[code]
    PROMO_DB[code]["used"] = True

    if key := premium_keys.get(code):
        key["used"] = True
        save_keys(premium_keys)

    save_promos(PROMO_DB)
    
    # Update user data with redemption time
    user_data["last_redeem"] = now.isoformat()
    user_store.save()
    
    set_role(uid, grant["role"])
    change_credits(uid, grant["credits"])

    await update.message.reply_text(
        to_small_caps(f"✅ ᴄᴏᴅᴇ ʀᴇᴅᴇᴇᴍᴇᴅ! ʏᴏᴜ ᴀʀᴇ ɴᴏᴡ {grant['role'].upper()} ᴀɴᴅ ɢᴏᴛ {grant['credits']} ᴄʀᴇᴅɪᴛꜱ."),
        parse_mode="HTML"
    )


GEN_CREDITS = 5  # how many credits per gen

def luhn_checksum(card_number):
    def digits_of(n): return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d*2))
    return checksum % 10

def generate_valid_card(pattern):
    """Generate a Luhn-valid card number from a pattern (e.g. 411111 or 378282)"""
    length = 16
    if pattern.startswith(('34', '37')):  # Amex
        length = 15
    elif pattern.startswith('36'):  # Diners Club (classic)
        length = 14
    elif pattern.startswith('6011') or pattern.startswith('65') or pattern.startswith('622'):
        length = 16  # Discover

    base = pattern
    while len(base) < length - 1:
        base += str(random.randint(0, 9))
    for check_digit in range(10):
        card = base + str(check_digit)
        if luhn_checksum(card) == 0:
            return card
    return None

def smart_mm_yy_cvv(mm, yy, cvv, pattern=None):
    """Generate MM/YY/CVV, using provided or random values. Amex gets 4-digit CVV."""
    now = datetime.now()
    # MM
    mmg = mm if mm and mm != "xx" else f"{random.randint(1,12):02d}"
    # YY
    yyg = yy if yy and yy != "xx" else f"{random.randint(now.year % 100 + 1, now.year % 100 + 5):02d}"
    # CVV
    if pattern and pattern.startswith(('34', '37')):
        cvv_len = 4
    else:
        cvv_len = 3
    cvvg = cvv if cvv and cvv not in ("xxx", "xxxx") else f"{random.randint(0, 10**cvv_len - 1):0{cvv_len}d}"
    return mmg, yyg, cvvg

async def enhanced_bin_lookup(bin_code):
    """Enhanced BIN lookup with multiple APIs"""
    bin_apis = [
        {
            'url': f"https://bins.su/lookup/{bin_code}",
            'parser': 'bins_su',
            'timeout': 8
        },
        {
            'url': f"https://lookup.binlist.net/{bin_code}",
            'parser': 'binlist',
            'timeout': 8
        },
        {
            'url': f"https://api.bintable.com/v1/{bin_code}",
            'parser': 'bintable',
            'timeout': 8
        }
    ]
    
    brand = issuer = country = ctype = "unknown"
    
    for api in bin_apis:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api['url'], 
                    headers=headers, 
                    timeout=api.get('timeout', 8)
                ) as resp:
                    
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if api['parser'] == 'bins_su':
                            brand = data.get("brand") or data.get("scheme", "unknown")
                            ctype = data.get("type", "unknown")
                            issuer = data.get("bank", "unknown")
                            country = data.get("country_name", "unknown")
                            flag = data.get("country_emoji", "")
                            if flag:
                                country = f"{country} {flag}"
                                
                        elif api['parser'] == 'binlist':
                            brand = data.get("scheme", "unknown")
                            ctype = data.get("type", "unknown")
                            bank_info = data.get("bank", {})
                            issuer = bank_info.get("name", "unknown")
                            country_info = data.get("country", {})
                            country = country_info.get("name", "unknown")
                            flag = country_info.get("emoji", "")
                            if flag:
                                country = f"{country} {flag}"
                                
                        elif api['parser'] == 'bintable':
                            brand = data.get("card_brand", "unknown")
                            ctype = data.get("card_type", "unknown")
                            issuer = data.get("bank", "unknown")
                            country = data.get("country", "unknown")
                        
                        if brand != "unknown":
                            break
                            
        except Exception as e:
            print(f"BIN API {api['url']} failed: {e}")
            continue
    
    return brand, issuer, country, ctype

async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced .gen command with valid cards and tap-to-copy format"""
    user_id = update.effective_user.id
    args = context.args

    if not is_premium(user_id):
        return await send_premium_denied(update)

    # Show usage for no args
    if not args:
        await update.message.reply_text(
            to_small_caps(
                "❌ ᴜꜱᴀɢᴇ:\n"
                "• .gen 411111|mm|yy|cvv\n"
                "• .gen 411111|xx|xx|xxx\n"
                "• .gen 411111\n"
                "• .gen visa 411111\n"
                "• .gen amex 378282\n"
                "• .gen mastercard 51\n"
                "\n"
                "ᴇxᴀᴍᴘʟᴇꜱ:\n"
                "• .gen 411111|12|29|123\n"
                "• .gen 379186\n"
                "• .gen amex 378282\n"
                "• .gen 6011"
            ),
            parse_mode="HTML"
        )
        return

    # Parse arguments
    brand = None
    pattern = None
    mm = yy = cvv = ""

    if "|" in args[0]:
        # .gen 411111|mm|yy|cvv
        try:
            pattern, mm, yy, cvv = (args[0] + "|||").split("|")[:4]
            if not pattern.isdigit() or len(pattern) < 6:
                raise ValueError("Invalid BIN pattern")
        except Exception:
            await update.message.reply_text(
                to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ. ᴜꜱᴇ: .gen 411111|mm|yy|cvv"),
                parse_mode="HTML"
            )
            return
    elif len(args) == 2 and args[0].isalpha() and args[1].isdigit():
        # .gen visa 411111 or .gen amex 378282
        brand = args[0].lower()
        pattern = args[1]
        if not pattern.isdigit() or len(pattern) < 6:
            await update.message.reply_text(
                to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ʙɪɴ. ᴜꜱᴇ 6+ ᴅɪɢɪᴛꜱ, ᴇ.ɢ. .gen visa 411111"),
                parse_mode="HTML"
            )
            return
    else:
        # .gen 411111 or .gen 379186
        pattern = args[0]
        if not pattern.isdigit() or len(pattern) < 6:
            await update.message.reply_text(
                to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ʙɪɴ. ᴜꜱᴇ 6+ ᴅɪɢɪᴛꜱ, ᴇ.ɢ. .gen 411111"),
                parse_mode="HTML"
            )
            return

    if get_credits(user_id) < 5:
        await update.message.reply_text(
            to_small_caps("❌ ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴄʀᴇᴅɪᴛꜱ!"),
            parse_mode="HTML"
        )
        return

    # Animated loading
    loading_frames = [
        f"⏳ ɪɴɪᴛɪᴀʟɪᴢɪɴɢ ɢᴇɴᴇʀᴀᴛᴏʀ ꜰᴏʀ `{pattern}`...",
        "🔍 ᴠᴀʟɪᴅᴀᴛɪɴɢ ʙɪɴ ᴘᴀᴛᴛᴇʀɴ...",
        "🌐 ꜰᴇᴛᴄʜɪɴɢ ʟɪᴠᴇ ʙɪɴ ᴅᴀᴛᴀ...",
        "💳 ɢᴇɴᴇʀᴀᴛɪɴɢ ᴠᴀʟɪᴅ ᴄᴀʀᴅꜱ...",
        "✨ ᴀᴘᴘʟʏɪɴɢ ʟᴜʜɴ ᴀʟɢᴏʀɪᴛʜᴍ...",
        "🎯 ꜰɪɴᴀʟɪᴢɪɴɢ ʀᴇꜱᴜʟᴛꜱ..."
    ]
    loading = await update.message.reply_text(
        to_small_caps(loading_frames[0]),
        parse_mode="HTML"
    )
    for frame in loading_frames[1:]:
        await asyncio.sleep(1)
        try:
            await loading.edit_text(to_small_caps(frame), parse_mode="HTML")
        except:
            pass

    # Generate 10 valid cards (change range(10) to desired count)
    cards = []
    for i in range(10):
        card_number = generate_valid_card(pattern)
        mmg, yyg, cvvg = smart_mm_yy_cvv(mm, yy, cvv, pattern)
        full_card = f"{card_number}|{mmg}|{yyg}|{cvvg}"
        cards.append(full_card)

    # BIN lookup for card information
    bin_code = pattern[:6].ljust(6, '0')
    try:
        brand_lookup, issuer, country = await enhanced_bin_lookup(bin_code)
        ctype = detect_card_type(pattern)
    except Exception:
        brand_lookup = issuer = country = ctype = "unknown"

    user = get_user_display_name(update.effective_user)
    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%I:%M:%S %p IST")

    # Format cards for tap-to-copy
    formatted_cards = [f"{i:02d}. <code>{card}</code>" for i, card in enumerate(cards, 1)]

    body = [
        to_small_caps("★━━ ᴠᴀʟɪᴅ ᴄᴀʀᴅ ɢᴇɴᴇʀᴀᴛᴏʀ ━━★"),
        f"{to_small_caps('ᴘᴀᴛᴛᴇʀɴ:')} <code>{pattern}|{mm or 'xx'}|{yy or 'xx'}|{cvv or 'xxx'}</code>",
        "",
        f"{to_small_caps('ʙɪɴ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ:')}",
        f" ↳ ʙɪɴ: <code>{bin_code}</code>",
        f" ↳ ʙʀᴀɴᴅ: {to_small_caps(brand_lookup)}",
        f" ↳ ᴛʏᴘᴇ: {to_small_caps(ctype)}",
        f" ↳ ɪꜱꜱᴜᴇʀ: {to_small_caps(issuer)}",
        f" ↳ ᴄᴏᴜɴᴛʀʏ: {to_small_caps(country)}",
        "",
        f"{to_small_caps('ɢᴇɴᴇʀᴀᴛᴇᴅ ᴄᴀʀᴅꜱ:')}",
    ] + formatted_cards + [
        "",
        f"💡 {to_small_caps('ᴛᴀᴘ ᴀɴʏ ᴄᴀʀᴅ ᴛᴏ ᴄᴏᴘʏ')}",
        f"✅ {to_small_caps('ᴀʟʟ ᴄᴀʀᴅꜱ ᴀʀᴇ ʟᴜʜɴ ᴠᴀʟɪᴅ')}",
        "",
        to_small_caps(f"ʀᴇQ ʙʏ: {user} | {now}"),
        to_small_caps("★━━━━━━━━━━━━━━━━━━━━━━━━★")
    ]
    box = "\n".join(body)

    change_credits(user_id, -5)
    try:
        await loading.edit_text(box, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(box, parse_mode="HTML")

# Gateway configurations for different card types
GATEWAY_CONFIG = {
    "visa": [
        {"name": "Stripe Live [1$]", "endpoint": "https://api.stripe.com/v1/charges", "weight": 30},
        {"name": "Braintree Live [0.5$]", "endpoint": "https://api.braintreegateway.com", "weight": 25},
        {"name": "Square Live [0.8$]", "endpoint": "https://connect.squareup.com", "weight": 20},
        {"name": "PayPal Live [1$]", "endpoint": "https://api.paypal.com", "weight": 15},
        {"name": "Authorize.net Live [0.7$]", "endpoint": "https://api.authorize.net", "weight": 10}
    ],
    "mastercard": [
        {"name": "Adyen Live [0.9$]", "endpoint": "https://checkout-test.adyen.com", "weight": 35},
        {"name": "Worldpay Live [1.2$]", "endpoint": "https://api.worldpay.com", "weight": 25},
        {"name": "Stripe Live [1$]", "endpoint": "https://api.stripe.com/v1/charges", "weight": 20},
        {"name": "PayPal Live [1$]", "endpoint": "https://api.paypal.com", "weight": 15}
    ],
    "amex": [
        {"name": "Amex Gateway [1.5$]", "endpoint": "https://api.americanexpress.com", "weight": 40},
        {"name": "Stripe Live [1$]", "endpoint": "https://api.stripe.com/v1/charges", "weight": 30},
        {"name": "Braintree Live [0.5$]", "endpoint": "https://api.braintreegateway.com", "weight": 20}
    ],
    "default": [
        {"name": "Stripe Live [1$]", "endpoint": "https://api.stripe.com/v1/charges", "weight": 40},
        {"name": "PayPal Live [1$]", "endpoint": "https://api.paypal.com", "weight": 30},
        {"name": "Braintree Live [0.5$]", "endpoint": "https://api.braintreegateway.com", "weight": 20}
    ]
}

def detect_card_type(card_number):
    """Detect card type based on card number patterns"""
    if not card_number or not isinstance(card_number, str):
        return "default"
        
    card_number = str(card_number).replace(" ", "").replace("-", "")
    
    # Visa: starts with 4
    if card_number.startswith('4'):
        return "visa"
    
    # Mastercard: starts with 5[1-5] or 2[2-7]
    elif card_number.startswith(('51', '52', '53', '54', '55')) or \
         (card_number.startswith('2') and len(card_number) >= 4 and 2221 <= int(card_number[:4]) <= 2720):
        return "mastercard"
    
    # American Express: starts with 34 or 37
    elif card_number.startswith(('34', '37')):
        return "amex"
    
    # Discover: starts with 6011, 65, or 622126-622925
    elif card_number.startswith('6011') or card_number.startswith('65'):
        return "discover"
    
    return "default"

def select_gateway_by_card(card_number):
    """Select appropriate gateway based on card type with weighted random selection"""
    
    # Validate input
    if not card_number or not isinstance(card_number, str):
        card_number = "4111111111111111"  # Default fallback
    
    card_type = detect_card_type(card_number)
    gateways = GATEWAY_CONFIG.get(card_type, GATEWAY_CONFIG["default"])
    
    # Use hashlib with proper error handling
    try:
        # Use hashlib.new() for better compatibility
        hash_obj = hashlib.new('md5')
        hash_obj.update(card_number.encode('utf-8'))
        card_hash = hash_obj.hexdigest()
    except Exception:
        # Fallback to sha256 if md5 fails
        try:
            hash_obj = hashlib.sha256()
            hash_obj.update(card_number.encode('utf-8'))
            card_hash = hash_obj.hexdigest()
        except Exception:
            # Ultimate fallback - use card number directly
            card_hash = str(hash(card_number))
    
    # Create deterministic selection based on card number
    try:
        seed = int(card_hash[:8], 16)
    except ValueError:
        seed = hash(card_number) % 1000000
    
    random.seed(seed)
    
    # Weighted random selection
    total_weight = sum(g["weight"] for g in gateways)
    rand_num = random.randint(1, total_weight)
    
    current_weight = 0
    for gateway in gateways:
        current_weight += gateway["weight"]
        if rand_num <= current_weight:
            return gateway, card_type
    
    return gateways[0], card_type  # Fallback

async def enhanced_bin_lookup(bin_code):
    """Enhanced BIN lookup with multiple APIs and error handling"""
    bin_apis = [
        {
            'url': f"https://bins.su/lookup/{bin_code}",
            'parser': 'bins_su',
            'timeout': 8
        },
        {
            'url': f"https://lookup.binlist.net/{bin_code}",
            'parser': 'binlist',
            'timeout': 8
        },
        {
            'url': f"https://api.bintable.com/v1/{bin_code}",
            'parser': 'bintable',
            'timeout': 8
        }
    ]
    
    brand = issuer = country = "unknown"
    
    for api in bin_apis:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api['url'], 
                    headers=headers, 
                    timeout=api.get('timeout', 8)
                ) as resp:
                    
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if api['parser'] == 'bins_su':
                            brand = data.get("brand") or data.get("scheme", "unknown")
                            issuer = data.get("type", "unknown")
                            country = data.get("country_name", "unknown")
                            flag = data.get("country_emoji", "")
                            if flag:
                                country = f"{country} {flag}"
                                
                        elif api['parser'] == 'binlist':
                            brand = data.get("scheme", "unknown")
                            bank_info = data.get("bank", {})
                            issuer = bank_info.get("name", "unknown")
                            country_info = data.get("country", {})
                            country = country_info.get("name", "unknown")
                            flag = country_info.get("emoji", "")
                            if flag:
                                country = f"{country} {flag}"
                                
                        elif api['parser'] == 'bintable':
                            brand = data.get("card_brand", "unknown")
                            issuer = data.get("bank", "unknown")
                            country = data.get("country", "unknown")
                        
                        if brand != "unknown":
                            break
                            
        except Exception as e:
            print(f"BIN API {api['url']} failed: {e}")
            continue
    
    return brand, issuer, country

def calculate_approval_rate(card_number, card_type):
    """Calculate approval rate based on card type"""
    base_rates = {
        "visa": 0.35,
        "mastercard": 0.30,
        "amex": 0.25,
        "discover": 0.28,
        "default": 0.25
    }
    
    base_rate = base_rates.get(card_type, 0.25)
    
    # Adjust based on BIN patterns
    try:
        bin_code = card_number[:6]
        bin_hash = hash(bin_code) % 10
        
        # Premium BINs have slightly higher approval rates
        if bin_hash < 3:  # 30% of BINs are "premium"
            base_rate += 0.05
    except:
        pass
    
    return min(base_rate, 0.45)  # Cap at 45%

async def cmd_chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced .chk command with automatic gateway selection and error handling"""
    args = context.args
    user_id = update.effective_user.id

    if not args or "|" not in args[0]:
        await update.message.reply_text(
            to_small_caps("❌ ᴜꜱᴀɢᴇ: .chk 4111111111111111|12|28|123")
        )
        return

    card = args[0].strip()
    number = card.split("|")[0].replace(" ", "")

    # Check if card is killed
    if number in KILLED_CARDS:
        killer = KILLED_CARDS[number]
        user = get_user_display_name(update.effective_user)
        now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%I:%M:%S %p IST")
        box = (
            "★━━ ᴄᴀʀᴅ ᴄʜᴇᴄᴋ ━━★\n"
            f"⟣ ᴄᴀʀᴅ : <code>{number}</code>\n"
            f"⟣ sᴛᴀᴛᴜs : <b>ᴅᴇᴀᴅ</b>\n"
            f"⟣ ʀᴇsᴘᴏɴsᴇ : ᴛʜɪs ᴄᴀʀᴅ ʜᴀꜱ ʙᴇᴇɴ ᴋɪʟʟᴇᴅ ʙʏ <b>{killer}</b>.\n"
            f"\nᴜꜱᴇʀ: {user}\nᴛɪᴍᴇ: {now}\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        return await update.message.reply_text(box, parse_mode="HTML")
    
    # Premium check and credits
    if not is_premium(user_id):
        return await send_premium_denied(update)

    if get_credits(user_id) < 2:
        await update.message.reply_text(
            to_small_caps("❌ ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴄʀᴇᴅɪᴛꜱ!")
        )
        return

    # Parse card details with validation
    try:
        parts = card.split("|")
        if len(parts) != 4:
            raise ValueError("Invalid card format")
            
        number, mm, yy, cvv = parts
        
        # Validate card number
        if not number or not number.isdigit() or len(number) < 13 or len(number) > 19:
            raise ValueError("Invalid card number")
            
        # Validate expiry
        if not mm or not mm.isdigit() or not (1 <= int(mm) <= 12):
            raise ValueError("Invalid month")
            
        if not yy or not yy.isdigit() or len(yy) != 2:
            raise ValueError("Invalid year")
            
        # Validate CVV
        if not cvv or not cvv.isdigit() or not (3 <= len(cvv) <= 4):
            raise ValueError("Invalid CVV")
            
        bin_code = number[:6]
        
    except Exception as e:
        await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ᴄᴀʀᴅ ꜰᴏʀᴍᴀᴛ\nᴜꜱᴇ: 4111111111111111|12|28|123")
        )
        return

    # Select gateway based on card type with error handling
    try:
        gateway_info, card_type = select_gateway_by_card(number)
        gateway_name = gateway_info["name"]
    except Exception as e:
        print(f"Gateway selection error: {e}")
        # Fallback gateway
        gateway_name = "Stripe Live [1$]"
        card_type = "visa"
    
    # Enhanced loading animation with gateway info
    CHK_LOADING_FRAMES = [
        f"🔍 ᴅᴇᴛᴇᴄᴛᴇᴅ {card_type.upper()} ᴄᴀʀᴅ...",
        f"🌐 ꜱᴇʟᴇᴄᴛɪɴɢ {gateway_name}...",
        "💳 ᴠᴇʀɪꜰʏɪɴɢ ᴄᴀʀᴅ ᴅᴀᴛᴀ...",
        "⚡ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ᴘᴀʏᴍᴇɴᴛ...",
        "✨ ꜰɪɴᴀʟɪᴢɪɴɢ ʀᴇꜱᴜʟᴛ..."
    ]

    loading_msg = await update.message.reply_text(
        to_small_caps(CHK_LOADING_FRAMES[0]), 
        parse_mode="HTML"
    )
    
    for frame in CHK_LOADING_FRAMES[1:]:
        await asyncio.sleep(1)
        try:
            await loading_msg.edit_text(to_small_caps(frame), parse_mode="HTML")
        except Exception:
            pass  # Ignore edit errors
    
    await asyncio.sleep(0.5)

    # BIN lookup with error handling
    try:
        brand, issuer, country = await enhanced_bin_lookup(bin_code)
    except Exception as e:
        print(f"BIN lookup error: {e}")
        brand = issuer = country = "unknown"

    # Calculate approval based on card type and gateway
    try:
        approval_rate = calculate_approval_rate(number, card_type)
        
        # Deterministic approval decision
        try:
            hash_obj = hashlib.md5()
            hash_obj.update((card + gateway_name).encode('utf-8'))
            card_hash = hash_obj.hexdigest()
            approval_seed = int(card_hash[:8], 16) % 100
        except Exception:
            approval_seed = hash(card + gateway_name) % 100
        
        approved = approval_seed < (approval_rate * 100)
    except Exception:
        # Fallback approval logic
        approved = hash(card) % 4 == 0  # 25% approval rate
    
    status = "approved" if approved else "declined"
    status_emoji = "✅" if approved else "❌"

    # Generate realistic response messages
    if approved:
        responses = [
            "payment successful",
            "transaction approved",
            "authorization successful",
            "charge completed",
            "payment processed"
        ]
    else:
        responses = [
            "payment declined",
            "insufficient funds",
            "card declined",
            "authorization failed",
            "transaction rejected",
            "invalid card",
            "expired card"
        ]
    
    try:
        response_msg = random.choice(responses)
    except:
        response_msg = "payment successful" if approved else "payment declined"
    
    user = get_user_display_name(update.effective_user)
    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%I:%M:%S %p IST")

    # Enhanced response format with gateway routing info
    box = (
        "┏━━━━━━━⍟\n"
        f"┃ {to_small_caps(status.title())} {status_emoji}\n"
        "┗━━━━━━━━━━━⊛\n\n"
        f"⌯ {to_small_caps('ᴄᴀʀᴅ')}\n"
        f" ↳ `{card}`\n"
        f"⌯ {to_small_caps('ᴄᴀʀᴅ ᴛʏᴘᴇ')} ➳ {card_type.upper()}\n"
        f"⌯ {to_small_caps('ɢᴀᴛᴇᴡᴀʏ')} ➳ {gateway_name}\n"
        f"⌯ {to_small_caps('ʀᴇꜱᴘᴏɴꜱᴇ')} ➳ {response_msg}\n\n"
        f"⌯ {to_small_caps('ʙɪɴ ɪɴꜰᴏ')}\n"
        f" ↳ ʙʀᴀɴᴅ: {brand}\n"
        f" ↳ ɪꜱꜱᴜᴇʀ: {issuer}\n"
        f" ↳ ᴄᴏᴜɴᴛʀʏ: {country}\n\n"
        f"⌯ {to_small_caps('ʀᴏᴜᴛɪɴɢ ɪɴꜰᴏ')}\n"
        f" ↳ ᴀᴜᴛᴏ-ꜱᴇʟᴇᴄᴛᴇᴅ ɢᴀᴛᴇᴡᴀʏ\n"
        f" ↳ ᴏᴘᴛɪᴍɪᴢᴇᴅ ꜰᴏʀ {card_type.upper()}\n\n"
        f"ʀᴇQ ʙʏ ➳ {user}\n"
        f"{now}"
    )

    try:
        change_credits(user_id, -2)
        await loading_msg.edit_text(box, parse_mode="HTML")
    except Exception as e:
        print(f"Error updating message: {e}")
        # Fallback - send new message if edit fails
        try:
            await update.message.reply_text(box, parse_mode="HTML")
        except Exception:
            await update.message.reply_text(
                to_small_caps("❌ ᴇʀʀᴏʀ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ʀᴇꜱᴜʟᴛ")
            )

# Additional utility function for gateway statistics
async def cmd_gateway_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show gateway routing statistics"""
    user_id = update.effective_user.id
    
    if not is_premium(user_id):
        return await send_premium_denied(update)
    
    stats_msg = (
        "★━━ ɢᴀᴛᴇᴡᴀʏ ʀᴏᴜᴛɪɴɢ ꜱᴛᴀᴛꜱ ━━★\n\n"
        f"{to_small_caps('ᴠɪꜱᴀ ᴄᴀʀᴅꜱ:')}\n"
        f" ↳ ᴘʀɪᴍᴀʀʏ: Stripe Live (30%)\n"
        f" ↳ ꜱᴇᴄᴏɴᴅᴀʀʏ: Braintree (25%)\n\n"
        f"{to_small_caps('ᴍᴀꜱᴛᴇʀᴄᴀʀᴅ:')}\n"
        f" ↳ ᴘʀɪᴍᴀʀʏ: Adyen Live (35%)\n"
        f" ↳ ꜱᴇᴄᴏɴᴅᴀʀʏ: Worldpay (25%)\n\n"
        f"{to_small_caps('ᴀᴍᴇʀɪᴄᴀɴ ᴇxᴘʀᴇꜱꜱ:')}\n"
        f" ↳ ᴘʀɪᴍᴀʀʏ: Amex Gateway (40%)\n"
        f" ↳ ꜱᴇᴄᴏɴᴅᴀʀʏ: Stripe Live (30%)\n\n"
        f"{to_small_caps('ᴅɪꜱᴄᴏᴠᴇʀ:')}\n"
        f" ↳ ᴘʀɪᴍᴀʀʏ: Discover Gateway (45%)\n"
        f" ↳ ꜱᴇᴄᴏɴᴅᴀʀʏ: Stripe Live (25%)\n\n"
        "💡 ɢᴀᴛᴇᴡᴀʏꜱ ᴀᴜᴛᴏ-ꜱᴇʟᴇᴄᴛᴇᴅ ʙᴀꜱᴇᴅ ᴏɴ ᴄᴀʀᴅ ᴛʏᴘᴇ\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await update.message.reply_text(to_small_caps(stats_msg), parse_mode="HTML")


async def cmd_slf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple self profile command"""
    user = update.effective_user
    data = user_store.get(user.id) or {}
    
    role = data.get("role", "free")
    credits = data.get("credits", 0)
    joined = pretty_time(datetime.fromtimestamp(data.get("joined", int(time.time()))))
    
    msg = (
        "★━━ ᴜꜱᴇʀ ɪɴꜰᴏ ━━★\n"
        f"ɪᴅ: `{user.id}`\n"
        f"ɴᴀᴍᴇ: {to_small_caps(get_user_display_name(user))}\n"
        f"ʀᴏʟᴇ: {to_small_caps(role)}\n"
        f"ᴄʀᴇᴅɪᴛꜱ: `{credits}`\n"
        f"ᴊᴏɪɴᴇᴅ: {joined}\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")
    
async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else "No Username"
    
    msg = (
        f"{to_small_caps('💎💰 ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴꜱ 💰💎')}\n"
        f"{to_small_caps('─────────────────────')}\n"
        f"{to_small_caps('₹20 → 100 ᴄʀᴇᴅɪᴛꜱ')}\n"
        f"{to_small_caps('₹50 → 250 ᴄʀᴇᴅɪᴛꜱ')}\n"
        f"{to_small_caps('₹100 → 1000 ᴄʀᴇᴅɪᴛꜱ')}\n"
        f"{to_small_caps('₹200 → ᴜɴʟɪᴍɪᴛᴇᴅ')}\n"
        "\n"
        f"{to_small_caps('📞 ᴄᴏɴᴛᴀᴄᴛ:')} @SIDIKI_MUSTAFA_92\n"
        f"{to_small_caps('─────────────────────')}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

  
ADMIN_ID = 8179218740  # Set your admin Telegram ID here

async def cmd_cr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Credit management command - shows balance or adds credits (admin only)"""
    user = update.effective_user
    user_id = user.id
    
    # If no arguments, show current credit balance
    if not context.args:
        # Get user data
        data = user_store.get(user_id) or {}
        credits = data.get("credits", 0)
        role = data.get("role", "free")
        
        # Get additional stats
        last_daily = data.get("last_daily", 0)
        if last_daily:
            try:
                last_daily_dt = datetime.fromisoformat(last_daily)
                last_daily_str = pretty_time(last_daily_dt)
            except:
                last_daily_str = "never"
        else:
            last_daily_str = "never"
        
        joined = pretty_time(datetime.fromtimestamp(data.get("joined", int(time.time()))))
        
        # Check if user can claim daily reward
        now = datetime.now(pytz.timezone("Asia/Kolkata"))
        can_claim_daily = False
        if last_daily:
            try:
                last_daily_dt = datetime.fromisoformat(last_daily)
                if now - last_daily_dt >= timedelta(hours=24):
                    can_claim_daily = True
            except:
                can_claim_daily = True
        else:
            can_claim_daily = True
        
        daily_status = "✅ ᴀᴠᴀɪʟᴀʙʟᴇ" if can_claim_daily else "❌ ᴄʟᴀɪᴍᴇᴅ"
        
        msg = (
            "★━━ ᴄʀᴇᴅɪᴛ ɪɴꜰᴏ ━━★\n"
            f"ɪᴅ: `{user_id}`\n"
            f"ɴᴀᴍᴇ: {get_user_display_name(user)}\n"
            f"ʀᴏʟᴇ: {to_small_caps(role)}\n"
            f"ᴄʀᴇᴅɪᴛꜱ: `{credits}`\n"
            f"ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ: {daily_status}\n"
            f"ʟᴀꜱᴛ ᴅᴀɪʟʏ: {last_daily_str}\n"
            f"ᴊᴏɪɴᴇᴅ: {joined}\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        
        await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")
        return
    
    # Admin-only credit addition functionality
    if user_id != ADMIN_ID:
        return await update.message.reply_text(
            to_small_caps("❌ ᴏɴʟʏ ᴀᴅᴍɪɴ ᴄᴀɴ ᴀᴅᴅ ᴄʀᴇᴅɪᴛꜱ!"),
            parse_mode="HTML"
        )
    
    # Parse arguments for credit addition
    if len(context.args) < 2:
        usage_msg = (
            "★━━ ᴄʀᴇᴅɪᴛ ᴍᴀɴᴀɢᴇʀ ━━★\n\n"
            "ᴜꜱᴀɢᴇ:\n"
            "• .cr - ꜱʜᴏᴡ ʏᴏᴜʀ ᴄʀᴇᴅɪᴛꜱ\n"
            "• .cr [user_id] [amount] - ᴀᴅᴅ ᴄʀᴇᴅɪᴛꜱ (ᴀᴅᴍɪɴ)\n"
            "• .cr [user_id] -[amount] - ʀᴇᴍᴏᴠᴇ ᴄʀᴇᴅɪᴛꜱ (ᴀᴅᴍɪɴ)\n\n"
            "ᴇxᴀᴍᴘʟᴇꜱ:\n"
            "• .cr 123456789 100\n"
            "• .cr 123456789 -50\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        return await update.message.reply_text(to_small_caps(usage_msg), parse_mode="HTML")
    
    try:
        target_user_id = int(context.args[0])
        credit_amount = int(context.args[1])
    except ValueError:
        return await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ᴜꜱᴇʀ ɪᴅ ᴏʀ ᴀᴍᴏᴜɴᴛ!"),
            parse_mode="HTML"
        )
    
    # Check if target user exists
    target_data = user_store.get(target_user_id)
    if not target_data:
        return await update.message.reply_text(
            to_small_caps("❌ ᴜꜱᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀꜱᴇ!"),
            parse_mode="HTML"
        )
    
    # Get current credits
    current_credits = target_data.get("credits", 0)
    new_credits = current_credits + credit_amount
    
    # Prevent negative credits
    if new_credits < 0:
        return await update.message.reply_text(
            to_small_caps(f"❌ ᴄᴀɴɴᴏᴛ ꜱᴇᴛ ɴᴇɢᴀᴛɪᴠᴇ ᴄʀᴇᴅɪᴛꜱ!\nᴄᴜʀʀᴇɴᴛ: {current_credits}"),
            parse_mode="HTML"
        )
    
    # Update credits
    change_credits(target_user_id, credit_amount)
    
    # Get target user info for display
    target_username = target_data.get("username", "Unknown")
    target_role = target_data.get("role", "free")
    
    # Determine action type
    action = "ᴀᴅᴅᴇᴅ" if credit_amount > 0 else "ʀᴇᴍᴏᴠᴇᴅ"
    action_emoji = "➕" if credit_amount > 0 else "➖"
    
    msg = (
        "★━━ ᴄʀᴇᴅɪᴛ ᴜᴘᴅᴀᴛᴇ ━━★\n"
        f"{action_emoji} {action} `{abs(credit_amount)}` ᴄʀᴇᴅɪᴛꜱ\n\n"
        f"ᴛᴀʀɢᴇᴛ ᴜꜱᴇʀ:\n"
        f"ɪᴅ: `{target_user_id}`\n"
        f"ᴜꜱᴇʀɴᴀᴍᴇ: @{target_username}\n"
        f"ʀᴏʟᴇ: {to_small_caps(target_role)}\n\n"
        f"ᴄʀᴇᴅɪᴛ ᴄʜᴀɴɢᴇ:\n"
        f"ᴘʀᴇᴠɪᴏᴜꜱ: `{current_credits}`\n"
        f"ᴄᴜʀʀᴇɴᴛ: `{new_credits}`\n"
        f"ᴄʜᴀɴɢᴇ: `{credit_amount:+d}`\n\n"
        f"ᴀᴅᴍɪɴ: {get_user_display_name(user)}\n"
        f"ᴛɪᴍᴇ: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%I:%M:%S %p IST')}\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")

# Enhanced version with bulk credit operations
async def cmd_cr_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bulk credit operations for admin"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return await update.message.reply_text(
            to_small_caps("❌ ᴏɴʟʏ ᴀᴅᴍɪɴ ᴄᴀɴ ᴜꜱᴇ ʙᴜʟᴋ ᴏᴘᴇʀᴀᴛɪᴏɴꜱ!"),
            parse_mode="HTML"
        )
    
    if not context.args:
        usage_msg = (
            "★━━ ʙᴜʟᴋ ᴄʀᴇᴅɪᴛ ᴍᴀɴᴀɢᴇʀ ━━★\n\n"
            "ᴄᴏᴍᴍᴀɴᴅꜱ:\n"
            "• .cr bulk all [amount] - ᴀᴅᴅ ᴛᴏ ᴀʟʟ ᴜꜱᴇʀꜱ\n"
            "• .cr bulk premium [amount] - ᴀᴅᴅ ᴛᴏ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ\n"
            "• .cr bulk free [amount] - ᴀᴅᴅ ᴛᴏ ꜰʀᴇᴇ ᴜꜱᴇʀꜱ\n"
            "• .cr bulk reset - ʀᴇꜱᴇᴛ ᴀʟʟ ᴄʀᴇᴅɪᴛꜱ ᴛᴏ 0\n\n"
            "ᴇxᴀᴍᴘʟᴇꜱ:\n"
            "• .cr bulk all 50\n"
            "• .cr bulk premium 100\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        return await update.message.reply_text(to_small_caps(usage_msg), parse_mode="HTML")
    
    operation = context.args[0].lower()
    
    if operation == "reset":
        # Reset all user credits to 0
        count = 0
        for uid, data in user_store.data.items():
            if data.get("credits", 0) > 0:
                data["credits"] = 0
                count += 1
        
        user_store.save()
        
        msg = (
            "★━━ ʙᴜʟᴋ ʀᴇꜱᴇᴛ ━━★\n"
            f"✅ ʀᴇꜱᴇᴛ ᴄʀᴇᴅɪᴛꜱ ꜰᴏʀ {count} ᴜꜱᴇʀꜱ\n"
            f"ᴀʟʟ ᴄʀᴇᴅɪᴛꜱ ꜱᴇᴛ ᴛᴏ 0\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        
        return await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")
    
    if len(context.args) < 2:
        return await update.message.reply_text(
            to_small_caps("❌ ᴍɪꜱꜱɪɴɢ ᴀᴍᴏᴜɴᴛ!"),
            parse_mode="HTML"
        )
    
    try:
        amount = int(context.args[1])
    except ValueError:
        return await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ᴀᴍᴏᴜɴᴛ!"),
            parse_mode="HTML"
        )
    
    # Loading message
    loading_msg = await update.message.reply_text(
        to_small_caps("⏳ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ʙᴜʟᴋ ᴏᴘᴇʀᴀᴛɪᴏɴ..."),
        parse_mode="HTML"
    )
    
    count = 0
    total_credits_added = 0
    
    for uid, data in user_store.data.items():
        should_update = False
        
        if operation == "all":
            should_update = True
        elif operation == "premium":
            should_update = data.get("role", "free") == "premium"
        elif operation == "free":
            should_update = data.get("role", "free") == "free"
        
        if should_update:
            change_credits(uid, amount)
            count += 1
            total_credits_added += amount
    
    msg = (
        "★━━ ʙᴜʟᴋ ᴏᴘᴇʀᴀᴛɪᴏɴ ᴄᴏᴍᴘʟᴇᴛᴇ ━━★\n"
        f"ᴏᴘᴇʀᴀᴛɪᴏɴ: {operation.upper()}\n"
        f"ᴜꜱᴇʀꜱ ᴀꜰꜰᴇᴄᴛᴇᴅ: `{count}`\n"
        f"ᴄʀᴇᴅɪᴛꜱ ᴘᴇʀ ᴜꜱᴇʀ: `{amount:+d}`\n"
        f"ᴛᴏᴛᴀʟ ᴄʀᴇᴅɪᴛꜱ ᴀᴅᴅᴇᴅ: `{total_credits_added:+d}`\n"
        f"ᴀᴅᴍɪɴ: {get_user_display_name(update.effective_user)}\n"
        f"ᴛɪᴍᴇ: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%I:%M:%S %p IST')}\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await loading_msg.edit_text(to_small_caps(msg), parse_mode="HTML")

async def cmd_bin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """BIN lookup command with deep analysis"""
    user_id = update.effective_user.id
    
    if not is_premium(user_id):
        return await send_premium_denied(update)
    
    if not context.args:
        await update.message.reply_text(
            to_small_caps("❌ ᴜꜱᴀɢᴇ: .bin 451210"),
            parse_mode="HTML"
        )
        return
    
    bin_code = context.args[0].strip()
    
    # Validate BIN format
    if not bin_code.isdigit() or len(bin_code) < 6:
        await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ʙɪɴ ꜰᴏʀᴍᴀᴛ. ᴜꜱᴇ 6+ ᴅɪɢɪᴛꜱ"),
            parse_mode="HTML"
        )
        return
    
    # Credit check
    if get_credits(user_id) < 1:
        await update.message.reply_text(
            to_small_caps("❌ ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴄʀᴇᴅɪᴛꜱ!"),
            parse_mode="HTML"
        )
        return
    
    # Loading animation
    BIN_LOADING_FRAMES = [
        "🔍 ɪɴɪᴛɪᴀʟɪᴢɪɴɢ ʙɪɴ ʟᴏᴏᴋᴜᴘ...",
        "🌐 ᴄᴏɴɴᴇᴄᴛɪɴɢ ᴛᴏ ᴅᴀᴛᴀʙᴀꜱᴇ...",
        "📊 ᴀɴᴀʟʏᴢɪɴɢ ʙɪɴ ᴅᴀᴛᴀ...",
        "🔐 ᴠᴇʀɪꜰʏɪɴɢ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ...",
        "✨ ᴄᴏᴍᴘɪʟɪɴɢ ʀᴇꜱᴜʟᴛꜱ..."
    ]
    
    loading_msg = await update.message.reply_text(
        to_small_caps(BIN_LOADING_FRAMES[0]), 
        parse_mode="HTML"
    )
    
    for frame in BIN_LOADING_FRAMES[1:]:
        await asyncio.sleep(1)
        await loading_msg.edit_text(to_small_caps(frame), parse_mode="HTML")
    
    await asyncio.sleep(0.5)
    
    # Multiple BIN API lookup for comprehensive data
    bin_data = {
        'brand': 'unknown',
        'type': 'unknown', 
        'level': 'unknown',
        'bank': 'unknown',
        'country': 'unknown',
        'currency': 'unknown',
        'website': 'unknown',
        'phone': 'unknown'
    }
    
    # Try multiple BIN APIs
    bin_apis = [
        {
            'url': f"https://bins.su/lookup/{bin_code}",
            'parser': 'bins_su'
        },
        {
            'url': f"https://lookup.binlist.net/{bin_code}",
            'parser': 'binlist'
        },
        {
            'url': f"https://api.bintable.com/v1/{bin_code}",
            'parser': 'bintable'
        }
    ]
    
    for api in bin_apis:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                async with session.get(api['url'], headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if api['parser'] == 'bins_su':
                            bin_data['brand'] = data.get('brand') or data.get('scheme', 'unknown')
                            bin_data['type'] = data.get('type', 'unknown')
                            bin_data['level'] = data.get('level', 'unknown')
                            bin_data['bank'] = data.get('bank', 'unknown')
                            bin_data['country'] = data.get('country_name', 'unknown')
                            bin_data['currency'] = data.get('currency', 'unknown')
                            flag = data.get('country_emoji', '')
                            if flag:
                                bin_data['country'] = f"{bin_data['country']} {flag}"
                        
                        elif api['parser'] == 'binlist':
                            bin_data['brand'] = data.get('scheme', 'unknown')
                            bin_data['type'] = data.get('type', 'unknown')
                            bin_data['level'] = data.get('brand', 'unknown')
                            
                            bank_info = data.get('bank', {})
                            bin_data['bank'] = bank_info.get('name', 'unknown')
                            bin_data['website'] = bank_info.get('url', 'unknown')
                            bin_data['phone'] = bank_info.get('phone', 'unknown')
                            
                            country_info = data.get('country', {})
                            country_name = country_info.get('name', 'unknown')
                            country_emoji = country_info.get('emoji', '')
                            bin_data['country'] = f"{country_name} {country_emoji}" if country_emoji else country_name
                            bin_data['currency'] = country_info.get('currency', 'unknown')
                        
                        elif api['parser'] == 'bintable':
                            bin_data['brand'] = data.get('card_brand', 'unknown')
                            bin_data['type'] = data.get('card_type', 'unknown')
                            bin_data['level'] = data.get('card_level', 'unknown')
                            bin_data['bank'] = data.get('bank', 'unknown')
                            bin_data['country'] = data.get('country', 'unknown')
                        
                        # If we got good data, break
                        if bin_data['brand'] != 'unknown':
                            break
                            
        except Exception as e:
            print(f"BIN API {api['url']} failed: {e}")
            continue
    
    # Generate additional BIN analysis
    bin_prefix = bin_code[:1]
    card_network = {
        '4': 'Visa',
        '5': 'Mastercard', 
        '3': 'American Express',
        '6': 'Discover'
    }.get(bin_prefix, 'Unknown')
    
    # BIN range analysis
    bin_range = f"{bin_code[:4]}xx-{bin_code[:4]}xx"
    
    user = get_user_display_name(update.effective_user)
    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%I:%M:%S %p IST")
    
    # Enhanced BIN response format
    box = (
        "┏━━━━━━━⍟\n"
        f"┃ {to_small_caps('ʙɪɴ ᴀɴᴀʟʏꜱɪꜱ')} 🔍\n"
        "┗━━━━━━━━━━━⊛\n\n"
        f"⌯ {to_small_caps('ʙɪɴ ᴄᴏᴅᴇ')}\n"
        f" ↳ `{bin_code}`\n\n"
        f"⌯ {to_small_caps('ᴄᴀʀᴅ ɪɴꜰᴏ')}\n"
        f" ↳ ʙʀᴀɴᴅ: {to_small_caps(bin_data['brand'])}\n"
        f" ↳ ᴛʏᴘᴇ: {to_small_caps(bin_data['type'])}\n"
        f" ↳ ʟᴇᴠᴇʟ: {to_small_caps(bin_data['level'])}\n"
        f" ↳ ɴᴇᴛᴡᴏʀᴋ: {to_small_caps(card_network)}\n\n"
        f"⌯ {to_small_caps('ʙᴀɴᴋ ɪɴꜰᴏ')}\n"
        f" ↳ ɪꜱꜱᴜᴇʀ: {to_small_caps(bin_data['bank'])}\n"
        f" ↳ ᴡᴇʙꜱɪᴛᴇ: {bin_data['website']}\n"
        f" ↳ ᴘʜᴏɴᴇ: {bin_data['phone']}\n\n"
        f"⌯ {to_small_caps('ʟᴏᴄᴀᴛɪᴏɴ')}\n"
        f" ↳ ᴄᴏᴜɴᴛʀʏ: {to_small_caps(bin_data['country'])}\n"
        f" ↳ ᴄᴜʀʀᴇɴᴄʏ: {bin_data['currency']}\n\n"
        f"⌯ {to_small_caps('ʀᴀɴɢᴇ ᴀɴᴀʟʏꜱɪꜱ')}\n"
        f" ↳ ʀᴀɴɢᴇ: {bin_range}\n"
        f" ↳ ʟᴇɴɢᴛʜ: {len(bin_code)} ᴅɪɢɪᴛꜱ\n\n"
        f"ʀᴇQ ʙʏ ➳ {user}\n"
        f"{now}"
    )
    
    change_credits(user_id, -1)
    await loading_msg.edit_text(box, parse_mode="HTML")


async def cmd_fake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced fake ID with real addresses from 30+ countries"""
    user_id = update.effective_user.id
    
    if not is_premium(user_id):
        return await send_premium_denied(update)
    
    # Extended country code mapping (30+ countries)
    COUNTRY_CODES = {
        "US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia",
        "DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain", "NL": "Netherlands",
        "BE": "Belgium", "CH": "Switzerland", "AT": "Austria", "SE": "Sweden", "NO": "Norway",
        "DK": "Denmark", "FI": "Finland", "IE": "Ireland", "PT": "Portugal", "GR": "Greece",
        "PL": "Poland", "CZ": "Czech Republic", "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria",
        "HR": "Croatia", "SK": "Slovakia", "SI": "Slovenia", "EE": "Estonia", "LV": "Latvia",
        "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "CY": "Cyprus", "IS": "Iceland",
        "BR": "Brazil", "MX": "Mexico", "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
        "PE": "Peru", "VE": "Venezuela", "UY": "Uruguay", "EC": "Ecuador", "BO": "Bolivia",
        "JP": "Japan", "KR": "South Korea", "CN": "China", "IN": "India", "TH": "Thailand",
        "SG": "Singapore", "MY": "Malaysia", "PH": "Philippines", "ID": "Indonesia", "VN": "Vietnam",
        "ZA": "South Africa", "EG": "Egypt", "MA": "Morocco", "NG": "Nigeria", "KE": "Kenya",
        "GH": "Ghana", "TN": "Tunisia", "DZ": "Algeria", "ET": "Ethiopia", "UG": "Uganda"
    }
    
    # Real verified addresses by country (government buildings, landmarks, corporate HQs)
    REAL_ADDRESSES = {
        "US": [
            {"street": "1600 Pennsylvania Avenue NW", "city": "Washington", "state": "DC", "zip": "20500"},
            {"street": "350 Fifth Avenue", "city": "New York", "state": "NY", "zip": "10118"},
            {"street": "1 Infinite Loop", "city": "Cupertino", "state": "CA", "zip": "95014"},
            {"street": "1 Microsoft Way", "city": "Redmond", "state": "WA", "zip": "98052"},
            {"street": "410 Terry Avenue North", "city": "Seattle", "state": "WA", "zip": "98109"}
        ],
        "GB": [
            {"street": "10 Downing Street", "city": "London", "state": "England", "zip": "SW1A 2AA"},
            {"street": "221B Baker Street", "city": "London", "state": "England", "zip": "NW1 6XE"},
            {"street": "Buckingham Palace", "city": "London", "state": "England", "zip": "SW1A 1AA"},
            {"street": "Tower Bridge Road", "city": "London", "state": "England", "zip": "SE1 2UP"}
        ],
        "CA": [
            {"street": "24 Sussex Drive", "city": "Ottawa", "state": "Ontario", "zip": "K1M 1M4"},
            {"street": "111 Wellington Street", "city": "Ottawa", "state": "Ontario", "zip": "K1A 0A6"},
            {"street": "1 Blue Jays Way", "city": "Toronto", "state": "Ontario", "zip": "M5V 1J1"},
            {"street": "290 Bremner Boulevard", "city": "Toronto", "state": "Ontario", "zip": "M5V 3L9"}
        ],
        "AU": [
            {"street": "Parliament House", "city": "Canberra", "state": "ACT", "zip": "2600"},
            {"street": "1 Macquarie Street", "city": "Sydney", "state": "NSW", "zip": "2000"},
            {"street": "1 Collins Street", "city": "Melbourne", "state": "VIC", "zip": "3000"},
            {"street": "Bennelong Point", "city": "Sydney", "state": "NSW", "zip": "2000"}
        ],
        "DE": [
            {"street": "Unter den Linden 77", "city": "Berlin", "state": "Berlin", "zip": "10117"},
            {"street": "Marienplatz 1", "city": "Munich", "state": "Bavaria", "zip": "80331"},
            {"street": "Rathausplatz 1", "city": "Hamburg", "state": "Hamburg", "zip": "20095"},
            {"street": "Brandenburger Tor", "city": "Berlin", "state": "Berlin", "zip": "10117"}
        ],
        "FR": [
            {"street": "55 Rue du Faubourg Saint-Honore", "city": "Paris", "state": "Ile-de-France", "zip": "75008"},
            {"street": "Place Charles de Gaulle", "city": "Paris", "state": "Ile-de-France", "zip": "75008"},
            {"street": "1 Place Vendome", "city": "Paris", "state": "Ile-de-France", "zip": "75001"},
            {"street": "Champ de Mars", "city": "Paris", "state": "Ile-de-France", "zip": "75007"}
        ],
        "IT": [
            {"street": "Piazza del Quirinale", "city": "Rome", "state": "Lazio", "zip": "00187"},
            {"street": "Piazza San Marco", "city": "Venice", "state": "Veneto", "zip": "30124"},
            {"street": "Piazza del Duomo", "city": "Milan", "state": "Lombardy", "zip": "20122"},
            {"street": "Via del Corso", "city": "Rome", "state": "Lazio", "zip": "00186"}
        ],
        "ES": [
            {"street": "Palacio de la Moncloa", "city": "Madrid", "state": "Madrid", "zip": "28071"},
            {"street": "Plaza Mayor", "city": "Madrid", "state": "Madrid", "zip": "28012"},
            {"street": "Sagrada Familia", "city": "Barcelona", "state": "Catalonia", "zip": "08013"},
            {"street": "Calle Gran Via", "city": "Madrid", "state": "Madrid", "zip": "28013"}
        ],
        "NL": [
            {"street": "Binnenhof 19", "city": "The Hague", "state": "South Holland", "zip": "2513 AA"},
            {"street": "Dam Square", "city": "Amsterdam", "state": "North Holland", "zip": "1012 JS"},
            {"street": "Museumplein", "city": "Amsterdam", "state": "North Holland", "zip": "1071 DJ"},
            {"street": "Lange Voorhout", "city": "The Hague", "state": "South Holland", "zip": "2514 EG"}
        ],
        "JP": [
            {"street": "1-1 Chiyoda", "city": "Tokyo", "state": "Tokyo", "zip": "100-8111"},
            {"street": "2-3-1 Marunouchi", "city": "Tokyo", "state": "Tokyo", "zip": "100-0005"},
            {"street": "1-1-1 Kasumigaseki", "city": "Tokyo", "state": "Tokyo", "zip": "100-8914"},
            {"street": "4-2-5 Kasumigaseki", "city": "Tokyo", "state": "Tokyo", "zip": "100-8919"}
        ],
        "BR": [
            {"street": "Praca dos Tres Poderes", "city": "Brasilia", "state": "DF", "zip": "70150-900"},
            {"street": "Avenida Paulista 1578", "city": "Sao Paulo", "state": "SP", "zip": "01310-200"},
            {"street": "Copacabana Beach", "city": "Rio de Janeiro", "state": "RJ", "zip": "22070-900"},
            {"street": "Rua Oscar Freire", "city": "Sao Paulo", "state": "SP", "zip": "01426-001"}
        ],
        "IN": [
            {"street": "Rashtrapati Bhavan", "city": "New Delhi", "state": "Delhi", "zip": "110004"},
            {"street": "Gateway of India", "city": "Mumbai", "state": "Maharashtra", "zip": "400001"},
            {"street": "Red Fort", "city": "New Delhi", "state": "Delhi", "zip": "110006"},
            {"street": "India Gate", "city": "New Delhi", "state": "Delhi", "zip": "110001"}
        ],
        "CN": [
            {"street": "Tiananmen Square", "city": "Beijing", "state": "Beijing", "zip": "100006"},
            {"street": "The Bund", "city": "Shanghai", "state": "Shanghai", "zip": "200002"},
            {"street": "Forbidden City", "city": "Beijing", "state": "Beijing", "zip": "100009"},
            {"street": "Oriental Pearl Tower", "city": "Shanghai", "state": "Shanghai", "zip": "200120"}
        ],
        "RU": [
            {"street": "Red Square", "city": "Moscow", "state": "Moscow", "zip": "109012"},
            {"street": "Kremlin", "city": "Moscow", "state": "Moscow", "zip": "103073"},
            {"street": "Palace Square", "city": "St. Petersburg", "state": "St. Petersburg", "zip": "190000"},
            {"street": "Nevsky Prospect", "city": "St. Petersburg", "state": "St. Petersburg", "zip": "191186"}
        ]
    }
    
    # Add more countries with basic addresses
    for country in ["SE", "NO", "DK", "FI", "BE", "CH", "AT", "PT", "GR", "PL", "CZ", "HU", "RO", "BG", "HR", "SK", "SI", "EE", "LV", "LT", "LU", "MT", "CY", "IS", "MX", "AR", "CL", "CO", "PE", "VE", "UY", "EC", "BO", "KR", "TH", "SG", "MY", "PH", "ID", "VN", "ZA", "EG", "MA", "NG", "KE", "GH", "TN", "DZ", "ET", "UG"]:
        if country not in REAL_ADDRESSES:
            REAL_ADDRESSES[country] = [
                {"street": "Government Building 1", "city": "Capital City", "state": "Main State", "zip": "10001"},
                {"street": "Central Square 5", "city": "Major City", "state": "Province", "zip": "20001"},
                {"street": "Main Street 100", "city": "Downtown", "state": "Region", "zip": "30001"}
            ]
    
    # Default country
    nat = "US"
    
    # Show usage if no args or help requested
    if not context.args or context.args[0].lower() in ["help", "list", "countries"]:
        # Split countries into chunks for better display
        countries_list = list(COUNTRY_CODES.items())
        chunks = [countries_list[i:i+3] for i in range(0, len(countries_list), 3)]
        
        country_display = []
        for chunk in chunks:
            line = " | ".join([f"{code}-{name[:12]}" for code, name in chunk])
            country_display.append(line)
        
        usage_msg = (
            "★━━ 𝙁𝘼𝙆𝙀 𝙄𝘿 𝙂𝙀𝙉 ━━★\n\n"
            "ᴜꜱᴀɢᴇ: .fake [ᴄᴏᴜɴᴛʀʏ_ᴄᴏᴅᴇ]\n"
            "ᴇxᴀᴍᴘʟᴇ: .fake US\n\n"
            "ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴜɴᴛʀɪᴇꜱ:\n"
            f"{chr(10).join(country_display[:10])}\n"
            "...ᴀɴᴅ 40+ ᴍᴏʀᴇ!\n\n"
            "ᴅᴇꜰᴀᴜʟᴛ: US\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        return await update.message.reply_text(to_small_caps(usage_msg), parse_mode="HTML")
    
    # Get country code from args
    if context.args:
        nat = context.args[0].upper()
        if nat not in COUNTRY_CODES:
            return await update.message.reply_text(
                to_small_caps(f"❌ ɪɴᴠᴀʟɪᴅ ᴄᴏᴜɴᴛʀʏ ᴄᴏᴅᴇ: {nat}\nᴜꜱᴇ .fake help ꜰᴏʀ ʟɪꜱᴛ"),
                parse_mode="HTML"
            )
    
    # Loading message
    loading_msg = await update.message.reply_text(
        to_small_caps("⏳ ɢᴇɴᴇʀᴀᴛɪɴɢ ʀᴇᴀʟ ɪᴅᴇɴᴛɪᴛʏ ᴅᴀᴛᴀ..."),
        parse_mode="HTML"
    )
    
    # Generate fake personal data
    user_data = None
    
    # Try RandomUser.me for personal data (works for most countries)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://randomuser.me/api/?nat={nat.lower()}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('results'):
                        info = data['results'][0]
                        
                        # Get real address for the country
                        import random
                        real_address = random.choice(REAL_ADDRESSES.get(nat, REAL_ADDRESSES["US"]))
                        
                        user_data = {
                            'name': f"{info['name']['first']} {info['name']['last']}",
                            'gender': info['gender'].title(),
                            'email': info['email'],
                            'phone': info.get('cell', info.get('phone', 'N/A')),
                            'dob': info['dob']['date'][:10],
                            'age': info['dob']['age'],
                            'address': real_address['street'],
                            'city': real_address['city'],
                            'state': real_address['state'],
                            'country': COUNTRY_CODES[nat],
                            'postcode': real_address['zip'],
                            'username': info['login']['username'],
                            'password': info['login']['password']
                        }
    except Exception as e:
        print(f"RandomUser API failed: {e}")
    
    # Fallback with real addresses if API fails
    if not user_data:
        import random
        import string
        
        first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Chris", "Lisa", "Mark", "Anna", "Alex", "Maria", "James", "Linda", "Robert", "Patricia", "William", "Jennifer", "Richard", "Elizabeth"]
        last_names = ["Smith", "Johnson", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Garcia", "Martinez", "Robinson", "Clark", "Rodriguez"]
        
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        real_address = random.choice(REAL_ADDRESSES.get(nat, REAL_ADDRESSES["US"]))
        
        user_data = {
            'name': f"{first_name} {last_name}",
            'gender': random.choice(['Male', 'Female']),
            'email': f"{first_name.lower()}.{last_name.lower()}@email.com",
            'phone': f"+1-555-{''.join(random.choices(string.digits, k=7))}",
            'dob': f"19{random.randint(70, 99)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
            'age': random.randint(18, 65),
            'address': real_address['street'],
            'city': real_address['city'],
            'state': real_address['state'],
            'country': COUNTRY_CODES[nat],
            'postcode': real_address['zip'],
            'username': f"{first_name.lower()}{random.randint(100, 999)}",
            'password': ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        }
    
    # Format the response using your existing style
    msg = (
        "★━━ 𝙁𝘼𝙆𝙀 𝙄𝘿 ━━★\n\n"
        "ɴᴀᴍᴇ:\n"
        f" `{user_data['name']}`\n\n"
        "ɢᴇɴᴅᴇʀ:\n"
        f" `{user_data['gender']}`\n\n"
        "ᴇᴍᴀɪʟ:\n"
        f" `{user_data['email']}`\n\n"
        "ᴘʜᴏɴᴇ:\n"
        f" `{user_data['phone']}`\n\n"
        "ᴀᴅᴅʀᴇꜱꜱ:\n"
        f" `{user_data['address']}`\n\n"
        "ᴄɪᴛʏ:\n"
        f" `{user_data['city']}`\n\n"
        "ꜱᴛᴀᴛᴇ:\n"
        f" `{user_data['state']}`\n\n"
        "ᴄᴏᴜɴᴛʀʏ:\n"
        f" `{user_data['country']}`\n\n"
        "ᴘɪɴ:\n"
        f" `{user_data['postcode']}`\n\n"
        "ᴅᴏʙ:\n"
        f" `{user_data['dob']}`\n\n"
        "ᴜꜱᴇʀɴᴀᴍᴇ:\n"
        f" `{user_data['username']}`\n\n"
        "ᴘᴀꜱꜱᴡᴏʀᴅ:\n"
        f" `{user_data['password']}`\n\n"
        "ɴᴏᴛᴇ: ᴠᴇʀɪꜰɪᴇᴅ ʀᴇᴀʟ ᴀᴅᴅʀᴇꜱꜱ\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await loading_msg.edit_text(msg, parse_mode="HTML")

async def cmd_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analytics command showing bot statistics"""
    user_id = update.effective_user.id
    
    if not is_premium(user_id):
        return await send_premium_denied(update)
    
    # Loading animation
    ANALYTICS_LOADING_FRAMES = [
        "📊 ɪɴɪᴛɪᴀʟɪᴢɪɴɢ ᴀɴᴀʟʏᴛɪᴄꜱ...",
        "🔍 ᴄᴏʟʟᴇᴄᴛɪɴɢ ᴜꜱᴇʀ ᴅᴀᴛᴀ...",
        "📈 ᴄᴀʟᴄᴜʟᴀᴛɪɴɢ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ...",
        "⚡ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ᴍᴇᴛʀɪᴄꜱ...",
        "✨ ꜰɪɴᴀʟɪᴢɪɴɢ ʀᴇᴘᴏʀᴛ..."
    ]
    
    loading_msg = await update.message.reply_text(
        to_small_caps(ANALYTICS_LOADING_FRAMES[0]), 
        parse_mode="HTML"
    )
    
    for frame in ANALYTICS_LOADING_FRAMES[1:]:
        await asyncio.sleep(1)
        await loading_msg.edit_text(to_small_caps(frame), parse_mode="HTML")
    
    await asyncio.sleep(0.5)
    
    # Calculate comprehensive statistics
    try:
        # User statistics
        total_users = len(user_store.data) if hasattr(user_store, 'data') else len(user_store)
        premium_users = 0
        free_users = 0
        total_credits = 0
        active_today = 0
        
        # Get current date for activity calculation
        today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
        
        # Iterate through users properly
        user_data = user_store.data if hasattr(user_store, 'data') else user_store
        
        for uid, data in user_data.items():
            role = data.get("role", "free")
            if role == "premium":
                premium_users += 1
            else:
                free_users += 1
            
            total_credits += data.get("credits", 0)
            
            # Check if user was active today (last command usage)
            last_used = data.get("last_used")
            if last_used:
                try:
                    last_used_date = datetime.fromisoformat(last_used).date()
                    if last_used_date == today:
                        active_today += 1
                except:
                    pass
        
        # Command usage statistics (you can track these in your commands)
        total_checks = stats_store.get("total_checks", 0) if 'stats_store' in globals() else 0
        total_vbv = stats_store.get("total_vbv", 0) if 'stats_store' in globals() else 0
        total_mass = stats_store.get("total_mass", 0) if 'stats_store' in globals() else 0
        total_bins = stats_store.get("total_bins", 0) if 'stats_store' in globals() else 0
        total_gens = stats_store.get("total_gens", 0) if 'stats_store' in globals() else 0
        total_fake = stats_store.get("total_fake", 0) if 'stats_store' in globals() else 0
        
        # Calculate percentages
        premium_percentage = (premium_users / total_users * 100) if total_users > 0 else 0
        activity_rate = (active_today / total_users * 100) if total_users > 0 else 0
        
        # Bot uptime (you can track this)
        bot_start_time = stats_store.get("bot_start_time", time.time()) if 'stats_store' in globals() else time.time()
        uptime_seconds = time.time() - bot_start_time
        uptime_hours = int(uptime_seconds // 3600)
        uptime_days = uptime_hours // 24
        
        # Top user by credits (optional)
        top_user_credits = 0
        top_user_id = "None"
        for uid, data in user_data.items():
            credits = data.get("credits", 0)
            if credits > top_user_credits:
                top_user_credits = credits
                top_user_id = uid
        
        # Current date and time
        now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d/%m/%Y %I:%M:%S %p IST")
        
        # Enhanced analytics message
        msg = (
            "★━━ ʙᴏᴛ ᴀɴᴀʟʏᴛɪᴄꜱ ━━★\n\n"
            f"👥 ᴜꜱᴇʀ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ\n"
            f"ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ: `{total_users}`\n"
            f"ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ: `{premium_users}` ({premium_percentage:.1f}%)\n"
            f"ꜰʀᴇᴇ ᴜꜱᴇʀꜱ: `{free_users}`\n"
            f"ᴀᴄᴛɪᴠᴇ ᴛᴏᴅᴀʏ: `{active_today}` ({activity_rate:.1f}%)\n\n"
            f"💰 ᴄʀᴇᴅɪᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ\n"
            f"ᴛᴏᴛᴀʟ ᴄʀᴇᴅɪᴛꜱ ɪɴ ᴘᴏᴏʟ: `{total_credits}`\n"
            f"ᴀᴠᴇʀᴀɢᴇ ᴘᴇʀ ᴜꜱᴇʀ: `{total_credits // total_users if total_users > 0 else 0}`\n"
            f"ᴛᴏᴘ ᴜꜱᴇʀ ᴄʀᴇᴅɪᴛꜱ: `{top_user_credits}`\n\n"
            f"⚡ ᴄᴏᴍᴍᴀɴᴅ ᴜꜱᴀɢᴇ\n"
            f"ᴛᴏᴛᴀʟ ᴄʜᴇᴄᴋꜱ: `{total_checks}`\n"
            f"ᴛᴏᴛᴀʟ ᴠʙᴠ: `{total_vbv}`\n"
            f"ᴛᴏᴛᴀʟ ᴍᴀꜱꜱ: `{total_mass}`\n"
            f"ᴛᴏᴛᴀʟ ʙɪɴꜱ: `{total_bins}`\n"
            f"ᴛᴏᴛᴀʟ ɢᴇɴꜱ: `{total_gens}`\n"
            f"ᴛᴏᴛᴀʟ ꜰᴀᴋᴇ: `{total_fake}`\n\n"
            f"🤖 ʙᴏᴛ ꜱᴛᴀᴛᴜꜱ\n"
            f"ᴜᴘᴛɪᴍᴇ: `{uptime_days}ᴅ {uptime_hours % 24}ʜ`\n"
            f"ꜱᴛᴀᴛᴜꜱ: 🟢 ᴏɴʟɪɴᴇ\n"
            f"ʟᴀꜱᴛ ᴜᴘᴅᴀᴛᴇ: {now}\n\n"
            f"👨‍💻 ᴀᴅᴍɪɴ: @SIDIKI_MUSTAFA_92\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        
        await loading_msg.edit_text(to_small_caps(msg), parse_mode="HTML")
        
    except Exception as e:
        error_msg = (
            "★━━ ᴀɴᴀʟʏᴛɪᴄꜱ ᴇʀʀᴏʀ ━━★\n"
            "❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ʟᴏᴀᴅ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ\n"
            f"ᴇʀʀᴏʀ: {str(e)[:50]}...\n"
            "ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ꜰᴏʀ ꜱᴜᴘᴘᴏʀᴛ\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        await loading_msg.edit_text(to_small_caps(error_msg), parse_mode="HTML")

# Enhanced version with more detailed analytics
async def cmd_analytics_detailed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed analytics with charts and trends"""
    user_id = update.effective_user.id
    
    if not is_premium(user_id):
        return await send_premium_denied(update)
    
    # Check if user wants specific analytics
    if context.args and context.args[0].lower() in ["users", "commands", "credits", "activity"]:
        category = context.args[0].lower()
        
        if category == "users":
            await cmd_analytics_users(update, context)
        elif category == "commands":
            await cmd_analytics_commands(update, context)
        elif category == "credits":
            await cmd_analytics_credits(update, context)
        elif category == "activity":
            await cmd_analytics_activity(update, context)
        return
    
    # Show analytics menu
    menu_msg = (
        "★━━ ᴀɴᴀʟʏᴛɪᴄꜱ ᴍᴇɴᴜ ━━★\n\n"
        "ᴄᴏᴍᴍᴀɴᴅꜱ:\n"
        "• .analytics - ɢᴇɴᴇʀᴀʟ ᴏᴠᴇʀᴠɪᴇᴡ\n"
        "• .analytics users - ᴜꜱᴇʀ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ\n"
        "• .analytics commands - ᴄᴏᴍᴍᴀɴᴅ ᴜꜱᴀɢᴇ\n"
        "• .analytics credits - ᴄʀᴇᴅɪᴛ ᴀɴᴀʟʏꜱɪꜱ\n"
        "• .analytics activity - ᴀᴄᴛɪᴠɪᴛʏ ᴛʀᴇɴᴅꜱ\n\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await update.message.reply_text(to_small_caps(menu_msg), parse_mode="HTML")

# Add tracking functions to increment stats in your commands
def track_command_usage(command_name):
    """Track command usage for analytics"""
    if 'stats_store' in globals():
        key = f"total_{command_name}"
        stats_store[key] = stats_store.get(key, 0) + 1
        stats_store.save()

#Git
GITHUB_PROXY_URL = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/main/http.txt"
# Use in-memory storage per user for "current" proxy index
user_proxy_index = {}

async def fetch_proxies():
    async with aiohttp.ClientSession() as session:
        async with session.get(GITHUB_PROXY_URL) as resp:
            text = await resp.text()
            proxies = [line.strip() for line in text.splitlines() if ':' in line]
            return proxies

async def check_proxy_status(proxy):
    try:
        ip, port = proxy.split(":")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://httpbin.org/ip",
                proxy=f"http://{proxy}",
                timeout=5
            ) as resp:
                if resp.status == 200:
                    return "🟢 ᴏɴʟɪɴᴇ"
    except Exception:
        pass
    return "🔴 ᴏꜰꜰʟɪɴᴇ"

# Global proxy storage
user_proxy_index = {}
cached_proxies = []
last_proxy_fetch = 0

async def fetch_proxies():
    """Fetch fresh proxy list from multiple sources"""
    global cached_proxies, last_proxy_fetch
    
    # Cache proxies for 10 minutes
    if time.time() - last_proxy_fetch < 600 and cached_proxies:
        return cached_proxies
    
    proxies = []
    
    # Multiple free proxy APIs
    proxy_apis = [
        "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"
    ]
    
    for api_url in proxy_apis:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=10) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # Parse different formats
                        for line in text.strip().split('\n'):
                            line = line.strip()
                            if ':' in line and len(line.split(':')) == 2:
                                ip, port = line.split(':')
                                if ip and port.isdigit():
                                    proxies.append(f"{ip}:{port}")
                        
                        if proxies:
                            break  # Got proxies, no need to try other APIs
        except Exception as e:
            print(f"Proxy API {api_url} failed: {e}")
            continue
    
    # Fallback hardcoded proxies if APIs fail
    if not proxies:
        proxies = [
            "8.210.83.33:80",
            "47.74.152.29:8888",
            "103.127.1.130:80",
            "185.162.231.106:80",
            "103.216.103.26:80"
        ]
    
    cached_proxies = proxies[:50]  # Limit to 50 proxies
    last_proxy_fetch = time.time()
    return cached_proxies

async def check_proxy_status(proxy):
    """Check if proxy is working"""
    try:
        proxy_url = f"http://{proxy}"
        connector = aiohttp.ProxyConnector.from_url(proxy_url)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get("http://httpbin.org/ip", timeout=5) as resp:
                if resp.status == 200:
                    return "🟢 ᴀᴄᴛɪᴠᴇ"
                else:
                    return "🔴 ɪɴᴀᴄᴛɪᴠᴇ"
    except Exception:
        return "🔴 ɪɴᴀᴄᴛɪᴠᴇ"

async def cmd_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Proxy management command"""
    user_id = update.effective_user.id
    
    if not is_premium(user_id):
        return await send_premium_denied(update)
    
    # Show usage if no args
    if not context.args:
        usage_msg = (
            "★━━ ᴘʀᴏxʏ ᴍᴀɴᴀɢᴇʀ ━━★\n\n"
            "ᴄᴏᴍᴍᴀɴᴅꜱ:\n"
            "• .proxy get - ɢᴇᴛ ʀᴀɴᴅᴏᴍ ᴘʀᴏxʏ\n"
            "• .proxy list - ꜱʜᴏᴡ ᴀᴠᴀɪʟᴀʙʟᴇ ᴘʀᴏxɪᴇꜱ\n"
            "• .proxy check [ip:port] - ᴄʜᴇᴄᴋ ᴘʀᴏxʏ ꜱᴛᴀᴛᴜꜱ\n"
            "• .proxy rotate - ɢᴇᴛ ɴᴇxᴛ ᴘʀᴏxʏ\n"
            "• .proxy refresh - ʀᴇꜰʀᴇꜱʜ ᴘʀᴏxʏ ʟɪꜱᴛ\n\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        return await update.message.reply_text(to_small_caps(usage_msg), parse_mode="HTML")
    
    action = context.args[0].lower()
    
    if action == "get":
        await cmd_proxy_get(update, context)
    elif action == "list":
        await cmd_proxy_list(update, context)
    elif action == "check":
        await cmd_proxy_check(update, context)
    elif action == "rotate":
        await cmd_proxy_rotate(update, context)
    elif action == "refresh":
        await cmd_proxy_refresh(update, context)
    else:
        await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ᴀᴄᴛɪᴏɴ. ᴜꜱᴇ .proxy ꜰᴏʀ ʜᴇʟᴘ"),
            parse_mode="HTML"
        )

async def cmd_proxy_get(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get random proxy"""
    loading_msg = await update.message.reply_text(
        to_small_caps("🔍 ꜰᴇᴛᴄʜɪɴɢ ʀᴀɴᴅᴏᴍ ᴘʀᴏxʏ..."),
        parse_mode="HTML"
    )
    
    proxies = await fetch_proxies()
    
    if not proxies:
        return await loading_msg.edit_text(
            to_small_caps("❌ ɴᴏ ᴘʀᴏxɪᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ!"),
            parse_mode="HTML"
        )
    
    proxy = random.choice(proxies)
    status = await check_proxy_status(proxy)
    
    msg = (
        "★━━ ʀᴀɴᴅᴏᴍ ᴘʀᴏxʏ ━━★\n"
        f"ᴘʀᴏxʏ:\n`{proxy}`\n\n"
        f"ꜱᴛᴀᴛᴜꜱ: {status}\n"
        f"ᴛʏᴘᴇ: HTTP\n"
        f"ᴀɴᴏɴʏᴍɪᴛʏ: ʜɪɢʜ\n\n"
        "ᴜꜱᴀɢᴇ ᴇxᴀᴍᴘʟᴇ:\n"
        f"`http://{proxy}`\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await loading_msg.edit_text(to_small_caps(msg), parse_mode="HTML")

async def cmd_proxy_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available proxies"""
    loading_msg = await update.message.reply_text(
        to_small_caps("📋 ʟᴏᴀᴅɪɴɢ ᴘʀᴏxʏ ʟɪꜱᴛ..."),
        parse_mode="HTML"
    )
    
    proxies = await fetch_proxies()
    
    if not proxies:
        return await loading_msg.edit_text(
            to_small_caps("❌ ɴᴏ ᴘʀᴏxɪᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ!"),
            parse_mode="HTML"
        )
    
    # Show first 10 proxies
    proxy_list = []
    for i, proxy in enumerate(proxies[:10], 1):
        proxy_list.append(f"{i}. `{proxy}`")
    
    msg = (
        "★━━ ᴀᴠᴀɪʟᴀʙʟᴇ ᴘʀᴏxɪᴇꜱ ━━★\n\n"
        f"{chr(10).join(proxy_list)}\n\n"
        f"ᴛᴏᴛᴀʟ: {len(proxies)} ᴘʀᴏxɪᴇꜱ\n"
        f"ꜱʜᴏᴡɪɴɢ: ꜰɪʀꜱᴛ 10\n\n"
        "💡 ᴜꜱᴇ .proxy get ꜰᴏʀ ʀᴀɴᴅᴏᴍ ᴘʀᴏxʏ\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await loading_msg.edit_text(to_small_caps(msg), parse_mode="HTML")

async def cmd_proxy_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check specific proxy status"""
    if len(context.args) < 2:
        return await update.message.reply_text(
            to_small_caps("❌ ᴜꜱᴀɢᴇ: .proxy check ip:port"),
            parse_mode="HTML"
        )
    
    proxy = context.args[1]
    
    if ':' not in proxy:
        return await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ. ᴜꜱᴇ ip:port"),
            parse_mode="HTML"
        )
    
    loading_msg = await update.message.reply_text(
        to_small_caps(f"🔍 ᴄʜᴇᴄᴋɪɴɢ {proxy}..."),
        parse_mode="HTML"
    )
    
    status = await check_proxy_status(proxy)
    
    msg = (
        "★━━ ᴘʀᴏxʏ ꜱᴛᴀᴛᴜꜱ ━━★\n"
        f"ᴘʀᴏxʏ:\n`{proxy}`\n\n"
        f"ꜱᴛᴀᴛᴜꜱ: {status}\n"
        f"ᴄʜᴇᴄᴋᴇᴅ: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%I:%M:%S %p')}\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await loading_msg.edit_text(to_small_caps(msg), parse_mode="HTML")

async def cmd_proxy_rotate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rotate to next proxy"""
    user_id = update.effective_user.id
    
    loading_msg = await update.message.reply_text(
        to_small_caps("🔄 ʀᴏᴛᴀᴛɪɴɢ ᴘʀᴏxʏ..."),
        parse_mode="HTML"
    )
    
    proxies = await fetch_proxies()
    
    if not proxies:
        return await loading_msg.edit_text(
            to_small_caps("❌ ɴᴏ ᴘʀᴏxɪᴇꜱ ꜰᴏᴜɴᴅ!"),
            parse_mode="HTML"
        )
    
    # Get next proxy in rotation
    idx = user_proxy_index.get(user_id, 0) + 1
    idx = idx % len(proxies)
    user_proxy_index[user_id] = idx
    
    proxy = proxies[idx]
    status = await check_proxy_status(proxy)
    
    msg = (
        "★━━ ᴘʀᴏxʏ ʀᴏᴛᴀᴛᴇᴅ ━━★\n"
        f"ɴᴇxᴛ ᴘʀᴏxʏ:\n`{proxy}`\n\n"
        f"ꜱᴛᴀᴛᴜꜱ: {status}\n"
        f"ɪɴᴅᴇx: {idx + 1}/{len(proxies)}\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await loading_msg.edit_text(to_small_caps(msg), parse_mode="HTML")

async def cmd_proxy_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh proxy list"""
    global cached_proxies, last_proxy_fetch
    
    loading_msg = await update.message.reply_text(
        to_small_caps("🔄 ʀᴇꜰʀᴇꜱʜɪɴɢ ᴘʀᴏxʏ ʟɪꜱᴛ..."),
        parse_mode="HTML"
    )
    
    # Force refresh by clearing cache
    cached_proxies = []
    last_proxy_fetch = 0
    
    proxies = await fetch_proxies()
    
    if not proxies:
        return await loading_msg.edit_text(
            to_small_caps("❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ʀᴇꜰʀᴇꜱʜ ᴘʀᴏxɪᴇꜱ!"),
            parse_mode="HTML"
        )
    
    msg = (
        "★━━ ᴘʀᴏxʏ ʀᴇꜰʀᴇꜱʜᴇᴅ ━━★\n"
        f"ɴᴇᴡ ᴘʀᴏxɪᴇꜱ ʟᴏᴀᴅᴇᴅ: {len(proxies)}\n"
        f"ʟᴀꜱᴛ ᴜᴘᴅᴀᴛᴇ: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%I:%M:%S %p')}\n\n"
        "💡 ᴜꜱᴇ .proxy get ꜰᴏʀ ɴᴇᴡ ᴘʀᴏxʏ\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await loading_msg.edit_text(to_small_caps(msg), parse_mode="HTML")


ADMIN_ID = 8179218740  # update as needed

async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return await update.message.reply_text(
            to_small_caps("❌ ᴏɴʟʏ ᴀᴅᴍɪɴ ᴄᴀɴ ᴇxᴘᴏʀᴛ ᴅᴀᴛᴀ!"),
            parse_mode="HTML"
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Username", "Role", "Credits", "Join Date"])

    # Iterate your user_store correctly (class-based)
    for uid, data in user_store.data.items():
        writer.writerow([
            uid,
            data.get("username", ""),
            data.get("role", "free"),
            data.get("credits", 0),
            data.get("joined", "")
        ])

    output.seek(0)
    csv_bytes = io.BytesIO(output.read().encode("utf-8"))

    await update.message.reply_document(
        document=csv_bytes,
        filename="user_export.csv",
        caption=to_small_caps(
            "★━━ ᴇxᴘᴏʀᴛ ꜱᴜᴄᴄᴇꜱꜱ ━━★\n"
            "ʏᴏᴜʀ ᴅᴀᴛᴀ ɪꜱ ʀᴇᴀᴅʏ!\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        ),
        parse_mode="HTML"
    )

import json
import os

# Admin management system
class AdminStore:
    def __init__(self):
        self.data = self.load()
    
    def load(self):
        try:
            with open("admins.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            # Default admins - replace with your actual admin ID
            return {
                "super_admin": 8179218740,  # Primary owner (your current ADMIN_ID)
                "admins": [8179218740]       # List of all admins
            }
    
    def save(self):
        with open("admins.json", "w") as f:
            json.dump(self.data, f, indent=2)
    
    def is_admin(self, user_id):
        return user_id in self.data["admins"]
    
    def is_super_admin(self, user_id):
        return user_id == self.data["super_admin"]
    
    def add_admin(self, user_id):
        if user_id not in self.data["admins"]:
            self.data["admins"].append(user_id)
            self.save()
            return True
        return False
    
    def remove_admin(self, user_id):
        if user_id in self.data["admins"] and user_id != self.data["super_admin"]:
            self.data["admins"].remove(user_id)
            self.save()
            return True
        return False

# Initialize admin store
admin_store = AdminStore()

# Admin management commands
async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new admin - Super admin only"""
    user_id = update.effective_user.id
    
    if not admin_store.is_super_admin(user_id):
        return await update.message.reply_text(
            to_small_caps("❌ ᴏɴʟʏ ꜱᴜᴘᴇʀ ᴀᴅᴍɪɴ ᴄᴀɴ ᴀᴅᴅ ᴀᴅᴍɪɴꜱ!"),
            parse_mode="HTML"
        )
    
    if not context.args:
        return await update.message.reply_text(
            to_small_caps("❌ ᴜꜱᴀɢᴇ: .addadmin [user_id]"),
            parse_mode="HTML"
        )
    
    try:
        new_admin_id = int(context.args[0])
    except ValueError:
        return await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ᴜꜱᴇʀ ɪᴅ!"),
            parse_mode="HTML"
        )
    
    # Check if user exists in bot database
    target_data = user_store.get(new_admin_id)
    if not target_data:
        return await update.message.reply_text(
            to_small_caps("❌ ᴜꜱᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ʙᴏᴛ ᴅᴀᴛᴀʙᴀꜱᴇ!"),
            parse_mode="HTML"
        )
    
    if admin_store.add_admin(new_admin_id):
        # Get user info for display
        target_username = target_data.get("username", "Unknown")
        
        msg = (
            "★━━ ᴀᴅᴍɪɴ ᴀᴅᴅᴇᴅ ━━★\n"
            f"✅ ᴜꜱᴇʀ `{new_admin_id}` ɪꜱ ɴᴏᴡ ᴀɴ ᴀᴅᴍɪɴ\n"
            f"ᴜꜱᴇʀɴᴀᴍᴇ: @{target_username}\n"
            f"ᴛᴏᴛᴀʟ ᴀᴅᴍɪɴꜱ: {len(admin_store.data['admins'])}\n"
            f"ᴀᴅᴅᴇᴅ ʙʏ: {get_user_display_name(update.effective_user)}\n"
            f"ᴛɪᴍᴇ: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%I:%M:%S %p IST')}\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
    else:
        msg = (
            "★━━ ᴀᴅᴍɪɴ ꜱᴛᴀᴛᴜꜱ ━━★\n"
            f"ℹ️ ᴜꜱᴇʀ `{new_admin_id}` ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀɴ ᴀᴅᴍɪɴ\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
    
    await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")

async def cmd_removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove admin - Super admin only"""
    user_id = update.effective_user.id
    
    if not admin_store.is_super_admin(user_id):
        return await update.message.reply_text(
            to_small_caps("❌ ᴏɴʟʏ ꜱᴜᴘᴇʀ ᴀᴅᴍɪɴ ᴄᴀɴ ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴꜱ!"),
            parse_mode="HTML"
        )
    
    if not context.args:
        return await update.message.reply_text(
            to_small_caps("❌ ᴜꜱᴀɢᴇ: .removeadmin [user_id]"),
            parse_mode="HTML"
        )
    
    try:
        remove_admin_id = int(context.args[0])
    except ValueError:
        return await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ᴜꜱᴇʀ ɪᴅ!"),
            parse_mode="HTML"
        )
    
    if admin_store.remove_admin(remove_admin_id):
        msg = (
            "★━━ ᴀᴅᴍɪɴ ʀᴇᴍᴏᴠᴇᴅ ━━★\n"
            f"✅ ᴜꜱᴇʀ `{remove_admin_id}` ɪꜱ ɴᴏ ʟᴏɴɢᴇʀ ᴀɴ ᴀᴅᴍɪɴ\n"
            f"ᴛᴏᴛᴀʟ ᴀᴅᴍɪɴꜱ: {len(admin_store.data['admins'])}\n"
            f"ʀᴇᴍᴏᴠᴇᴅ ʙʏ: {get_user_display_name(update.effective_user)}\n"
            f"ᴛɪᴍᴇ: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%I:%M:%S %p IST')}\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
    else:
        msg = (
            "★━━ ᴇʀʀᴏʀ ━━★\n"
            f"❌ ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ᴜꜱᴇʀ `{remove_admin_id}`\n"
            "ʀᴇᴀꜱᴏɴ: ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ᴏʀ ɪꜱ ꜱᴜᴘᴇʀ ᴀᴅᴍɪɴ\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
    
    await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")

async def cmd_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all admins - Admin only"""
    user_id = update.effective_user.id
    
    if not admin_store.is_admin(user_id):
        return await update.message.reply_text(
            to_small_caps("❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴠɪᴇᴡ ᴀᴅᴍɪɴ ʟɪꜱᴛ!"),
            parse_mode="HTML"
        )
    
    admin_list = []
    for admin_id in admin_store.data["admins"]:
        # Get admin info from user store
        admin_data = user_store.get(admin_id)
        username = admin_data.get("username", "Unknown") if admin_data else "Unknown"
        
        if admin_id == admin_store.data["super_admin"]:
            admin_list.append(f"👑 `{admin_id}` (@{username}) - ꜱᴜᴘᴇʀ ᴀᴅᴍɪɴ")
        else:
            admin_list.append(f"⚡ `{admin_id}` (@{username}) - ᴀᴅᴍɪɴ")
    
    msg = (
        "★━━ ᴀᴅᴍɪɴ ʟɪꜱᴛ ━━★\n\n"
        f"{chr(10).join(admin_list)}\n\n"
        f"ᴛᴏᴛᴀʟ ᴀᴅᴍɪɴꜱ: {len(admin_store.data['admins'])}\n"
        f"ʀᴇQᴜᴇꜱᴛᴇᴅ ʙʏ: {get_user_display_name(update.effective_user)}\n"
        f"ᴛɪᴍᴇ: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%I:%M:%S %p IST')}\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")

async def cmd_adminhelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin help command"""
    user_id = update.effective_user.id
    
    if not admin_store.is_admin(user_id):
        return await update.message.reply_text(
            to_small_caps("❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴠɪᴇᴡ ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅꜱ!"),
            parse_mode="HTML"
        )
    
    is_super = admin_store.is_super_admin(user_id)
    
    msg = (
        "★━━ ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅꜱ ━━★\n\n"
        "ᴀʟʟ ᴀᴅᴍɪɴꜱ:\n"
        "• .genkey [role] [credits] [count]\n"
        "• .export - ᴇxᴘᴏʀᴛ ᴜꜱᴇʀ ᴅᴀᴛᴀ\n"
        "• .listadmins - ᴠɪᴇᴡ ᴀʟʟ ᴀᴅᴍɪɴꜱ\n"
        "• .adminhelp - ᴛʜɪꜱ ʜᴇʟᴘ\n\n"
    )
    
    if is_super:
        msg += (
            "ꜱᴜᴘᴇʀ ᴀᴅᴍɪɴ ᴏɴʟʏ:\n"
            "• .addadmin [user_id] - ᴀᴅᴅ ᴀᴅᴍɪɴ\n"
            "• .removeadmin [user_id] - ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴ\n\n"
        )
    
    msg += (
        f"ʏᴏᴜʀ ʀᴏʟᴇ: {'👑 ꜱᴜᴘᴇʀ ᴀᴅᴍɪɴ' if is_super else '⚡ ᴀᴅᴍɪɴ'}\n"
        "★━━━━━━━━━━━━━━━━━━━━━━━━★"
    )
    
    await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")

# Update all admin-only commands to use the new system
async def cmd_genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate premium keys command - Admin only"""
    user_id = update.effective_user.id
    
    # Change from: if user_id != ADMIN_ID:
    if not admin_store.is_admin(user_id):
        return await update.message.reply_text(
            to_small_caps("❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ɢᴇɴᴇʀᴀᴛᴇ ᴋᴇʏꜱ!"),
            parse_mode="HTML"
        )
    
    # Rest of your existing genkey code...
    if not context.args or len(context.args) < 3:
        usage_msg = (
            "★━━ ᴋᴇʏ ɢᴇɴᴇʀᴀᴛᴏʀ ━━★\n\n"
            "ᴜꜱᴀɢᴇ: .genkey [role] [credits] [count]\n\n"
            "ᴇxᴀᴍᴘʟᴇꜱ:\n"
            "• .genkey premium 100 5\n"
            "• .genkey free 25 10\n\n"
            "ʀᴏʟᴇꜱ: free, premium\n"
            "ᴍᴀx ᴄᴏᴜɴᴛ: 20 ᴋᴇʏꜱ\n"
            "★━━━━━━━━━━━━━━━━━━━━━━━━★"
        )
        return await update.message.reply_text(to_small_caps(usage_msg), parse_mode="HTML")
    
    # Continue with your existing genkey logic...
    try:
        role = context.args[0].lower()
        credits = int(context.args[1])
        count = int(context.args[2])
    except ValueError:
        return await update.message.reply_text(
            to_small_caps("❌ ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ꜰᴏʀᴍᴀᴛ"),
            parse_mode="HTML"
        )
    
    # Validation and key generation (your existing code)...
    if role not in ["free", "premium"]:
        return await update.message.reply_text(
            to_small_caps("❌ ʀᴏʟᴇ ᴍᴜꜱᴛ ʙᴇ 'free' ᴏʀ 'premium'"),
            parse_mode="HTML"
        )
    
    if credits < 0 or credits > 10000:
        return await update.message.reply_text(
            to_small_caps("❌ ᴄʀᴇᴅɪᴛꜱ ᴍᴜꜱᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 0-10000"),
            parse_mode="HTML"
        )
    
    if count < 1 or count > 20:
        return await update.message.reply_text(
            to_small_caps("❌ ᴄᴏᴜɴᴛ ᴍᴜꜱᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 1-20"),
            parse_mode="HTML"
        )
    
    # Loading animation
    loading_msg = await update.message.reply_text(
        to_small_caps("⏳ ɢᴇɴᴇʀᴀᴛɪɴɢ ᴋᴇʏꜱ..."),
        parse_mode="HTML"
    )
    
    await asyncio.sleep(1)
    
    # Generate keys
    generated_keys = []
    for _ in range(count):
        # Generate 12-character key: ABC123DEF456
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        
        # Store in premium_keys database
        premium_keys[key] = {
            "role": role,
            "credits": credits,
            "used": False,
            "created": datetime.now(pytz.timezone("Asia/Kolkata")).isoformat(),
            "created_by": user_id
        }
        
        # Also store in PROMO_DB for compatibility
        PROMO_DB[key] = {
            "role": role,
            "credits": credits,
            "used": False
        }
        
        generated_keys.append(key)
    
    # Save to files
    save_keys(premium_keys)
    save_promos(PROMO_DB)
    
    # Format response - each key as .redeem KEY in code block, with a blank line between
    key_list = "\n\n".join([f"<code>.redeem {key}</code>" for key in generated_keys])

    msg = (
        f"{to_small_caps('★━━ ᴋᴇʏꜱ ɢᴇɴᴇʀᴀᴛᴇᴅ ━━★')}\n\n"
        f"{to_small_caps('ʀᴏʟᴇ:')} {role.upper()}\n"
        f"{to_small_caps('ᴄʀᴇᴅɪᴛꜱ:')} {credits}\n"
        f"{to_small_caps('ᴄᴏᴜɴᴛ:')} {count}\n\n"
        f"{to_small_caps('ɢᴇɴᴇʀᴀᴛᴇᴅ ᴋᴇʏꜱ:')}\n\n"
        f"{key_list}\n\n"
        f"{to_small_caps('💡 ᴜꜱᴇʀꜱ ᴄᴀɴ ʀᴇᴅᴇᴇᴍ ᴡɪᴛʜ:')} .redeem KEY\n"
    f"{to_small_caps('★━━━━━━━━━━━━━━━━━━━━━━━━★')}"
    )

    await loading_msg.edit_text(msg, parse_mode="HTML")
 
@require_premium
async def cmd_mchk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Extract cards from reply or args (handle both line and space separated)
    if update.message.reply_to_message:
        input_text = update.message.reply_to_message.text
    else:
        input_text = " ".join(context.args)
    # Accept both line-separated and space-separated cards
    cards = []
    for line in input_text.replace(",", " ").splitlines():
        for c in line.strip().split():
            if "|" in c:
                cards.append(c.strip())
    MAX_MCHK_CARDS = 40
    total = len(cards)
    if total == 0:
        return await update.message.reply_text(
            to_small_caps("❌ ᴜꜱᴀɢᴇ: .mchk 4111|01|23|123 ..."),
            parse_mode="HTML"
        )
    if total > MAX_MCHK_CARDS:
        return await update.message.reply_text(
            to_small_caps(f"❌ ᴍᴀx {MAX_MCHK_CARDS} ᴄᴀʀᴅꜱ ᴀʟʟᴏᴡᴇᴅ ᴘᴇʀ .mchk!"),
            parse_mode="HTML"
        )
    user_id = update.effective_user.id
    if get_credits(user_id) < total:
        return await update.message.reply_text(
            to_small_caps(f"❌ ɴᴇᴇᴅ {total} ᴄʀᴇᴅɪᴛꜱ ꜰᴏʀ {total} ᴄᴀʀᴅꜱ!"),
            parse_mode="HTML"
        )
    user = get_user_display_name(update.effective_user)
    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%I:%M:%S %p IST")
    header = to_small_caps("★━━ ᴍᴀꜱꜱ ᴄʜᴇᴄᴋ ʀᴇꜱᴜʟᴛꜱ ━━★") + "\n"
    footer = to_small_caps("★━━━━━━━━━━━━━━━━━━━━━━━━★")
    results = [header]
    # Animated loading frames
    MCHK_LOADING_FRAMES = [
        to_small_caps(f"🔄 Checking {total} cards..."),
        to_small_caps("⏳ Processing batch..."),
        to_small_caps("🔍 Validating info..."),
        to_small_caps("✨ Finalizing results...")
    ]
    anim_msg = await update.message.reply_text(MCHK_LOADING_FRAMES[0], parse_mode="HTML")
    for txt in MCHK_LOADING_FRAMES[1:]:
        await asyncio.sleep(1)
        await anim_msg.edit_text(txt, parse_mode="HTML")
    await asyncio.sleep(0.5)
    import hashlib
    for idx, card in enumerate(cards, 1):
        number = card.split("|")[0].replace(" ", "")
        extra = "|".join(card.split("|")[1:])
        bin_code = number[:6]
        # Try to get BIN info, or fallback to "unknown"
        try:
            brand, issuer, country = await get_bin_details(bin_code)
            brand = brand or "unknown"
            issuer = issuer or "unknown"
            country = country or "unknown"
        except Exception:
            brand = issuer = country = "unknown"
        # DEAD CARD CHECK
        if number in KILLED_CARDS:
            killer = KILLED_CARDS[number]
            results.append(
                f"[{idx}]\n"
                f"☠️ {number}|{extra}\n"
                f"    ├─ {to_small_caps('ꜱᴛᴀᴛᴜꜱ')}: {to_small_caps('ᴅᴇᴀᴅ')}\n"
                f"    ├─ {to_small_caps('ʀᴇᴀꜱᴏɴ')}: {to_small_caps('ᴄᴀʀᴅ ᴋɪʟʟᴇᴅ ʙʏ')} @{killer}\n"
                f"    └─ {to_small_caps('ʀᴇꜱᴘᴏɴꜱᴇ')}: {to_small_caps('ᴛʜɪꜱ ᴄᴀʀᴅ ɪꜱ ᴅᴇᴀᴅ.')}\n"
            )
            await anim_msg.edit_text("\n".join(results), parse_mode="HTML")
            await asyncio.sleep(2)
            continue
        # Deterministic approval logic
        hash_val = int(hashlib.md5(number.encode()).hexdigest(), 16)
        approved = (hash_val % 100) < 30  # 30% pass rate
        icon = "✅" if approved else "❌"
        results.append(
            f"[{idx}]\n"
            f"{icon} {number}|{extra}\n"
            f"    ├─ {to_small_caps('ᴛʏᴘᴇ')}: {to_small_caps(brand)}\n"
            f"    ├─ {to_small_caps('ʙʀᴀɴᴅ')}: {to_small_caps(brand)}\n"
            f"    ├─ {to_small_caps('ɪꜱꜱᴜᴇʀ')}: {to_small_caps(issuer)}\n"
            f"    └─ {to_small_caps('ᴄᴏᴜɴᴛʀʏ')}: {to_small_caps(country)}\n"
        )
        await anim_msg.edit_text("\n".join(results), parse_mode="HTML")
        await asyncio.sleep(2)
    # Footer
    results.append(f"\nʀᴇǫ ʙʏ: {user}\nᴛɪᴍᴇ: {now}\n{footer}")
    await anim_msg.edit_text("\n".join(results), parse_mode="HTML")
    change_credits(user_id, -total)

@require_premium
async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or "|" not in context.args[0]:
        return await update.message.reply_text(
            "✧ ᴄᴀʀᴅ ᴋɪʟʟᴇʀ ✧\n\n"
            "⟣ ᴜꜱᴀɢᴇ : .kill 4111111111111111|12|28|123",
            parse_mode="HTML"
        )
    start_time = time.time()
    card = context.args[0].strip()
    number = card.split("|")[0].replace(" ", "")
    bin_code = number[:6]

    # BIN lookup (reuse your get_bin_details)
    try:
        brand, issuer, country = await get_bin_details(bin_code)
    except Exception:
        brand, issuer, country = "unknown", "unknown", "unknown"

    # Terminal Hacker Style Animation
    KILL_LOADING_FRAMES = [
        "⌲ ᴇɴᴛᴇʀɪɴɢ ᴅᴀʀᴋɴᴇᴛ...",
        "⌲ ʜᴀᴄᴋɪɴɢ ɢᴀᴛᴇᴡᴀʏ...",
        "⌲ ᴇxᴇᴄᴜᴛɪɴɢ ᴋɪʟʟ ꜱᴄʀɪᴘᴛ...",
        "⌲ ᴄᴏɴꜰɪʀᴍɪɴɢ ᴋɪʟʟ...",
        "⌲ 🔪 ᴄᴀʀᴅ ᴋɪʟʟɪɴɢ..."
    ]
    loading_msg = await update.message.reply_text(KILL_LOADING_FRAMES[0])
    for frame in KILL_LOADING_FRAMES[1:]:
        await asyncio.sleep(1.7)
        await loading_msg.edit_text(frame)

    # Simulate total delay between 30 and 40 seconds (including animation time)
    delay_to_kill = random.uniform(30, 40)
    anim_time = len(KILL_LOADING_FRAMES) * 1.7
    remaining_delay = max(0, delay_to_kill - anim_time)
    await asyncio.sleep(remaining_delay)

    # Save killer's username or display name
    username = f"@{update.effective_user.username}" if update.effective_user.username else get_user_display_name(update.effective_user)
    KILLED_CARDS[number] = username
    save_killed_cards()

    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M:%S %p IST")
    total_delay = time.time() - start_time

    box = (
        "✧ ᴄᴀʀᴅ ᴋɪʟʟᴇʀ ✧\n\n"
        f"⟣ ᴄᴀʀᴅ : <code>{number}</code>\n"
        f"⟣ ʙɪɴ : <code>{bin_code}</code>\n"
        f"⟣ ʙʀᴀɴᴅ : {brand}\n"
        f"⟣ ɪssᴜᴇʀ : {issuer}\n"
        f"⟣ ᴄᴏᴜɴᴛʀʏ : {country}\n"
        f"⟣ sᴛᴀᴛᴜs : ᴋɪʟʟᴇᴅ ☠️\n"
        f"⟣ ʀᴇsᴘᴏɴsᴇ : sᴜᴄᴄᴇssғᴜʟʟʏ ᴋɪʟʟᴇᴅ\n"
        f"⟣ ᴅᴀᴛᴇ : {now}\n"
        f"⟣ ᴛɪᴍᴇ ᴛᴏ ᴋɪʟʟ : {total_delay:.2f}s\n\n"
        f"⌁ ᴋɪʟʟᴇᴅ ʙʏ : {username}\n"
        "━━━━━━━━━━━━━━━━"
    )
    await loading_msg.edit_text(box, parse_mode="HTML")
    
async def cmd_checkcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Check another user's credits by user ID."""
    ADMIN_ID = 8179218740  # replace with your Telegram user ID
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text(to_small_caps("❌ ᴀᴅᴍɪɴ ᴏɴʟʏ!"), parse_mode="HTML")
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text(to_small_caps("ᴜꜱᴀɢᴇ: .checkcredits USER_ID"), parse_mode="HTML")
    user_id = int(context.args[0])
    credits = get_credits(user_id)
    msg = f"ᴜꜱᴇʀ ɪᴅ: `{user_id}`\nᴄʀᴇᴅɪᴛꜱ: `{credits}`"
    await update.message.reply_text(to_small_caps(msg), parse_mode="HTML")
    
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text(to_small_caps("❌ ᴀᴅᴍɪɴ ᴏɴʟʏ!"), parse_mode="HTML")
    if not context.args:
        return await update.message.reply_text(to_small_caps("ᴜꜱᴀɢᴇ: .broadcast your message here"), parse_mode="HTML")
    msg = " ".join(context.args)
    users = user_store.data if hasattr(user_store, "data") else {}
    if not users:
        return await update.message.reply_text(to_small_caps("ɴᴏ ᴜꜱᴇʀꜱ ꜰᴏᴜɴᴅ."), parse_mode="HTML")

    sent, failed = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(uid, msg)
            sent += 1
            await asyncio.sleep(0.05)  # Avoid hitting rate limits
        except Exception:
            failed += 1
            continue
    summary = f"Broadcast finished!\nSent: {sent}\nFailed: {failed}"
    await update.message.reply_text(to_small_caps(summary), parse_mode="HTML")   

ADMIN_ID = 8179218740  # Replace with your Telegram user ID

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text(to_small_caps("❌ ᴀᴅᴍɪɴ ᴏɴʟʏ!"), parse_mode="HTML")

    users = user_store.data if hasattr(user_store, "data") else {}
    if not users:
        return await update.message.reply_text(to_small_caps("ɴᴏ ᴜꜱᴇʀꜱ ꜰᴏᴜɴᴅ."), parse_mode="HTML")

    msg_lines = [to_small_caps("★━━ ᴜꜱᴇʀ ʟɪꜱᴛ ━━★")]
    for uid, info in users.items():
        uname = info.get("username", "")
        name = info.get("name", "")
        credits = info.get("credits", 0)
        role = info.get("role", "free")
        msg_lines.append(f"• <code>{uid}</code> | {name} | {uname} | {role} | {credits} credits")
    msg = "\n".join(msg_lines)
    # Telegram limits message length, so send as file if too long
    if len(msg) > 4000:
        with open("user_list.txt", "w", encoding="utf-8") as f:
            f.write(msg)
        await update.message.reply_document("user_list.txt", caption=to_small_caps("ᴜꜱᴇʀ ʟɪꜱᴛ"))
    else:
        await update.message.reply_text(msg, parse_mode="HTML")
        

    
# --- Command router mapping ---
COMMANDS = {
    "chk": cmd_chk,
    "vbv": cmd_vbv,
    "mass": cmd_mass,
    "slf": cmd_slf,      # profile/info alias
    "daily": cmd_daily,
    "info": cmd_info,
    "plans": cmd_plans,    # you can split out if you want .plans details
    "help": cmd_help,
    "cr": cmd_cr,         # alias if needed
    "gen": cmd_gen,
    "bin": cmd_bin,       # stub, you can wire real .bin logic
    "genkey": cmd_genkey,
    "redeem": cmd_redeem,
    "fake": cmd_fake, 
    "addadmin": cmd_addadmin,
    "removeadmin": cmd_removeadmin,
    "listadmins": cmd_listadmins,
    "adminhelp": cmd_adminhelp,   # stub, you can wire real .fake logic
    "proxy rotate": cmd_proxy_rotate,
    "analytics": cmd_analytics, # stub, add analytics logic if needed
    "cr_bulk": cmd_cr_bulk,
    "proxy": cmd_proxy,     # stub, add proxy logic if needed
    "mchk": cmd_mchk,
    "kill": cmd_kill,
    "users": cmd_users,
    "broadcast": cmd_broadcast,
    "checkcredits": cmd_checkcredits,
    "export": cmd_export     # stub, add export logic if needed
}

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        to_small_caps("❌ ᴜɴᴋɴᴏᴡɴ ᴄᴏᴍᴍᴀɴᴅ.\nᴛʏᴘᴇ .ʜᴇʟᴘ ꜰᴏʀ ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅꜱ."),
        parse_mode="HTML"
    )

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    
    # Only process messages that start with "." (dot commands)
    if txt.startswith("."):
        cmd, *args = txt[1:].split(" ", 1)
        cmd = cmd.lower()
        context.args = args[0].split() if args else []
        
        handler = COMMANDS.get(cmd)
        if handler:
            await handler(update, context)
        else:
            # Only respond with unknown command for actual dot commands
            await unknown(update, context)
    # If message doesn't start with ".", do nothing (ignore regular chat)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        to_small_caps("❌ ᴜɴᴋɴᴏᴡɴ ᴄᴏᴍᴍᴀɴᴅ.\nᴛʏᴘᴇ .ʜᴇʟᴘ ꜰᴏʀ ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅꜱ."),
        parse_mode="HTML"
    )

def main():
    import logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    print_startup_box()
    application = Application.builder().token(BOT_TOKEN).build()

    # ONLY handle messages that start with "." (dot commands)
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^\."), handle_command))
    
    # Handle /start command specifically
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/start"), cmd_start))
    
    # REMOVE this line - it was causing all text to trigger unknown command:
    # application.add_handler(MessageHandler(filters.TEXT, unknown))

    application.run_polling()
    
if __name__ == "__main__":
    main()
    
n()
    
