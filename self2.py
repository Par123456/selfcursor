# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import logging
import datetime
import re
import json
import sqlite3
import time
from telethon import TelegramClient, events, utils
from telethon.tl.types import (
    User, Chat, Channel,
    MessageMediaPhoto, MessageMediaDocument,
    MessageEntityBold, MessageEntityItalic, MessageEntityUnderline,
    MessageEntityStrike, MessageEntityCode, MessageEntityPre,
    MessageEntityTextUrl, MessageEntityMentionName, MessageEntityUrl,
    MessageEntityEmail, MessageEntityPhoneNumber, MessageEntitySpoiler
)
from telethon.errors import (
    rpcbaseerrors,
    ChatAdminRequiredError,
    UserAdminInvalidError,
    MessageNotModifiedError,
    PhotoInvalidError,
    MessageIdInvalidError,
    FloodWaitError,
    AuthKeyUnregisteredError,
    SessionPasswordNeededError
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetMessagesRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest, GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.messages import DeleteHistoryRequest, EditMessageRequest, SendReactionRequest
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChannelBannedRights, ReactionEmpty, ReactionEmoji

# --- 1. Imports and Global Configuration ---

# Initialize logging for better debugging and error tracking
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# User needs to fill these. Get from my.telegram.org
# It's recommended to set these as environment variables for security.
API_ID = os.getenv('TG_API_ID', 'YOUR_API_ID_HERE')
API_HASH = os.getenv('TG_API_HASH', 'YOUR_API_HASH_HERE')

# Self-bot specific settings
SESSION_NAME = 'selfbot_session'
PREFIX = os.getenv('TG_PREFIX', '.')  # Command prefix. All self-bot commands will start with this.

# Data Storage - SQLite database for persistence
DB_NAME = 'selfbot_data.db'

# --- 2. Database Management ---

def init_db():
    """Initializes the SQLite database and creates necessary tables."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Table for general key-value settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Table for auto-reply rules
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auto_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_text TEXT NOT NULL,
            response_text TEXT,
            response_media_path TEXT,
            exact_match BOOLEAN NOT NULL,
            specific_peer_id INTEGER DEFAULT NULL, -- For auto-reply to specific users
            enabled BOOLEAN NOT NULL DEFAULT 1
        )
    ''')

    # Table for users/chats in the 'special list'
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS special_users (
            user_id INTEGER PRIMARY KEY,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table for custom/enabled fonts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_fonts (
            id INTEGER PRIMARY KEY, -- Using font ID as primary key
            font_name TEXT NOT NULL,
            font_map TEXT NOT NULL -- Storing the JSON representation of font mapping
        )
    ''')

    # Table for reaction targets (users/chats to react to)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reaction_targets (
            entity_id INTEGER PRIMARY KEY,
            enabled BOOLEEN NOT NULL DEFAULT 1
        )
    ''')

    # Table for reaction settings (e.g., the emoji to use)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reaction_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Table for shapeshifter profile backups
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shapeshifter_backup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT,
            bio TEXT,
            profile_photo_path TEXT,
            backup_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Initialize default settings if they don't exist
    for key, default_value in {
        'clock_in_name': '0', 'clock_in_bio': '0', 'bio_auto_text': '0',
        'custom_bio_text': '', 'auto_bold': '0', 'anti_login_on': '0',
        'hard_anti_login_on': '0', 'monshi_enabled': '0',
        'default_monshi_response': 'من در حال حاضر پاسخگو نیستم.',
        'reaction_on': '0', 'reaction_emoji': '👍',
        'view_edit_on': '0', 'view_del_on': '0', 'view_all_on': '0',
        'report_bot_id': '', 'spam_speed': '0.5'
    }.items():
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, default_value))

    conn.commit()
    conn.close()

def get_setting(key, default=None):
    """Retrieves a setting from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(key, value):
    """Stores a setting in the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

# --- 3. Utility Functions ---

async def get_user_id(client, peer_str):
    """
    Tries to resolve a peer_str (username, ID) to a Telethon entity and its ID.
    Returns (entity, id) or (None, None).
    """
    if isinstance(peer_str, (User, Chat, Channel)):
        return peer_str, utils.get_peer_id(peer_str)

    try:
        # Try to parse as integer ID
        entity_id = int(peer_str)
        entity = await client.get_entity(entity_id)
        return entity, utils.get_peer_id(entity)
    except (ValueError, rpcbaseerrors.rpcbase.RPCError):
        pass  # Not an integer ID or entity not found by ID

    try:
        # Try to resolve as username or channel/group invite link
        entity = await client.get_entity(peer_str)
        return entity, utils.get_peer_id(entity)
    except rpcbaseerrors.rpcbase.RPCError:
        return None, None

async def parse_entity_from_message(event, arg=None):
    """
    Parses an entity from a reply, a provided argument (ID/username), or the current chat.
    Returns (entity, entity_id).
    """
    target_entity = None
    target_id = None

    if event.is_reply:
        reply_message = await event.get_reply_message()
        if reply_message and reply_message.sender:
            target_entity = reply_message.sender
            target_id = utils.get_peer_id(target_entity)
    elif arg:
        target_entity, target_id = await get_user_id(event.client, arg)
    else:
        # If no reply and no arg, target the sender of the command
        target_entity = await event.get_chat()
        target_id = utils.get_peer_id(target_entity)

    return target_entity, target_id

def parse_time_arg(time_str):
    """Parses a time string like '1h', '30m', '5d' into minutes. Returns 0 for permanent."""
    if not time_str:
        return 0  # Permanent

    match = re.match(r'(\d+)([smhd])', time_str.lower())
    if not match:
        return 0

    value = int(match.group(1))
    unit = match.group(2)

    if unit == 's':
        return value / 60
    elif unit == 'm':
        return value
    elif unit == 'h':
        return value * 60
    elif unit == 'd':
        return value * 60 * 24
    return 0

async def async_safe_delete_message(event_or_message, client):
    """Safely deletes a message, handling potential errors."""
    try:
        if isinstance(event_or_message, events.NewMessage.Event):
            await event_or_message.delete()
        else:
            await client.delete_messages(event_or_message.peer_id, event_or_message.id)
    except MessageIdInvalidError:
        logger.warning(f"Attempted to delete a message that no longer exists or is invalid.")
    except Exception as e:
        logger.warning(f"Failed to delete message: {e}")

# --- Font Converter ---
# Extensive Unicode font mappings for digits and Latin alphabet
FONTS = {
    1: {'name': 'Digits Bold', 'normal': "0123456789", 'map': "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"},
    2: {'name': 'Digits Full-width', 'normal': "0123456789", 'map': "０１２３４５６７８９"},
    3: {'name': 'Digits Superscript', 'normal': "0123456789", 'map': "⁰¹²³⁴⁵⁶⁷⁸⁹"},
    4: {'name': 'Digits Subscript', 'normal': "0123456789", 'map': "₀₁₂₃₄₅₆₇₈₉"},
    5: {'name': 'Digits Circled', 'normal': "0123456789", 'map': "⓪①②③④⑤⑥⑦⑧⑨"},
    6: {'name': 'Digits Double Circled', 'normal': "0123456789", 'map': "⓿❶❷❸❹❺❻❼❽❾"},
    7: {'name': 'Digits Math Bold', 'normal': "0123456789", 'map': "𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡"},
    8: {'name': 'Digits Sans', 'normal': "0123456789", 'map': "𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫"},
    9: {'name': 'Digits Monospace', 'normal': "0123456789", 'map': "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"},
    10: {'name': 'Digits Serif Bold', 'normal': "0123456789", 'map': "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"},
    11: {'name': 'Latin Bold', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙"},
    12: {'name': 'Latin Italic', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "𝑎𝑏𝑐𝑑𝑒𝑓𝑔ℎ𝑖𝑗𝑘𝑙𝑚𝑛𝑜𝑝𝑞𝑟𝑠𝑡𝑢𝑣𝑤𝑥𝑦𝑧𝐴𝐵𝐶𝐷𝐸𝐹𝐺𝐻𝐼𝐽𝐾𝐿𝑀𝑁𝑂𝑃𝑄𝑅𝑆𝑇𝑈𝑉𝑊𝑋𝑌𝑍"},
    13: {'name': 'Latin Bold Italic', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁"},
    14: {'name': 'Latin Script', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "𝒶𝒷𝒸𝒹𝑒𝒻𝑔𝒽𝒾𝒿𝓀𝓁𝓂𝓃𝑜𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏𝒜𝐵𝒞𝒟𝐸𝐹𝒢𝐻𝐼𝒥𝒦𝐿𝑀𝒩𝒪𝒫𝒬𝑅𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵"},
    15: {'name': 'Latin Bold Script', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃𝓐𝓑𝓒𝓓𝓔𝓕𝓖𝓗𝓘𝓙𝓚𝓛𝓜𝓝𝓞𝓟𝓠𝓡𝓢𝓣𝓤𝓥𝓦𝓧𝓨𝓩"},
    16: {'name': 'Latin Fraktur', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ"},
    17: {'name': 'Latin Bold Fraktur', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "𝖆𝖇𝖈𝖉𝖊𝖋𝖌𝖍𝖎𝖏𝖐𝖑𝖒𝖓𝖔𝖕𝖖𝖗𝖘𝖙𝖚𝖛𝖜𝖝𝖞𝖟   Q𝕮𝕱𝕭𝕲𝕳𝕴𝕵𝕷𝕸𝕹𝕬𝕶𝕹𝕺𝕷𝕾𝕿𝕽𝕰𝕷𝕹𝕾𝕹𝕬𝕻𝕼𝕽𝕾𝕿𝖀𝖁𝖂𝖃𝖄𝖅"}, # Some might not exist
    18: {'name': 'Latin Double-Struck', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡   x𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ"},
    19: {'name': 'Latin Monospace', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉"},
    20: {'name': 'Latin Circled', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ"},
    21: {'name': 'Latin Squared', 'normal': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 'map': "🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🄠🄬🄢🄣🄤🄥🄦🄧🄨🄩"}, # Limited
}
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"

def apply_font(text, font_id):
    """Applies a specified font transformation to the text."""
    if not isinstance(text, str) or not text:
        return text

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT font_map FROM custom_fonts WHERE id = ?', (font_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        # Fallback to predefined if not in DB, though ideally it should be added.
        if font_id not in FONTS:
            return text
        font_data = FONTS[font_id]
    else:
        font_data = json.loads(result[0])
    
    normal_chars = font_data['normal']
    target_chars = font_data['map']
    
    # Also handle Persian/Arabic digits if present in original text
    converted_text = ""
    for char in text:
        if char in normal_chars:
            converted_text += target_chars[normal_chars.find(char)]
        elif char in PERSIAN_DIGITS: # Convert Persian digits to Latin, then apply font if applicable
            latin_digit = str(PERSIAN_DIGITS.find(char))
            if latin_digit in normal_chars:
                converted_text += target_chars[normal_chars.find(latin_digit)]
            else:
                converted_text += char # Keep original if no Latin mapping
        elif char in ARABIC_DIGITS: # Convert Arabic digits to Latin, then apply font if applicable
            latin_digit = str(ARABIC_DIGITS.find(char))
            if latin_digit in normal_chars:
                converted_text += target_chars[normal_chars.find(latin_digit)]
            else:
                converted_text += char # Keep original if no Latin mapping
        else:
            converted_text += char
            
    return converted_text


# --- 4. Command Handler Decorator ---
class CommandHandler:
    """
    Manages self-bot commands, their registration, and message parsing.
    Also stores and serves the self-bot manual.
    """
    def __init__(self, client_instance):
        self.client = client_instance
        self.commands = {}
        self.manual_pages = {}
        self._load_manual_pages() # Load manual content upon initialization

    def _load_manual_pages(self):
        """Populates the manual_pages dictionary with the Persian help text."""
        self.add_manual_page(1, f"""
< راهنمای سلف صفحه ۱ >
(پیشوند دستورات: `{PREFIX}`)

➖➖➖➖➖➖➖➖➖➖➖
👥 مدیریت کاربران:

بلاک کردن کاربر ( ریپلای یا ایدی/یوزرنیم ) => `{PREFIX}Block [ایدی/یوزرنیم]`
آنبلاک کردن کاربر ( ریپلای یا ایدی/یوزرنیم ) => `{PREFIX}UnBlock [ایدی/یوزرنیم]`
سکوت کاربر ( ریپلای یا نوشتن ایدی بعد از دستور ) => `{PREFIX}سکوت [ایدی/یوزرنیم]`
حذف سکوت کاربر ( ریپلای یا نوشتن ایدی بعد از دستور ) => `{PREFIX}حذف سکوت [ایدی/یوزرنیم]`

➖➖➖➖➖➖➖➖➖➖➖

تنظیم اسم => `{PREFIX}SetName [متن]` (یا ریپلای به متنی که اسم جدید است)
تنظیم بیو => `{PREFIX}SetBio [متن]` (یا ریپلای به متنی که بیو جدید است)
تنظیم پروفایل ( عکس , ویدیو ) ( ریپلای ) => `{PREFIX}SetProfile` (ریپلای به عکس/ویدیو)
   
➖➖➖➖➖➖➖➖➖➖➖
تایم در اسم => `{PREFIX}clock on | off`
تایم در بیو => `{PREFIX}bio on | off`
روشن کردن بیو خودکار => `{PREFIX}bio text on | off`
اضافه کردن بیو خودکار => `{PREFIX}add bio | [متن بیو]`
روشن / خاموش کردن بولد => `{PREFIX}bold on | off`

➖➖➖➖➖➖➖➖➖➖➖
سیو ( عکس , فیلم ) تایم دار => `{PREFIX}خودکار` (فعلا غیرفعال)
آنتی لاگین => `{PREFIX}anti login on | off`
آنتی لاگین نسخه ی 2 (چک کردن نشست ها) => `{PREFIX}hard anti login on | off`
ابدیت کردن سلف => `{PREFIX}restart` | `{PREFIX}ریست`
قطع کردن فوری سلف => `{PREFIX}kill` | `{PREFIX}کیل`

➖➖➖➖➖➖➖➖➖➖➖
👥 دستورات مدیریتی گروه:
(نیاز به دسترسی ادمین در گروه برای این دستورات)
بن کردن کاربر (ریپلای یا آیدی عددی/یوزرنیم) => `{PREFIX}ban [ایدی/یوزرنیم]`
آنبن کردن کاربر (ریپلای یا آیدی عددی/یوزرنیم) => `{PREFIX}unban [ایدی/یوزرنیم]`
سکوت کردن کاربر (ریپلای یا آیدی عددی/یوزرنیم) => `{PREFIX}mute [ایدی/یوزرنیم] [زمان (مثال: 30m, 1h, 2d)]` (در صورت نبود زمان، سکوت دائمی خواهد بود)
حذف سکوت کاربر => `{PREFIX}unmute [ایدی/یوزرنیم]`

➖➖➖➖➖➖➖➖➖➖➖

دیدن تنظیمات (روشن یا خاموش بودن قابلیت ها ) => `{PREFIX}وضعیت`

➖➖➖➖➖➖➖➖➖➖➖

صفحه دوم راهنما => `{PREFIX}راهنما 2` یا `{PREFIX}help2`
""")
        self.add_manual_page(2, f"""
< راهنمای سلف صفحه ۲ >
(پیشوند دستورات: `{PREFIX}`)
➖➖➖➖➖➖➖➖➖➖➖

کپی کردن همه پروفایل‌های دیگران (ریپلای یا نوشتن ایدی (عددی یا یوزرنیم)) =>
`{PREFIX}shapeshifter [ایدی/یوزرنیم]`
کپی کردن همه پروفایل‌های دیگران سایلنت (ریپلای یا نوشتن ایدی (عددی یا یوزرنیم)) =>
`{PREFIX}shapeshifter.s [ایدی/یوزرنیم]`
سیو پروفایل‌ها (ریپلای یا نوشتن ایدی (عددی یا یوزرنیم)) =>
`{PREFIX}shapeshifter save`
ریست پروفایل‌ها (ریپلای یا نوشتن ایدی (عددی یا یوزرنیم)) =>
`{PREFIX}shapeshifter backup`

➖➖➖➖➖➖➖➖➖➖➖

سرگرمی ها :  
=> فعلا خاموش هستند ! (این بخش پیاده سازی نشده است)

➖➖➖➖➖➖➖➖➖➖➖

تنظیم پاسخ خودکار:  
• `{PREFIX}منشی روشن`    - فعال‌سازی منشی  
• `{PREFIX}منشی خاموش`   - غیرفعال‌سازی منشی  
• `{PREFIX}تنظیم منشی [پیام]` - تنظیم پیام منشی پیشفرض
• `{PREFIX}تنظیم فرد منتخب` - شروع فرآیند تنظیم پاسخ خودکار برای یک فرد خاص (در چت با ربات)
    ○ ابتدا شناسه کاربری را وارد کنید (در چت با ربات)
    ○ سپس پیام یا رسانه مورد نظر را ارسال کنید (در چت با ربات)


مدیریت لیست خاص:  
• `{PREFIX}اضافه کردن خاص [شناسه]` - افزودن به لیست خاص  
• `{PREFIX}حذف خاص [شناسه]`    - حذف از لیست خاص  
• `{PREFIX}لیست خاص`            - نمایش لیست  
• `{PREFIX}پاک کردن لیست خاص`  - پاک کردن کل لیست

📝 نکته: در دستورات اضافه/حذف خاص اگر شناسه وارد نشود، چت فعلی اضافه/حذف می‌شود.

➖➖➖➖➖➖➖➖➖➖➖

صفحه سوم راهنما =>  
`{PREFIX}راهنما 3`  
یا  
`{PREFIX}help3`
""")
        self.add_manual_page(3, f"""
< راهنمای سلف صفحه 3 >
(پیشوند دستورات: `{PREFIX}`)

➖➖➖➖➖➖➖➖➖➖➖
مدیریت فونت‌ها:

• `{PREFIX}لیست فونت`: نمایش لیست فونت‌های فعال فعلی.
• `{PREFIX}اضافه کردن فونت [شماره]`: اضافه کردن فونت جدید به لیست فعال.
مثال: `{PREFIX}اضافه کردن فونت 3`
• `{PREFIX}حذف فونت [شماره]`: حذف فونت از لیست فعال.
مثال: `{PREFIX}حذف فونت 2`
• `{PREFIX}انواع فونت ساعت`: نمایش ساعت فعلی با استفاده از تمام فونت‌های موجود.

➖➖➖➖➖➖➖➖➖➖➖
نمایش ساعت 00:00 با تمام فونت‌ها (نمونه):

1- 𝟬𝟬:𝟬𝟬
2- ００：００
3- ⁰⁰：⁰⁰
4- ₀₀：₀₀
5- ⓪⓪：⓪⓪
6- ⓿⓿：⓿⓿
7- 𝟘𝟘：𝟘𝟘
8- 𝟢𝟢：𝟢𝟢
9- 𝟬𝟬：𝟬𝟬
10- 𝟶𝟶：𝟶𝟶
11- 𝟎𝟎:𝟎𝟎
(تا فونت‌های بیشتر...)

➖➖➖➖➖➖➖➖➖➖➖

صفحه بعدی راهنما => `{PREFIX}راهنما 4` یا `{PREFIX}help4`
""")
        self.add_manual_page(4, f"""
< راهنمای سلف صفحه 4 >
(پیشوند دستورات: `{PREFIX}`)

➖➖➖➖➖➖➖➖➖➖➖
مدیریت بخش ریاکشن:

• `{PREFIX}reaction on | off`: روشن یا خاموش کردن ریاکشن
• `{PREFIX}لیست ریاکشن`: نمایش لیست ریاکشن های فعال فعلی.
• `{PREFIX}تنظیم ریاکشن [ایدی عددی/یوزرنیم]`: اضافه کردن فرد یا گروه برای دریافت ریاکشن.
• `{PREFIX}حذف ریاکشن [ایدی عددی/یوزرنیم]`: حذف کردن فرد یا گروه از لیست دریافت ریاکشن.
• `{PREFIX}set reaction [ایموجی مد نظر]`: تنظیم ایموجی پیشفرض برای ریاکشن (مثال: `{PREFIX}set reaction 👍`)

➖➖➖➖➖➖➖➖➖➖➖
مدیریت پاسخ‌های خودکار:

• تنظیم پاسخ دقیق خودکار: تنظیم پاسخ خودکار برای پیام‌هایی که دقیقاً برابر کلید هستند (مثلاً فقط "سلام").  
فرمت:  
`{PREFIX}تنظیم پاسخ خودکار کلید : پاسخ`  
مثال:  
`{PREFIX}تنظیم پاسخ خودکار سلام : درود بر تو`

• تنظیم پاسخ شامل خودکار: تنظیم پاسخ خودکار برای پیام‌هایی که کلید داخل متن آن‌ها وجود دارد (مثلاً پیام‌هایی شامل "سلام").  
فرمت:  
`{PREFIX}تنظیم پاسخ شامل خودکار کلید : پاسخ`  
مثال:  
`{PREFIX}تنظیم پاسخ شامل خودکار خداحافظ : بدرود`

• `{PREFIX}حذف پاسخ خودکار [کلید]`: حذف یک قانون پاسخ خودکار.
• `{PREFIX}لیست پاسخ خودکار`: نمایش تمام قوانین پاسخ خودکار.
• `{PREFIX}منشی پاک کردن`: پاک کردن تمام قوانین پاسخ خودکار.


صفحه بعدی راهنما => `{PREFIX}راهنما 5` یا `{PREFIX}help5`

➖➖➖➖➖➖➖➖➖➖➖
""")
        self.add_manual_page(5, f"""
< راهنمای سلف صفحه 5 >
(پیشوند دستورات: `{PREFIX}`)

➖➖➖➖➖➖➖➖➖➖➖
مدیریت بخش مشاهده پیام‌ها:

• `{PREFIX}view edit on | off`: روشن یا خاموش کردن دیدن پیام های ادیت شده
• `{PREFIX}view del on | off`: روشن یا خاموش کردن دیدن پیام های حذف شده
• `{PREFIX}view all on | off`: روشن یا خاموش کردن دیدن پیام های حذف / ادیت شده در سطح گروه ها (همه جا)
• `{PREFIX}ایدی ربات گزارش [ایدی عددی/یوزرنیم]`: تنظیم ایدی ربات یا چت برای ارسال گزارش پیام‌های حذف/ادیت شده.

➖➖➖➖➖➖➖➖➖➖➖

صفحه بعدی راهنما => `{PREFIX}راهنما 6` یا `{PREFIX}help6`
""")
        self.add_manual_page(6, f"""
< راهنمای سلف صفحه 6 >
(پیشوند دستورات: `{PREFIX}`)

➖➖➖➖➖➖➖➖➖➖➖
دستورات ارسال پیام و اسپم:

• ارسال پیام یا فایل چندباره  
پشتیبانی از: `{PREFIX}send`, `{PREFIX}spam`, `{PREFIX}اسپم`  
ارسال چندباره پیام یا فایل ریپلای‌شده.  
`{PREFIX}send [تعداد] [متن دلخواه]`
اگر ریپلای کنید و عدد بنویسید، همان پیام ارسال می‌شود.

• ارسال پیام شماره‌دار (psend)  
افزودن شمارنده به انتهای هر پیام ارسالی.  
`{PREFIX}psend [تعداد] [متن دلخواه]`
یا ریپلای کنید به پیام و فقط تعداد را وارد کنید.

• ارسال به گروه دیگر (gsend)  
ارسال پیام یا فایل ریپلای‌شده به گروه دیگر با ID عددی/یوزرنیم.  
`{PREFIX}gsend [ایدی گروه/یوزرنیم] [تعداد] [متن]`
یا ریپلای کنید و وارد کنید: `{PREFIX}gsend [ایدی گروه/یوزرنیم] [تعداد]`

• ارسال و حذف فوری در گروه (dgsend)  
ارسال پیام به گروه دیگر و حذف بلافاصله پس از ارسال.  
`{PREFIX}dgsend [ایدی گروه/یوزرنیم] [تعداد] [متن]`
یا ریپلای کنید و وارد کنید: `{PREFIX}dgsend [ایدی گروه/یوزرنیم] [تعداد]`

• ارسال همه پیام‌ها و حذف همزمان (dgsend2)  
ارسال همه پیام‌ها و حذف یکجا پس از پایان.  
`{PREFIX}dgsend2 [ایدی گروه/یوزرنیم] [تعداد] [متن]`

• ارسال و حذف فوری در همین چت (dsend)  
ارسال پیام و حذف بلافاصله پس از هر بار ارسال.  
`{PREFIX}dsend [تعداد] [متن]`

• ارسال و حذف با فایل یا متن (dsend2)  
ارسال فایل ریپلای‌شده یا پیام متنی و حذف سریع آن.  
`{PREFIX}dsend2 [تعداد] [متن]`
یا ریپلای کنید و فقط عدد را وارد نمایید.

➖➖➖➖➖➖➖➖➖➖➖

🛡 نکات:  
• حروف بزرگ و کوچک در دستور تاثیری ندارند.  
• فاصله زمانی بین ارسال‌ها با تنظیم سرعت با دستور `{PREFIX}سرعت [عدد (ثانیه)]` کنترل می‌شود (پیشفرض 0.5 ثانیه).
""")

    def add_manual_page(self, page_num, text):
        """Adds a page of manual text."""
        self.manual_pages[page_num] = text

    def command(self, name, description="", allow_edited=False):
        """Decorator to register a command with its handler function."""
        def decorator(func):
            # Store command with its handler function and metadata
            self.commands[name.lower()] = {
                'func': func,
                'description': description,
                'allow_edited': allow_edited
            }
            return func
        return decorator

    async def handle_message(self, event):
        """
        Parses incoming messages to check for commands and executes them.
        Handles the command prefix and arguments.
        """
        if not event.raw_text.lower().startswith(PREFIX.lower()):
            return  # Not a prefixed command for the self-bot

        command_line = event.raw_text[len(PREFIX):].strip()
        parts = command_line.split(maxsplit=1)
        command_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Handle help commands separately as they don't require specific registration
        if command_name == "help" or command_name.startswith("راهنما"):
            page_num_str = re.search(r'\d+', command_name)
            page_num = int(page_num_str.group()) if page_num_str else 1
            if page_num in self.manual_pages:
                await event.reply(self.manual_pages[page_num])
            else:
                await event.reply(f"صفحه راهنما {page_num} یافت نشد. لطفا بین 1 تا {len(self.manual_pages)} انتخاب کنید.")
            return

        # Check for registered commands
        if command_name in self.commands:
            cmd_info = self.commands[command_name]
            # Prevent edited commands from running in groups/channels unless allowed
            if not event.is_private and not cmd_info['allow_edited'] and event.edited:
                logger.info(f"Ignored edited command '{command_name}' in group {event.chat_id}.")
                return
            
            # Execute the command
            try:
                logger.info(f"Executing command: {command_name} with args: '{args}' from {event.sender_id}")
                await cmd_info['func'](event, args)
            except FloodWaitError as e:
                await event.reply(f"⚠️ Flood Wait Error: Please wait {e.seconds} seconds before sending more commands.")
                logger.warning(f"Flood wait for {e.seconds}s while executing {command_name}")
                await asyncio.sleep(e.seconds)
            except ChatAdminRequiredError:
                await event.reply("❌ Error: I need admin rights to perform this action in this chat.")
            except UserAdminInvalidError:
                await event.reply("❌ Error: Cannot perform this action on an administrator or owner.")
            except Exception as e:
                logger.exception(f"Error executing command '{command_name}':")
                await event.reply(f"❌ An unexpected error occurred: <code>{type(e).__name__} - {e}</code>", parse_mode='html')
        else:
            await event.reply(f"❌ Command `{PREFIX}{command_name}` not recognized. Use `{PREFIX}help` for manual.", parse_mode='html')

# --- 5. Telethon Client Initialization ---
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
command_handler = CommandHandler(client)

# --- 6. Core Self-Bot Commands (organized by categories from the manual) ---

# --- User Management ---
@command_handler.command("block", description="بلاک کردن کاربر")
async def block_user(event, args):
    """Blocks a user based on reply or provided ID/username."""
    await event.delete() # Delete command message immediately
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Usage: `.Block [user_id/username]` or reply to a user.", reply_to=event.id)
        return
    if not isinstance(target_entity, User):
        await client.send_message(event.chat_id, "❌ Can only block users, not channels or groups.", reply_to=event.id)
        return

    try:
        await client(BlockRequest(target_entity))
        await client.send_message(event.chat_id, f"✅ User [{target_entity.first_name}](tg://user?id={target_id}) has been blocked.", parse_mode='md', reply_to=event.id)
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error blocking user: {e}", reply_to=event.id)

@command_handler.command("unblock", description="آنبلاک کردن کاربر")
async def unblock_user(event, args):
    """Unblocks a user based on reply or provided ID/username."""
    await event.delete()
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Usage: `.UnBlock [user_id/username]` or reply to a user.", reply_to=event.id)
        return
    if not isinstance(target_entity, User):
        await client.send_message(event.chat_id, "❌ Can only unblock users, not channels or groups.", reply_to=event.id)
        return

    try:
        await client(UnblockRequest(target_entity))
        await client.send_message(event.chat_id, f"✅ User [{target_entity.first_name}](tg://user?id={target_id}) has been unblocked.", parse_mode='md', reply_to=event.id)
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error unblocking user: {e}", reply_to=event.id)

@command_handler.command("سکوت", description="سکوت کاربر (نادیده گرفتن پیام‌ها توسط سلف)")
async def mute_user_self(event, args):
    """Adds a user to the self-bot's ignore list."""
    await event.delete()
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Usage: `.سکوت [user_id/username]` or reply to a user.", reply_to=event.id)
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO special_users (user_id) VALUES (?)', (target_id,))
        conn.commit()
        await client.send_message(event.chat_id, f"✅ User [{target_entity.first_name or target_entity.title}](tg://user?id={target_id}) has been muted (added to ignore list).", parse_mode='md', reply_to=event.id)
    except sqlite3.IntegrityError:
        await client.send_message(event.chat_id, f"ℹ️ User [{target_entity.first_name or target_entity.title}](tg://user?id={target_id}) is already in the ignore list.", parse_mode='md', reply_to=event.id)
    conn.close()

@command_handler.command("حذف سکوت", description="حذف سکوت کاربر (حذف از لیست نادیده گرفتن)")
async def unmute_user_self(event, args):
    """Removes a user from the self-bot's ignore list."""
    await event.delete()
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Usage: `.حذف سکوت [user_id/username]` or reply to a user.", reply_to=event.id)
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM special_users WHERE user_id = ?', (target_id,))
    if cursor.rowcount > 0:
        await client.send_message(event.chat_id, f"✅ User [{target_entity.first_name or target_entity.title}](tg://user?id={target_id}) has been unmuted (removed from ignore list).", parse_mode='md', reply_to=event.id)
    else:
        await client.send_message(event.chat_id, f"ℹ️ User [{target_entity.first_name or target_entity.title}](tg://user?id={target_id}) was not in the ignore list.", parse_mode='md', reply_to=event.id)
    conn.commit()
    conn.close()

# --- Profile Settings ---
@command_handler.command("setname", description="تنظیم اسم اکانت", allow_edited=True)
async def set_name(event, args):
    """Sets the first and last name of the user's account."""
    if not args and not event.is_reply:
        await event.edit("❌ Usage: `.SetName [new name]` or reply to a message containing the new name.", parse_mode='html')
        return

    new_name = args
    if event.is_reply:
        reply_message = await event.get_reply_message()
        if reply_message and reply_message.text:
            new_name = reply_message.text.strip()
        else:
            await event.edit("❌ Replied message contains no text for the new name.", parse_mode='html')
            return

    if not new_name:
        await event.edit("❌ Please provide a name to set.", parse_mode='html')
        return

    try:
        first_name = new_name.split(' ', 1)[0]
        last_name = new_name.split(' ', 1)[1] if ' ' in new_name else ''
        await client(UpdateProfileRequest(first_name=first_name, last_name=last_name))
        await event.edit(f"✅ Profile name updated to: <b>{new_name}</b>", parse_mode='html')
    except Exception as e:
        await event.edit(f"❌ Error setting name: {e}", parse_mode='html')

@command_handler.command("setbio", description="تنظیم بیو اکانت", allow_edited=True)
async def set_bio(event, args):
    """Sets the bio of the user's account."""
    if not args and not event.is_reply:
        await event.edit("❌ Usage: `.SetBio [new bio]` or reply to a message containing the new bio.", parse_mode='html')
        return

    new_bio = args
    if event.is_reply:
        reply_message = await event.get_reply_message()
        if reply_message and reply_message.text:
            new_bio = reply_message.text.strip()
        else:
            await event.edit("❌ Replied message contains no text for the new bio.", parse_mode='html')
            return

    # Allow clearing bio by providing empty argument
    if not new_bio:
        new_bio = ""

    try:
        await client(UpdateProfileRequest(about=new_bio))
        await event.edit(f"✅ Profile bio updated to: <b>{new_bio or '(cleared)'}</b>", parse_mode='html')
    except Exception as e:
        await event.edit(f"❌ Error setting bio: {e}", parse_mode='html')

@command_handler.command("setprofile", description="تنظیم عکس/ویدیوی پروفایل", allow_edited=True)
async def set_profile_photo(event, args):
    """Sets the profile picture or video from a replied media."""
    if not event.is_reply:
        await event.edit("❌ Usage: Reply to a photo or video to set it as your profile picture. `.SetProfile`", parse_mode='html')
        return

    reply_message = await event.get_reply_message()
    if not reply_message or not (reply_message.photo or reply_message.video):
        await event.edit("❌ Reply to a photo or video to set it as your profile picture.", parse_mode='html')
        return

    try:
        media = reply_message.photo or reply_message.video
        await client(UploadProfilePhotoRequest(file=media))
        await event.edit("✅ Profile picture/video updated successfully!", parse_mode='html')
    except PhotoInvalidError:
        await event.edit("❌ Invalid photo/video. Please ensure it's a valid media file.", parse_mode='html')
    except Exception as e:
        await event.edit(f"❌ Error setting profile picture: {e}", parse_mode='html')

# --- Time/Bio Automation ---
@command_handler.command("clock", description="روشن/خاموش کردن نمایش ساعت در اسم", allow_edited=True)
async def toggle_clock_in_name(event, args):
    """Toggles displaying current time in the user's first name."""
    if args.lower() == "on":
        set_setting('clock_in_name', '1')
        await event.edit("✅ Time in name: <b>ON</b>", parse_mode='html')
    elif args.lower() == "off":
        set_setting('clock_in_name', '0')
        await event.edit("✅ Time in name: <b>OFF</b>", parse_mode='html')
    else:
        await event.edit("❌ Usage: `.clock on | off`", parse_mode='html')

@command_handler.command("bio", description="روشن/خاموش کردن نمایش ساعت/متن خودکار در بیو", allow_edited=True)
async def toggle_clock_in_bio(event, args):
    """Toggles displaying current time or custom text in the user's bio."""
    if args.lower() == "on":
        set_setting('clock_in_bio', '1')
        await event.edit("✅ Time in bio: <b>ON</b>", parse_mode='html')
    elif args.lower() == "off":
        set_setting('clock_in_bio', '0')
        await event.edit("✅ Time in bio: <b>OFF</b>", parse_mode='html')
    elif args.lower() == "text on":
        set_setting('bio_auto_text', '1')
        await event.edit("✅ Automatic bio text: <b>ON</b>", parse_mode='html')
    elif args.lower() == "text off":
        set_setting('bio_auto_text', '0')
        await event.edit("✅ Automatic bio text: <b>OFF</b>", parse_mode='html')
    else:
        await event.edit("❌ Usage: `.bio on | off` or `.bio text on | off`", parse_mode='html')

@command_handler.command("add bio", description="اضافه کردن متن برای بیو خودکار", allow_edited=True)
async def add_auto_bio_text(event, args):
    """Sets the custom text to be used for automatic bio updates."""
    if not args or '|' not in args:
        await event.edit("❌ Usage: `.add bio | [your bio text]`", parse_mode='html')
        return
    
    parts = args.split('|', 1)
    if len(parts) < 2 or not parts[1].strip():
        await event.edit("❌ Usage: `.add bio | [your bio text]` - Please provide text after '|'", parse_mode='html')
        return

    bio_text = parts[1].strip()
    set_setting('custom_bio_text', bio_text)
    await event.edit(f"✅ Custom auto bio text set to: <b>{bio_text}</b>", parse_mode='html')

@command_handler.command("bold", description="روشن/خاموش کردن بولد خودکار (برای پیام‌های ارسالی)", allow_edited=True)
async def toggle_bold_auto(event, args):
    """Toggles automatic bold formatting for outgoing messages (not yet fully implemented as global formatter)."""
    # This feature would require intercepting outgoing messages and applying bold.
    # For now, it's a placeholder.
    if args.lower() == "on":
        set_setting('auto_bold', '1')
        await event.edit("✅ Auto bold: <b>ON</b> (Note: This feature is under development for general outgoing messages.)", parse_mode='html')
    elif args.lower() == "off":
        set_setting('auto_bold', '0')
        await event.edit("✅ Auto bold: <b>OFF</b>", parse_mode='html')
    else:
        await event.edit("❌ Usage: `.bold on | off`", parse_mode='html')

# --- Self-Bot Management ---
@command_handler.command("restart", description="ریبوت کردن سلف")
async def restart_self(event, args):
    """Restarts the self-bot process."""
    await event.edit("🔄 Restarting selfbot...")
    # This method of restart assumes the script is run by a process manager (like systemd, Docker, or forever)
    # that will automatically restart it if it exits.
    python = sys.executable
    os.execl(python, python, *sys.argv)

@command_handler.command("kill", description="خاموش کردن فوری سلف")
async def kill_self(event, args):
    """Shuts down the self-bot process."""
    await event.edit("💀 Shutting down selfbot...", parse_mode='html')
    await client.disconnect()
    sys.exit(0)

# --- Group Management (Admin actions by self-bot) ---
@command_handler.command("ban", description="بن کردن کاربر در گروه")
async def ban_user_group(event, args):
    """Bans a user from the current group (requires admin rights)."""
    await event.delete()
    if not event.is_group and not event.is_channel:
        await client.send_message(event.chat_id, "❌ This command can only be used in a group or channel.", reply_to=event.id)
        return
    
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Could not find user. Please provide a valid ID, username, or reply.", reply_to=event.id)
        return
    if not isinstance(target_entity, User):
        await client.send_message(event.chat_id, "❌ Can only ban users, not channels or groups.", reply_to=event.id)
        return

    try:
        await client(EditBannedRequest(
            event.chat_id,
            target_id,
            ChannelBannedRights(
                until_date=None,  # Permanent ban
                view_messages=True, send_messages=True, send_media=True,
                send_stickers=True, send_gifs=True, send_games=True,
                send_inline=True, embed_links=True, send_polls=True,
                change_info=True, invite_users=True, pin_messages=True,
                manage_topics=True
            )
        ))
        await client.send_message(event.chat_id, f"✅ User [{target_entity.first_name}](tg://user?id={target_id}) has been banned from this group.", parse_mode='md', reply_to=event.id)
    except ChatAdminRequiredError:
        await client.send_message(event.chat_id, "❌ Error: I need admin rights to ban users in this chat.", reply_to=event.id)
    except UserAdminInvalidError:
        await client.send_message(event.chat_id, "❌ Error: Cannot ban an admin or owner.", reply_to=event.id)
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error banning user: {e}", reply_to=event.id)

@command_handler.command("unban", description="آنبن کردن کاربر در گروه")
async def unban_user_group(event, args):
    """Unbans a user from the current group (requires admin rights)."""
    await event.delete()
    if not event.is_group and not event.is_channel:
        await client.send_message(event.chat_id, "❌ This command can only be used in a group or channel.", reply_to=event.id)
        return
    
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Could not find user. Please provide a valid ID, username, or reply.", reply_to=event.id)
        return
    if not isinstance(target_entity, User):
        await client.send_message(event.chat_id, "❌ Can only unban users, not channels or groups.", reply_to=event.id)
        return

    try:
        # To unban, we set all banned rights to False
        await client(EditBannedRequest(
            event.chat_id,
            target_id,
            ChannelBannedRights(
                until_date=None,
                view_messages=False, send_messages=False, send_media=False,
                send_stickers=False, send_gifs=False, send_games=False,
                send_inline=False, embed_links=False, send_polls=False,
                change_info=False, invite_users=False, pin_messages=False,
                manage_topics=False
            )
        ))
        await client.send_message(event.chat_id, f"✅ User [{target_entity.first_name}](tg://user?id={target_id}) has been unbanned from this group.", parse_mode='md', reply_to=event.id)
    except ChatAdminRequiredError:
        await client.send_message(event.chat_id, "❌ Error: I need admin rights to unban users in this chat.", reply_to=event.id)
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error unbanning user: {e}", reply_to=event.id)

@command_handler.command("mute", description="سکوت کاربر در گروه")
async def mute_user_group(event, args):
    """Mutes a user in the current group for a specified duration (requires admin rights)."""
    await event.delete()
    if not event.is_group and not event.is_channel:
        await client.send_message(event.chat_id, "❌ This command can only be used in a group or channel.", reply_to=event.id)
        return
    
    args_split = args.split(' ', 1)
    peer_str = args_split[0]
    time_str = args_split[1] if len(args_split) > 1 else ""

    target_entity, target_id = await parse_entity_from_message(event, peer_str)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Could not find user. Please provide a valid ID, username, or reply.", reply_to=event.id)
        return
    if not isinstance(target_entity, User):
        await client.send_message(event.chat_id, "❌ Can only mute users, not channels or groups.", reply_to=event.id)
        return

    mute_duration_minutes = parse_time_arg(time_str)
    # Telegram API expects `until_date` for mute/ban. None means permanent for ban, but for mute, it implies default (unmute).
    # To mute, we set `send_messages` to True in ChannelBannedRights and define `until_date`.
    # If `until_date` is not provided, it's a permanent mute (until manually unmuted).
    until_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=mute_duration_minutes) if mute_duration_minutes else None

    try:
        await client(EditBannedRequest(
            event.chat_id,
            target_id,
            ChannelBannedRights(
                until_date=until_date,
                send_messages=True, send_media=True, send_stickers=True, send_gifs=True,
                send_games=True, send_inline=True, embed_links=True, send_polls=True,
                change_info=False, invite_users=False, pin_messages=False,
                manage_topics=False
            )
        ))
        duration_msg = f" for {mute_duration_minutes} minutes" if mute_duration_minutes else " permanently"
        await client.send_message(event.chat_id, f"✅ User [{target_entity.first_name}](tg://user?id={target_id}) has been muted{duration_msg} in this group.", parse_mode='md', reply_to=event.id)
    except ChatAdminRequiredError:
        await client.send_message(event.chat_id, "❌ Error: I need admin rights to mute users in this chat.", reply_to=event.id)
    except UserAdminInvalidError:
        await client.send_message(event.chat_id, "❌ Error: Cannot mute an admin or owner.", reply_to=event.id)
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error muting user: {e}", reply_to=event.id)

@command_handler.command("unmute", description="حذف سکوت کاربر در گروه")
async def unmute_user_group(event, args):
    """Unmutes a user in the current group (requires admin rights)."""
    await event.delete()
    if not event.is_group and not event.is_channel:
        await client.send_message(event.chat_id, "❌ This command can only be used in a group or channel.", reply_to=event.id)
        return
    
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Could not find user. Please provide a valid ID, username, or reply.", reply_to=event.id)
        return
    if not isinstance(target_entity, User):
        await client.send_message(event.chat_id, "❌ Can only unmute users, not channels or groups.", reply_to=event.id)
        return

    try:
        # To unmute, we set all relevant banned rights to False (revoking the mute)
        await client(EditBannedRequest(
            event.chat_id,
            target_id,
            ChannelBannedRights(
                until_date=None,
                send_messages=False, send_media=False, send_stickers=False, send_gifs=False,
                send_games=False, send_inline=False, embed_links=False, send_polls=False,
                change_info=False, invite_users=False, pin_messages=False,
                manage_topics=False
            )
        ))
        await client.send_message(event.chat_id, f"✅ User [{target_entity.first_name}](tg://user?id={target_id}) has been unmuted in this group.", parse_mode='md', reply_to=event.id)
    except ChatAdminRequiredError:
        await client.send_message(event.chat_id, "❌ Error: I need admin rights to unmute users in this chat.", reply_to=event.id)
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error unmuting user: {e}", reply_to=event.id)

# --- Status/Settings View ---
@command_handler.command("وضعیت", description="دیدن تنظیمات فعال/غیرفعال", allow_edited=True)
async def show_status(event, args):
    """Displays the current status of various self-bot settings."""
    status_msg = "<b>Current Self-Bot Settings:</b>\n"
    status_msg += f"⏰ Time in Name: <b>{'ON' if get_setting('clock_in_name') == '1' else 'OFF'}</b>\n"
    status_msg += f"📝 Time in Bio: <b>{'ON' if get_setting('clock_in_bio') == '1' else 'OFF'}</b>\n"
    status_msg += f"✍️ Auto Bio Text: <b>{'ON' if get_setting('bio_auto_text') == '1' else 'OFF'}</b> (Text: <code>{get_setting('custom_bio_text', 'N/A')}</code>)\n"
    status_msg += f"🅱️ Auto Bold: <b>{'ON' if get_setting('auto_bold') == '1' else 'OFF'}</b>\n"
    status_msg += f"🔐 Anti Login: <b>{'ON' if get_setting('anti_login_on') == '1' else 'OFF'}</b>\n"
    status_msg += f"🔒 Hard Anti Login (Session Check): <b>{'ON' if get_setting('hard_anti_login_on') == '1' else 'OFF'}</b>\n"
    status_msg += f"🤖 Auto Reply (Monshi): <b>{'ON' if get_setting('monshi_enabled') == '1' else 'OFF'}</b> (Default: <code>{get_setting('default_monshi_response', 'N/A')}</code>)\n"
    status_msg += f"❤️ Reaction On: <b>{'ON' if get_setting('reaction_on') == '1' else 'OFF'}</b> (Emoji: <b>{get_setting('reaction_emoji', '👍')}</b>)\n"
    status_msg += f"👁️ View Edited Messages: <b>{'ON' if get_setting('view_edit_on') == '1' else 'OFF'}</b>\n"
    status_msg += f"🗑️ View Deleted Messages: <b>{'ON' if get_setting('view_del_on') == '1' else 'OFF'}</b>\n"
    status_msg += f"🌐 View All (Group Edits/Deletions): <b>{'ON' if get_setting('view_all_on') == '1' else 'OFF'}</b>\n"
    status_msg += f"📬 Report Bot ID: <b>{get_setting('report_bot_id', 'Not Set')}</b>\n"
    status_msg += f"⚡ Spam Speed (seconds): <b>{get_setting('spam_speed', '0.5')}</b>\n"

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, font_name FROM custom_fonts')
    active_fonts = [f"{row[0]} ({row[1]})" for row in cursor.fetchall()]
    conn.close()
    status_msg += f"🅰️ Active Fonts: <b>{', '.join(active_fonts) or 'None'}</b>\n"

    await event.edit(status_msg, parse_mode='html')

# --- Shapeshifter (Profile Copying) ---
async def _get_profile_data(client_instance, entity):
    """Fetches profile data (name, bio, photos) for an entity."""
    full_entity = await client_instance(GetFullUserRequest(entity=entity))
    user_data = full_entity.user
    profile_photos = await client_instance.get_profile_photos(entity, limit=1)
    
    name = f"{user_data.first_name or ''} {user_data.last_name or ''}".strip()
    bio = full_entity.about or ""
    
    photo_path = None
    if profile_photos:
        # Save photo to a temporary file, named uniquely
        photo_filename = f"profile_photo_backup_{entity.id}_{int(time.time())}.jpg"
        photo_path = await client_instance.download_media(profile_photos[0], file=photo_filename)
    
    return name, bio, photo_path

async def _set_profile_data(client_instance, name, bio, photo_path):
    """Sets the current user's profile data."""
    first_name = name.split(' ', 1)[0]
    last_name = name.split(' ', 1)[1] if ' ' in name else ''
    await client_instance(UpdateProfileRequest(first_name=first_name, last_name=last_name, about=bio))
    
    if photo_path and os.path.exists(photo_path):
        # Delete existing profile photos first for a clean copy
        existing_photos = await client_instance.get_profile_photos('me')
        if existing_photos:
            await client_instance(DeletePhotosRequest([p.id for p in existing_photos]))
        
        await client_instance(UploadProfilePhotoRequest(file=photo_path))
        os.remove(photo_path)  # Clean up temporary photo file

@command_handler.command("shapeshifter", description="کپی پروفایل دیگران")
async def shapeshifter_command(event, args):
    """Copies the profile (name, bio, photo) of another user to the self-bot's profile."""
    await event.delete()
    silent_mode = False
    if args.lower().endswith(".s"):
        silent_mode = True
        args = args[:-2].strip()

    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not isinstance(target_entity, User):
        await client.send_message(event.chat_id, "❌ Please specify a user to shapeshift to (reply or ID/username).", reply_to=event.id)
        return

    if not silent_mode:
        await client.send_message(event.chat_id, f"🎭 Shapeshifting to [{target_entity.first_name}](tg://user?id={target_id})...", parse_mode='md', reply_to=event.id)
    
    # Backup current profile first
    me = await client.get_me()
    current_name, current_bio, current_photo_path = await _get_profile_data(client, me)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO shapeshifter_backup (user_id, name, bio, profile_photo_path) VALUES (?, ?, ?, ?)''',
                   (me.id, current_name, current_bio, current_photo_path))
    conn.commit()
    conn.close()

    # Get target profile data
    name, bio, photo_path = await _get_profile_data(client, target_entity)

    try:
        await _set_profile_data(client, name, bio, photo_path)
        if not silent_mode:
            await client.send_message(event.chat_id, f"✅ Successfully shapeshifted to [{target_entity.first_name}](tg://user?id={target_id})'s profile.", parse_mode='md', reply_to=event.id)
    except Exception as e:
        logger.exception("Shapeshifter failed:")
        if not silent_mode:
            await client.send_message(event.chat_id, f"❌ Failed to shapeshift: {e}", reply_to=event.id)
        # Attempt to restore from backup if failed
        if await _restore_from_backup_internal(me.id):
            if not silent_mode:
                await client.send_message(event.chat_id, "ℹ️ Attempted to restore previous profile due to failure.", reply_to=event.id)
        else:
            if not silent_mode:
                await client.send_message(event.chat_id, "❌ Could not restore previous profile from backup.", reply_to=event.id)

@command_handler.command("shapeshifter.s", description="کپی پروفایل دیگران (سایلنت)")
async def shapeshifter_silent_command(event, args):
    """Silent version of shapeshifter command."""
    # This command is handled by the main shapeshifter function using the .s suffix logic
    await shapeshifter_command(event, args + " .s")

@command_handler.command("shapeshifter save", description="ذخیره پروفایل فعلی", allow_edited=True)
async def shapeshifter_save_command(event, args):
    """Saves the current user's profile as a backup."""
    me = await client.get_me()
    current_name, current_bio, current_photo_path = await _get_profile_data(client, me)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO shapeshifter_backup (user_id, name, bio, profile_photo_path) VALUES (?, ?, ?, ?)''',
                   (me.id, current_name, current_bio, current_photo_path))
    conn.commit()
    conn.close()
    await event.edit("✅ Your current profile has been saved as a backup.", parse_mode='html')

async def _restore_from_backup_internal(user_id):
    """Internal function to restore profile from the latest backup."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''SELECT name, bio, profile_photo_path FROM shapeshifter_backup WHERE user_id = ? ORDER BY backup_time DESC LIMIT 1''', (user_id,))
    backup_data = cursor.fetchone()
    conn.close()

    if backup_data:
        name, bio, photo_path = backup_data
        try:
            await _set_profile_data(client, name, bio, photo_path)
            # Delete the backup file after successful restoration
            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)
            return True
        except Exception as e:
            logger.error(f"Failed to restore profile from backup: {e}")
            return False
    return False

@command_handler.command("shapeshifter backup", description="ریست پروفایل به آخرین بکاپ", allow_edited=True)
async def shapeshifter_backup_command(event, args):
    """Restores the user's profile to the latest saved backup."""
    me = await client.get_me()
    if await _restore_from_backup_internal(me.id):
        await event.edit("✅ Your profile has been restored from the latest backup.", parse_mode='html')
    else:
        await event.edit("❌ No backup found to restore from.", parse_mode='html')

# --- Anti-Login ---
# Note: Full 'hard anti login' (terminating other sessions) is complex for userbots due to API limitations
# and the risk of terminating the current session. This implementation focuses on reporting.
async def check_active_sessions_task():
    """
    Periodically checks active sessions and reports new ones if anti-login is enabled.
    This runs as a background task.
    """
    if get_setting('anti_login_on') != '1' and get_setting('hard_anti_login_on') != '1':
        return

    report_chat_id = get_setting('report_bot_id')
    if not report_chat_id:
        logger.warning("Anti-login is ON but no report bot ID is set.")
        return

    try:
        devices = await client(GetAuthorizationsRequest())
        
        known_sessions = json.loads(get_setting('known_sessions', '[]'))
        current_session_hash = None # Telethon does not directly expose current auth_key_id. This is a placeholder.
                                    # In a real scenario, you'd uniquely identify the current session
                                    # perhaps by some metadata or by comparing IP/device info.

        new_sessions = []
        updated_known_sessions = []
        for auth in devices.authorizations:
            session_info = {
                'hash': auth.hash,
                'app_name': auth.app_name,
                'platform': auth.platform,
                'device_model': auth.device_model,
                'ip': auth.ip,
                'country': auth.country,
                'date_created': auth.date_created.isoformat(),
                'date_active': auth.date_active.isoformat()
            }
            updated_known_sessions.append(session_info)

            if not any(s['hash'] == auth.hash for s in known_sessions):
                new_sessions.append(session_info)

        if new_sessions:
            report_msg = "⚠️ <b>New Telegram Session(s) Detected!</b> ⚠️\n"
            for session in new_sessions:
                report_msg += (
                    f"  - App: <code>{session['app_name']}</code>\n"
                    f"  - Platform: <code>{session['platform']}</code>\n"
                    f"  - Device: <code>{session['device_model']}</code>\n"
                    f"  - IP: <code>{session['ip']}</code> ({session['country']})\n"
                    f"  - Active: {session['date_active']}\n"
                    f"  - Created: {session['date_created']}\n\n"
                )
            report_msg += "Please review your active sessions in Telegram settings for unauthorized access."
            
            try:
                await client.send_message(int(report_chat_id), report_msg, parse_mode='html')
            except Exception as e:
                logger.error(f"Failed to send anti-login report to {report_chat_id}: {e}")
            
            # Update known sessions after reporting new ones
            set_setting('known_sessions', json.dumps(updated_known_sessions))
        else:
            set_setting('known_sessions', json.dumps(updated_known_sessions)) # Keep up-to-date
            logger.info("No new sessions detected.")

        if get_setting('hard_anti_login_on') == '1':
            # Aggressively terminate ALL other sessions. This will log out current bot if not careful.
            # Telethon's `client.log_out()` logs out *all* sessions. To log out *others* requires specific API calls.
            # ResetAuthorizationRequest(hash=...) requires hash of specific session.
            # This is a dangerous operation. For a self-bot, logging out all sessions effectively kills it.
            # A safer "hard anti-login" might involve notifying the user *and then* waiting for manual intervention.
            logger.warning("Hard Anti-login enabled. Automatic termination of *other* sessions is highly risky for self-bots.")
            # Implementation for terminating *specific* other sessions is complex and might involve
            # iterating `devices.authorizations` and calling `client(ResetAuthorizationRequest(hash=auth.hash))`
            # for each session *except* the current one. Identifying the current one reliably is the challenge.
            # For simplicity, we'll keep `hard anti login` as primarily an enhanced notification mechanism here.

    except AuthKeyUnregisteredError:
        logger.error("Anti-login check failed: Session is no longer valid. Re-login required.")
    except Exception as e:
        logger.error(f"Error during anti-login check: {e}")

@command_handler.command("anti login", description="روشن/خاموش کردن آنتی لاگین", allow_edited=True)
async def toggle_anti_login(event, args):
    """Toggles the basic anti-login (session monitoring) feature."""
    if args.lower() == "on":
        set_setting('anti_login_on', '1')
        await event.edit("✅ Anti login: <b>ON</b>. New sessions will be reported to the configured chat.", parse_mode='html')
        # Also, clear known sessions so it detects all existing ones on next check
        set_setting('known_sessions', '[]') 
    elif args.lower() == "off":
        set_setting('anti_login_on', '0')
        await event.edit("✅ Anti login: <b>OFF</b>", parse_mode='html')
    else:
        await event.edit("❌ Usage: `.anti login on | off`", parse_mode='html')

@command_handler.command("hard anti login", description="روشن/خاموش کردن آنتی لاگین نسخه ی 2 (چک کردن نشست ها)", allow_edited=True)
async def toggle_hard_anti_login(event, args):
    """Toggles the 'hard' anti-login feature (more aggressive session monitoring/reporting)."""
    if args.lower() == "on":
        set_setting('hard_anti_login_on', '1')
        await event.edit("✅ Hard anti login (aggressive session check): <b>ON</b>. New sessions will be reported. Be cautious, automatic termination is complex and risky for self-bots.", parse_mode='html')
        set_setting('known_sessions', '[]')
    elif args.lower() == "off":
        set_setting('hard_anti_login_on', '0')
        await event.edit("✅ Hard anti login: <b>OFF</b>", parse_mode='html')
    else:
        await event.edit("❌ Usage: `.hard anti login on | off`", parse_mode='html')

# --- Auto-reply (Monshi) ---
class AutoReplyState:
    """Manages the multi-step state for setting individual auto-replies."""
    def __init__(self):
        # {sender_id: {'state': 'waiting_for_id' or 'waiting_for_message', 'temp_id': None, 'temp_media': None, 'is_reply': False}}
        self.active_user_setup = {} 

auto_reply_state = AutoReplyState()

@command_handler.command("منشی روشن", description="فعال‌سازی منشی", allow_edited=True)
async def monshi_on(event, args):
    set_setting('monshi_enabled', '1')
    await event.edit("✅ منشی فعال شد.", parse_mode='html')

@command_handler.command("منشی خاموش", description="غیرفعال‌سازی منشی", allow_edited=True)
async def monshi_off(event, args):
    set_setting('monshi_enabled', '0')
    await event.edit("✅ منشی غیرفعال شد.", parse_mode='html')

@command_handler.command("تنظیم منشی", description="تنظیم پیام منشی پیشفرض", allow_edited=True)
async def set_default_monshi_message(event, args):
    """Sets the default auto-reply message."""
    if not args and not event.is_reply:
        await event.edit("❌ Usage: `.تنظیم منشی [پیام]` or reply to message.", parse_mode='html')
        return
    
    message_text = args
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.text:
            message_text = reply_msg.text
        else:
            await event.edit("❌ Reply message has no text.", parse_mode='html')
            return

    set_setting('default_monshi_response', message_text)
    await event.edit(f"✅ پیام پیشفرض منشی به: <b>{message_text}</b> تنظیم شد.", parse_mode='html')

@command_handler.command("تنظیم فرد منتخب", description="شروع فرآیند تنظیم پاسخ خودکار برای فرد خاص", allow_edited=True)
async def set_individual_auto_reply_start(event, args):
    """Initiates a multi-step process to set an auto-reply for a specific user."""
    await event.delete()
    sender_id = event.sender_id # The one sending the command
    auto_reply_state.active_user_setup[sender_id] = {'state': 'waiting_for_id', 'temp_id': None, 'temp_media': None, 'is_reply': event.is_reply}
    await client.send_message(event.chat_id, "🔢 لطفا شناسه کاربری (عددی یا یوزرنیم) فرد مورد نظر را وارد کنید.", reply_to=event.id)

@command_handler.command("تنظیم پاسخ خودکار", description="تنظیم پاسخ دقیق خودکار", allow_edited=True)
async def set_exact_auto_reply(event, args):
    """Sets an auto-reply rule for exact message matches."""
    if ':' not in args:
        await event.edit("❌ Usage: `.تنظیم پاسخ خودکار [کلید] : [پاسخ]`", parse_mode='html')
        return
    
    key, response = args.split(':', 1)
    key = key.strip()
    response = response.strip()

    if not key or not response:
        await event.edit("❌ کلید و پاسخ نمی‌توانند خالی باشند.", parse_mode='html')
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO auto_replies (trigger_text, response_text, exact_match) VALUES (?, ?, ?)''',
                   (key, response, True))
    conn.commit()
    conn.close()
    await event.edit(f"✅ پاسخ خودکار دقیق برای '<b>{key}</b>' به '<b>{response}</b>' تنظیم شد.", parse_mode='html')

@command_handler.command("تنظیم پاسخ شامل خودکار", description="تنظیم پاسخ شامل خودکار", allow_edited=True)
async def set_inclusive_auto_reply(event, args):
    """Sets an auto-reply rule for partial message matches."""
    if ':' not in args:
        await event.edit("❌ Usage: `.تنظیم پاسخ شامل خودکار [کلید] : [پاسخ]`", parse_mode='html')
        return
    
    key, response = args.split(':', 1)
    key = key.strip()
    response = response.strip()

    if not key or not response:
        await event.edit("❌ کلید و پاسخ نمی‌توانند خالی باشند.", parse_mode='html')
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO auto_replies (trigger_text, response_text, exact_match) VALUES (?, ?, ?)''',
                   (key, response, False))
    conn.commit()
    conn.close()
    await event.edit(f"✅ پاسخ خودکار شامل برای '<b>{key}</b>' به '<b>{response}</b>' تنظیم شد.", parse_mode='html')

@command_handler.command("حذف پاسخ خودکار", description="حذف یک قانون پاسخ خودکار", allow_edited=True)
async def delete_auto_reply(event, args):
    """Deletes an auto-reply rule by its trigger key."""
    if not args:
        await event.edit("❌ Usage: `.حذف پاسخ خودکار [کلید]`", parse_mode='html')
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM auto_replies WHERE trigger_text = ?''', (args.strip(),))
    if cursor.rowcount > 0:
        await event.edit(f"✅ پاسخ خودکار برای '<b>{args.strip()}</b>' حذف شد.", parse_mode='html')
    else:
        await event.edit(f"ℹ️ پاسخ خودکاری با کلید '<b>{args.strip()}</b>' یافت نشد.", parse_mode='html')
    conn.commit()
    conn.close()

@command_handler.command("لیست پاسخ خودکار", description="نمایش تمام قوانین پاسخ خودکار", allow_edited=True)
async def list_auto_replies(event, args):
    """Lists all configured auto-reply rules."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT trigger_text, response_text, exact_match, specific_peer_id FROM auto_replies')
    replies = cursor.fetchall()
    conn.close()

    if not replies:
        await event.edit("ℹ️ هیچ قانون پاسخ خودکاری تنظیم نشده است.", parse_mode='html')
        return

    msg = "<b>قوانین پاسخ خودکار:</b>\n"
    for trigger, response, exact, peer_id in replies:
        peer_info = ""
        if peer_id:
            try:
                entity = await client.get_entity(peer_id)
                name = getattr(entity, 'first_name', getattr(entity, 'title', 'Unknown'))
                peer_info = f" (برای: [{name}](tg://user?id={peer_id}))"
            except Exception:
                peer_info = f" (برای ID: {peer_id})"
        msg += f"  - <b>{trigger}</b> {'(دقیق)' if exact else '(شامل)'}: {response}{peer_info}\n"
    await event.edit(msg, parse_mode='html')

@command_handler.command("منشی پاک کردن", description="پاک کردن تمام قوانین پاسخ خودکار", allow_edited=True)
async def clear_auto_replies(event, args):
    """Deletes all auto-reply rules."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM auto_replies')
    conn.commit()
    conn.close()
    await event.edit("✅ تمام قوانین پاسخ خودکار حذف شدند.", parse_mode='html')

# --- Special List Management (for 'self-mute' and other custom behaviors) ---
@command_handler.command("اضافه کردن خاص", description="افزودن به لیست خاص", allow_edited=True)
async def add_special_user(event, args):
    """Adds a user or chat to the special list."""
    await event.delete()
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Could not find user/chat. Please provide a valid ID, username, or reply.", reply_to=event.id)
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''INSERT INTO special_users (user_id) VALUES (?)''', (target_id,))
        conn.commit()
        await client.send_message(event.chat_id, f"✅ Entity [{target_entity.first_name if isinstance(target_entity, User) else target_entity.title}](tg://user?id={target_id}) added to special list.", parse_mode='md', reply_to=event.id)
    except sqlite3.IntegrityError:
        await client.send_message(event.chat_id, f"ℹ️ Entity [{target_entity.first_name if isinstance(target_entity, User) else target_entity.title}](tg://user?id={target_id}) is already in the special list.", parse_mode='md', reply_to=event.id)
    conn.close()

@command_handler.command("حذف خاص", description="حذف از لیست خاص", allow_edited=True)
async def remove_special_user(event, args):
    """Removes a user or chat from the special list."""
    await event.delete()
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Could not find user/chat. Please provide a valid ID, username, or reply.", reply_to=event.id)
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM special_users WHERE user_id = ?''', (target_id,))
    if cursor.rowcount > 0:
        await client.send_message(event.chat_id, f"✅ Entity [{target_entity.first_name if isinstance(target_entity, User) else target_entity.title}](tg://user?id={target_id}) removed from special list.", parse_mode='md', reply_to=event.id)
    else:
        await client.send_message(event.chat_id, f"ℹ️ Entity [{target_entity.first_name if isinstance(target_entity, User) else target_entity.title}](tg://user?id={target_id}) not found in special list.", parse_mode='md', reply_to=event.id)
    conn.commit()
    conn.close()

@command_handler.command("لیست خاص", description="نمایش لیست خاص", allow_edited=True)
async def list_special_users(event, args):
    """Lists all users/chats in the special list."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM special_users')
    special_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not special_ids:
        await event.edit("ℹ️ Special list is empty.", parse_mode='html')
        return

    msg = "<b>Special Users/Chats:</b>\n"
    for user_id in special_ids:
        try:
            entity = await client.get_entity(user_id)
            name = getattr(entity, 'first_name', getattr(entity, 'title', 'Unknown'))
            msg += f"  - [{name}](tg://user?id={user_id}) (ID: {user_id})\n"
        except Exception:
            msg += f"  - Unknown Entity (ID: {user_id})\n"
    await event.edit(msg, parse_mode='html')

@command_handler.command("پاک کردن لیست خاص", description="پاک کردن کل لیست خاص", allow_edited=True)
async def clear_special_users(event, args):
    """Clears all entries from the special list."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM special_users')
    conn.commit()
    conn.close()
    await event.edit("✅ Special list cleared.", parse_mode='html')

# --- Font Management ---
@command_handler.command("لیست فونت", description="نمایش لیست فونت‌های فعال", allow_edited=True)
async def list_fonts(event, args):
    """Displays currently active fonts and available default fonts."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, font_name FROM custom_fonts')
    active_fonts = cursor.fetchall()
    conn.close()

    msg = "<b>فونت‌های فعال:</b>\n"
    if active_fonts:
        for font_id, font_name in active_fonts:
            msg += f"  - {font_id}: {font_name}\n"
    else:
        msg += "  <i>هیچ فونتی فعال نیست.</i>\n"
    
    msg += "\n<b>فونت‌های پیش‌فرض قابل اضافه کردن:</b>\n"
    for font_id, font_data in FONTS.items():
        # Only show if not already active
        if font_id not in [f[0] for f in active_fonts]:
            sample_text = "00:00 ABC abc"
            # Ensure 'map' key exists for samples, fallback to 'normal'
            mapped_sample = "".join([font_data['map'][font_data['normal'].find(char)] if char in font_data['normal'] else char for char in sample_text])
            msg += f"  - {font_id}: {font_data['name']} (نمونه: {mapped_sample})\n"

    await event.edit(msg, parse_mode='html')

@command_handler.command("اضافه کردن فونت", description="اضافه کردن فونت جدید به لیست فعال", allow_edited=True)
async def add_font(event, args):
    """Adds a predefined font to the active list for use."""
    try:
        font_id = int(args.strip())
        if font_id not in FONTS:
            await event.edit(f"❌ فونت شماره {font_id} یافت نشد. لطفا یک شماره معتبر از لیست فونت‌های پیش‌فرض انتخاب کنید.", parse_mode='html')
            return
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        font_data = FONTS[font_id]
        cursor.execute('''INSERT INTO custom_fonts (id, font_name, font_map) VALUES (?, ?, ?)''',
                       (font_id, font_data['name'], json.dumps(font_data))) # Store mapping as JSON
        conn.commit()
        conn.close()
        await event.edit(f"✅ فونت <b>{font_data['name']}</b> (شماره {font_id}) اضافه شد.", parse_mode='html')
    except ValueError:
        await event.edit("❌ Usage: `.اضافه کردن فونت [شماره]`", parse_mode='html')
    except sqlite3.IntegrityError:
        await event.edit(f"ℹ️ فونت شماره {font_id} قبلا اضافه شده است.", parse_mode='html')
    except Exception as e:
        await event.edit(f"❌ Error adding font: {e}", parse_mode='html')

@command_handler.command("حذف فونت", description="حذف فونت از لیست فعال", allow_edited=True)
async def remove_font(event, args):
    """Removes an active font from the list."""
    try:
        font_id = int(args.strip())
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''DELETE FROM custom_fonts WHERE id = ?''', (font_id,))
        if cursor.rowcount > 0:
            await event.edit(f"✅ فونت شماره {font_id} حذف شد.", parse_mode='html')
        else:
            await event.edit(f"ℹ️ فونت شماره {font_id} یافت نشد.", parse_mode='html')
        conn.commit()
        conn.close()
    except ValueError:
        await event.edit("❌ Usage: `.حذف فونت [شماره]`", parse_mode='html')
    except Exception as e:
        await event.edit(f"❌ Error removing font: {e}", parse_mode='html')

@command_handler.command("انواع فونت ساعت", description="نمایش ساعت با تمام فونت‌ها", allow_edited=True)
async def show_all_font_clocks(event, args):
    """Displays the current time formatted with all available predefined fonts."""
    now = datetime.datetime.now().strftime("%H:%M")
    msg = "<b>نمایش ساعت با تمام فونت‌های موجود:</b>\n"
    
    # Iterate through all integer keys in FONTS
    for font_id in sorted([k for k in FONTS.keys() if isinstance(k, int)]):
        msg += f"{font_id}- {apply_font(now, font_id)}\n"
    
    await event.edit(msg, parse_mode='html')

# --- Reaction Management ---
@command_handler.command("reaction", description="روشن/خاموش کردن ریاکشن", allow_edited=True)
async def toggle_reaction(event, args):
    """Toggles the auto-reaction feature."""
    if args.lower() == "on":
        set_setting('reaction_on', '1')
        await event.edit("✅ Reaction: <b>ON</b>", parse_mode='html')
    elif args.lower() == "off":
        set_setting('reaction_on', '0')
        await event.edit("✅ Reaction: <b>OFF</b>", parse_mode='html')
    else:
        await event.edit("❌ Usage: `.reaction on | off`", parse_mode='html')

@command_handler.command("لیست ریاکشن", description="نمایش لیست ریاکشن های فعال", allow_edited=True)
async def list_reaction_targets(event, args):
    """Lists entities to which the self-bot will auto-react."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT entity_id FROM reaction_targets WHERE enabled = 1')
    target_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not target_ids:
        await event.edit("ℹ️ هیچ فرد یا گروهی برای ریاکشن فعال نیست.", parse_mode='html')
        return

    msg = "<b>فرد/گروه‌هایی که به پیام‌هایشان ریاکشن داده می‌شود:</b>\n"
    for entity_id in target_ids:
        try:
            entity = await client.get_entity(entity_id)
            name = getattr(entity, 'first_name', getattr(entity, 'title', 'Unknown'))
            msg += f"  - [{name}](tg://user?id={entity_id}) (ID: {entity_id})\n"
        except Exception:
            msg += f"  - Unknown Entity (ID: {entity_id})\n"
    await event.edit(msg, parse_mode='html')

@command_handler.command("تنظیم ریاکشن", description="اضافه کردن فرد یا گروه برای دریافت ریاکشن", allow_edited=True)
async def add_reaction_target(event, args):
    """Adds an entity to the list of auto-reaction targets."""
    await event.delete()
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Could not find user/chat. Please provide a valid ID, username, or reply.", reply_to=event.id)
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''INSERT OR REPLACE INTO reaction_targets (entity_id, enabled) VALUES (?, 1)''', (target_id,))
        conn.commit()
        await client.send_message(event.chat_id, f"✅ Entity [{target_entity.first_name if isinstance(target_entity, User) else target_entity.title}](tg://user?id={target_id}) added to reaction targets.", parse_mode='md', reply_to=event.id)
    except Exception as e:
        await client.send_message(event.chat_id, f"❌ Error adding reaction target: {e}", reply_to=event.id)
    conn.close()

@command_handler.command("حذف ریاکشن", description="حذف فرد یا گروه از لیست ریاکشن", allow_edited=True)
async def remove_reaction_target(event, args):
    """Removes an entity from the list of auto-reaction targets."""
    await event.delete()
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_entity or not target_id:
        await client.send_message(event.chat_id, "❌ Could not find user/chat. Please provide a valid ID, username, or reply.", reply_to=event.id)
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM reaction_targets WHERE entity_id = ?''', (target_id,))
    if cursor.rowcount > 0:
        await client.send_message(event.chat_id, f"✅ Entity [{target_entity.first_name if isinstance(target_entity, User) else target_entity.title}](tg://user?id={target_id}) removed from reaction targets.", parse_mode='md', reply_to=event.id)
    else:
        await client.send_message(event.chat_id, f"ℹ️ Entity [{target_entity.first_name if isinstance(target_entity, User) else target_entity.title}](tg://user?id={target_id}) not found in reaction targets.", parse_mode='md', reply_to=event.id)
    conn.commit()
    conn.close()

@command_handler.command("set reaction", description="تنظیم ایموجی ریاکشن", allow_edited=True)
async def set_reaction_emoji(event, args):
    """Sets the default emoji for auto-reactions."""
    if not args:
        await event.edit("❌ Usage: `.set reaction [emoji]` (e.g., `.set reaction 👍`)", parse_mode='html')
        return
    
    # Basic validation for emoji (can be improved)
    # This regex is a simple attempt; full emoji detection is complex.
    if len(args.strip()) > 10: # Likely not a single emoji if too long
        await event.edit("❌ Please provide a single valid emoji.", parse_mode='html')
        return
        
    set_setting('reaction_emoji', args.strip())
    await event.edit(f"✅ Reaction emoji set to: <b>{args.strip()}</b>", parse_mode='html')

# --- View Edited/Deleted Messages ---
@command_handler.command("view edit", description="روشن/خاموش کردن دیدن پیام های ادیت شده", allow_edited=True)
async def toggle_view_edit(event, args):
    """Toggles logging of edited messages."""
    if args.lower() == "on":
        set_setting('view_edit_on', '1')
        await event.edit("✅ Viewing edited messages: <b>ON</b>", parse_mode='html')
    elif args.lower() == "off":
        set_setting('view_edit_on', '0')
        await event.edit("✅ Viewing edited messages: <b>OFF</b>", parse_mode='html')
    else:
        await event.edit("❌ Usage: `.view edit on | off`", parse_mode='html')

@command_handler.command("view del", description="روشن/خاموش کردن دیدن پیام های حذف شده", allow_edited=True)
async def toggle_view_del(event, args):
    """Toggles logging of deleted messages."""
    if args.lower() == "on":
        set_setting('view_del_on', '1')
        await event.edit("✅ Viewing deleted messages: <b>ON</b>", parse_mode='html')
    elif args.lower() == "off":
        set_setting('view_del_on', '0')
        await event.edit("✅ Viewing deleted messages: <b>OFF</b>", parse_mode='html')
    else:
        await event.edit("❌ Usage: `.view del on | off`", parse_mode='html')

@command_handler.command("view all", description="روشن/خاموش کردن دیدن پیام های حذف / ادیت شده در سطح گروه ها", allow_edited=True)
async def toggle_view_all(event, args):
    """Toggles logging of all edits/deletions across all chats (groups/channels)."""
    if args.lower() == "on":
        set_setting('view_all_on', '1')
        await event.edit("✅ Viewing all edits/deletions (groups/channels): <b>ON</b>", parse_mode='html')
    elif args.lower() == "off":
        set_setting('view_all_on', '0')
        await event.edit("✅ Viewing all edits/deletions (groups/channels): <b>OFF</b>", parse_mode='html')
    else:
        await event.edit("❌ Usage: `.view all on | off`", parse_mode='html')

@command_handler.command("ایدی ربات گزارش", description="تنظیم ایدی ربات گزارش", allow_edited=True)
async def set_report_bot_id(event, args):
    """Sets the ID of the bot or chat to which reports of edits/deletions are sent."""
    if not args:
        await event.edit("❌ Usage: `.ایدی ربات گزارش [user_id/username]`", parse_mode='html')
        return
    
    target_entity, target_id = await parse_entity_from_message(event, args)

    if not target_id:
        await event.edit("❌ Could not find entity. Please provide a valid ID or username.", parse_mode='html')
        return
    
    set_setting('report_bot_id', str(target_id))
    await event.edit(f"✅ Report bot/chat ID set to: <b>{target_id}</b>", parse_mode='html')

# --- Message Sending and Spam Commands ---
async def send_message_or_file(client_instance, peer, message=None, file=None, count=1, delete_after_send=False, add_counter=False, delay=0.5):
    """
    Helper function to send messages/files repeatedly, with options for deletion and counter.
    """
    sent_messages = []
    for i in range(count):
        text_to_send = message
        if add_counter:
            text_to_send = f"{message or ''} ({i+1})"
        
        try:
            msg_obj = None
            if file:
                msg_obj = await client_instance.send_file(peer, file, caption=text_to_send)
            elif text_to_send:
                msg_obj = await client_instance.send_message(peer, text_to_send)
            else:
                continue # Nothing to send

            if msg_obj:
                sent_messages.append(msg_obj)
                if delete_after_send:
                    await async_safe_delete_message(msg_obj, client_instance)
            await asyncio.sleep(delay)
        except FloodWaitError as e:
            logger.warning(f"Flood wait during send_message_or_file: {e.seconds}s. Pausing.")
            await asyncio.sleep(e.seconds + 1) # Add a small buffer
        except Exception as e:
            logger.error(f"Error sending message in loop: {e}")
            break # Exit loop on error
    return sent_messages

@command_handler.command("send", description="ارسال پیام یا فایل چندباره")
@command_handler.command("spam", description="ارسال پیام یا فایل چندباره")
@command_handler.command("اسپم", description="ارسال پیام یا فایل چندباره")
async def send_spam_command(event, args):
    """Sends a message or file multiple times."""
    await event.delete()
    reply_message = await event.get_reply_message()
    
    count = 1
    text_to_send = None
    file_to_send = None

    if reply_message:
        # If replying, args can be count and optional additional text
        parts = args.split(maxsplit=1)
        if parts and parts[0].isdigit():
            count = int(parts[0])
            text_to_send = parts[1] if len(parts) > 1 else None
        else:
            text_to_send = args if args else None
        
        # Prefer replied message's text/media
        text_to_send = text_to_send or reply_message.text
        file_to_send = reply_message.media
    else:
        # Not replying, args contains count and text
        parts = args.split(maxsplit=1)
        if not parts:
            await client.send_message(event.chat_id, "❌ Usage: `.send [count] [text]` or reply to a message/file.", reply_to=event.id)
            return
        
        if parts[0].isdigit():
            count = int(parts[0])
            text_to_send = parts[1] if len(parts) > 1 else None
        else:
            count = 1
            text_to_send = args

    if not text_to_send and not file_to_send:
        await client.send_message(event.chat_id, "❌ Please provide text or reply to a message/file to send.", reply_to=event.id)
        return

    delay = float(get_setting('spam_speed', '0.5'))
    
    await client.send_message(event.chat_id, f"🔄 Sending {count} messages...", reply_to=event.id)
    await send_message_or_file(
        client,
        event.chat_id,
        message=text_to_send,
        file=file_to_send,
        count=count,
        delay=delay
    )

@command_handler.command("psend", description="ارسال پیام شماره‌دار")
async def psend_command(event, args):
    """Sends numbered messages."""
    await event.delete()
    reply_message = await event.get_reply_message()
    
    count = 1
    base_text = None

    if reply_message:
        parts = args.split(maxsplit=1)
        if parts and parts[0].isdigit():
            count = int(parts[0])
            base_text = parts[1] if len(parts) > 1 else reply_message.text
        else:
            base_text = args if args else reply_message.text
    else:
        parts = args.split(maxsplit=1)
        if not parts:
            await client.send_message(event.chat_id, "❌ Usage: `.psend [count] [text]` or reply to a message.", reply_to=event.id)
            return
        
        if parts[0].isdigit():
            count = int(parts[0])
            base_text = parts[1] if len(parts) > 1 else None
        else:
            count = 1
            base_text = args

    if not base_text:
        await client.send_message(event.chat_id, "❌ Please provide text or reply to a message to send.", reply_to=event.id)
        return

    delay = float(get_setting('spam_speed', '0.5'))

    await client.send_message(event.chat_id, f"🔄 Sending {count} numbered messages...", reply_to=event.id)
    for i in range(count):
        full_text = f"{base_text} ({i+1})"
        try:
            await client.send_message(event.chat_id, full_text)
            await asyncio.sleep(delay)
        except FloodWaitError as e:
            logger.warning(f"Flood wait during psend: {e.seconds}s. Pausing.")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            logger.error(f"Error during psend: {e}")
            break

@command_handler.command("gsend", description="ارسال به گروه دیگر")
async def gsend_command(event, args):
    """Sends a message or file to another group/chat."""
    await event.delete()
    reply_message = await event.get_reply_message()
    
    parts = args.split(maxsplit=2)
    if len(parts) < 2:
        await client.send_message(event.chat_id, "❌ Usage: `.gsend [group_id/username] [count] [text]` or reply: `.gsend [group_id/username] [count]`", reply_to=event.id)
        return
    
    target_chat_str = parts[0]
    try:
        count = int(parts[1])
        message_text = parts[2] if len(parts) > 2 else (reply_message.text if reply_message else None)
    except ValueError:
        await client.send_message(event.chat_id, "❌ Invalid count. Usage: `.gsend [group_id/username] [count] [text]`", reply_to=event.id)
        return

    target_entity, target_id = await get_user_id(client, target_chat_str)
    if not target_id:
        await client.send_message(event.chat_id, f"❌ Could not find target group/channel '{target_chat_str}'.", reply_to=event.id)
        return

    if not message_text and not reply_message:
        await client.send_message(event.chat_id, "❌ Please provide text or reply to a message/file to send.", reply_to=event.id)
        return

    delay = float(get_setting('spam_speed', '0.5'))

    await client.send_message(event.chat_id, f"🔄 Sending {count} messages to {target_chat_str}...", reply_to=event.id)
    await send_message_or_file(
        client,
        target_id,
        message=message_text,
        file=reply_message.media if reply_message else None,
        count=count,
        delay=delay
    )

@command_handler.command("dgsend", description="ارسال و حذف فوری در گروه")
async def dgsend_command(event, args):
    """Sends a message to another group and deletes each message immediately after sending."""
    await event.delete()
    reply_message = await event.get_reply_message()
    
    parts = args.split(maxsplit=2)
    if len(parts) < 2:
        await client.send_message(event.chat_id, "❌ Usage: `.dgsend [group_id/username] [count] [text]` or reply: `.dgsend [group_id/username] [count]`", reply_to=event.id)
        return
    
    target_chat_str = parts[0]
    try:
        count = int(parts[1])
        message_text = parts[2] if len(parts) > 2 else (reply_message.text if reply_message else None)
    except ValueError:
        await client.send_message(event.chat_id, "❌ Invalid count. Usage: `.dgsend [group_id/username] [count] [text]`", reply_to=event.id)
        return

    target_entity, target_id = await get_user_id(client, target_chat_str)
    if not target_id:
        await client.send_message(event.chat_id, f"❌ Could not find target group/channel '{target_chat_str}'.", reply_to=event.id)
        return

    if not message_text and not reply_message:
        await client.send_message(event.chat_id, "❌ Please provide text or reply to a message/file to send.", reply_to=event.id)
        return

    delay = float(get_setting('spam_speed', '0.5'))

    await client.send_message(event.chat_id, f"🔄 Sending {count} messages to {target_chat_str} and deleting immediately...", reply_to=event.id)
    await send_message_or_file(
        client,
        target_id,
        message=message_text,
        file=reply_message.media if reply_message else None,
        count=count,
        delete_after_send=True,
        delay=delay
    )

@command_handler.command("dgsend2", description="ارسال همه پیام‌ها و حذف همزمان")
async def dgsend2_command(event, args):
    """Sends multiple messages to another group and deletes them all after all messages are sent."""
    await event.delete()
    reply_message = await event.get_reply_message()
    
    parts = args.split(maxsplit=2)
    if len(parts) < 2:
        await client.send_message(event.chat_id, "❌ Usage: `.dgsend2 [group_id/username] [count] [text]` or reply: `.dgsend2 [group_id/username] [count]`", reply_to=event.id)
        return
    
    target_chat_str = parts[0]
    try:
        count = int(parts[1])
        message_text = parts[2] if len(parts) > 2 else (reply_message.text if reply_message else None)
    except ValueError:
        await client.send_message(event.chat_id, "❌ Invalid count. Usage: `.dgsend2 [group_id/username] [count] [text]`", reply_to=event.id)
        return

    target_entity, target_id = await get_user_id(client, target_chat_str)
    if not target_id:
        await client.send_message(event.chat_id, f"❌ Could not find target group/channel '{target_chat_str}'.", reply_to=event.id)
        return

    if not message_text and not reply_message:
        await client.send_message(event.chat_id, "❌ Please provide text or reply to a message/file to send.", reply_to=event.id)
        return

    delay = float(get_setting('spam_speed', '0.5'))

    await client.send_message(event.chat_id, f"🔄 Sending {count} messages to {target_chat_str} and collecting for bulk deletion...", reply_to=event.id)
    sent_msgs = []
    for i in range(count):
        try:
            msg_obj = None
            if reply_message and reply_message.media:
                msg_obj = await client.send_file(target_id, reply_message.media, caption=message_text)
            elif message_text:
                msg_obj = await client.send_message(target_id, message_text)
            
            if msg_obj:
                sent_msgs.append(msg_obj)
            await asyncio.sleep(delay)
        except FloodWaitError as e:
            logger.warning(f"Flood wait during dgsend2 (send phase): {e.seconds}s. Pausing.")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            logger.error(f"Error during dgsend2 (send phase): {e}")
            break
    
    if sent_msgs:
        try:
            await client.delete_messages(target_id, [m.id for m in sent_msgs])
            await client.send_message(event.chat_id, f"✅ All {len(sent_msgs)} messages sent to {target_chat_str} have been deleted.", reply_to=event.id)
        except Exception as e:
            await client.send_message(event.chat_id, f"❌ Failed to delete all messages from {target_chat_str}: {e}", reply_to=event.id)
    else:
        await client.send_message(event.chat_id, "ℹ️ No messages were successfully sent for bulk deletion.", reply_to=event.id)

@command_handler.command("dsend", description="ارسال و حذف فوری در همین چت")
async def dsend_command(event, args):
    """Sends a message to the current chat and deletes each message immediately after sending."""
    await event.delete()
    reply_message = await event.get_reply_message()
    
    count = 1
    text_to_send = None

    if reply_message:
        parts = args.split(maxsplit=1)
        if parts and parts[0].isdigit():
            count = int(parts[0])
            text_to_send = parts[1] if len(parts) > 1 else reply_message.text
        else:
            text_to_send = args if args else reply_message.text
    else:
        parts = args.split(maxsplit=1)
        if not parts:
            await client.send_message(event.chat_id, "❌ Usage: `.dsend [count] [text]` or reply to a message.", reply_to=event.id)
            return
        
        if parts[0].isdigit():
            count = int(parts[0])
            text_to_send = parts[1] if len(parts) > 1 else None
        else:
            count = 1
            text_to_send = args

    if not text_to_send:
        await client.send_message(event.chat_id, "❌ Please provide text or reply to a message to send.", reply_to=event.id)
        return

    delay = float(get_setting('spam_speed', '0.5'))

    await client.send_message(event.chat_id, f"🔄 Sending {count} messages and deleting immediately...", reply_to=event.id)
    await send_message_or_file(
        client,
        event.chat_id,
        message=text_to_send,
        file=None, # dsend is text only as per manual's example implying text
        count=count,
        delete_after_send=True,
        delay=delay
    )

@command_handler.command("dsend2", description="ارسال و حذف با فایل یا متن")
async def dsend2_command(event, args):
    """Sends a file or text message to the current chat and deletes each message immediately after sending."""
    await event.delete()
    reply_message = await event.get_reply_message()
    
    count = 1
    text_to_send = None
    file_to_send = None

    if reply_message:
        parts = args.split(maxsplit=1)
        if parts and parts[0].isdigit():
            count = int(parts[0])
            text_to_send = parts[1] if len(parts) > 1 else reply_message.text
        else:
            text_to_send = args if args else reply_message.text

        file_to_send = reply_message.media
    else:
        parts = args.split(maxsplit=1)
        if not parts:
            await client.send_message(event.chat_id, "❌ Usage: `.dsend2 [count] [text]` or reply to a message/file.", reply_to=event.id)
            return
        
        if parts[0].isdigit():
            count = int(parts[0])
            text_to_send = parts[1] if len(parts) > 1 else None
        else:
            count = 1
            text_to_send = args

    if not text_to_send and not file_to_send:
        await client.send_message(event.chat_id, "❌ Please provide text or reply to a message/file to send.", reply_to=event.id)
        return

    delay = float(get_setting('spam_speed', '0.5'))

    await client.send_message(event.chat_id, f"🔄 Sending {count} messages/files and deleting immediately...", reply_to=event.id)
    await send_message_or_file(
        client,
        event.chat_id,
        message=text_to_send,
        file=file_to_send,
        count=count,
        delete_after_send=True,
        delay=delay
    )

@command_handler.command("سرعت", description="تنظیم فاصله زمانی بین ارسال‌های اسپم", allow_edited=True)
async def set_spam_speed(event, args):
    """Sets the delay between messages for spam commands."""
    try:
        speed = float(args.strip())
        if speed < 0:
            raise ValueError("Speed cannot be negative.")
        set_setting('spam_speed', str(speed))
        await event.edit(f"✅ Spam speed set to <b>{speed}</b> seconds.", parse_mode='html')
    except ValueError:
        await event.edit("❌ Usage: `.سرعت [عدد (ثانیه)]` (e.g., `.سرعت 0.5`)", parse_mode='html')
    except Exception as e:
        await event.edit(f"❌ Error setting spam speed: {e}", parse_mode='html')


# --- 7. Event Handlers ---

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handle_private_message(event):
    """
    Handles incoming private messages, primarily for auto-reply and multi-step setup.
    """
    me = await client.get_me()
    if event.sender_id == me.id:
        # Ignore messages from self if it's a command being handled
        if event.raw_text and event.raw_text.lower().startswith(PREFIX.lower()):
            await command_handler.handle_message(event)
        return

    # Check for 'self-mute' (special list)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM special_users WHERE user_id = ?', (event.sender_id,))
    is_muted_self = cursor.fetchone()
    conn.close()
    if is_muted_self:
        logger.info(f"Ignoring message from self-muted user: {event.sender_id}")
        return

    # Handle multi-step auto-reply setup
    if event.sender_id in auto_reply_state.active_user_setup:
        state_data = auto_reply_state.active_user_setup[event.sender_id]
        if state_data['state'] == 'waiting_for_id':
            target_entity, target_id = await parse_entity_from_message(event, event.raw_text.strip())
            if target_id:
                state_data['temp_id'] = target_id
                state_data['state'] = 'waiting_for_message'
                await event.reply(f"✅ شناسه کاربری <code>{target_id}</code> تنظیم شد. حالا پیام یا رسانه مورد نظر برای پاسخ را ارسال کنید.", parse_mode='html')
            else:
                await event.reply("❌ شناسه کاربری نامعتبر. لطفا دوباره تلاش کنید.")
            return
        elif state_data['state'] == 'waiting_for_message':
            target_id = state_data['temp_id']
            response_text = event.text
            response_media_path = None

            if event.media:
                media_path = await client.download_media(event.media, file=f"auto_reply_media_{target_id}_{int(time.time())}")
                response_media_path = media_path
                response_text = event.raw_text # Use caption if any

            if not response_text and not response_media_path:
                await event.reply("❌ پیام یا رسانه خالی است. لطفا دوباره تلاش کنید.")
                return
            
            # Save the specific auto-reply
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO auto_replies (trigger_text, response_text, response_media_path, exact_match, specific_peer_id) VALUES (?, ?, ?, ?, ?)''',
                           (f"specific_monshi_{target_id}", response_text, response_media_path, True, target_id)) # Using a unique trigger for specific replies
            conn.commit()
            conn.close()
            await event.reply(f"✅ پاسخ خودکار برای <code>{target_id}</code> با موفقیت تنظیم شد.", parse_mode='html')
            del auto_reply_state.active_user_setup[event.sender_id] # Clear state
            return

    # Auto-reply (Monshi) logic
    if get_setting('monshi_enabled') == '1':
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Check for specific auto-replies for this sender first
        cursor.execute('SELECT response_text, response_media_path FROM auto_replies WHERE specific_peer_id = ? AND enabled = 1 LIMIT 1', (event.sender_id,))
        specific_reply = cursor.fetchone()
        if specific_reply:
            response_text, response_media_path = specific_reply
            if response_media_path and os.path.exists(response_media_path):
                await client.send_file(event.chat_id, response_media_path, caption=response_text)
            elif response_text:
                await event.reply(response_text)
            conn.close()
            return # Specific reply sent

        # Check for general auto-replies (exact match)
        cursor.execute('SELECT response_text, response_media_path FROM auto_replies WHERE exact_match = 1 AND trigger_text = ? AND specific_peer_id IS NULL AND enabled = 1 LIMIT 1', (event.text,))
        exact_match_reply = cursor.fetchone()
        if exact_match_reply:
            response_text, response_media_path = exact_match_reply
            if response_media_path and os.path.exists(response_media_path):
                await client.send_file(event.chat_id, response_media_path, caption=response_text)
            elif response_text:
                await event.reply(response_text)
            conn.close()
            return # Exact match reply sent

        # Check for general auto-replies (inclusive match)
        cursor.execute('SELECT response_text, response_media_path FROM auto_replies WHERE exact_match = 0 AND ? LIKE \'%\' || trigger_text || \'%\' AND specific_peer_id IS NULL AND enabled = 1 LIMIT 1', (event.text,))
        inclusive_match_reply = cursor.fetchone()
        if inclusive_match_reply:
            response_text, response_media_path = inclusive_match_reply
            if response_media_path and os.path.exists(response_media_path):
                await client.send_file(event.chat_id, response_media_path, caption=response_text)
            elif response_text:
                await event.reply(response_text)
            conn.close()
            return # Inclusive match reply sent

        # If no specific or custom reply, send default monshi message if configured
        default_monshi = get_setting('default_monshi_response')
        if default_monshi:
            await event.reply(default_monshi)
        conn.close()


@client.on(events.NewMessage(incoming=True))
async def handle_all_new_messages(event):
    """
    Handles all incoming messages for command parsing and auto-reaction.
    This runs after handle_private_message for commands, but includes auto-reaction logic.
    """
    me = await client.get_me()
    if event.sender_id == me.id:
        # Commands are handled in command_handler.handle_message directly within the main `on(events.NewMessage)`
        # if the message starts with the prefix.
        if event.raw_text and event.raw_text.lower().startswith(PREFIX.lower()):
            # This is already handled by `handle_private_message` if in private chat.
            # For group commands, we need to explicitly call here if not already processed.
            # To avoid double processing, `handle_message` should be smart about the `event.sender_id == me.id` check.
            pass # Commands from self are handled by `command_handler.handle_message` via the filter below for all messages
    else:
        # Process commands from self
        if event.raw_text and event.raw_text.lower().startswith(PREFIX.lower()):
            await command_handler.handle_message(event)
            return # Don't process other logic if it was a command

        # Check for auto-reaction
        if get_setting('reaction_on') == '1':
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM reaction_targets WHERE entity_id = ? AND enabled = 1', (event.chat_id,))
            react_to_chat = cursor.fetchone()
            cursor.execute('SELECT 1 FROM reaction_targets WHERE entity_id = ? AND enabled = 1', (event.sender_id,))
            react_to_sender = cursor.fetchone()
            conn.close()

            if react_to_chat or react_to_sender:
                reaction_emoji = get_setting('reaction_emoji', '👍')
                try:
                    # Telegram reactions can be sent to messages.
                    # SendReactionRequest requires message ID and peer.
                    await client(SendReactionRequest(
                        peer=event.chat_id,
                        msg_id=event.id,
                        reaction=[ReactionEmoji(emoticon=reaction_emoji)]
                    ))
                    logger.info(f"Reacted to message {event.id} from {event.sender_id} in {event.chat_id} with {reaction_emoji}")
                except Exception as e:
                    logger.error(f"Failed to send reaction: {e}")

@client.on(events.MessageEdited(incoming=True, outgoing=False))
async def handle_message_edited(event):
    """Logs edited messages to a report chat if enabled."""
    if get_setting('view_edit_on') == '1' or (get_setting('view_all_on') == '1' and (event.is_group or event.is_channel)):
        report_chat_id = get_setting('report_bot_id')
        if report_chat_id:
            try:
                original_message = (await client(GetMessagesRequest(peer=event.chat_id, id=[event.id]))).messages[0]
                if original_message and original_message.text:
                    sender = await event.get_sender()
                    sender_name = utils.get_display_name(sender)
                    chat_name = utils.get_display_name(await event.get_chat())
                    report_msg = (
                        f"✏️ <b>Message Edited</b> in {chat_name} (<code>{event.chat_id}</code>)\n"
                        f"  <b>From:</b> [{sender_name}](tg://user?id={event.sender_id})\n"
                        f"  <b>Original:</b> <code>{original_message.text}</code>\n"
                        f"  <b>New:</b> <code>{event.text}</code>\n"
                        f"  <b>Link:</b> <a href='{event.message.url}'>View Message</a>"
                    )
                    await client.send_message(int(report_chat_id), report_msg, parse_mode='html', link_preview=False)
            except Exception as e:
                logger.error(f"Error logging edited message: {e}")

@client.on(events.Raw) # Using Raw event to catch deleted messages more reliably
async def handle_message_deleted(event):
    """Logs deleted messages to a report chat if enabled."""
    if isinstance(event, events.MessageDeleted):
        if get_setting('view_del_on') == '1' or (get_setting('view_all_on') == '1' and event.chat_id and (await client.get_entity(event.chat_id)).is_group or (await client.get_entity(event.chat_id)).is_channel):
            report_chat_id = get_setting('report_bot_id')
            if report_chat_id:
                for msg_id in event.deleted_ids:
                    try:
                        # Attempt to retrieve the message content from local cache or a history-keeping mechanism
                        # Telethon does not store deleted messages. This is a best-effort, usually requires a separate message logger.
                        # For this bot, we can't reliably get the *content* of a deleted message unless it was already processed.
                        chat_entity = await client.get_entity(event.chat_id) if event.chat_id else "Unknown Chat"
                        chat_name = utils.get_display_name(chat_entity) if isinstance(chat_entity, (Chat, Channel)) else str(chat_entity)

                        report_msg = (
                            f"🗑️ <b>Message Deleted</b> in {chat_name} (<code>{event.chat_id}</code>)\n"
                            f"  <b>Message ID:</b> <code>{msg_id}</code>\n"
                            f"  <i>(Content unavailable as Telegram API does not provide deleted message content)</i>"
                        )
                        await client.send_message(int(report_chat_id), report_msg, parse_mode='html')
                    except Exception as e:
                        logger.error(f"Error logging deleted message (ID: {msg_id}): {e}")

# --- 8. Scheduled Background Tasks ---
async def update_profile_task():
    """Background task to update profile name/bio with time or custom text."""
    while True:
        await asyncio.sleep(60) # Update every minute

        me = await client.get_me()
        current_first_name = me.first_name
        current_last_name = me.last_name
        current_bio = me.about

        # Update Name with Clock
        if get_setting('clock_in_name') == '1':
            now = datetime.datetime.now().strftime("%H:%M")
            new_first_name = f"{now} {me.first_name.split(' ', 1)[1] if ' ' in me.first_name else 'User'}"
            if new_first_name != current_first_name:
                try:
                    await client(UpdateProfileRequest(first_name=new_first_name, last_name=current_last_name))
                except MessageNotModifiedError:
                    pass # Name already updated or not changed
                except Exception as e:
                    logger.error(f"Error updating name with clock: {e}")
        
        # Update Bio with Clock or Custom Text
        if get_setting('bio_auto_text') == '1':
            custom_bio_text = get_setting('custom_bio_text')
            if custom_bio_text and custom_bio_text != current_bio:
                try:
                    await client(UpdateProfileRequest(about=custom_bio_text))
                except MessageNotModifiedError:
                    pass
                except Exception as e:
                    logger.error(f"Error updating bio with custom text: {e}")
        elif get_setting('clock_in_bio') == '1':
            now = datetime.datetime.now().strftime("%H:%M:%S")
            new_bio = f"Current Time: {now}"
            if new_bio != current_bio:
                try:
                    await client(UpdateProfileRequest(about=new_bio))
                except MessageNotModifiedError:
                    pass
                except Exception as e:
                    logger.error(f"Error updating bio with clock: {e}")

        # Run anti-login check
        await check_active_sessions_task()

# --- 9. Main Execution Block ---
async def main():
    """Main function to start the self-bot."""
    init_db() # Initialize database at startup

    if not API_ID or not API_HASH or API_ID == 'YOUR_API_ID_HERE':
        logger.critical("API_ID and API_HASH are not set. Please get them from my.telegram.org and update the script or environment variables.")
        sys.exit(1)

    print("Connecting to Telegram...")
    try:
        await client.start()
        if not await client.is_user_authorized():
            print("Please log in:")
            await client.run_until_disconnected()
        else:
            me = await client.get_me()
            print(f"Self-bot started for @{me.username or me.first_name} (ID: {me.id})!")
            logger.info(f"Self-bot started for @{me.username or me.first_name} (ID: {me.id})!")
            
            # Start background tasks
            asyncio.create_task(update_profile_task())

            await client.run_until_disconnected()
    except SessionPasswordNeededError:
        password = input("2FA required: Enter password: ")
        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            print(f"Self-bot restarted for @{me.username or me.first_name} (ID: {me.id})!")
            logger.info(f"Self-bot restarted for @{me.username or me.first_name} (ID: {me.id})!")
            asyncio.create_task(update_profile_task())
            await client.run_until_disconnected()
        except Exception as e:
            logger.critical(f"Failed to log in with 2FA password: {e}")
            sys.exit(1)
    except Exception as e:
        logger.critical(f"An error occurred during client start: {e}")
        sys.exit(1)

if __name__ == '__main__':
    # Ensure all temporary photo files are cleaned up on start/exit
    for f in os.listdir('.'):
        if f.startswith('profile_photo_backup_') and f.endswith('.jpg'):
            try:
                os.remove(f)
            except OSError as e:
                logger.warning(f"Error removing old backup photo {f}: {e}")

    # Use a custom event loop policy for Windows if needed (optional, helps with some async issues)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
