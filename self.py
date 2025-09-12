from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file immediately

import os
import sys
import asyncio
import logging
import re
import math
import time
import json
import random
import platform
import psutil
from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import urlparse

# External Libraries
try:
    from telethon import TelegramClient, events, functions, types
    from telethon.tl.types import User, Channel, Chat, Message, Document, Photo, Sticker
    from telethon.errors import UserNotParticipantError, ChatAdminRequiredError, MessageIdInvalidError, FloodWaitError, PhotoInvalidError, ChatWriteForbiddenError
    from telethon.tl.functions.channels import GetParticipantRequest
    from telethon.tl.functions.messages import GetHistoryRequest
    from telethon.tl.functions.photos import GetUserPhotosRequest
    from telethon.tl.functions.account import UpdateProfileRequest, UploadProfilePhotoRequest
    from telethon.utils import get_display_name, get_peer_id
except ImportError:
    print("Telethon library not found. Please install it using 'pip install telethon'")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Httpx library not found. Please install it using 'pip install httpx'")
    sys.exit(1)

try:
    import aiosqlite
except ImportError:
    print("Aiosqlite library not found. Please install it using 'pip install aiosqlite'")
    sys.exit(1)

try:
    import pyshorteners
except ImportError:
    print("Pyshorteners library not found. Please install it using 'pip install pyshorteners'")
    sys.exit(1)

try:
    from gtts import gTTS
except ImportError:
    print("gTTS library not found. Please install it using 'pip install gtts'")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow library not found. Please install it using 'pip install Pillow'")
    sys.exit(1)

try:
    import qrcode
except ImportError:
    print("QRCode library not found. Please install it using 'pip install qrcode'")
    sys.exit(1)

try:
    import wikipediaapi
except ImportError:
    print("Wikipedia-API library not found. Please install it using 'pip install wikipedia-api'")
    sys.exit(1)

try:
    # Prefer deep_translator over googletrans_py due to googletrans_py's frequent breakage
    from deep_translator import GoogleTranslator
    Translator = None # Ensure googletrans_py is not used if deep_translator is available
    print("Using deep_translator for translation.")
except ImportError:
    try:
        from googletrans_py import Translator
        GoogleTranslator = None # Ensure deep_translator is not used if googletrans_py is available
        print("Using googletrans_py for translation.")
    except ImportError:
        print("Neither googletrans_py nor deep_translator found. Translation command will not work.")
        GoogleTranslator = None # Placeholder to prevent errors
        Translator = None # Placeholder to prevent errors


# --- 1. Configuration & Constants ---
# Load environment variables
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID", 0))  # Convert to int, default to 0 if not set
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", ".")

# External API Keys (Get these from their respective websites)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
TINYURL_API_KEY = os.getenv("TINYURL_API_KEY") # Optional, TinyURL has a free tier for basic usage
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY") # Required for .google
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX") # Required for .google

# Sanity checks for essential configurations
if not all([API_ID, API_HASH, OWNER_ID]):
    print("Error: Please set API_ID, API_HASH, and OWNER_ID environment variables in your .env file or environment.")
    sys.exit(1)

# Paths
DB_PATH = "userbot.db"
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# Other constants
START_TIME = datetime.now()
AFK_TIMEOUT_SECONDS = 300 # 5 minutes before AFK is considered "stale" for auto-replying

# Define default fonts for image generation (adjust paths as needed on your system)
FONT_PATH = os.getenv("FONT_PATH", None)
if FONT_PATH and not os.path.exists(FONT_PATH):
    print(f"Warning: Custom font at {FONT_PATH} not found. Using default Pillow font.")
    FONT_PATH = None

# --- Command Information for .help command ---
# This dictionary holds all command metadata for the help command and argument validation.
# {COMMAND_KEY: {"short_desc": "brief", "full_desc": "detailed", "owner_only": bool}}
ALL_COMMANDS_INFO = {
    f"{COMMAND_PREFIX}help": {
        "short_desc": "📚 نمایش لیست دستورات یا جزئیات یک دستور.",
        "full_desc": f"`{{COMMAND_PREFIX}}help [command]`: نمایش لیست تمامی دستورات Userbot یا راهنمای دقیق برای یک دستور خاص."
    },
    # A. مدیریت پیام و چت:
    f"{COMMAND_PREFIX}echo": {
        "short_desc": "تکرار متن ارسالی.",
        "full_desc": f"`{{COMMAND_PREFIX}}echo <text>`: متن داده شده را تکرار می‌کند."
    },
    f"{COMMAND_PREFIX}type": {
        "short_desc": "شبیه‌سازی تایپ و ارسال متن.",
        "full_desc": f"`{{COMMAND_PREFIX}}type <text>`: تایپ کردن را شبیه‌سازی کرده و سپس متن را ارسال می‌کند."
    },
    f"{COMMAND_PREFIX}del": {
        "short_desc": "حذف پیام ریپلای شده و دستور.",
        "full_desc": f"`{{COMMAND_PREFIX}}del`: پیام ریپلای شده را به همراه دستور خود حذف می‌کند."
    },
    f"{COMMAND_PREFIX}edit": {
        "short_desc": "ویرایش پیام ریپلای شده با متن جدید.",
        "full_desc": f"`{{COMMAND_PREFIX}}edit <new text>`: پیام ریپلای شده را با متن جدید ویرایش می‌کند. اگر ریپلای نباشد، دستور خود را ویرایش می‌کند."
    },
    f"{COMMAND_PREFIX}purge": {
        "short_desc": "حذف N پیام آخر در چت (نیاز به ادمین).",
        "full_desc": f"`{{COMMAND_PREFIX}}purge <N>`: N پیام آخر را از چت فعلی حذف می‌کند (شامل دستور خود). نیاز به دسترسی ادمین دارد."
    },
    f"{COMMAND_PREFIX}pin": {
        "short_desc": "پین کردن پیام ریپلای شده (نیاز به ادمین).",
        "full_desc": f"`{{COMMAND_PREFIX}}pin`: پیام ریپلای شده را پین می‌کند. نیاز به دسترسی ادمین دارد."
    },
    f"{COMMAND_PREFIX}unpin": {
        "short_desc": "آنپین کردن پیام ریپلای شده یا آخرین پیام پین شده (نیاز به ادمین).",
        "full_desc": f"`{{COMMAND_PREFIX}}unpin`: پیام ریپلای شده را آنپین می‌کند. اگر ریپلای نباشد، آخرین پیام پین شده را آنپین می‌کند. نیاز به دسترسی ادمین دارد."
    },
    f"{COMMAND_PREFIX}fwd": {
        "short_desc": "فوروارد کردن یک پیام به چت/کاربر هدف.",
        "full_desc": f"`{{COMMAND_PREFIX}}fwd <target_chat_id/username> [message_id]`: پیام را به چت یا کاربر هدف فوروارد می‌کند. اگر message_id داده نشود، پیام ریپلای شده فوروارد می‌شود."
    },
    f"{COMMAND_PREFIX}react": {
        "short_desc": "افزودن واکنش (ایموجی) به پیام ریپلای شده.",
        "full_desc": f"`{{COMMAND_PREFIX}}react <emoji>`: یک واکنش (ایموجی) به پیام ریپلای شده اضافه می‌کند."
    },
    f"{COMMAND_PREFIX}spam": {
        "short_desc": "ارسال تعداد مشخصی پیام (با احتیاط استفاده کنید!).",
        "full_desc": f"`{{COMMAND_PREFIX}}spam <count> <text>`: تعداد مشخصی پیام را ارسال می‌کند. با احتیاط فراوان استفاده کنید تا تلگرام شما را محدود نکند (محدودیت 100 پیام).",
        "owner_only": False # For general use, but with internal limits
    },
    # B. بازیابی اطلاعات:
    f"{COMMAND_PREFIX}id": {
        "short_desc": "نمایش ID چت/کاربر فعلی.",
        "full_desc": f"`{{COMMAND_PREFIX}}id`: ID چت فعلی را نمایش می‌دهد. اگر روی پیامی ریپلای شود، ID فرستنده آن پیام را نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}chatinfo": {
        "short_desc": "نمایش اطلاعات چت فعلی.",
        "full_desc": f"`{{COMMAND_PREFIX}}chatinfo`: اطلاعات کاملی در مورد چت فعلی (گروه/کانال/چت خصوصی) نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}userinfo": {
        "short_desc": "نمایش اطلاعات کاربر.",
        "full_desc": f"`{{COMMAND_PREFIX}}userinfo [username/id]`: اطلاعات یک کاربر را نمایش می‌دهد. اگر بدون آرگومان و با ریپلای باشد، اطلاعات کاربر ریپلای شده را نشان می‌دهد."
    },
    f"{COMMAND_PREFIX}adminlist": {
        "short_desc": "لیست ادمین‌های چت (فقط برای گروه‌ها/کانال‌ها).",
        "full_desc": f"`{{COMMAND_PREFIX}}adminlist`: لیستی از ادمین‌های چت فعلی را نمایش می‌دهد (فقط در گروه‌ها و کانال‌ها)."
    },
    f"{COMMAND_PREFIX}me": {
        "short_desc": "نمایش اطلاعات پروفایل خود کاربر.",
        "full_desc": f"`{{COMMAND_PREFIX}}me`: اطلاعات مربوط به حساب کاربری خودتان را نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}whois": {
        "short_desc": "نمایش اطلاعات دقیق‌تر یک کاربر.",
        "full_desc": f"`{{COMMAND_PREFIX}}whois [username/id]`: اطلاعات دقیق‌تر یک کاربر شامل بیوگرافی و تعداد چت‌های مشترک را نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}photo": {
        "short_desc": "دریافت عکس پروفایل کاربر.",
        "full_desc": f"`{{COMMAND_PREFIX}}photo [username/id]`: عکس پروفایل یک کاربر را ارسال می‌کند. اگر بدون آرگومان و با ریپلای باشد، عکس کاربر ریپلای شده را نشان می‌دهد."
    },
    f"{COMMAND_PREFIX}getbio": {
        "short_desc": "دریافت بیوگرافی کاربر.",
        "full_desc": f"`{{COMMAND_PREFIX}}getbio [username/id]`: بیوگرافی یک کاربر را نمایش می‌دهد. اگر بدون آرگومان و با ریپلای باشد، بیو کاربر ریپلای شده را نشان می‌دهد."
    },
    f"{COMMAND_PREFIX}stickerinfo": {
        "short_desc": "نمایش اطلاعات استیکر ریپلای شده.",
        "full_desc": f"`{{COMMAND_PREFIX}}stickerinfo`: اطلاعات استیکر موجود در پیام ریپلای شده را نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}fileinfo": {
        "short_desc": "نمایش اطلاعات فایل/مدیای ریپلای شده.",
        "full_desc": f"`{{COMMAND_PREFIX}}fileinfo`: اطلاعات فایل یا مدیای موجود در پیام ریپلای شده را نمایش می‌دهد."
    },
    # C. ابزارهای کاربردی و سرگرمی:
    f"{COMMAND_PREFIX}calc": {
        "short_desc": "ماشین حساب ساده.",
        "full_desc": f"`{{COMMAND_PREFIX}}calc <expression>`: یک عبارت ریاضی ساده را محاسبه می‌کند."
    },
    f"{COMMAND_PREFIX}short": {
        "short_desc": "کوتاه کردن URL.",
        "full_desc": f"`{{COMMAND_PREFIX}}short <url>`: یک URL طولانی را با استفاده از سرویس‌های کوتاه کننده URL کوتاه می‌کند."
    },
    f"{COMMAND_PREFIX}long": {
        "short_desc": "باز کردن URL کوتاه شده.",
        "full_desc": f"`{{COMMAND_PREFIX}}long <short_url>`: یک URL کوتاه شده را باز کرده و لینک اصلی را نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}weather": {
        "short_desc": "نمایش اطلاعات آب و هوا.",
        "full_desc": f"`{{COMMAND_PREFIX}}weather <city>`: اطلاعات آب و هوا برای شهر مشخص شده را با استفاده از OpenWeatherMap API نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}google": {
        "short_desc": "جستجوی گوگل و نمایش خلاصه.",
        "full_desc": f"`{{COMMAND_PREFIX}}google <query>`: یک کوئری را در گوگل جستجو کرده و نتایج را به صورت خلاصه نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}wiki": {
        "short_desc": "جستجو در ویکی‌پدیا.",
        "full_desc": f"`{{COMMAND_PREFIX}}wiki <query>`: یک کوئری را در ویکی‌پدیا جستجو کرده و خلاصه‌ای از آن را نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}ud": {
        "short_desc": "جستجو در Urban Dictionary.",
        "full_desc": f"`{{COMMAND_PREFIX}}ud <word>`: کلمه مورد نظر را در Urban Dictionary جستجو می‌کند."
    },
    f"{COMMAND_PREFIX}tr": {
        "short_desc": "ترجمه متن به زبان مشخص.",
        "full_desc": f"`{{COMMAND_PREFIX}}tr <lang_code> <text>`: متن را به زبان مقصد (مانند `en` برای انگلیسی) ترجمه می‌کند. می‌توانید روی پیام ریپلای کنید."
    },
    f"{COMMAND_PREFIX}qr": {
        "short_desc": "تولید QR کد از متن.",
        "full_desc": f"`{{COMMAND_PREFIX}}qr <text>`: یک کد QR از متن داده شده تولید کرده و به عنوان عکس ارسال می‌کند."
    },
    f"{COMMAND_PREFIX}tts": {
        "short_desc": "تبدیل متن به گفتار (Text-to-Speech).",
        "full_desc": f"`{{COMMAND_PREFIX}}tts [lang_code] <text>`: متن را به گفتار تبدیل کرده و به عنوان ویس ارسال می‌کند. زبان پیش‌فرض Farsi (fa) است."
    },
    f"{COMMAND_PREFIX}ss": {
        "short_desc": "گرفتن اسکرین‌شات از یک وب‌سایت.",
        "full_desc": f"`{{COMMAND_PREFIX}}ss <url>`: از یک وب‌سایت اسکرین‌شات گرفته و آن را ارسال می‌کند."
    },
    f"{COMMAND_PREFIX}quote": {
        "short_desc": "تولید یک تصویر نقل قول با متن و نام نویسنده.",
        "full_desc": f"`{{COMMAND_PREFIX}}quote <text> [/ <author>]`: یک تصویر نقل قول زیبا از متن و نام نویسنده (اختیاری) تولید می‌کند."
    },
    f"{COMMAND_PREFIX}carbon": {
        "short_desc": "تبدیل کد به تصویر زیبا (Placeholder).",
        "full_desc": f"`{{COMMAND_PREFIX}}carbon <code>`: یک قطعه کد را به یک تصویر زیبا تبدیل می‌کند (این قابلیت نیاز به سرویس Carbon.sh یا جایگزین آن دارد و در این نسخه در حد یک Placeholder است).",
        "owner_only": False # Could be general, but implementation depends on external service
    },
    # D. مدیریت ربات و سیستم (⚠️ بسیار خطرناک ⚠️):
    f"{COMMAND_PREFIX}afk": {
        "short_desc": "فعال/غیرفعال کردن حالت AFK.",
        "full_desc": f"`{{COMMAND_PREFIX}}afk [reason]`: حالت AFK (Away From Keyboard) را فعال می‌کند. اگر کسی به شما پیام دهد، ربات با دلیل مشخص شده پاسخ می‌دهد.",
        "owner_only": False # AFK is a user feature, not owner-only
    },
    f"{COMMAND_PREFIX}ping": {
        "short_desc": "تست زمان تأخیر ربات.",
        "full_desc": f"`{{COMMAND_PREFIX}}ping`: زمان تأخیر (latency) ربات را نسبت به سرور تلگرام اندازه‌گیری می‌کند."
    },
    f"{COMMAND_PREFIX}restart": {
        "short_desc": "راه‌اندازی مجدد Userbot (فقط مالک).",
        "full_desc": f"`{{COMMAND_PREFIX}}restart`: فرآیند Userbot را راه‌اندازی مجدد می‌کند. (فقط برای مالک)",
        "owner_only": True
    },
    f"{COMMAND_PREFIX}stats": {
        "short_desc": "نمایش آمار سیستم (RAM، آپتایم، CPU).",
        "full_desc": f"`{{COMMAND_PREFIX}}stats`: آمار مربوط به مصرف منابع سیستم (مانند RAM، CPU) و مدت زمان فعال بودن Userbot را نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}exec": {
        "short_desc": "اجرای کد پایتون (فقط مالک - ⚠️ خطرناک!).",
        "full_desc": f"`{{COMMAND_PREFIX}}exec <code>`: یک قطعه کد پایتون را مستقیماً بر روی سرور اجرا می‌کند. (فقط برای OWNER_ID - ⚠️ بسیار خطرناک! با مسئولیت خودتان استفاده کنید.)",
        "owner_only": True
    },
    f"{COMMAND_PREFIX}term": {
        "short_desc": "اجرای دستورات شل (فقط مالک - ⚠️ خطرناک!).",
        "full_desc": f"`{{COMMAND_PREFIX}}term <command>`: یک دستور شل (command line) را بر روی سرور اجرا می‌کند. (فقط برای OWNER_ID - ⚠️ بسیار خطرناک! با مسئولیت خودتان استفاده کنید.)",
        "owner_only": True
    },
    f"{COMMAND_PREFIX}sendfile": {
        "short_desc": "ارسال یک فایل از سیستم.",
        "full_desc": f"`{{COMMAND_PREFIX}}sendfile <path_to_file>`: یک فایل از مسیر مشخص شده در سیستم عامل سرور را ارسال می‌کند. (فقط برای OWNER_ID)",
        "owner_only": True
    },
    f"{COMMAND_PREFIX}upload": {
        "short_desc": "آپلود یک فایل از URL.",
        "full_desc": f"`{{COMMAND_PREFIX}}upload <file_url>`: یک فایل را از یک آدرس URL دانلود کرده و به چت فعلی آپلود می‌کند."
    },
    f"{COMMAND_PREFIX}download": {
        "short_desc": "دانلود مدیای ریپلای شده.",
        "full_desc": f"`{{COMMAND_PREFIX}}download`: مدیای موجود در پیام ریپلای شده را دانلود کرده و مسیر ذخیره آن را نمایش می‌دهد."
    },
    f"{COMMAND_PREFIX}setname": {
        "short_desc": "تغییر نام پروفایل تلگرام (فقط مالک).",
        "full_desc": f"`{{COMMAND_PREFIX}}setname <first_name> [last_name]`: نام و نام خانوادگی پروفایل تلگرام شما را تغییر می‌دهد. (فقط برای OWNER_ID)",
        "owner_only": True
    },
    f"{COMMAND_PREFIX}setbio": {
        "short_desc": "تغییر بیوگرافی پروفایل تلگرام (فقط مالک).",
        "full_desc": f"`{{COMMAND_PREFIX}}setbio <new_bio_text>`: بیوگرافی پروفایل تلگرام شما را تغییر می‌دهد. (فقط برای OWNER_ID)",
        "owner_only": True
    },
    f"{COMMAND_PREFIX}setpfp": {
        "short_desc": "تغییر عکس پروفایل تلگرام با عکس ریپلای شده (فقط مالک).",
        "full_desc": f"`{{COMMAND_PREFIX}}setpfp`: عکس پروفایل شما را با عکس موجود در پیام ریپلای شده تغییر می‌دهد. (فقط برای OWNER_ID)",
        "owner_only": True
    },
}

# Post-process ALL_COMMANDS_INFO to replace {COMMAND_PREFIX} placeholder in full_desc
for cmd_key in list(ALL_COMMANDS_INFO.keys()):
    info = ALL_COMMANDS_INFO[cmd_key]
    info["full_desc"] = info["full_desc"].format(COMMAND_PREFIX=COMMAND_PREFIX)


# --- 2. Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s - %(levelname)s] - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# --- 3. Database Setup (SQLite with aiosqlite) ---
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._db = None
        self._lock = asyncio.Lock() # To prevent concurrent writes to SQLite

    async def connect(self):
        async with self._lock:
            if not self._db:
                self._db = await aiosqlite.connect(self.db_path)
                await self._db.execute("""
                    CREATE TABLE IF NOT EXISTS afk_status (
                        user_id INTEGER PRIMARY KEY,
                        is_afk BOOLEAN NOT NULL,
                        reason TEXT,
                        start_time TEXT NOT NULL
                    )
                """)
                await self._db.commit()

    async def disconnect(self):
        async with self._lock:
            if self._db:
                await self._db.close()
                self._db = None

    async def get_afk_status(self, user_id):
        await self.connect()
        async with self._lock:
            async with self._db.execute("SELECT is_afk, reason, start_time FROM afk_status WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"is_afk": bool(row[0]), "reason": row[1], "start_time": datetime.fromisoformat(row[2])}
                return None

    async def set_afk_status(self, user_id, is_afk, reason=None):
        await self.connect()
        async with self._lock:
            start_time = datetime.now().isoformat()
            await self._db.execute(
                "INSERT OR REPLACE INTO afk_status (user_id, is_afk, reason, start_time) VALUES (?, ?, ?, ?)",
                (user_id, is_afk, reason, start_time)
            )
            await self._db.commit()

    async def clear_afk_status(self, user_id):
        await self.connect()
        async with self._lock:
            await self._db.execute("DELETE FROM afk_status WHERE user_id = ?", (user_id,))
            await self._db.commit()

db_manager = DatabaseManager(DB_PATH)

# --- 4. Helper Functions ---

async def run_in_executor(func, *args, **kwargs):
    """
    Runs a blocking function in a thread pool executor to prevent blocking the asyncio event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

def parse_arguments(message_text, command_prefix):
    """
    Parses arguments from a command message.
    e.g., ".command arg1 arg2" -> ["arg1", "arg2"]
    """
    parts = message_text.split(maxsplit=1)
    if len(parts) > 1:
        return parts[1]
    return ""

def get_arg_list(message_text, command_prefix):
    """
    Parses arguments into a list.
    e.g., ".command arg1 arg2" -> ["arg1", "arg2"]
    """
    parts = message_text.split()
    if len(parts) > 1:
        return parts[1:]
    return []

async def get_user_entity(client, user_input):
    """
    Retrieves a user entity by ID, username, or replied message.
    """
    if isinstance(user_input, Message):
        return await user_input.get_sender()
    try:
        user_input = str(user_input)
        if user_input.isdigit():
            return await client.get_entity(int(user_input))
        elif user_input.startswith('@'):
            return await client.get_entity(user_input)
        else:
            # Try to resolve as username. This can sometimes fail if the username is not public or doesn't exist.
            return await client.get_entity(user_input)
    except Exception as e:
        logger.error(f"Error getting user entity for '{user_input}': {e}")
        return None

async def get_chat_entity(client, chat_input):
    """
    Retrieves a chat entity by ID, username, or replied message.
    """
    if isinstance(chat_input, Message):
        return await chat_input.get_chat()
    try:
        chat_input = str(chat_input)
        if chat_input.isdigit():
            return await client.get_entity(int(chat_input))
        elif chat_input.startswith('@'):
            return await client.get_entity(chat_input)
        else:
            # Try to resolve as chat name (less reliable)
            return await client.get_entity(chat_input)
    except Exception as e:
        logger.error(f"Error getting chat entity for '{chat_input}': {e}")
        return None

def format_timedelta(td: timedelta) -> str:
    """Formats a timedelta object into a human-readable string."""
    total_seconds = int(td.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")

    return " ".join(parts) if parts else "0s"

# --- External API Wrappers ---

async def get_weather(city: str) -> str:
    """Fetches weather information for a given city."""
    if not OPENWEATHER_API_KEY:
        return "⚠️ API Key OpenWeatherMap تنظیم نشده است."
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric", # For Celsius
        "lang": "fa" # For Farsi description
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            if data["cod"] != 200:
                return f"خطا در دریافت آب و هوا: {data.get('message', 'خطای ناشناخته')}"

            city_name = data["name"]
            country = data["sys"]["country"]
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            description = data["weather"][0]["description"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]

            return (
                f"📊 **آب و هوای {city_name}, {country}**:\n"
                f"🌡 دما: `{temp}°C` (احساس می‌شود `{feels_like}°C`)\n"
                f"☁️ وضعیت: `{description}`\n"
                f"💧 رطوبت: `{humidity}%`\n"
                f"💨 سرعت باد: `{wind_speed} m/s`"
            )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for weather API: {e.response.status_code} - {e.response.text}")
        return f"❌ خطای HTTP در دریافت آب و هوا: {e.response.status_code}"
    except httpx.RequestError as e:
        logger.error(f"Network error for weather API: {e}")
        return "❌ خطای شبکه در ارتباط با OpenWeatherMap."
    except Exception as e:
        logger.error(f"Unexpected error in get_weather: {e}")
        return f"❌ خطای ناشناخته: {e}"

async def shorten_url(url: str) -> str:
    """Shortens a URL using TinyURL."""
    if not urlparse(url).scheme:
        url = "http://" + url # Prepend scheme if missing

    s = pyshorteners.Shortener()
    try:
        # TinyURL's basic API usually doesn't require a key, but some shorteners do.
        shortened_url = await run_in_executor(s.tinyurl.short, url)
        return shortened_url
    except Exception as e:
        logger.error(f"Error shortening URL {url}: {e}")
        return f"❌ خطا در کوتاه کردن URL: {e}"

async def expand_url(url: str) -> str:
    """Expands a shortened URL."""
    s = pyshorteners.Shortener()
    try:
        expanded_url = await run_in_executor(s.tinyurl.expand, url)
        return expanded_url
    except Exception as e:
        logger.error(f"Error expanding URL {url}: {e}")
        return f"❌ خطا در باز کردن URL: {e}"

async def google_search(query: str) -> str:
    """Performs a Google search and returns a summary."""
    if not all([GOOGLE_SEARCH_API_KEY, GOOGLE_SEARCH_CX]):
        return "⚠️ API Key یا Custom Search Engine ID برای گوگل سرچ تنظیم نشده است."

    base_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": GOOGLE_SEARCH_CX,
        "q": query,
        "num": 3 # Number of results
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            items = data.get("items")
            if not items:
                return "🔍 نتیجه‌ای برای جستجوی شما یافت نشد."

            results_text = []
            for item in items:
                title = item.get("title")
                link = item.get("link")
                snippet = item.get("snippet")
                results_text.append(f"🔗 [{title}]({link})\n{snippet}\n")
            
            return "🌐 **نتایج جستجوی گوگل**:\n\n" + "\n".join(results_text)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for Google Search API: {e.response.status_code} - {e.response.text}")
        return f"❌ خطای HTTP در جستجوی گوگل: {e.response.status_code}"
    except httpx.RequestError as e:
        logger.error(f"Network error for Google Search API: {e}")
        return "❌ خطای شبکه در ارتباط با Google Search API."
    except Exception as e:
        logger.error(f"Unexpected error in google_search: {e}")
        return f"❌ خطای ناشناخته: {e}"

async def wikipedia_search(query: str, lang: str = "fa") -> str:
    """Searches Wikipedia for a query."""
    wiki_wiki = wikipediaapi.Wikipedia('Userbot (Userbot@example.com)', lang)
    
    try:
        page = await run_in_executor(wiki_wiki.page, query)
        if not page.exists():
            return f"❌ صفحه‌ای با عنوان '{query}' در ویکی‌پدیا یافت نشد."
        
        # Get first 500 chars of summary, then find last full sentence
        summary = await run_in_executor(lambda: page.summary)
        if len(summary) > 500:
            summary = summary[:500]
            last_sentence_end = summary.rfind('.')
            if last_sentence_end != -1:
                summary = summary[:last_sentence_end + 1]
            else:
                summary = summary + "..."
        
        return f"📚 **{page.title}**\n\n{summary}\n\n[ادامه مطلب]({page.fullurl})"
    except Exception as e:
        logger.error(f"Error searching Wikipedia for '{query}': {e}")
        return f"❌ خطایی در جستجوی ویکی‌پدیا رخ داد: {e}"

async def urban_dictionary_search(word: str) -> str:
    """Searches Urban Dictionary for a word."""
    base_url = "http://api.urbandictionary.com/v0/define"
    params = {"term": word}
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            list_defs = data.get("list")
            if not list_defs:
                return f"🧐 کلمه '{word}' در Urban Dictionary یافت نشد."

            definition = list_defs[0]
            word_name = definition["word"]
            meaning = definition["definition"]
            example = definition.get("example", "مثالی موجود نیست.")

            return (
                f"📖 **Urban Dictionary: {word_name}**\n\n"
                f"معنی:\n`{meaning}`\n\n"
                f"مثال:\n`{example}`"
            )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for Urban Dictionary API: {e.response.status_code} - {e.response.text}")
        return f"❌ خطای HTTP در جستجو در Urban Dictionary: {e.response.status_code}"
    except httpx.RequestError as e:
        logger.error(f"Network error for Urban Dictionary API: {e}")
        return "❌ خطای شبکه در ارتباط با Urban Dictionary API."
    except Exception as e:
        logger.error(f"Unexpected error in urban_dictionary_search: {e}")
        return f"❌ خطای ناشناخته: {e}"

async def translate_text(text: str, target_lang: str) -> str:
    """Translates text to a target language."""
    if Translator: # Using googletrans_py
        translator = Translator()
        try:
            translated = await run_in_executor(translator.translate, text, dest=target_lang)
            return f"🌐 **ترجمه به {target_lang}**: `{translated.text}`"
        except Exception as e:
            logger.error(f"Error with googletrans_py translation: {e}")
            return f"❌ خطا در ترجمه با googletrans_py: {e}"
    elif GoogleTranslator: # Using deep_translator
        try:
            translated = await run_in_executor(GoogleTranslator(source='auto', target=target_lang).translate, text)
            return f"🌐 **ترجمه به {target_lang}**: `{translated}`"
        except Exception as e:
            logger.error(f"Error with deep_translator translation: {e}")
            return f"❌ خطا در ترجمه با deep_translator: {e}"
    else:
        return "⚠️ کتابخانه ترجمه (googletrans_py یا deep_translator) نصب نشده است."

async def generate_tts_audio(text: str, lang: str = "fa") -> BytesIO:
    """Generates a Text-to-Speech audio file."""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        audio_buffer = BytesIO()
        await run_in_executor(tts.write_to_fp, audio_buffer)
        audio_buffer.seek(0)
        return audio_buffer
    except Exception as e:
        logger.error(f"Error generating TTS audio: {e}")
        return None

async def generate_qr_code_image(text: str) -> BytesIO:
    """Generates a QR code image."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = await run_in_executor(qr.make_image, fill_color="black", back_color="white")
        
        img_buffer = BytesIO()
        await run_in_executor(img.save, img_buffer, format="PNG")
        img_buffer.seek(0)
        return img_buffer
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        return None

async def generate_quote_image(text: str, author: str = "ناشناس") -> BytesIO:
    """Generates an image with a quote."""
    try:
        # Image dimensions and colors
        img_width, img_height = 800, 400
        bg_color = (30, 30, 30) # Dark gray
        text_color = (255, 255, 255) # White
        author_color = (180, 180, 180) # Light gray
        padding = 40

        # Create blank image
        img = Image.new('RGB', (img_width, img_height), color = bg_color)
        d = ImageDraw.Draw(img)

        # Load font or use default
        try:
            if FONT_PATH:
                font_quote = ImageFont.truetype(FONT_PATH, 36)
                font_author = ImageFont.truetype(FONT_PATH, 24)
            else:
                font_quote = ImageFont.load_default() 
                font_author = ImageFont.load_default()
        except Exception as font_err:
            logger.warning(f"Could not load custom font, using default: {font_err}")
            font_quote = ImageFont.load_default()
            font_author = ImageFont.load_default()

        # Wrap text
        max_width = img_width - 2 * padding
        wrapped_text = []
        words = text.split()
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            text_size = d.textbbox((0,0), test_line, font=font_quote) # Calculate text width
            if (text_size[2] - text_size[0]) <= max_width:
                current_line.append(word)
            else:
                wrapped_text.append(" ".join(current_line))
                current_line = [word]
        wrapped_text.append(" ".join(current_line))
        
        quote_text = "\n".join(wrapped_text)
        author_text = f"- {author}"

        # Calculate text position (using multiline_textbbox for accurate measurement)
        quote_text_bbox = d.multiline_textbbox((0,0), quote_text, font=font_quote, anchor="lt")
        quote_text_height = quote_text_bbox[3] - quote_text_bbox[1]

        author_text_bbox = d.textbbox((0,0), author_text, font=font_author, anchor="lt")
        author_text_height = author_text_bbox[3] - author_text_bbox[1]

        total_content_height = quote_text_height + author_text_height + 20 # 20px space

        # Center vertically and horizontally
        start_y_quote = (img_height - total_content_height) // 2
        start_y_author = start_y_quote + quote_text_height + 20

        d.multiline_text(
            (img_width / 2, start_y_quote), 
            quote_text, 
            font=font_quote, 
            fill=text_color, 
            anchor="mm", 
            align="center"
        )
        d.text(
            (img_width / 2, start_y_author), 
            author_text, 
            font=font_author, 
            fill=author_color, 
            anchor="mm" 
        )

        img_buffer = BytesIO()
        await run_in_executor(img.save, img_buffer, format="PNG")
        img_buffer.seek(0)
        return img_buffer
    except Exception as e:
        logger.error(f"Error generating quote image: {e}")
        return None

async def get_webpage_screenshot(url: str) -> BytesIO:
    """
    Attempts to get a screenshot of a webpage using a public API.
    Note: Public APIs often have rate limits or watermarks. For a robust solution,
    consider running a headless browser like Playwright/Puppeteer on your server.
    This example uses a simple public API.
    """
    screenshot_api_url = "https://image.thum.io/get/width/800/crop/600/png/"
    # Alternative example APIs if thum.io fails or is insufficient:
    # "https://urlbox.io/api/v1/render" (requires API key)
    # "https://shot.screenshotapi.net/screenshot" (check pricing/limits)
    
    if not urlparse(url).scheme:
        url = "http://" + url # Prepend scheme if missing

    try:
        await asyncio.sleep(1) # Small delay before fetching to avoid hammering
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{screenshot_api_url}{url}", follow_redirects=True)
            response.raise_for_status()

            if response.headers.get("Content-Type", "").startswith("image"):
                img_buffer = BytesIO(response.content)
                img_buffer.seek(0)
                return img_buffer
            else:
                logger.error(f"Screenshot API returned non-image content or error for {url}: {response.text}")
                return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for screenshot API: {e.response.status_code} - {e.response.text}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Network error for screenshot API: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_webpage_screenshot: {e}")
        return None

# --- 5. Telethon Client Initialization ---
client = TelegramClient('session', API_ID, API_HASH)

# --- 6. Command Handlers ---

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'help(?: (.*))?', outgoing=True))
async def help_command(event):
    """
    Handles the .help command to display a list of all commands or detailed help for a specific command.
    """
    await event.delete() # Delete the original command message

    args_raw = parse_arguments(event.raw_text, COMMAND_PREFIX)
    args = args_raw.split() if args_raw else []
    
    if args:
        # If the user requested help for a specific command
        requested_command_key = f"{COMMAND_PREFIX}{args[0]}"
        if requested_command_key in ALL_COMMANDS_INFO:
            cmd_info = ALL_COMMANDS_INFO[requested_command_key]
            full_desc = cmd_info["full_desc"]
            
            # Add owner-only warning if applicable
            if cmd_info.get("owner_only", False):
                full_desc += "\n\n⚠️ **این دستور فقط توسط مالک ربات قابل اجرا است.**"

            await event.respond(f"**راهنمای دستور `{requested_command_key}`**:\n{full_desc}")
        else:
            await event.respond(f"❌ دستور `{requested_command_key}` یافت نشد. برای دیدن لیست کامل، `.{COMMAND_PREFIX}help` را ارسال کنید.")
    else:
        # Display the full list of commands
        help_message = "📚 **لیست دستورات Userbot**:\n\n"
        
        categories = {
            "مدیریت پیام و چت": [],
            "بازیابی اطلاعات": [],
            "ابزارهای کاربردی و سرگرمی": [],
            "مدیریت ربات و سیستم": []
        }
        
        # Populate categories dynamically using ALL_COMMANDS_INFO
        for cmd_key, cmd_data in sorted(ALL_COMMANDS_INFO.items()):
            short_desc = cmd_data["short_desc"]
            
            # Grouping logic based on common characteristics
            if "echo" in cmd_key or "type" in cmd_key or "del" in cmd_key or "edit" in cmd_key or "purge" in cmd_key or "pin" in cmd_key or "fwd" in cmd_key or "react" in cmd_key or "spam" in cmd_key:
                categories["مدیریت پیام و چت"].append(f"`{cmd_key}`: {short_desc}")
            elif "id" in cmd_key or "info" in cmd_key or "adminlist" in cmd_key or "me" in cmd_key or "whois" in cmd_key or "photo" in cmd_key or "getbio" in cmd_key or "stickerinfo" in cmd_key or "fileinfo" in cmd_key:
                categories["بازیابی اطلاعات"].append(f"`{cmd_key}`: {short_desc}")
            elif "calc" in cmd_key or "short" in cmd_key or "long" in cmd_key or "weather" in cmd_key or "google" in cmd_key or "wiki" in cmd_key or "ud" in cmd_key or "tr" in cmd_key or "qr" in cmd_key or "tts" in cmd_key or "ss" in cmd_key or "quote" in cmd_key or "carbon" in cmd_key:
                categories["ابزارهای کاربردی و سرگرمی"].append(f"`{cmd_key}`: {short_desc}")
            elif "afk" in cmd_key or "ping" in cmd_key or "restart" in cmd_key or "stats" in cmd_key or "exec" in cmd_key or "term" in cmd_key or "sendfile" in cmd_key or "upload" in cmd_key or "download" in cmd_key or "setname" in cmd_key or "setbio" in cmd_key or "setpfp" in cmd_key:
                categories["مدیریت ربات و سیستم"].append(f"`{cmd_key}`: {short_desc}")
            else:
                 categories["ابزارهای کاربردی و سرگرمی"].append(f"`{cmd_key}`: {short_desc}") # Fallback for any uncategorized

        for category, cmds in categories.items():
            if cmds:
                help_message += f"**{category}**:\n"
                help_message += "\n".join(cmds) + "\n\n"

        help_message += f"برای اطلاعات بیشتر در مورد یک دستور، `.{COMMAND_PREFIX}help <command>` را تایپ کنید."
        
        # Handle Telegram message length limits
        if len(help_message) > 4096:
            await event.respond(f"{help_message[:4000]}...\n\n(پیام راهنما خیلی طولانی است، بخشی از آن نمایش داده شد.)")
        else:
            await event.respond(help_message)
        logger.info("Displayed help message.")

    await asyncio.sleep(60) # Keep help message for 60 seconds
    try:
        await event.delete()
    except Exception as e:
        logger.warning(f"Failed to delete help message (ID: {event.id}): {e}")


@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'echo (.*)', outgoing=True))
async def echo_command(event):
    await event.delete()
    text_to_echo = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if text_to_echo:
        await event.respond(text_to_echo)
        logger.info(f"Echoed: {text_to_echo}")
    else:
        await event.respond(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}echo"]["full_desc"])

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'type (.*)', outgoing=True))
async def type_command(event):
    await event.delete()
    text_to_type = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not text_to_type:
        await event.respond(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}type"]["full_desc"])
        return

    try:
        async with client.action(event.chat_id, 'typing'):
            await asyncio.sleep(len(text_to_type) * 0.1) # Simulate typing speed
            await event.respond(text_to_type)
        logger.info(f"Typed and sent: {text_to_type}")
    except Exception as e:
        logger.error(f"Error in .type command: {e}")
        await event.respond(f"خطا در شبیه‌سازی تایپ: {e}")

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'del', outgoing=True))
async def delete_command(event):
    try:
        if event.reply_to_msg_id:
            target_msg = await event.get_reply_message()
            await target_msg.delete()
            await event.delete()
            logger.info(f"Deleted message {target_msg.id} and command {event.id}.")
        else:
            await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}del"]["full_desc"])
            await asyncio.sleep(3)
            await event.delete()
    except MessageIdInvalidError:
        logger.warning(f"Could not delete message. Message ID {event.reply_to_msg_id} is invalid or already deleted.")
        await event.edit("❌ پیام مورد نظر برای حذف یافت نشد یا قبلاً حذف شده است.")
        await asyncio.sleep(3)
        await event.delete()
    except Exception as e:
        logger.error(f"Error in .del command: {e}")
        await event.edit(f"❌ خطا در حذف پیام: {e}")
        await asyncio.sleep(3)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'edit (.*)', outgoing=True))
async def edit_command(event):
    new_text = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not new_text:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}edit"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return

    try:
        if event.reply_to_msg_id:
            target_msg = await event.get_reply_message()
            await target_msg.edit(new_text)
            await event.delete()
            logger.info(f"Edited message {target_msg.id} with new text.")
        else:
            await event.edit(new_text) # Edit own command if no reply
            logger.info(f"Edited own command {event.id} with new text.")
    except Exception as e:
        logger.error(f"Error in .edit command: {e}")
        await event.edit(f"❌ خطا در ویرایش پیام: {e}")
        await asyncio.sleep(3)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'purge(?: (\d+))?', outgoing=True))
async def purge_command(event):
    try:
        args = get_arg_list(event.raw_text, COMMAND_PREFIX)
        limit = 1
        if args and args[0].isdigit():
            limit = int(args[0])
            if limit <= 0:
                await event.edit("تعداد پیام‌ها باید یک عدد مثبت باشد.")
                await asyncio.sleep(3)
                await event.delete()
                return
        
        messages_to_delete_ids = []
        # Fetch messages including the command itself. `min_id=event.id` would get messages *after* the command.
        # So we iterate backwards from the current message.
        async for msg in client.iter_messages(event.chat_id, limit=limit + 1, offset_id=event.id, reverse=True):
            messages_to_delete_ids.append(msg.id)
            if len(messages_to_delete_ids) >= limit + 1:
                break
        
        if not messages_to_delete_ids:
            await event.edit("پیامی برای حذف یافت نشد.")
            await asyncio.sleep(3)
            await event.delete()
            return
        
        await client.delete_messages(event.chat_id, messages_to_delete_ids)
        logger.info(f"Purged {len(messages_to_delete_ids)} messages in chat {event.chat_id}.")

    except ChatAdminRequiredError:
        logger.error(f"Cannot purge messages in {event.chat_id}: Admin rights required.")
        await event.edit("❌ برای حذف پیام‌ها به دسترسی ادمین نیاز است.")
        await asyncio.sleep(3)
        await event.delete()
    except Exception as e:
        logger.error(f"Error in .purge command: {e}")
        await event.edit(f"❌ خطا در حذف پیام‌ها: {e}")
        await asyncio.sleep(3)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'pin', outgoing=True))
async def pin_command(event):
    try:
        if event.reply_to_msg_id:
            target_msg = await event.get_reply_message()
            await client(functions.channels.UpdatePinnedMessageRequest(
                channel=event.chat_id,
                id=target_msg.id,
                pinned=True
            ))
            await event.edit("📌 پیام پین شد.")
            logger.info(f"Pinned message {target_msg.id} in chat {event.chat_id}.")
        else:
            await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}pin"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
    except ChatAdminRequiredError:
        logger.error(f"Cannot pin message in {event.chat_id}: Admin rights required.")
        await event.edit("❌ برای پین کردن پیام به دسترسی ادمین نیاز است.")
        await asyncio.sleep(3)
        await event.delete()
    except ChatWriteForbiddenError:
        logger.error(f"Cannot pin message in {event.chat_id}: Chat is read-only or bot has no write access.")
        await event.edit("❌ برای پین کردن پیام، چت باید قابل نوشتن باشد.")
        await asyncio.sleep(3)
        await event.delete()
    except Exception as e:
        logger.error(f"Error in .pin command: {e}")
        await event.edit(f"❌ خطا در پین کردن پیام: {e}")
        await asyncio.sleep(3)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'unpin', outgoing=True))
async def unpin_command(event):
    try:
        if event.reply_to_msg_id:
            target_msg = await event.get_reply_message()
            await client(functions.channels.UpdatePinnedMessageRequest(
                channel=event.chat_id,
                id=target_msg.id,
                pinned=False
            ))
            await event.edit("🗑️ پیام از پین خارج شد.")
            logger.info(f"Unpinned message {target_msg.id} in chat {event.chat_id}.")
        else:
            # Unpin the last pinned message if no reply (id=0 usually means last pinned)
            await client(functions.channels.UpdatePinnedMessageRequest(
                channel=event.chat_id,
                id=0, 
                pinned=False
            ))
            await event.edit("🗑️ آخرین پیام پین شده از پین خارج شد.")
            logger.info(f"Unpinned last pinned message in chat {event.chat_id}.")

        await asyncio.sleep(3)
        await event.delete()
    except ChatAdminRequiredError:
        logger.error(f"Cannot unpin message in {event.chat_id}: Admin rights required.")
        await event.edit("❌ برای آنپین کردن پیام به دسترسی ادمین نیاز است.")
        await asyncio.sleep(3)
        await event.delete()
    except ChatWriteForbiddenError:
        logger.error(f"Cannot unpin message in {event.chat_id}: Chat is read-only or bot has no write access.")
        await event.edit("❌ برای آنپین کردن پیام، چت باید قابل نوشتن باشد.")
        await asyncio.sleep(3)
        await event.delete()
    except Exception as e:
        logger.error(f"Error in .unpin command: {e}")
        await event.edit(f"❌ خطا در آنپین کردن پیام: {e}")
        await asyncio.sleep(3)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'fwd (.*)', outgoing=True))
async def forward_command(event):
    await event.delete()
    args = get_arg_list(event.raw_text, COMMAND_PREFIX)

    if len(args) < 1:
        await event.respond(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}fwd"]["full_desc"])
        return

    target_chat_input = args[0]
    message_id = event.reply_to_msg_id

    if len(args) > 1 and args[1].isdigit():
        message_id = int(args[1])
    elif not message_id:
        await event.respond("برای فوروارد، یا باید ID پیام را بدهید یا روی پیامی ریپلای کنید.")
        return

    try:
        target_entity = await get_chat_entity(client, target_chat_input)
        if not target_entity:
            await event.respond(f"❌ چت/کاربر هدف '{target_chat_input}' یافت نشد.")
            return

        await client.forward_messages(target_entity, message_id, event.chat_id)
        await event.respond(f"✅ پیام {message_id} با موفقیت به `{get_display_name(target_entity)}` فوروارد شد.")
        logger.info(f"Forwarded message {message_id} from {event.chat_id} to {get_display_name(target_entity)}.")
    except Exception as e:
        logger.error(f"Error in .fwd command: {e}")
        await event.respond(f"❌ خطا در فوروارد کردن پیام: {e}")

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'react (\S+)', outgoing=True))
async def react_command(event):
    await event.delete()
    args = get_arg_list(event.raw_text, COMMAND_PREFIX)

    if not args:
        await event.respond(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}react"]["full_desc"])
        return

    emoji = args[0]
    
    if event.reply_to_msg_id:
        target_msg = await event.get_reply_message()
        try:
            await client(functions.messages.SendReactionRequest(
                peer=event.chat_id,
                msg_id=target_msg.id,
                big=False, # Normal reaction
                add_to_history=True, # Add reaction to chat history
                reaction=[types.ReactionEmoji(emoticon=emoji)]
            ))
            logger.info(f"Added reaction '{emoji}' to message {target_msg.id}.")
        except Exception as e:
            logger.error(f"Error adding reaction: {e}")
            await event.respond(f"❌ خطا در افزودن واکنش: {e}")
            await asyncio.sleep(3)
            await event.delete()
    else:
        await event.respond("برای افزودن واکنش باید روی یک پیام ریپلای کنید.")
        await asyncio.sleep(3)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'spam (\d+) (.*)', outgoing=True))
async def spam_command(event):
    await event.delete()
    args = get_arg_list(event.raw_text, COMMAND_PREFIX)

    if len(args) < 2:
        await event.respond(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}spam"]["full_desc"])
        return

    count = int(args[0])
    text = " ".join(args[1:])

    if count <= 0 or count > 100: # Limit spam count to prevent abuse/errors
        await event.respond("تعداد اسپم باید بین 1 تا 100 باشد.")
        return

    try:
        for i in range(count):
            await client.send_message(event.chat_id, text)
            await asyncio.sleep(0.5) # Small delay to reduce flood wait risk
        await event.respond(f"✅ با موفقیت {count} پیام اسپم شد.")
        logger.info(f"Spammed {count} messages in chat {event.chat_id}.")
    except FloodWaitError as e:
        logger.warning(f"Flood wait during spam command: {e.seconds} seconds.")
        await event.respond(f"❌ به دلیل محدودیت‌های تلگرام، اسپم متوقف شد. لطفا `{e.seconds}` ثانیه صبر کنید.")
    except Exception as e:
        logger.error(f"Error in .spam command: {e}")
        await event.respond(f"❌ خطا در اسپم کردن پیام: {e}")

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'id', outgoing=True))
async def get_id_command(event):
    target_entity = None
    if event.reply_to_msg_id:
        reply_msg = await event.get_reply_message()
        if reply_msg:
            # Prioritize sender, then forward_from, then forward_from_chat
            if reply_msg.sender:
                target_entity = await reply_msg.get_sender()
            elif reply_msg.forward_from:
                target_entity = reply_msg.forward_from
            elif reply_msg.forward_from_chat:
                target_entity = reply_msg.forward_from_chat
    else:
        target_entity = await event.get_chat()

    if target_entity:
        name = get_display_name(target_entity)
        entity_type = "موجودیت"
        if isinstance(target_entity, User):
            entity_type = "کاربر"
        elif isinstance(target_entity, Channel):
            entity_type = "کانال" if not target_entity.megagroup else "سوپرگروه"
        elif isinstance(target_entity, Chat):
            entity_type = "گروه"
        
        await event.edit(f"🆔 ID این {entity_type} (`{name}`) است: `{target_entity.id}`")
        logger.info(f"Retrieved ID for {name} ({entity_type}): {target_entity.id}")
    else:
        await event.edit("❌ نتوانستم ID این چت/کاربر را دریافت کنم.")
    await asyncio.sleep(5)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'chatinfo', outgoing=True))
async def chat_info_command(event):
    try:
        chat = await event.get_chat()
        if not chat:
            await event.edit("❌ این چت عمومی نیست یا اطلاعات آن قابل دسترسی نیست.")
            await asyncio.sleep(5)
            await event.delete()
            return

        chat_id = chat.id
        title = chat.title or "نامعلوم"
        chat_type = ""
        description = "بدون توضیحات"
        participants_count = "نامعلوم"
        username = chat.username or "ندارد"
        dc_id = getattr(chat, 'dc_id', 'نامعلوم') # Data Center ID

        if isinstance(chat, Channel):
            chat_type = "کانال"
            if chat.megagroup:
                chat_type = "سوپرگروه"
            try:
                full_chat = await client(functions.channels.GetFullChannelRequest(chat_id))
                description = full_chat.full_chat.about or description
                participants_count = full_chat.full_chat.participants_count
            except Exception as e:
                logger.warning(f"Could not get full channel info for {chat_id}: {e}")
        elif isinstance(chat, Chat): # Legacy group chat
            chat_type = "گروه قدیمی" 
            participants_count = chat.participants_count if hasattr(chat, 'participants_count') else "نامعلوم"
        elif isinstance(chat, User):
            chat_type = "چت خصوصی"
            title = get_display_name(chat)
            description = "چت خصوصی با کاربر"

        response_text = (
            f"ℹ️ **اطلاعات چت**:\n"
            f"عنوان: `{title}`\n"
            f"نوع: `{chat_type}`\n"
            f"ID: `{chat_id}`\n"
            f"نام کاربری: @{username}\n"
            f"تعداد اعضا: `{participants_count}`\n"
            f"DC ID: `{dc_id}`\n"
            f"توضیحات: `{description}`"
        )
        await event.edit(response_text)
        logger.info(f"Retrieved chat info for {title} ({chat_id}).")
    except Exception as e:
        logger.error(f"Error in .chatinfo command: {e}")
        await event.edit(f"❌ خطا در دریافت اطلاعات چت: {e}")
    await asyncio.sleep(10)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'userinfo(?: (.*))?', outgoing=True))
async def user_info_command(event):
    args = parse_arguments(event.raw_text, COMMAND_PREFIX)
    target_user_input = args or event.reply_to_msg_id

    if not target_user_input:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}userinfo"]["full_desc"])
        await asyncio.sleep(5)
        await event.delete()
        return

    try:
        user = await get_user_entity(client, target_user_input)
        if not user or not isinstance(user, User):
            await event.edit(f"❌ کاربر '{target_user_input}' یافت نشد.")
            await asyncio.sleep(5)
            await event.delete()
            return

        # Fetch full user details for more info like bio
        full_user = await client(functions.users.GetFullUserRequest(user.id))
        
        first_name = user.first_name or "نامعلوم"
        last_name = user.last_name or ""
        username = user.username or "ندارد"
        user_id = user.id
        phone = user.phone or "ناشناس"
        is_bot = "بله" if user.bot else "خیر"
        is_verified = "بله" if user.verified else "خیر"
        is_scam = "بله" if user.scam else "خیر"
        is_contact = "بله" if user.contact else "خیر"
        bio = full_user.full_user.about or "بیوگرافی ندارد."
        
        common_chats = "نامعلوم"
        if full_user.full_user.common_chats_count is not None:
             common_chats = full_user.full_user.common_chats_count
        
        last_online = "نامعلوم"
        if user.status:
            if isinstance(user.status, types.UserStatusOffline):
                last_online = f"آخرین بازدید در {user.status.was_online.strftime('%Y-%m-%d %H:%M:%S')}"
            elif isinstance(user.status, types.UserStatusOnline):
                last_online = "آنلاین"
            elif isinstance(user.status, types.UserStatusRecently):
                last_online = "اخیراً آنلاین"
            elif isinstance(user.status, types.UserStatusLastWeek):
                last_online = "در این هفته"
            elif isinstance(user.status, types.UserStatusLastMonth):
                last_online = "در این ماه"

        response_text = (
            f"👤 **اطلاعات کاربر**:\n"
            f"نام: `{first_name} {last_name}`\n"
            f"نام کاربری: @{username}\n"
            f"ID: `{user_id}`\n"
            f"شماره تلفن: `{phone}`\n"
            f"ربات است؟: `{is_bot}`\n"
            f"تأیید شده؟: `{is_verified}`\n"
            f"کلاهبرداری؟: `{is_scam}`\n"
            f"در لیست مخاطبین: `{is_contact}`\n"
            f"آخرین فعالیت: `{last_online}`\n"
            f"تعداد چت‌های مشترک: `{common_chats}`\n"
            f"بیوگرافی: \n`{bio}`"
        )
        await event.edit(response_text)
        logger.info(f"Retrieved user info for {first_name} ({user_id}).")
    except Exception as e:
        logger.error(f"Error in .userinfo command: {e}")
        await event.edit(f"❌ خطا در دریافت اطلاعات کاربر: {e}")
    await asyncio.sleep(10)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'adminlist', outgoing=True))
async def admin_list_command(event):
    try:
        chat = await event.get_chat()
        if not isinstance(chat, (Channel, Chat)):
            await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}adminlist"]["full_desc"])
            await asyncio.sleep(5)
            await event.delete()
            return

        admins_list = []
        async for admin in client.iter_participants(chat, filter=types.ChannelParticipantsAdmins):
            admins_list.append(f"• [{get_display_name(admin)}](tg://user?id={admin.id}) (`{admin.id}`)")
        
        if not admins_list:
            await event.edit("❌ ادمینی در این چت یافت نشد.")
            await asyncio.sleep(5)
            await event.delete()
            return
        
        response_text = "👑 **لیست ادمین‌های چت**:\n" + "\n".join(admins_list)
        await event.edit(response_text)
        logger.info(f"Retrieved admin list for {get_display_name(chat)}.")
    except Exception as e:
        logger.error(f"Error in .adminlist command: {e}")
        await event.edit(f"❌ خطا در دریافت لیست ادمین‌ها: {e}")
    await asyncio.sleep(15)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'me', outgoing=True))
async def me_command(event):
    try:
        me_user = await client.get_me()
        
        first_name = me_user.first_name or "نامعلوم"
        last_name = me_user.last_name or ""
        username = me_user.username or "ندارد"
        user_id = me_user.id
        phone = me_user.phone or "ناشناس"

        response_text = (
            f"😎 **اطلاعات حساب من**:\n"
            f"نام: `{first_name} {last_name}`\n"
            f"نام کاربری: @{username}\n"
            f"ID: `{user_id}`\n"
            f"شماره تلفن: `{phone}`"
        )
        await event.edit(response_text)
        logger.info(f"Displayed own user info for {first_name} ({user_id}).")
    except Exception as e:
        logger.error(f"Error in .me command: {e}")
        await event.edit(f"❌ خطا در دریافت اطلاعات حساب من: {e}")
    await asyncio.sleep(10)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'whois(?: (.*))?', outgoing=True))
async def whois_command(event):
    args = parse_arguments(event.raw_text, COMMAND_PREFIX)
    target_user_input = args or event.reply_to_msg_id

    if not target_user_input:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}whois"]["full_desc"])
        await asyncio.sleep(5)
        await event.delete()
        return

    try:
        user = await get_user_entity(client, target_user_input)
        if not user or not isinstance(user, User):
            await event.edit(f"❌ کاربر '{target_user_input}' یافت نشد.")
            await asyncio.sleep(5)
            await event.delete()
            return

        full_user = await client(functions.users.GetFullUserRequest(user.id))
        
        first_name = user.first_name or "نامعلوم"
        last_name = user.last_name or ""
        username = user.username or "ندارد"
        user_id = user.id
        phone = user.phone or "ناشناس"
        is_bot = "بله" if user.bot else "خیر"
        is_verified = "بله" if user.verified else "خیر"
        is_scam = "بله" if user.scam else "خیر"
        bio = full_user.full_user.about or "بیوگرافی ندارد."
        
        common_chats = "نامعلوم"
        if full_user.full_user.common_chats_count is not None:
             common_chats = full_user.full_user.common_chats_count

        response_text = (
            f"🔎 **Whois: {first_name} {last_name}**\n"
            f"نام کاربری: @{username}\n"
            f"ID: `{user_id}`\n"
            f"شماره تلفن: `{phone}`\n"
            f"ربات است؟: `{is_bot}`\n"
            f"تأیید شده؟: `{is_verified}`\n"
            f"کلاهبرداری؟: `{is_scam}`\n"
            f"تعداد چت‌های مشترک: `{common_chats}`\n"
            f"بیوگرافی: \n`{bio}`"
        )
        await event.edit(response_text)
        logger.info(f"Retrieved detailed user info for {first_name} ({user_id}).")
    except Exception as e:
        logger.error(f"Error in .whois command: {e}")
        await event.edit(f"❌ خطا در دریافت اطلاعات دقیق کاربر: {e}")
    await asyncio.sleep(15)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'photo(?: (.*))?', outgoing=True))
async def photo_command(event):
    args = parse_arguments(event.raw_text, COMMAND_PREFIX)
    target_user_input = args or event.reply_to_msg_id

    if not target_user_input:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}photo"]["full_desc"])
        await asyncio.sleep(5)
        await event.delete()
        return

    try:
        user = await get_user_entity(client, target_user_input)
        if not user or not isinstance(user, User):
            await event.edit(f"❌ کاربر '{target_user_input}' یافت نشد.")
            await asyncio.sleep(5)
            await event.delete()
            return
        
        photos = await client(GetUserPhotosRequest(user_id=user.id, offset=0, max_id=0, limit=1))
        if not photos.photos:
            await event.edit(f"❌ کاربر '{get_display_name(user)}' عکس پروفایل ندارد.")
            await asyncio.sleep(5)
            await event.delete()
            return
        
        photo = photos.photos[0]
        photo_path = await client.download_media(photo, file=os.path.join(TEMP_DIR, f"profile_photo_{user.id}_{int(time.time())}.jpg"))
        
        await client.send_file(event.chat_id, photo_path, caption=f"🖼 عکس پروفایل کاربر {get_display_name(user)}")
        await event.delete() # Delete original command
        os.remove(photo_path) # Clean up downloaded file
        logger.info(f"Sent profile photo for {get_display_name(user)}.")
    except PhotoInvalidError:
        logger.error(f"User {target_user_input} has no valid photos or access denied.")
        await event.edit(f"❌ عکس پروفایل معتبری برای کاربر '{get_display_name(user)}' یافت نشد یا قابل دسترسی نیست.")
        await asyncio.sleep(5)
        await event.delete()
    except Exception as e:
        logger.error(f"Error in .photo command: {e}")
        await event.edit(f"❌ خطا در دریافت عکس پروفایل: {e}")
    await asyncio.sleep(5)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'getbio(?: (.*))?', outgoing=True))
async def get_bio_command(event):
    args = parse_arguments(event.raw_text, COMMAND_PREFIX)
    target_user_input = args or event.reply_to_msg_id

    if not target_user_input:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}getbio"]["full_desc"])
        await asyncio.sleep(5)
        await event.delete()
        return

    try:
        user = await get_user_entity(client, target_user_input)
        if not user or not isinstance(user, User):
            await event.edit(f"❌ کاربر '{target_user_input}' یافت نشد.")
            await asyncio.sleep(5)
            await event.delete()
            return
        
        full_user = await client(functions.users.GetFullUserRequest(user.id))
        bio = full_user.full_user.about
        
        if bio:
            await event.edit(f"📝 **بیوگرافی {get_display_name(user)}**:\n`{bio}`")
            logger.info(f"Retrieved bio for {get_display_name(user)}.")
        else:
            await event.edit(f"❌ کاربر {get_display_name(user)} بیوگرافی ندارد.")
    except Exception as e:
        logger.error(f"Error in .getbio command: {e}")
        await event.edit(f"❌ خطا در دریافت بیوگرافی کاربر: {e}")
    await asyncio.sleep(10)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'stickerinfo', outgoing=True))
async def sticker_info_command(event):
    await event.delete()
    if not event.reply_to_msg_id:
        await event.respond(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}stickerinfo"]["full_desc"])
        return
    
    try:
        reply_msg = await event.get_reply_message()
        if not reply_msg or not reply_msg.sticker:
            await event.respond("پیام ریپلای شده حاوی استیکر نیست.")
            return

        sticker: Sticker = reply_msg.sticker
        attributes = sticker.attributes[0] if sticker.attributes else None
        
        response_text = (
            f"ℹ️ **اطلاعات استیکر**:\n"
            f"ID: `{sticker.id}`\n"
            f"دسترسی هش: `{sticker.access_hash}`\n"
            f"فایل رفرنس: `{sticker.file_reference.hex() if sticker.file_reference else 'ندارد'}`\n"
            f"مجموعه استیکر ID: `{attributes.stickerset.id}`\n" if attributes and hasattr(attributes, 'stickerset') else ""
            f"ایموجی: `{attributes.alt}`\n" if attributes and attributes.alt else ""
            f"متحرک: `{'بله' if sticker.mime_type == 'application/x-tgsticker' else 'خیر'}`\n"
            f"ویدیو: `{'بله' if sticker.mime_type == 'video/webm' else 'خیر'}`\n"
            f"نوع MIME: `{sticker.mime_type}`\n"
            f"اندازه فایل: `{sticker.size / 1024:.2f} KB`"
        )
        await event.respond(response_text)
        logger.info(f"Retrieved sticker info for sticker ID: {sticker.id}.")
    except Exception as e:
        logger.error(f"Error in .stickerinfo command: {e}")
        await event.respond(f"❌ خطا در دریافت اطلاعات استیکر: {e}")
    await asyncio.sleep(10)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'fileinfo', outgoing=True))
async def file_info_command(event):
    await event.delete()
    if not event.reply_to_msg_id:
        await event.respond(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}fileinfo"]["full_desc"])
        return
    
    try:
        reply_msg = await event.get_reply_message()
        if not reply_msg or not reply_msg.media:
            await event.respond("پیام ریپلای شده حاوی هیچ مدیایی نیست.")
            return

        media = reply_msg.media
        response_text = f"ℹ️ **اطلاعات مدیا/فایل**:\n"

        if isinstance(media, Document):
            doc: Document = media
            response_text += f"نوع: `فایل (Document)`\n"
            response_text += f"ID: `{doc.id}`\n"
            response_text += f"دسترسی هش: `{doc.access_hash}`\n"
            response_text += f"نام فایل: `{doc.attributes[0].file_name}`\n" if doc.attributes and hasattr(doc.attributes[0], 'file_name') else "نامعلوم"
            response_text += f"نوع MIME: `{doc.mime_type}`\n"
            response_text += f"اندازه فایل: `{doc.size / (1024*1024):.2f} MB`\n"
        elif isinstance(media, Photo):
            photo: Photo = media
            response_text += f"نوع: `عکس (Photo)`\n"
            response_text += f"ID: `{photo.id}`\n"
            response_text += f"دسترسی هش: `{photo.access_hash}`\n"
            response_text += f"عرض: `{photo.sizes[-1].w}`\n" # Get width of largest size
            response_text += f"ارتفاع: `{photo.sizes[-1].h}`\n" # Get height of largest size
            response_text += f"اندازه فایل: `{photo.sizes[-1].size / (1024*1024):.2f} MB`\n"
        elif isinstance(media, Sticker): # Already handled by stickerinfo, but for generality
            sticker: Sticker = media
            response_text += f"نوع: `استیکر (Sticker)`\n"
            response_text += f"ID: `{sticker.id}`\n"
            response_text += f"ایموجی: `{sticker.attributes[0].alt}`\n" if sticker.attributes and sticker.attributes[0].alt else ""
            response_text += f"اندازه فایل: `{sticker.size / 1024:.2f} KB`\n"
        else:
            response_text += f"نوع: `ناشناخته ({type(media).__name__})`\n"
            response_text += f"داده خام: ```json\n{json.dumps(media.to_dict(), indent=2)}```"

        await event.respond(response_text)
        logger.info(f"Retrieved file info for message {reply_msg.id}.")
    except Exception as e:
        logger.error(f"Error in .fileinfo command: {e}")
        await event.respond(f"❌ خطا در دریافت اطلاعات فایل: {e}")
    await asyncio.sleep(15)
    await event.delete()


@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'calc (.*)', outgoing=True))
async def calc_command(event):
    expression = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not expression:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}calc"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return

    try:
        # Basic security: only allow safe operations
        # For full math, a sandbox or dedicated math library is better
        # This is DANGEROUS, but for a self-bot, owner is assumed to be responsible.
        # NEVER use eval() with untrusted input in a public bot.
        allowed_chars_regex = r"^[0-9\.\+\-\*/%\(\) ]+$"
        if not re.match(allowed_chars_regex, expression):
            raise ValueError("عبارت شامل کاراکترهای غیرمجاز است.")
        
        # Prevent common exploits like __import__('os').system('rm -rf /')
        if any(keyword in expression for keyword in ['import', 'os', 'sys', 'subprocess', 'eval', 'exec', 'open']):
            raise ValueError("عبارت شامل کلمات کلیدی خطرناک است.")

        result = await run_in_executor(eval, expression)
        await event.edit(f"🧮 نتیجه `{expression}`: `{result}`")
        logger.info(f"Calculated '{expression}' = '{result}'.")
    except (SyntaxError, ZeroDivisionError, ValueError) as e:
        logger.error(f"Calculation error for '{expression}': {e}")
        await event.edit(f"❌ خطا در محاسبه: `{e}`")
    except Exception as e:
        logger.error(f"Unexpected error in .calc command: {e}")
        await event.edit(f"❌ خطای ناشناخته در محاسبه: `{e}`")
    await asyncio.sleep(5)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'short (.*)', outgoing=True))
async def short_url_command(event):
    url = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not url:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}short"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    await event.edit("⏳ در حال کوتاه کردن URL...")
    shortened_url = await shorten_url(url)
    if shortened_url.startswith("❌"):
        await event.edit(shortened_url)
    else:
        await event.edit(f"🔗 URL کوتاه شده: `{shortened_url}`")
        logger.info(f"Shortened URL '{url}' to '{shortened_url}'.")
    await asyncio.sleep(5)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'long (.*)', outgoing=True))
async def long_url_command(event):
    short_url = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not short_url:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}long"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    await event.edit("⏳ در حال باز کردن URL...")
    expanded_url = await expand_url(short_url)
    if expanded_url.startswith("❌"):
        await event.edit(expanded_url)
    else:
        await event.edit(f"🌐 URL باز شده: `{expanded_url}`")
        logger.info(f"Expanded URL '{short_url}' to '{expanded_url}'.")
    await asyncio.sleep(5)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'weather (.*)', outgoing=True))
async def weather_command(event):
    city = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not city:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}weather"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return

    await event.edit(f"⏳ در حال دریافت آب و هوای `{city}`...")
    weather_info = await get_weather(city)
    await event.edit(weather_info)
    logger.info(f"Retrieved weather for '{city}'.")
    await asyncio.sleep(10)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'google (.*)', outgoing=True))
async def google_command(event):
    query = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not query:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}google"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    await event.edit(f"⏳ در حال جستجوی `{query}` در گوگل...")
    search_results = await google_search(query)
    await event.edit(search_results)
    logger.info(f"Performed Google search for '{query}'.")
    await asyncio.sleep(15)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'wiki (.*)', outgoing=True))
async def wiki_command(event):
    query = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not query:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}wiki"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    await event.edit(f"⏳ در حال جستجوی `{query}` در ویکی‌پدیا...")
    wiki_summary = await wikipedia_search(query)
    await event.edit(wiki_summary)
    logger.info(f"Performed Wikipedia search for '{query}'.")
    await asyncio.sleep(15)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'ud (.*)', outgoing=True))
async def ud_command(event):
    word = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not word:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}ud"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    await event.edit(f"⏳ در حال جستجوی `{word}` در Urban Dictionary...")
    ud_definition = await urban_dictionary_search(word)
    await event.edit(ud_definition)
    logger.info(f"Performed Urban Dictionary search for '{word}'.")
    await asyncio.sleep(15)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'tr(?: (\S+))? (.*)', outgoing=True))
async def translate_command(event):
    args = get_arg_list(event.raw_text, COMMAND_PREFIX)
    
    text_to_translate = None
    target_lang = None

    if event.reply_to_msg_id:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.text:
            text_to_translate = reply_msg.text
            if args and len(args[0]) == 2 and args[0].isalpha(): # Lang code might be provided as first arg
                target_lang = args[0].lower()
            else: # Default to English if no language is specified for replied message
                target_lang = "en" 
    elif len(args) >= 2 and len(args[0]) == 2 and args[0].isalpha():
        target_lang = args[0].lower()
        text_to_translate = " ".join(args[1:])
    elif len(args) == 1: # If only one arg and no reply, assume it's text to translate to default lang
        target_lang = "en" # Default to English if only text is provided
        text_to_translate = args[0]
    
    if not target_lang or not text_to_translate:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}tr"]["full_desc"])
        await asyncio.sleep(5)
        await event.delete()
        return
    
    await event.edit(f"⏳ در حال ترجمه به `{target_lang}`...")
    translated_text = await translate_text(text_to_translate, target_lang)
    await event.edit(translated_text)
    logger.info(f"Translated text to '{target_lang}'.")
    await asyncio.sleep(10)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'qr (.*)', outgoing=True))
async def qr_command(event):
    text_for_qr = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not text_for_qr:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}qr"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    await event.edit("⏳ در حال تولید QR کد...")
    qr_image_buffer = await generate_qr_code_image(text_for_qr)
    if qr_image_buffer:
        await client.send_file(event.chat_id, qr_image_buffer, caption=f"🖼 QR کد برای: `{text_for_qr}`", reply_to=event.reply_to_msg_id)
        await event.delete()
        logger.info(f"Generated QR code for '{text_for_qr}'.")
    else:
        await event.edit("❌ خطا در تولید QR کد.")
        await asyncio.sleep(3)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'tts(?: (\S+))? (.*)', outgoing=True))
async def tts_command(event):
    args = get_arg_list(event.raw_text, COMMAND_PREFIX)
    
    lang = "fa" # Default language
    text_for_tts = None

    if not args:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}tts"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    # Check if the first argument is a 2-letter language code
    if len(args) >= 2 and len(args[0]) == 2 and args[0].isalpha():
        lang = args[0].lower()
        text_for_tts = " ".join(args[1:])
    else:
        text_for_tts = " ".join(args) # Assume all arguments are text, use default language

    if not text_for_tts:
        await event.edit("متنی برای تبدیل به گفتار ارائه نشده است.")
        await asyncio.sleep(3)
        await event.delete()
        return
    
    await event.edit("⏳ در حال تولید فایل صوتی...")
    audio_buffer = await generate_tts_audio(text_for_tts, lang)
    if audio_buffer:
        audio_filename = os.path.join(TEMP_DIR, f"tts_audio_{int(time.time())}.mp3")
        with open(audio_filename, "wb") as f:
            f.write(audio_buffer.getbuffer())
        
        await client.send_file(event.chat_id, audio_filename, caption=f"🗣️ TTS ({lang}): `{text_for_tts[:50]}...`", reply_to=event.reply_to_msg_id, voice_note=True)
        await event.delete()
        os.remove(audio_filename)
        logger.info(f"Generated TTS audio for '{text_for_tts[:50]}...' in lang '{lang}'.")
    else:
        await event.edit("❌ خطا در تولید فایل صوتی.")
        await asyncio.sleep(3)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'ss (.*)', outgoing=True))
async def ss_command(event):
    url = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not url:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}ss"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return

    await event.edit(f"⏳ در حال گرفتن اسکرین‌شات از `{url}`...")
    screenshot_buffer = await get_webpage_screenshot(url)
    if screenshot_buffer:
        await client.send_file(event.chat_id, screenshot_buffer, caption=f"📸 اسکرین‌شات از: `{url}`", reply_to=event.reply_to_msg_id)
        await event.delete()
        logger.info(f"Generated screenshot for '{url}'.")
    else:
        await event.edit("❌ خطا در گرفتن اسکرین‌شات. شاید URL نامعتبر است یا سرویس اسکرین‌شات در دسترس نیست.")
        await asyncio.sleep(5)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'quote (.*)', outgoing=True))
async def quote_command(event):
    args_text = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not args_text:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}quote"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    text_parts = args_text.split('/', 1)
    quote_text = text_parts[0].strip()
    quote_author = text_parts[1].strip() if len(text_parts) > 1 else "ناشناس"

    if not quote_text:
        await event.edit("متنی برای نقل قول ارائه نشده است.")
        await asyncio.sleep(3)
        await event.delete()
        return

    await event.edit("⏳ در حال تولید تصویر نقل قول...")
    quote_image_buffer = await generate_quote_image(quote_text, quote_author)
    if quote_image_buffer:
        await client.send_file(event.chat_id, quote_image_buffer, caption=f"💬 نقل قول: `{quote_text[:50]}...`", reply_to=event.reply_to_msg_id)
        await event.delete()
        logger.info(f"Generated quote image for '{quote_text[:50]}...' by '{quote_author}'.")
    else:
        await event.edit("❌ خطا در تولید تصویر نقل قول.")
        await asyncio.sleep(3)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'carbon (.*)', outgoing=True))
async def carbon_command(event):
    code_text = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not code_text:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}carbon"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return

    await event.edit("⏳ در حال تبدیل کد به تصویر (این قابلیت نیاز به سرویس Carbon.sh یا مشابه آن دارد و فعلاً در حد Placeholder است)...")
    logger.info(f"Carbon command called for code: {code_text[:100]}")
    # Placeholder for actual Carbon API integration
    await event.respond("❌ این قابلیت هنوز به طور کامل پیاده‌سازی نشده است یا نیاز به پیکربندی API خارجی دارد.")
    await asyncio.sleep(5)
    await event.delete()


@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'afk(?: (.*))?', outgoing=True))
async def afk_set_command(event):
    reason = parse_arguments(event.raw_text, COMMAND_PREFIX) or "در حال حاضر در دسترس نیستم."
    user_id = event.sender_id
    
    await db_manager.set_afk_status(user_id, True, reason)
    await event.edit(f"✅ شما اکنون AFK هستید. دلیل: `{reason}`")
    logger.info(f"User {user_id} set AFK with reason: {reason}")
    # Delete after a short while to keep chat clean, but let user see confirmation
    await asyncio.sleep(5)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'ping', outgoing=True))
async def ping_command(event):
    start = time.perf_counter()
    message = await event.edit("🏓 پینگ...")
    end = time.perf_counter()
    latency_ms = (end - start) * 1000
    
    await message.edit(f"🏓 پونگ! تأخیر: `{latency_ms:.2f}ms`")
    logger.info(f"Ping command executed. Latency: {latency_ms:.2f}ms.")
    await asyncio.sleep(5)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'restart', outgoing=True))
async def restart_command(event):
    if event.sender_id != OWNER_ID:
        await event.edit("❌ شما اجازه اجرای این دستور را ندارید.")
        await asyncio.sleep(3)
        await event.delete()
        return

    await event.edit("🔄 در حال راه‌اندازی مجدد...")
    logger.warning("Bot is restarting by command.")
    
    await client.disconnect() # Disconnect gracefully
    # Execute the script again in a new process, ensures clean restart
    os.execl(sys.executable, sys.executable, *sys.argv)

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'stats', outgoing=True))
async def stats_command(event):
    try:
        current_time = datetime.now()
        uptime = format_timedelta(current_time - START_TIME)
        
        # Get memory usage
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        memory_usage_mb = mem_info.rss / (1024 * 1024) # Resident Set Size in MB
        
        # Get CPU usage (could be high for a brief moment due to this call itself)
        cpu_percent = psutil.cpu_percent(interval=1) # Blocking call, but for 1 sec is fine
        
        response_text = (
            f"📈 **آمار Userbot**:\n"
            f"🕰 آپتایم: `{uptime}`\n"
            f"💾 مصرف RAM: `{memory_usage_mb:.2f} MB`\n"
            f"📊 مصرف CPU: `{cpu_percent:.2f}%`\n"
            f"🐍 نسخه پایتون: `{platform.python_version()}`\n"
            f"🖥 سیستم عامل: `{platform.system()} {platform.release()}`\n"
            f"Telethon: `{telethon.__version__}`"
        )
        await event.edit(response_text)
        logger.info("Displayed bot statistics.")
    except Exception as e:
        logger.error(f"Error in .stats command: {e}")
        await event.edit(f"❌ خطا در دریافت آمار: {e}")
    await asyncio.sleep(10)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'exec (.*)', outgoing=True))
async def exec_command(event):
    if event.sender_id != OWNER_ID:
        await event.edit("❌ شما اجازه اجرای این دستور را ندارید.")
        await asyncio.sleep(3)
        await event.delete()
        return

    code = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not code:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}exec"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return

    # Use a string buffer to capture stdout/stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = BytesIO()
    sys.stdout = redirected_output
    sys.stderr = redirected_output

    exec_result = "کدی اجرا نشد."
    try:
        # Create a dictionary to execute the code in, giving access to client and event
        exec_globals = {
            'client': client,
            'event': event,
            '__builtins__': __builtins__, # Give access to built-in functions
            '__name__': '__main__',
            '__file__': '<exec_command>',
            'os': os, 'sys': sys, 'asyncio': asyncio, 'logging': logging,
            'db_manager': db_manager, # Give access to database manager
            'functions': functions, 'types': types # Telethon types/functions
        }
        # Execute the code. Use compile() for syntax check.
        compiled_code = compile(code, '<string>', 'exec')
        # Execute in an executor to avoid blocking main thread if code is blocking
        await run_in_executor(exec, compiled_code, exec_globals, exec_globals)
        exec_result = redirected_output.getvalue().decode('utf-8', errors='ignore') or "✅ اجرا با موفقیت انجام شد (بدون خروجی)."
        logger.info(f"Executed Python code: '{code}', Result: '{exec_result}'")
    except Exception as e:
        exec_result = f"❌ خطا در اجرای کد: {e}\n{redirected_output.getvalue().decode('utf-8', errors='ignore')}"
        logger.error(f"Error executing Python code: '{code}', Error: {e}")
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    await event.edit(f"🐍 **خروجی Exec**:\n```python\n{exec_result[:4000]}```") # Truncate output if too long
    await asyncio.sleep(30)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'term (.*)', outgoing=True))
async def term_command(event):
    if event.sender_id != OWNER_ID:
        await event.edit("❌ شما اجازه اجرای این دستور را ندارید.")
        await asyncio.sleep(3)
        await event.delete()
        return

    command = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not command:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}term"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return

    term_result = "دستوری اجرا نشد."
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        output = stdout.decode('utf-8', errors='ignore')
        error = stderr.decode('utf-8', errors='ignore')

        if output:
            term_result = output
        if error:
            term_result += f"\n❌ خطا:\n{error}"
        if not output and not error:
            term_result = "✅ دستور با موفقیت اجرا شد (بدون خروجی)."

        logger.info(f"Executed shell command: '{command}', Result: '{term_result}'")
    except Exception as e:
        term_result = f"❌ خطا در اجرای دستور شل: {e}"
        logger.error(f"Error executing shell command: '{command}', Error: {e}")

    await event.edit(f"💻 **خروجی ترمینال**:\n```bash\n{term_result[:4000]}```") # Truncate output if too long
    await asyncio.sleep(30)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'sendfile (.*)', outgoing=True))
async def send_file_command(event):
    if event.sender_id != OWNER_ID:
        await event.edit("❌ شما اجازه اجرای این دستور را ندارید.")
        await asyncio.sleep(3)
        await event.delete()
        return

    file_path = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not file_path:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}sendfile"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    # Sanitize path to prevent directory traversal attacks (basic check)
    if ".." in file_path or not os.path.isabs(file_path):
        await event.edit("❌ مسیر فایل نامعتبر است. فقط مسیرهای مطلق و معتبر مجاز هستند.")
        await asyncio.sleep(5)
        await event.delete()
        return

    if not os.path.exists(file_path):
        await event.edit(f"❌ فایل `{file_path}` یافت نشد.")
        await asyncio.sleep(3)
        await event.delete()
        return
    
    if not os.path.isfile(file_path):
        await event.edit(f"❌ `{file_path}` یک فایل نیست.")
        await asyncio.sleep(3)
        await event.delete()
        return

    try:
        await event.edit(f"⏳ در حال ارسال فایل `{file_path}`...")
        await client.send_file(event.chat_id, file_path, reply_to=event.reply_to_msg_id)
        await event.delete()
        logger.info(f"Sent file from path: '{file_path}'.")
    except Exception as e:
        logger.error(f"Error sending file from path '{file_path}': {e}")
        await event.edit(f"❌ خطا در ارسال فایل: {e}")
        await asyncio.sleep(5)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'upload (.*)', outgoing=True))
async def upload_from_url_command(event):
    file_url = parse_arguments(event.raw_text, COMMAND_PREFIX)
    if not file_url:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}upload"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    if not (file_url.startswith("http://") or file_url.startswith("https://")):
        await event.edit("❌ URL نامعتبر است. URL باید با `http://` یا `https://` شروع شود.")
        await asyncio.sleep(5)
        await event.delete()
        return

    await event.edit(f"⏳ در حال دانلود و آپلود فایل از URL: `{file_url}`...")
    
    try:
        async with httpx.AsyncClient(timeout=60) as http_client: # Increased timeout for large files
            response = await http_client.get(file_url, follow_redirects=True)
            response.raise_for_status()
            
            # Determine filename from Content-Disposition or URL path
            filename = None
            content_disposition = response.headers.get("Content-Disposition")
            if content_disposition:
                filename_match = re.search(r'filename="?([^"]+)"?', content_disposition)
                if filename_match:
                    filename = filename_match.group(1)
            
            if not filename:
                filename = os.path.basename(urlparse(file_url).path)
                if not filename or len(filename) > 255: # Fallback if URL path is also empty or too long
                    filename = f"downloaded_file_{int(time.time())}"
            
            temp_file_path = os.path.join(TEMP_DIR, filename)
            with open(temp_file_path, "wb") as f:
                f.write(response.content)
            
            await client.send_file(event.chat_id, temp_file_path, caption=f"⬆️ فایل آپلود شده از: `{file_url}`", reply_to=event.reply_to_msg_id)
            await event.delete()
            os.remove(temp_file_path) # Clean up
            logger.info(f"Uploaded file from URL: '{file_url}'.")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading from URL {file_url}: {e.response.status_code} - {e.response.text}")
        await event.edit(f"❌ خطای HTTP در دانلود فایل: {e.response.status_code}")
        await asyncio.sleep(5)
        await event.delete()
    except httpx.RequestError as e:
        logger.error(f"Network error downloading from URL {file_url}: {e}")
        await event.edit("❌ خطای شبکه در دانلود فایل.")
        await asyncio.sleep(5)
        await event.delete()
    except Exception as e:
        logger.error(f"Error uploading from URL '{file_url}': {e}")
        await event.edit(f"❌ خطا در دانلود و آپلود فایل: {e}")
        await asyncio.sleep(5)
        await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'download', outgoing=True))
async def download_media_command(event):
    await event.delete()
    if not event.reply_to_msg_id:
        await event.respond(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}download"]["full_desc"])
        return
    
    try:
        reply_msg = await event.get_reply_message()
        if not reply_msg or not reply_msg.media:
            await event.respond("پیام ریپلای شده حاوی هیچ مدیایی نیست.")
            return

        await event.respond("⏳ در حال دانلود مدیا...")
        
        # Telethon's download_media automatically handles filenames fairly well
        file_path = await client.download_media(reply_msg.media, file=TEMP_DIR)
        
        await event.respond(f"✅ مدیا با موفقیت دانلود شد: `{file_path}`")
        logger.info(f"Downloaded media from message {reply_msg.id} to '{file_path}'.")
    except Exception as e:
        logger.error(f"Error downloading media from message {event.reply_to_msg_id}: {e}")
        await event.respond(f"❌ خطا در دانلود مدیا: {e}")
    await asyncio.sleep(10)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'setname (.*)', outgoing=True))
async def setname_command(event):
    if event.sender_id != OWNER_ID:
        await event.edit("❌ شما اجازه اجرای این دستور را ندارید.")
        await asyncio.sleep(3)
        await event.delete()
        return

    name_args = parse_arguments(event.raw_text, COMMAND_PREFIX).strip().split(maxsplit=1)
    if not name_args:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}setname"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    first_name = name_args[0]
    last_name = name_args[1] if len(name_args) > 1 else ""

    try:
        await client(UpdateProfileRequest(first_name=first_name, last_name=last_name))
        await event.edit(f"✅ نام پروفایل شما به `{first_name} {last_name}` تغییر یافت.")
        logger.info(f"Profile name changed to {first_name} {last_name}.")
    except Exception as e:
        logger.error(f"Error changing profile name: {e}")
        await event.edit(f"❌ خطا در تغییر نام پروفایل: {e}")
    await asyncio.sleep(5)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'setbio (.*)', outgoing=True))
async def setbio_command(event):
    if event.sender_id != OWNER_ID:
        await event.edit("❌ شما اجازه اجرای این دستور را ندارید.")
        await asyncio.sleep(3)
        await event.delete()
        return

    new_bio = parse_arguments(event.raw_text, COMMAND_PREFIX).strip()
    if not new_bio:
        await event.edit(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}setbio"]["full_desc"])
        await asyncio.sleep(3)
        await event.delete()
        return
    
    # Telegram bio limit is 70 characters
    if len(new_bio) > 70:
        await event.edit("❌ بیوگرافی نباید بیشتر از 70 کاراکتر باشد.")
        await asyncio.sleep(5)
        await event.delete()
        return

    try:
        await client(UpdateProfileRequest(about=new_bio))
        await event.edit(f"✅ بیوگرافی پروفایل شما به `{new_bio}` تغییر یافت.")
        logger.info(f"Profile bio changed to {new_bio}.")
    except Exception as e:
        logger.error(f"Error changing profile bio: {e}")
        await event.edit(f"❌ خطا در تغییر بیوگرافی پروفایل: {e}")
    await asyncio.sleep(5)
    await event.delete()

@client.on(events.NewMessage(pattern=re.escape(COMMAND_PREFIX) + r'setpfp', outgoing=True))
async def setpfp_command(event):
    if event.sender_id != OWNER_ID:
        await event.edit("❌ شما اجازه اجرای این دستور را ندارید.")
        await asyncio.sleep(3)
        await event.delete()
        return

    await event.delete()
    if not event.reply_to_msg_id:
        await event.respond(ALL_COMMANDS_INFO[f"{COMMAND_PREFIX}setpfp"]["full_desc"])
        return
    
    try:
        reply_msg = await event.get_reply_message()
        if not reply_msg or not reply_msg.photo:
            await event.respond("❌ برای تغییر عکس پروفایل، باید روی یک عکس ریپلای کنید.")
            return

        photo_path = await client.download_media(reply_msg.photo, file=os.path.join(TEMP_DIR, f"new_pfp_{int(time.time())}.jpg"))
        
        await client(UploadProfilePhotoRequest(file=await client.upload_file(photo_path)))
        await event.respond("✅ عکس پروفایل شما با موفقیت تغییر یافت.")
        logger.info("Profile picture updated.")
        os.remove(photo_path)
    except Exception as e:
        logger.error(f"Error setting new profile picture: {e}")
        await event.respond(f"❌ خطا در تغییر عکس پروفایل: {e}")
    await asyncio.sleep(5)
    await event.delete()


# --- 7. AFK System Handlers ---

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private or e.mentioned))
async def afk_incoming_handler(event):
    """
    Handles incoming messages (private or mentions) to check AFK status and auto-reply.
    Also clears AFK status if the user sends a message.
    """
    me = await client.get_me()

    # If the message is from myself, it indicates I'm back, so clear AFK.
    if event.sender_id == me.id:
        afk_status = await db_manager.get_afk_status(me.id)
        if afk_status and afk_status["is_afk"]:
            # Check if this is a command, if so, don't clear AFK.
            # We can detect this by checking if the message starts with the command prefix
            # and is listed in our commands.
            is_command = False
            if event.text and event.text.startswith(COMMAND_PREFIX):
                cmd_name = event.text.split()[0]
                if cmd_name in ALL_COMMANDS_INFO:
                    is_command = True
            
            if not is_command:
                await db_manager.clear_afk_status(me.id)
                logger.info(f"AFK status cleared for {me.id} due to outgoing message.")
                # Send a message to confirm AFK is off
                await client.send_message(event.chat_id, "بازگشتم! 😊")
        return

    # If the message is from someone else, and I'm AFK, auto-reply.
    afk_data = await db_manager.get_afk_status(OWNER_ID) # Assuming AFK is for the bot owner
    if afk_data and afk_data["is_afk"]:
        current_time = datetime.now()
        time_since_afk = current_time - afk_data["start_time"]
        
        # Simple rate limiting for AFK replies per chat:
        # We store the last AFK reply time per chat to prevent spamming.
        # This requires a more persistent per-chat storage, which would make the single-file setup
        # more complex (e.g., adding a new table for chat-specific AFK last_reply_time).
        # For this version, we'll simplify and only reply if the AFK status was set a reasonable time ago
        # to prevent instant replies if I go AFK then someone messages.
        
        # A more robust rate limit could be a dict like:
        # AFK_LAST_REPLY_TIMES = {}
        # if event.chat_id not in AFK_LAST_REPLY_TIMES or (current_time - AFK_LAST_REPLY_TIMES[event.chat_id]).total_seconds() > SOME_COOLDOWN:
        #    ... send reply ...
        #    AFK_LAST_REPLY_TIMES[event.chat_id] = current_time

        if time_since_afk.total_seconds() > 5: # Don't reply if AFK was just set (first 5 seconds after setting)
             afk_time_str = format_timedelta(time_since_afk)
             response_text = (
                 f"👋 من در حال حاضر AFK هستم.\n"
                 f"⏰ از `{afk_time_str}` پیش AFK شدم.\n"
                 f"دلیل: `{afk_data['reason']}`"
             )
             try:
                await event.reply(response_text)
                logger.info(f"AFK auto-reply sent to {event.sender_id} in chat {event.chat_id}.")
             except ChatWriteForbiddenError:
                logger.warning(f"Could not send AFK reply in chat {event.chat_id}: Chat is read-only or bot has no write access.")
             except Exception as e:
                logger.error(f"Error sending AFK reply in chat {event.chat_id}: {e}")
        else:
             logger.debug(f"Skipping AFK auto-reply for {event.sender_id} due to recent AFK status change.")


# --- 8. Main Bot Logic ---

async def main():
    logger.info("Starting Userbot...")
    await db_manager.connect() # Ensure DB connection at startup

    try:
        await client.start()
        me = await client.get_me()
        logger.info(f"Userbot started as @{me.username} (ID: {me.id})")
        
        # Override OWNER_ID if it was set to 0 (meaning not explicitly provided)
        # In this case, the bot owner is the logged-in user.
        global OWNER_ID
        if OWNER_ID == 0:
            OWNER_ID = me.id
            logger.info(f"OWNER_ID was not set, automatically set to bot's ID: {OWNER_ID}")

        logger.info(f"Bot prefix: '{COMMAND_PREFIX}'")
        logger.info(f"Owner ID: {OWNER_ID}")
        logger.info(f"Temporary files directory: '{TEMP_DIR}'")
        logger.info("Userbot is running! Send '.help' for commands. Press Ctrl+C to stop.")
        
        await client.run_until_disconnected()
    except Exception as e:
        logger.critical(f"Fatal error during bot startup or runtime: {e}")
    finally:
        logger.info("Userbot is shutting down...")
        await db_manager.disconnect()
        logger.info("Database disconnected. Goodbye!")
        # Clean up temporary files
        if os.path.exists(TEMP_DIR):
            for f in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, f)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path): # Recursively remove directories if any (unlikely for temp files)
                        import shutil
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.error(f"Error removing temporary file/dir {file_path}: {e}")
            try:
                os.rmdir(TEMP_DIR) # Try to remove the directory if empty
            except OSError as e:
                logger.warning(f"Could not remove temporary directory {TEMP_DIR} (might not be empty): {e}")
        logger.info("Temporary files cleaned up.")


if __name__ == '__main__':
    # Telethon logs verbosely, set its logger level to WARNING or ERROR
    logging.getLogger('telethon').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    # Run the main async function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Userbot stopped by KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main execution: {e}")
