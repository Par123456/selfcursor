# -*- coding: utf-8 -*-
# index.py

"""
********************************************************************************
                       ⚠️⚠️⚠️ هشدار بسیار مهم ⚠️⚠️⚠️
********************************************************************************
این اسکریپت به درخواست کاربر، با تعداد خطوط بالا و بدون ماژول‌بندی نوشته شده است.
این رویکرد **به شدت نامناسب و خطرناک** برای توسعه نرم‌افزار است، به ویژه برای
یک ابزار سلف-اکانت که با حساب کاربری شما در تلگرام در ارتباط است.

- **مسدود شدن حساب:** استفاده از سلف-اکانت‌ها (یوزربات‌ها) نقض شرایط خدمات تلگرام است
  و می‌تواند منجر به مسدود شدن دائمی حساب کاربری شما شود.
- **مشکلات نگهداری:** یک فایل ۴۰۰۰ خطی بدون ساختار، کابوس‌وار برای خواندن،
  اشکال‌زدایی (Debug) و افزودن قابلیت‌های جدید است. احتمال بروز باگ‌ها در این
  ساختار بسیار بالاست، حتی با بهترین تلاش برای مدیریت خطا.
- **مسئولیت:** هرگونه استفاده از این اسکریپت و عواقب ناشی از آن (از جمله
  مسدود شدن حساب، مشکلات امنیتی یا آزار و اذیت دیگران) **کاملاً بر عهده شماست.**

این اسکریپت تنها برای اهداف آموزشی و نمایش قابلیت‌های Telethon، با تاکید بر
**هشدارهای امنیتی و مسئولیت‌پذیری فردی** ارائه شده است.
********************************************************************************
"""

import os
import asyncio
import re
import random
import datetime
import math
import logging
import json
import ast  # برای eval امن‌تر در ماشین حساب و جلوگیری از آسیب‌پذیری
import time
import subprocess # برای اجرای دستورات سیستمی مانند speedtest-cli

# کتابخانه‌های خارجی برای دستورات خاص. مطمئن شوید که اینها را نصب کرده‌اید.
# pip install requests wikipedia speedtest-cli pyfiglet google_trans_new psutil
try:
    import requests  # برای وب‌هوک‌ها، آب و هوا، ترجمه، IMDB و سایر API‌های خارجی
except ImportError:
    print("ماژول 'requests' نصب نیست. برخی دستورات ممکن است کار نکنند. لطفاً 'pip install requests' را اجرا کنید.")
    requests = None

try:
    import wikipedia  # برای دستور wikipedia
    wikipedia.set_lang("fa") # تنظیم زبان فارسی برای ویکی پدیا
except ImportError:
    print("ماژول 'wikipedia' نصب نیست. دستور 'wiki' کار نخواهد کرد. لطفاً 'pip install wikipedia' را اجرا کنید.")
    wikipedia = None
except Exception as e:
    print(f"خطا در تنظیم زبان ویکی‌پدیا (فارسی): {e}. ممکن است 'wiki' به زبان انگلیسی جستجو کند یا کار نکند.")
    wikipedia = None

try:
    import speedtest # برای دستور speedtest
except ImportError:
    print("ماژول 'speedtest-cli' نصب نیست. دستور 'speedtest' کار نخواهد کرد. لطفاً 'pip install speedtest-cli' را اجرا کنید.")
    speedtest = None

try:
    import pyfiglet # برای دستور figlet
except ImportError:
    print("ماژول 'pyfiglet' نصب نیست. دستور 'figlet' کار نخواهد کرد. لطفاً 'pip install pyfiglet' را اجرا کنید.")
    pyfiglet = None

try:
    # GoogleTranslator از google_trans_new یا Translator از deep_translator
    from google_trans_new import google_translator
    TRANSLATOR = google_translator()
except ImportError:
    try:
        from deep_translator import GoogleTranslator
        TRANSLATOR = GoogleTranslator(source='auto', target='en') # پیش‌فرض به انگلیسی
        print("ماژول 'deep_translator' به عنوان جایگزین 'google_trans_new' استفاده می‌شود.")
    except ImportError:
        print("هیچ یک از ماژول‌های 'google_trans_new' یا 'deep_translator' نصب نیستند. دستور 'translate' ممکن است کار نکند. لطفاً 'pip install google_trans_new' یا 'pip install deep_translator' را اجرا کنید.")
        TRANSLATOR = None

try:
    import psutil # برای اطلاعات سیستم
except ImportError:
    print("ماژول 'psutil' نصب نیست. دستورات 'sysinfo', 'cpu', 'ram', 'disk' کار نخواهند کرد. لطفاً 'pip install psutil' را اجرا کنید.")
    psutil = None


# ماژول اصلی Telethon
from telethon import TelegramClient, events
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import (
    User, Chat, Channel, Message, MessageMediaPhoto, MessageMediaDocument,
    ChatBannedRights, ChannelParticipantsAdmins, ChannelParticipantAdmin,
    ChannelParticipantCreator
)
from telethon.errors.rpcerrorlist import (
    PeerIdInvalidError, UserNotParticipantError, UserAdminInvalidError,
    MessageDeleteForbiddenError, PhotoCropSizeSmallError, WebpageCurlFailedError,
    ChatSendMediaForbiddenError, MessageTooLongError, ChannelsAdminNotAggregatorError,
    UserAdminRightsForbiddenError, ChannelPrivateError, ChatAdminRequiredError,
    UserIsBotError, UsernameNotOccupiedError, YouBlockedUserError
)
from telethon.errors import SessionPasswordNeededError


# --- تنظیمات عمومی ---
# API ID و API Hash خود را از my.telegram.org دریافت کنید.
# **توصیه می‌شود برای امنیت، این مقادیر را از متغیرهای محیطی بخوانید.**
# مثال: TG_API_ID=1234567 TG_API_HASH=abcdef1234567890abcdef1234567890 python index.py
API_ID = os.environ.get('TG_API_ID', '29042268')  # <<--- با API ID خود جایگزین کنید
API_HASH = os.environ.get('TG_API_HASH', '54a7b377dd4a04a58108639febe2f443')  # <<--- با API Hash خود جایگزین کنید
SESSION_NAME = 'my_userbot_session'  # نام فایل سشن برای ذخیره اطلاعات لاگین

# این را به یک آیدی عددی تبدیل کنید تا فقط خودتان بتوانید دستورات را اجرا کنید.
# برای یافتن User ID خود، می‌توانید با بات @userinfobot صحبت کنید.
OWNER_ID = int(os.environ.get('TG_OWNER_ID', 6508600903)) # <<--- با User ID خود جایگزین کنید (فقط عددی)

# API Key برای OpenWeatherMap (برای دستور .weather)
OWM_API_KEY = os.environ.get('OWM_API_KEY', 'YOUR_OPENWEATHERMAP_API_KEY_HERE') # <<--- API Key را اینجا قرار دهید

# API Key برای OMDb API (برای دستور .imdb)
OMDB_API_KEY = os.environ.get('OMDB_API_KEY', 'YOUR_OMDB_API_KEY_HERE') # <<--- API Key را اینجا قرار دهید


# تنظیمات لاگین
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.WARNING)
logger = logging.getLogger(__name__)

# --- راه‌اندازی کلاینت تلگرام ---
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# --- متغیرهای سراسری برای وضعیت‌ها و داده‌ها ---
AFK_STATUS = False
AFK_REASON = ""
AFK_START_TIME = None
LAST_SEEN_MESSAGE = {} # ذخیره آخرین پیام دیده شده در هر چت برای دستور afk_auto_reply
DISABLED_CHATS = set() # چت‌هایی که AFK در آنها غیرفعال است (برای جلوگیری از اسپم در گروه‌های بزرگ)

# --- توابع کمکی (Helper Functions) ---

async def get_target_entity(event, input_param=None):
    """
    تلاش می‌کند تا entity یک کاربر یا چت را بر اساس ریپلای، یوزرنیم، شناسه یا ورودی مستقیم به دست آورد.
    اگر هیچ کدام داده نشود، entity ارسال کننده رویداد را برمی‌گرداند.
    """
    if input_param:
        try:
            return await client.get_entity(input_param)
        except (ValueError, PeerIdInvalidError, UsernameNotOccupiedError):
            return None
    elif event.is_reply:
        try:
            replied_message = await event.get_reply_message()
            if replied_message.sender_id:
                return await client.get_entity(replied_message.sender_id)
            else: # در صورتی که پیام از کانال یا بات باشد و sender_id مشخص نباشد
                return await client.get_entity(replied_message.peer_id)
        except Exception:
            return None
    elif event.is_private:
        return await client.get_entity(event.chat_id)
    else:
        return await client.get_entity(event.sender_id)

async def get_chat_entity_from_event(event, input_param=None):
    """
    تلاش می‌کند تا entity یک چت را بر اساس ورودی یا از رویداد به دست آورد.
    """
    if input_param:
        try:
            return await client.get_entity(input_param)
        except (ValueError, PeerIdInvalidError, UsernameNotOccupiedError):
            return None
    return await event.get_chat()

def parse_command_args(event, cmd_prefix_len):
    """
    متن پیام را پس از دستور (با فرض حذف پیشوند دستور) تجزیه می‌کند.
    """
    text = event.message.message[cmd_prefix_len:].strip()
    return text

def human_readable_time(seconds):
    """
    زمان را به فرمت قابل خواندن برای انسان تبدیل می‌کند.
    """
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days:
        parts.append(f"{int(days)} روز")
    if hours:
        parts.append(f"{int(hours)} ساعت")
    if minutes:
        parts.append(f"{int(minutes)} دقیقه")
    if seconds:
        parts.append(f"{int(seconds)} ثانیه")

    if not parts:
        return "همین الان"
    return ", ".join(parts)

async def get_admin_rights(chat_id, user_id):
    """
    حقوق ادمین یک کاربر در چت/کانال را برمی‌گرداند.
    """
    try:
        participants = await client(ChannelParticipantsAdmins(chat_id, offset=0, limit=100))
        for p in participants.participants:
            if p.user_id == user_id:
                return p.admin_rights
        return None
    except Exception as e:
        logger.error(f"خطا در دریافت حقوق ادمین برای {user_id} در چت {chat_id}: {e}")
        return None

# --- دستورات اصلی ---

@client.on(events.NewMessage(pattern=r'^\.ping(?:@\w+)?$', outgoing=True))
async def ping_command(event):
    """
    .ping: برای تست فعال بودن ربات پاسخ می‌دهد "Pong!".
    این دستور فقط زمانی که خود شما آن را ارسال می‌کنید، فعال می‌شود.
    """
    if event.sender_id != OWNER_ID:
        return

    start_time = time.time()
    try:
        await event.edit('پینگ! 🚀')
        end_time = time.time()
        latency = round((end_time - start_time) * 1000)
        await event.edit(f'پینگ! 🚀 (`{latency}ms`)')
        logger.info(f"دستور .ping با موفقیت اجرا شد. تاخیر: {latency}ms")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .ping: {e}")
        await event.edit(f"خطا در اجرای پینگ: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.echo (.*)(?:@\w+)?$', outgoing=True))
async def echo_command(event):
    """
    .echo <متن>: متن ارسالی شما را بازتاب می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        text_to_echo = event.pattern_match.group(1)
        await event.edit(f'شما گفتی: {text_to_echo}')
        logger.info(f"دستور .echo با موفقیت اجرا شد: '{text_to_echo}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .echo: {e}")
        await event.edit(f"خطا در اجرای echo: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.myid(?:@\w+)?$', outgoing=True))
async def my_id_command(event):
    """
    .myid: User ID شما را نشان می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        await event.edit(f'User ID شما: `{event.sender_id}`')
        logger.info(f"دستور .myid با موفقیت اجرا شد. User ID: {event.sender_id}")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .myid: {e}")
        await event.edit(f"خطا در دریافت User ID: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.chatid(?:@\w+)?$', outgoing=True))
async def chat_id_command(event):
    """
    .chatid: Chat ID چت فعلی را نشان می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        await event.edit(f'Chat ID این چت: `{event.chat_id}`')
        logger.info(f"دستور .chatid با موفقیت اجرا شد. Chat ID: {event.chat_id}")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .chatid: {e}")
        await event.edit(f"خطا در دریافت Chat ID: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.info(?:@\w+)?$', outgoing=True))
async def user_info_command(event):
    """
    .info: اطلاعات پایه درباره حساب کاربری شما را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        user = await client.get_me()
        response = (
            f"**اطلاعات حساب شما:**\n"
            f"نام: {user.first_name} {user.last_name or ''}\n"
            f"یوزرنیم: @{user.username or 'ندارد'}\n"
            f"آیدی کاربری: `{user.id}`\n"
            f"شماره تلفن: `{user.phone or 'ندارد'}`\n"
            f"وضعیت ربات: {'بله' if user.bot else 'خیر'}\n"
            f"دسترسی‌ها: {'محدود' if user.restricted else 'عادی'}"
        )
        await event.edit(response, parse_mode='md')
        logger.info(f"دستور .info با موفقیت اجرا شد. اطلاعات کاربر: {user.id}")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .info: {e}")
        await event.edit(f"خطا در دریافت اطلاعات: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.del(?:@\w+)?$', outgoing=True))
async def delete_message_command(event):
    """
    .del: پیامی که روی آن ریپلای شده را پاک می‌کند (اگر خودتان یا ادمین با حق حذف باشید).
    """
    if event.sender_id != OWNER_ID:
        return

    if not event.is_reply:
        await event.edit("برای پاک کردن پیام، روی آن ریپلای کنید. 🗑️")
        return

    try:
        replied_message = await event.get_reply_message()
        # بررسی کنیم که آیا کاربر ادمین است و اجازه حذف پیام دارد
        can_delete = False
        if event.is_private or replied_message.sender_id == OWNER_ID:
            can_delete = True
        elif event.is_group or event.is_channel:
            # فقط در چت‌هایی که از نوع کانال (گروه سوپرگروه) هستند می‌توانیم حقوق ادمین را بررسی کنیم
            try:
                chat_full = await client(GetFullChannelRequest(event.chat_id))
                my_participant = await client.get_participant(event.chat_id, OWNER_ID)
                if isinstance(my_participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
                    if my_participant.admin_rights and my_participant.admin_rights.delete_messages:
                        can_delete = True
            except (UserNotParticipantError, UserAdminInvalidError, ChannelPrivateError):
                pass # در گروه های معمولی یا اگر ادمین نیستید، این متد کار نمی کند یا نیاز به بررسی متفاوت دارد

        if can_delete:
            await client.delete_messages(event.chat_id, [replied_message.id, event.message.id])
            logger.info(f"دستور .del با موفقیت اجرا شد. پیام ID: {replied_message.id} حذف شد.")
        else:
            await event.edit("شما نمی‌توانید این پیام را پاک کنید (شما مالک آن نیستید یا ادمین با حق حذف نیستید).")
    except MessageDeleteForbiddenError:
        logger.warning(f"خطا: اجازه حذف پیام {replied_message.id} در چت {event.chat_id} وجود ندارد (خیلی قدیمی).")
        await event.edit("خطا: اجازه حذف این پیام را ندارید (ممکن است خیلی قدیمی باشد یا ادمین نباشید).")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .del: {e}")
        await event.edit(f"خطا در حذف پیام: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.purge(?: (\d+))?(?:@\w+)?$', outgoing=True))
async def purge_messages_command(event):
    """
    .purge [تعداد]: N پیام آخر ارسالی شما را پاک می‌کند. اگر تعداد مشخص نشود، ۱۰ پیام.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        count_str = event.pattern_match.group(1)
        count = int(count_str) if count_str else 10 # پیش‌فرض ۱۰ پیام

        if count <= 0:
            await event.edit("لطفاً یک عدد مثبت برای تعداد پیام‌ها وارد کنید.")
            return
        
        # تلگرام محدودیت در تعداد پیام‌های قابل حذف در یک درخواست دارد
        if count > 100:
            await event.edit("برای جلوگیری از خطا، حداکثر ۱۰۰ پیام را می‌توان در هر بار پاکسازی کرد.")
            count = 100

        await event.edit(f"در حال پاکسازی {count} پیام آخر شما...")

        chat_id = event.chat_id
        messages_to_delete_ids = []
        # +1 برای حذف خود دستور .purge
        async for msg in client.iter_messages(chat_id, limit=count + 1, from_user=OWNER_ID):
            messages_to_delete_ids.append(msg.id)
            if len(messages_to_delete_ids) >= count + 1:
                break
        
        if not messages_to_delete_ids:
            await event.edit("هیچ پیامی برای پاک کردن پیدا نشد.")
            return

        # حذف پیام‌ها
        await client.delete_messages(chat_id, messages_to_delete_ids)
        await client.send_message(chat_id, f"✅ `{len(messages_to_delete_ids) - 1}` پیام آخر شما پاک شد.", delete_in=3) # ارسال پیام تایید و حذف آن پس از ۳ ثانیه
        logger.info(f"دستور .purge با موفقیت اجرا شد. {len(messages_to_delete_ids)} پیام در چت {chat_id} حذف شد.")
    except MessageDeleteForbiddenError:
        logger.warning(f"خطا: اجازه حذف برخی پیام‌ها در چت {event.chat_id} وجود ندارد (خیلی قدیمی یا ادمین نیستید).")
        await event.edit("خطا: اجازه حذف برخی از این پیام‌ها را ندارید (ممکن است خیلی قدیمی باشند یا ادمین نباشید).")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .purge: {e}")
        await event.edit(f"خطا در پاکسازی پیام‌ها: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.readall(?:@\w+)?$', outgoing=True))
async def read_all_messages_command(event):
    """
    .readall: تمام پیام‌های خوانده نشده در چت فعلی را به عنوان خوانده شده علامت می‌زند.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        await client.send_read_acknowledge(event.chat_id)
        await event.edit("✅ همه پیام‌ها خوانده شدند.")
        logger.info(f"دستور .readall با موفقیت اجرا شد در چت: {event.chat_id}")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .readall: {e}")
        await event.edit(f"خطا در علامت‌گذاری پیام‌ها: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.type (.*)(?:@\w+)?$', outgoing=True))
async def type_command(event):
    """
    .type <متن>: شروع به تایپ کردن یک متن خاص می‌کند و سپس آن را ارسال می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        text_to_type = event.pattern_match.group(1)
        original_message = await event.edit("تایپ کردن...") # ویرایش اولیه پیام به "تایپ کردن..."
        # ارسال حالت "تایپ" به چت
        async with client.action(event.chat_id, 'typing'):
            # برای واقعی‌تر شدن، می‌توان زمان کوتاهی مکث کرد
            await asyncio.sleep(len(text_to_type) * 0.05) # هر حرف 0.05 ثانیه
            await client.send_message(event.chat_id, text_to_type, parse_mode='md')
        await original_message.delete() # پاک کردن پیام "تایپ کردن..."
        logger.info(f"دستور .type با موفقیت اجرا شد: '{text_to_type}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .type: {e}")
        await event.edit(f"خطا در شبیه‌سازی تایپ: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.afk(?: (.*))?(?:@\w+)?$', outgoing=True))
async def afk_command(event):
    """
    .afk [دلیل]: وضعیت شما را به AFK (Away From Keyboard) تغییر می‌دهد.
    اگر کسی در این حالت به شما پیام دهد، پاسخ خودکار دریافت می‌کند.
    """
    global AFK_STATUS, AFK_REASON, AFK_START_TIME
    if event.sender_id != OWNER_ID:
        return

    AFK_STATUS = True
    AFK_REASON = event.pattern_match.group(1) or "هیچ دلیلی ارائه نشده است."
    AFK_START_TIME = datetime.datetime.now()

    response_text = f"حالت AFK فعال شد! 😴\nدلیل: `{AFK_REASON}`"
    try:
        await event.edit(response_text)
        logger.info(f"دستور .afk با موفقیت اجرا شد. دلیل: '{AFK_REASON}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .afk: {e}")
        await event.edit(f"خطا در فعال‌سازی AFK: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.unafk(?:@\w+)?$', outgoing=True))
async def unafk_command(event):
    """
    .unafk: حالت AFK شما را غیرفعال می‌کند.
    """
    global AFK_STATUS, AFK_REASON, AFK_START_TIME
    if event.sender_id != OWNER_ID:
        return

    if not AFK_STATUS:
        await event.edit("شما در حال حاضر AFK نیستید.")
        return

    AFK_STATUS = False
    AFK_REASON = ""
    afk_duration = ""
    if AFK_START_TIME:
        duration = datetime.datetime.now() - AFK_START_TIME
        afk_duration = f" ({human_readable_time(duration.total_seconds())} AFK بودید)."
        AFK_START_TIME = None

    response_text = f"حالت AFK غیرفعال شد! 👋{afk_duration}"
    try:
        await event.edit(response_text)
        logger.info(f"دستور .unafk با موفقیت اجرا شد. مدت AFK: {afk_duration}")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .unafk: {e}")
        await event.edit(f"خطا در غیرفعال‌سازی AFK: `{e}`")


@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private or (e.is_group and e.chat_id not in DISABLED_CHATS)))
async def afk_auto_reply_handler(event):
    """
    اگر AFK فعال باشد، به پیام‌های خصوصی و پیام‌های گروه (به جز چت‌های غیرفعال شده) پاسخ خودکار می‌دهد.
    """
    global AFK_STATUS, AFK_REASON, AFK_START_TIME, LAST_SEEN_MESSAGE
    
    # اگر پیام از طرف خودمان باشد یا AFK غیرفعال باشد، کاری انجام نمی‌دهیم.
    if event.sender_id == OWNER_ID or not AFK_STATUS:
        return
    
    # اگر پیام در گروه باشد و چت در لیست DISABLED_CHATS باشد، پاسخ نمی‌دهیم.
    if event.is_group and event.chat_id in DISABLED_CHATS:
        return

    # برای جلوگیری از اسپم کردن یک چت، فقط به اولین پیام در هر چت پاسخ می‌دهیم.
    # یا اگر پیام جدیدتر از آخرین پیام دیده شده باشد.
    if event.chat_id in LAST_SEEN_MESSAGE and event.message.id <= LAST_SEEN_MESSAGE[event.chat_id]:
        return

    # اگر کاربر ربات باشد، پاسخ نمی‌دهیم.
    sender = await event.get_sender()
    if sender and sender.bot:
        return

    try:
        duration = datetime.datetime.now() - AFK_START_TIME if AFK_START_TIME else "ناشناخته"
        afk_duration_text = f"به مدت **{human_readable_time(duration.total_seconds())}**" if isinstance(duration, datetime.timedelta) else str(duration)

        response_text = (
            f"سلام، من در حال حاضر AFK هستم. 😴\n"
            f"**دلیل:** `{AFK_REASON}`\n"
            f"**مدت زمان AFK:** {afk_duration_text}\n"
            f"به محض بازگشت پاسخ خواهم داد."
        )
        
        # در گروه‌ها، اگر روی پیام ما ریپلای شده باشد یا ما تگ شده باشیم، پاسخ می‌دهیم.
        if event.is_group:
            if event.is_reply and (await event.get_reply_message()).sender_id == OWNER_ID:
                await event.reply(response_text)
                LAST_SEEN_MESSAGE[event.chat_id] = event.message.id
                logger.info(f"پاسخ AFK به {event.sender_id} در گروه {event.chat_id} (ریپلای) ارسال شد.")
            elif f"@{ (await client.get_me()).username }" in event.raw_text: # اگر یوزرنیم ما تگ شده باشد
                await event.reply(response_text)
                LAST_SEEN_MESSAGE[event.chat_id] = event.message.id
                logger.info(f"پاسخ AFK به {event.sender_id} در گروه {event.chat_id} (تگ) ارسال شد.")
        elif event.is_private:
            await event.reply(response_text)
            LAST_SEEN_MESSAGE[event.chat_id] = event.message.id
            logger.info(f"پاسخ AFK به {event.sender_id} در چت خصوصی ارسال شد.")

    except YouBlockedUserError:
        logger.warning(f"ربات AFK نتوانست به کاربر {event.sender_id} پاسخ دهد: کاربر ربات را بلاک کرده.")
    except Exception as e:
        logger.error(f"خطا در ارسال پاسخ AFK به {event.sender_id} در چت {event.chat_id}: {e}")
        pass # پیام خطا را در چت ارسال نمی‌کنیم تا مزاحمت ایجاد نشود


@client.on(events.NewMessage(pattern=r'^\.afkignore(?:@\w+)?$', outgoing=True))
async def afk_ignore_command(event):
    """
    .afkignore: AFK را در چت فعلی غیرفعال می‌کند. (برای جلوگیری از اسپم در گروه‌های بزرگ)
    """
    if event.sender_id != OWNER_ID:
        return

    chat_id = event.chat_id
    if chat_id in DISABLED_CHATS:
        await event.edit("AFK از قبل در این چت نادیده گرفته شده است.")
    else:
        DISABLED_CHATS.add(chat_id)
        await event.edit("✅ AFK در این چت نادیده گرفته خواهد شد.")
        logger.info(f"AFK در چت {chat_id} غیرفعال شد.")

@client.on(events.NewMessage(pattern=r'^\.afkunignore(?:@\w+)?$', outgoing=True))
async def afk_unignore_command(event):
    """
    .afkunignore: AFK را در چت فعلی فعال می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    chat_id = event.chat_id
    if chat_id not in DISABLED_CHATS:
        await event.edit("AFK از قبل در این چت فعال است.")
    else:
        DISABLED_CHATS.remove(chat_id)
        await event.edit("✅ AFK در این چت دوباره فعال شد.")
        logger.info(f"AFK در چت {chat_id} فعال شد.")


@client.on(events.NewMessage(pattern=r'^\.shrug(?:@\w+)?$', outgoing=True))
async def shrug_command(event):
    """
    .shrug: شانه بالا انداختن (¯\\\_(ツ)\_/¯).
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        await event.edit('¯\\\_(ツ)\_/¯')
        logger.info("دستور .shrug با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .shrug: {e}")
        await event.edit(f"خطا در ارسال shrug: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.owo(?:@\w+)?$', outgoing=True))
async def owo_command(event):
    """
    .owo: ارسال "OwO".
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        await event.edit('OwO')
        logger.info("دستور .owo با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .owo: {e}")
        await event.edit(f"خطا در ارسال owo: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.cp (.*) ; (.*)(?:@\w+)?$', outgoing=True))
async def replace_text_command(event):
    """
    .cp <متن قدیمی> ; <متن جدید>: متن قدیمی را در پیام ریپلای شده با متن جدید جایگزین می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    if not event.is_reply:
        await event.edit("برای استفاده از این دستور، روی پیامی که می‌خواهید ویرایش کنید ریپلای کنید.")
        return

    try:
        old_text = event.pattern_match.group(1)
        new_text = event.pattern_match.group(2)
        replied_message = await event.get_reply_message()

        if replied_message.text and old_text in replied_message.text:
            updated_text = replied_message.text.replace(old_text, new_text)
            await replied_message.edit(updated_text)
            await event.delete() # پاک کردن دستور اصلی
            logger.info(f"دستور .cp با موفقیت اجرا شد. متن در پیام {replied_message.id} جایگزین شد.")
        else:
            await event.edit("متن قدیمی در پیام ریپلای شده یافت نشد یا پیام متنی نیست.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .cp: {e}")
        await event.edit(f"خطا در جایگزینی متن: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.reverse (.*)(?:@\w+)?$', outgoing=True))
async def reverse_text_command(event):
    """
    .reverse <متن>: متن ارسالی را برعکس می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        text_to_reverse = event.pattern_match.group(1)
        reversed_text = text_to_reverse[::-1]
        await event.edit(f'متن برعکس شده: `{reversed_text}`')
        logger.info(f"دستور .reverse با موفقیت اجرا شد: '{text_to_reverse}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .reverse: {e}")
        await event.edit(f"خطا در برعکس کردن متن: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.upcase (.*)(?:@\w+)?$', outgoing=True))
async def uppercase_command(event):
    """
    .upcase <متن>: متن را به حروف بزرگ تبدیل می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return
    try:
        text = event.pattern_match.group(1)
        await event.edit(f'`{text.upper()}`')
        logger.info(f"دستور .upcase با موفقیت اجرا شد: '{text}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .upcase: {e}")
        await event.edit(f"خطا در تبدیل به حروف بزرگ: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.lowcase (.*)(?:@\w+)?$', outgoing=True))
async def lowercase_command(event):
    """
    .lowcase <متن>: متن را به حروف کوچک تبدیل می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return
    try:
        text = event.pattern_match.group(1)
        await event.edit(f'`{text.lower()}`')
        logger.info(f"دستور .lowcase با موفقیت اجرا شد: '{text}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .lowcase: {e}")
        await event.edit(f"خطا در تبدیل به حروف کوچک: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.calc (.*)(?:@\w+)?$', outgoing=True))
async def calculate_command(event):
    """
    .calc <عبارت ریاضی>: یک عبارت ریاضی ساده را محاسبه می‌کند.
    برای امنیت، فقط از عملیات پایه و توابع math استفاده می‌شود.
    """
    if event.sender_id != OWNER_ID:
        return

    expression = event.pattern_match.group(1)
    
    # لیست توابع/مقادیر ایمن که می‌توانند استفاده شوند
    safe_dict = {
        'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'log': math.log, 'log10': math.log10, 'pi': math.pi, 'e': math.e,
        'abs': abs, 'round': round, 'sum': sum, 'max': max, 'min': min,
        'pow': pow, 'len': len # اضافه کردن توابع مفید دیگر
    }
    
    try:
        # فیلتر کردن عبارت برای حذف هر چیزی که غیر از اعداد، عملگرهای ریاضی و توابع امن باشد
        # این یک فیلتر قوی است اما ممکن است برخی عبارات معتبر را هم رد کند.
        # راه حل ایده‌آل یک parser ریاضی کامل است که فراتر از scope این اسکریپت است.
        
        # تنها کاراکترهای مجاز را در عبارت نگه دارید. این کار امنیتی مهم است.
        allowed_chars = "0123456789.+-*/()% " + "".join(c for c in safe_dict.keys())
        filtered_expression = "".join(c for c in expression if c in allowed_chars)

        # ارزیابی عبارت در یک محیط محدود شده
        result = eval(filtered_expression, {"__builtins__": None}, safe_dict)
        await event.edit(f'نتیجه: `{result}`')
        logger.info(f"دستور .calc با موفقیت اجرا شد. عبارت: '{expression}', نتیجه: {result}")
    except (SyntaxError, NameError, TypeError, ValueError, ZeroDivisionError) as e:
        logger.error(f"خطا در محاسبه عبارت '{expression}': {e}")
        await event.edit(f'خطا در عبارت ریاضی: `{e}`')
    except Exception as e:
        logger.error(f"خطای ناشناخته در محاسبه عبارت '{expression}': {e}")
        await event.edit(f'خطای ناشناخته در محاسبه: `{e}`')

@client.on(events.NewMessage(pattern=r'^\.quote(?:@\w+)?$', outgoing=True))
async def random_quote_command(event):
    """
    .quote: یک نقل قول تصادفی نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    quotes = [
        "تنها راه انجام کارهای بزرگ، دوست داشتن کاری است که انجام می‌دهید. - استیو جابز",
        "زندگی ۱۰% آن چیزی است که برای شما اتفاق می‌افتد و ۹۰% آن چیزی است که شما به آن واکنش نشان می‌دهید. - لو هولتز",
        "آینده متعلق به کسانی است که به زیبایی رویاهایشان ایمان دارند. - النور روزولت",
        "تغییر تنها چیزی است که ثابت می‌ماند. - هراکلیتوس",
        "موفقیت نهایی نیست، شکست کشنده نیست: این شجاعت ادامه دادن است که اهمیت دارد. - وینستون چرچیل",
        "شادی یک مقصد نیست، یک سفر است. - بن هپکینز",
        "هرگز از رویاپردازی دست نکشید، حتی اگر رویاهایتان شکسته شوند، با ایمان به آینده دوباره شروع کنید. - ناشناس",
        "پشت هر آرزویی، تلاشی نهفته است. - ناشناس",
        "سعی نکنید انسان موفق شوید، بلکه سعی کنید انسان باارزشی شوید. - آلبرت اینشتین"
    ]
    try:
        await event.edit(f'"{random.choice(quotes)}"')
        logger.info("دستور .quote با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .quote: {e}")
        await event.edit(f"خطا در دریافت نقل قول: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.dice(?:@\w+)?$', outgoing=True))
async def dice_command(event):
    """
    .dice: یک تاس مجازی (عدد ۱ تا ۶) پرتاب می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        await event.edit(f'🎲 شما پرتاب کردید: `{random.randint(1, 6)}`')
        logger.info("دستور .dice با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .dice: {e}")
        await event.edit(f"خطا در پرتاب تاس: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.coin(?:@\w+)?$', outgoing=True))
async def coin_command(event):
    """
    .coin: یک سکه مجازی پرتاب می‌کند (شیر یا خط).
    """
    if event.sender_id != OWNER_ID:
        return

    result = random.choice(['شیر 🦁', 'خط 🪙'])
    try:
        await event.edit(f'پرتاب سکه: `{result}`')
        logger.info("دستور .coin با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .coin: {e}")
        await event.edit(f"خطا در پرتاب سکه: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.roll(?:@\w+)?$', outgoing=True))
async def roll_command(event):
    """
    .roll: یک عدد تصادفی بین ۱ تا ۱۰۰ ایجاد می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        await event.edit(f'🔢 عدد تصادفی: `{random.randint(1, 100)}`')
        logger.info("دستور .roll با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .roll: {e}")
        await event.edit(f"خطا در تولید عدد تصادفی: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.choose (.*)(?:@\w+)?$', outgoing=True))
async def choose_command(event):
    """
    .choose <گزینه۱, گزینه۲, ...>: از بین گزینه‌های داده شده یکی را انتخاب می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    choices_str = event.pattern_match.group(1)
    if not choices_str:
        await event.edit("لطفاً گزینه‌هایی را برای انتخاب وارد کنید (با کاما جدا کنید).")
        return

    choices = [c.strip() for c in choices_str.split(',') if c.strip()]
    if not choices:
        await event.edit("هیچ گزینه‌ای برای انتخاب یافت نشد.")
        return

    try:
        chosen = random.choice(choices)
        await event.edit(f'من انتخاب کردم: `{chosen}`')
        logger.info(f"دستور .choose با موفقیت اجرا شد. انتخاب: '{chosen}' از '{choices_str}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .choose: {e}")
        await event.edit(f"خطا در انتخاب گزینه: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.gm(?:@\w+)?$', outgoing=True))
async def gm_command(event):
    """
    .gm: ارسال پیام "صبح بخیر".
    """
    if event.sender_id != OWNER_ID:
        return
    try:
        await event.edit("صبح بخیر! ☀️")
        logger.info("دستور .gm با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .gm: {e}")
        await event.edit(f"خطا در ارسال gm: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.gn(?:@\w+)?$', outgoing=True))
async def gn_command(event):
    """
    .gn: ارسال پیام "شب بخیر".
    """
    if event.sender_id != OWNER_ID:
        return
    try:
        await event.edit("شب بخیر! 🌙")
        logger.info("دستور .gn با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .gn: {e}")
        await event.edit(f"خطا در ارسال gn: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.time(?:@\w+)?$', outgoing=True))
async def time_command(event):
    """
    .time: زمان فعلی را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        await event.edit(f'زمان فعلی: `{current_time}`')
        logger.info(f"دستور .time با موفقیت اجرا شد: {current_time}")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .time: {e}")
        await event.edit(f"خطا در دریافت زمان: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.google (.*)(?:@\w+)?$', outgoing=True))
async def google_search_command(event):
    """
    .google <عبارت جستجو>: یک لینک جستجوی گوگل برای عبارت مورد نظر ایجاد می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    query = event.pattern_match.group(1)
    if not query:
        await event.edit("لطفاً عبارتی برای جستجو وارد کنید.")
        return

    search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    try:
        await event.edit(f"نتیجه جستجوی گوگل برای '{query}':\n[اینجا کلیک کنید]({search_url})")
        logger.info(f"دستور .google با موفقیت اجرا شد برای: '{query}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .google: {e}")
        await event.edit(f"خطا در ایجاد لینک جستجو: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.ddg (.*)(?:@\w+)?$', outgoing=True))
async def duckduckgo_search_command(event):
    """
    .ddg <عبارت جستجو>: یک لینک جستجوی DuckDuckGo برای عبارت مورد نظر ایجاد می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    query = event.pattern_match.group(1)
    if not query:
        await event.edit("لطفاً عبارتی برای جستجو وارد کنید.")
        return

    search_url = f"https://duckduckgo.com/?q={requests.utils.quote(query)}"
    try:
        await event.edit(f"نتیجه جستجوی DuckDuckGo برای '{query}':\n[اینجا کلیک کنید]({search_url})")
        logger.info(f"دستور .ddg با موفقیت اجرا شد برای: '{query}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .ddg: {e}")
        await event.edit(f"خطا در ایجاد لینک جستجو: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.id(?:@\w+)?$', outgoing=True))
async def get_target_id_command(event):
    """
    .id: User ID کاربر ریپلای شده یا چت فعلی را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        target_entity = await get_target_entity(event)

        if target_entity:
            if isinstance(target_entity, User):
                await event.edit(f"User ID کاربر: `{target_entity.id}`\nنام: {target_entity.first_name}")
            elif isinstance(target_entity, (Chat, Channel)):
                await event.edit(f"Chat ID: `{target_entity.id}`\nعنوان: {target_entity.title}")
            else:
                await event.edit("نتوانستم آیدی معتبری پیدا کنم.")
            logger.info(f"دستور .id با موفقیت اجرا شد. ID: {target_entity.id}")
        else:
            await event.edit("لطفاً روی یک پیام ریپلای کنید یا در چت خصوصی/گروه استفاده کنید.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .id: {e}")
        await event.edit(f"خطا در دریافت ID: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.username(?:@\w+)?$', outgoing=True))
async def get_target_username_command(event):
    """
    .username: یوزرنیم کاربر ریپلای شده یا خودتان را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        user_entity = await get_target_entity(event)

        if user_entity and isinstance(user_entity, User):
            username = user_entity.username
            if username:
                await event.edit(f"یوزرنیم: @{username}")
            else:
                await event.edit("این کاربر یوزرنیم عمومی ندارد.")
            logger.info(f"دستور .username با موفقیت اجرا شد. یوزرنیم: {username}")
        else:
            await event.edit("نتوانستم اطلاعات یوزرنیم را پیدا کنم.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .username: {e}")
        await event.edit(f"خطا در دریافت یوزرنیم: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.whois (.*)(?:@\w+)?$', outgoing=True))
@client.on(events.NewMessage(pattern=r'^\.whois(?:@\w+)?$', outgoing=True))
async def whois_command(event):
    """
    .whois [یوزرنیم/آیدی/ریپلای]: اطلاعات یک کاربر را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        input_param = event.pattern_match.group(1) if event.pattern_match and event.pattern_match.groups() else None
        target_entity = await get_target_entity(event, input_param)

        if not target_entity or not isinstance(target_entity, User):
            await event.edit("نتوانستم کاربر مورد نظر را پیدا کنم. لطفاً یوزرنیم، آیدی یا روی پیام ریپلای کنید.")
            return

        full_user = await client(GetFullUserRequest(target_entity.id))
        user = full_user.user
        
        # اطلاعات دقیق‌تر
        profile_photos_count = await client.get_profile_photos(user, limit=0, count=True)

        response = (
            f"**اطلاعات کاربر:**\n"
            f"نام: {user.first_name} {user.last_name or ''}\n"
            f"یوزرنیم: @{user.username or 'ندارد'}\n"
            f"آیدی کاربری: `{user.id}`\n"
            f"دسترسی‌ها: {('محدود' if user.restricted else 'عادی')}\n"
            f"وضعیت ربات: {('بله' if user.bot else 'خیر')}\n"
            f"تأیید شده: {('بله' if user.verified else 'خیر')}\n"
            f"ساخته شده توسط تلگرام: {('بله' if user.min else 'خیر')}\n"
            f"وضعیت آنلاین: {('آنلاین' if user.status and hasattr(user.status, 'expires') and (user.status.expires is None or user.status.expires > datetime.datetime.now()) else 'آفلاین')}\n"
            f"عکس پروفایل: {profile_photos_count} عدد\n"
            f"پروفایل: [لینک](tg://user?id={user.id})\n"
            f"شماره تلفن: `{full_user.full_user.phone_numbers[0] if full_user.full_user.phone_numbers else 'مخفی/ندارد'}`\n"
            f"بیو: {full_user.full_user.about or 'ندارد'}"
        )
        await event.edit(response, parse_mode='md')
        logger.info(f"دستور .whois با موفقیت اجرا شد برای کاربر: {user.id}")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .whois: {e}")
        await event.edit(f"خطا در دریافت اطلاعات کاربر: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.chatinfo (.*)(?:@\w+)?$', outgoing=True))
@client.on(events.NewMessage(pattern=r'^\.chatinfo(?:@\w+)?$', outgoing=True))
async def chat_info_command(event):
    """
    .chatinfo [یوزرنیم/آیدی/ریپلای]: اطلاعات یک چت (گروه/کانال) را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        input_param = event.pattern_match.group(1) if event.pattern_match and event.pattern_match.groups() else None
        target_chat = await get_chat_entity_from_event(event, input_param)

        if not target_chat or not isinstance(target_chat, (Chat, Channel)):
            await event.edit("نتوانستم چت مورد نظر را پیدا کنم یا ورودی یک چت نیست. لطفاً یوزرنیم، آیدی یا در داخل چت استفاده کنید.")
            return

        full_chat = await client(GetFullChannelRequest(target_chat.id)) if isinstance(target_chat, Channel) else None
        
        response = (
            f"**اطلاعات چت:**\n"
            f"عنوان: {target_chat.title}\n"
            f"آیدی چت: `{target_chat.id}`\n"
            f"نوع: {('کانال' if isinstance(target_chat, Channel) else 'گروه')}\n"
            f"یوزرنیم: @{target_chat.username or 'ندارد'}\n"
            f"اعضا: `{full_chat.full_chat.participants_count if full_chat else 'ناشناس'}`\n"
            f"پین شده: `{full_chat.full_chat.pinned_msg_id if full_chat and full_chat.full_chat.pinned_msg_id else 'خیر'}`\n"
            f"توضیحات: {full_chat.full_chat.about or 'ندارد' if full_chat else 'ندارد'}"
        )
        await event.edit(response, parse_mode='md')
        logger.info(f"دستور .chatinfo با موفقیت اجرا شد برای چت: {target_chat.id}")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .chatinfo: {e}")
        await event.edit(f"خطا در دریافت اطلاعات چت: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.pfp(?:@\w+)?$', outgoing=True))
async def get_profile_photo_command(event):
    """
    .pfp: عکس پروفایل کاربر ریپلای شده یا خودتان را ارسال می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        target_entity = await get_target_entity(event)

        if not target_entity or not isinstance(target_entity, User):
            await event.edit("نتوانستم کاربر مورد نظر را پیدا کنم.")
            return

        photos = await client.get_profile_photos(target_entity, limit=1)
        if photos:
            await client.send_file(event.chat_id, photos[0], caption=f"عکس پروفایل {target_entity.first_name}")
            await event.delete() # پاک کردن دستور اصلی
            logger.info(f"دستور .pfp با موفقیت اجرا شد برای کاربر: {target_entity.id}")
        else:
            await event.edit("این کاربر عکس پروفایل ندارد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .pfp: {e}")
        await event.edit(f"خطا در دریافت عکس پروفایل: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.setpfp (.*)(?:@\w+)?$', outgoing=True))
async def set_profile_photo_command(event):
    """
    .setpfp <مسیر_فایل/لینک_عکس>: عکس پروفایل شما را تنظیم می‌کند.
    مسیر فایل می‌تواند یک فایل محلی یا یک لینک مستقیم به عکس باشد.
    """
    if event.sender_id != OWNER_ID:
        return

    photo_input = event.pattern_match.group(1)
    if not photo_input:
        await event.edit("لطفاً مسیر فایل یا لینک عکس را وارد کنید.")
        return

    try:
        await event.edit("در حال تنظیم عکس پروفایل...")
        # اگر لینک باشد
        if photo_input.startswith("http://") or photo_input.startswith("https://"):
            if requests:
                response = requests.get(photo_input, stream=True, timeout=10)
                response.raise_for_status()
                temp_file_path = "temp_pfp.jpg"
                with open(temp_file_path, "wb") as f:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                await client(UploadProfilePhotoRequest(file=await client.upload_file(temp_file_path)))
                os.remove(temp_file_path)
            else:
                await event.edit("ماژول 'requests' برای دانلود عکس از لینک نصب نیست.")
                return
        # اگر مسیر فایل محلی باشد
        else:
            if not os.path.exists(photo_input):
                await event.edit(f"فایل یافت نشد: `{photo_input}`")
                return
            await client(UploadProfilePhotoRequest(file=await client.upload_file(photo_input)))

        await event.edit("✅ عکس پروفایل با موفقیت تنظیم شد!")
        logger.info(f"دستور .setpfp با موفقیت اجرا شد. عکس از: '{photo_input}'")
    except PhotoCropSizeSmallError:
        logger.error(f"خطا در تنظیم عکس پروفایل: عکس خیلی کوچک است.")
        await event.edit("خطا: عکس خیلی کوچک است، لطفاً عکس بزرگتری را انتخاب کنید.")
    except WebpageCurlFailedError:
        logger.error(f"خطا در تنظیم عکس پروفایل: مشکل در دانلود لینک عکس.")
        await event.edit("خطا در دانلود عکس از لینک. مطمئن شوید لینک معتبر است.")
    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در دانلود عکس از لینک با requests: {e}")
        await event.edit(f"خطا در دانلود عکس از لینک: `{e}`")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .setpfp: {e}")
        await event.edit(f"خطا در تنظیم عکس پروفایل: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.delpfp(?:@\w+)?$', outgoing=True))
async def delete_profile_photo_command(event):
    """
    .delpfp: آخرین عکس پروفایل شما را حذف می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        photos = await client.get_profile_photos('me', limit=1)
        if photos:
            await client(DeletePhotosRequest(id=[photos[0]]))
            await event.edit("✅ آخرین عکس پروفایل شما حذف شد.")
            logger.info("دستور .delpfp با موفقیت اجرا شد.")
        else:
            await event.edit("شما هیچ عکس پروفایلی برای حذف ندارید.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .delpfp: {e}")
        await event.edit(f"خطا در حذف عکس پروفایل: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.react (.+)(?:@\w+)?$', outgoing=True))
async def react_command(event):
    """
    .react <اموجی>: به پیامی که روی آن ریپلای شده، با اموجی واکنش نشان می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    if not event.is_reply:
        await event.edit("برای واکنش نشان دادن، روی یک پیام ریپلای کنید.")
        return

    try:
        emoji = event.pattern_match.group(1).strip()
        replied_message = await event.get_reply_message()
        await replied_message.react(emoji)
        await event.delete() # پاک کردن دستور اصلی
        logger.info(f"دستور .react با موفقیت اجرا شد با اموجی: '{emoji}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .react: {e}")
        await event.edit(f"خطا در واکنش نشان دادن: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.ud (.*)(?:@\w+)?$', outgoing=True))
async def urban_dictionary_command(event):
    """
    .ud <کلمه>: معنی یک کلمه را از Urban Dictionary جستجو می‌کند (نیاز به requests).
    """
    if event.sender_id != OWNER_ID:
        return
    if not requests:
        await event.edit("ماژول 'requests' نصب نیست. این دستور کار نمی‌کند. `pip install requests`")
        return

    term = event.pattern_match.group(1).strip()
    if not term:
        await event.edit("لطفاً کلمه‌ای برای جستجو در Urban Dictionary وارد کنید.")
        return

    url = f"http://api.urbandictionary.com/v0/define?term={term}"
    try:
        async with client.action(event.chat_id, 'typing'): # نمایش وضعیت "در حال تایپ"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data['list']:
                definition = data['list'][0]['definition']
                example = data['list'][0]['example']
                await event.edit(
                    f"**{term}**\n"
                    f"**معنی:** `{definition}`\n"
                    f"**مثال:** `{example}`"
                )
                logger.info(f"دستور .ud با موفقیت اجرا شد برای: '{term}'")
            else:
                await event.edit(f"معنایی برای '{term}' در Urban Dictionary یافت نشد.")
    except requests.exceptions.Timeout:
        logger.error(f"خطا: درخواست UD برای '{term}' به دلیل اتمام زمان انجام نشد.")
        await event.edit("خطا: زمان درخواست Urban Dictionary به پایان رسید.")
    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در درخواست Urban Dictionary برای '{term}': {e}")
        await event.edit(f"خطا در اتصال به Urban Dictionary: `{e}`")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .ud برای '{term}': {e}")
        await event.edit(f"خطای ناشناخته در Urban Dictionary: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.weather (.*)(?:@\w+)?$', outgoing=True))
async def weather_command(event):
    """
    .weather <شهر>: آب و هوای یک شهر را نمایش می‌دهد (نیاز به API Key از OpenWeatherMap و requests).
    """
    if event.sender_id != OWNER_ID:
        return
    if not requests:
        await event.edit("ماژول 'requests' نصب نیست. این دستور کار نمی‌کند. `pip install requests`")
        return

    if OWM_API_KEY == 'YOUR_OPENWEATHERMAP_API_KEY_HERE' or not OWM_API_KEY:
        await event.edit("خطا: API Key برای OpenWeatherMap تنظیم نشده است. لطفاً آن را در کد یا متغیر محیطی 'OWM_API_KEY' تنظیم کنید.")
        return

    city = event.pattern_match.group(1).strip()
    if not city:
        await event.edit("لطفاً نام شهری را برای آب و هوا وارد کنید.")
        return

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OWM_API_KEY}&units=metric&lang=fa"
    try:
        async with client.action(event.chat_id, 'typing'):
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data['cod'] == 200:
                main = data['main']
                weather_desc = data['weather'][0]['description']
                temp = main['temp']
                feels_like = main['feels_like']
                humidity = main['humidity']
                wind_speed = data['wind']['speed']
                city_name = data['name']
                country = data['sys']['country']

                weather_report = (
                    f"**آب و هوای {city_name}, {country}:**\n"
                    f"وضعیت: `{weather_desc.capitalize()}`\n"
                    f"دما: `{temp}°C` (حس می‌شود: `{feels_like}°C`)\n"
                    f"رطوبت: `{humidity}%`\n"
                    f"سرعت باد: `{wind_speed} m/s`"
                )
                await event.edit(weather_report)
                logger.info(f"دستور .weather با موفقیت اجرا شد برای: '{city}'")
            else:
                await event.edit(f"خطا در دریافت آب و هوا برای '{city}': {data.get('message', 'خطای ناشناخته')}")
    except requests.exceptions.Timeout:
        logger.error(f"خطا: درخواست آب و هوا برای '{city}' به دلیل اتمام زمان انجام نشد.")
        await event.edit("خطا: زمان درخواست آب و هوا به پایان رسید.")
    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در درخواست آب و هوا برای '{city}': {e}")
        await event.edit(f"خطا در اتصال به سرویس آب و هوا: `{e}`")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .weather برای '{city}': {e}")
        await event.edit(f"خطای ناشناخته در آب و هوا: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.wiki (.*)(?:@\w+)?$', outgoing=True))
async def wikipedia_command(event):
    """
    .wiki <عبارت جستجو>: خلاصه‌ای از ویکی‌پدیا را برای عبارت مورد نظر نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return
    if not wikipedia:
        await event.edit("ماژول 'wikipedia' نصب نیست. این دستور کار نمی‌کند. `pip install wikipedia`")
        return

    query = event.pattern_match.group(1).strip()
    if not query:
        await event.edit("لطفاً عبارتی برای جستجو در ویکی‌پدیا وارد کنید.")
        return

    try:
        async with client.action(event.chat_id, 'typing'):
            search_results = wikipedia.search(query, results=1)
            if search_results:
                page = wikipedia.page(search_results[0])
                summary = wikipedia.summary(search_results[0], sentences=3) # 3 جمله اول
                response_text = (
                    f"**{page.title}**\n"
                    f"`{summary}`\n"
                    f"[ادامه مطلب]({page.url})"
                )
                await event.edit(response_text, parse_mode='md', link_preview=False)
                logger.info(f"دستور .wiki با موفقیت اجرا شد برای: '{query}'")
            else:
                await event.edit(f"نتیجه‌ای برای '{query}' در ویکی‌پدیا یافت نشد.")
    except wikipedia.exceptions.PageError:
        logger.error(f"خطا: صفحه ویکی‌پدیا برای '{query}' یافت نشد.")
        await event.edit(f"نتیجه‌ای برای '{query}' در ویکی‌پدیا یافت نشد.")
    except wikipedia.exceptions.DisambiguationError as e:
        logger.warning(f"خطا: ابهام‌زدایی برای '{query}'. گزینه‌ها: {e.options}")
        await event.edit(f"ابهام برای '{query}'. لطفاً دقیق‌تر باشید. گزینه‌های احتمالی: {', '.join(e.options[:3])}...")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .wiki برای '{query}': {e}")
        await event.edit(f"خطای ناشناخته در ویکی‌پدیا: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.translate (\w{2}) (.*)(?:@\w+)?$', outgoing=True))
async def translate_command(event):
    """
    .translate <کد_زبان_مقصد> <متن>: متن را به زبان مقصد ترجمه می‌کند.
    مثال: .translate en سلام چطوری -> "Hello, how are you?"
    """
    if event.sender_id != OWNER_ID:
        return
    if not TRANSLATOR:
        await event.edit("ماژول ترجمه (google_trans_new یا deep_translator) نصب نیست. این دستور کار نمی‌کند.")
        return

    target_lang = event.pattern_match.group(1).lower()
    text_to_translate = event.pattern_match.group(2)

    if not text_to_translate:
        await event.edit("لطفاً متنی برای ترجمه وارد کنید.")
        return

    try:
        async with client.action(event.chat_id, 'typing'):
            # اگر از google_trans_new استفاده می‌کنید
            if hasattr(TRANSLATOR, 'translate'):
                translated_text = TRANSLATOR.translate(text_to_translate, lang_tgt=target_lang)
            # اگر از deep_translator.GoogleTranslator استفاده می‌کنید
            elif hasattr(TRANSLATOR, 'translate_text'):
                TRANSLATOR.target = target_lang # تغییر زبان مقصد
                translated_text = TRANSLATOR.translate_text(text_to_translate)
            else:
                translated_text = None # نباید اتفاق بیفتد

            if translated_text:
                await event.edit(f"**ترجمه به {target_lang.upper()}:**\n`{translated_text}`")
                logger.info(f"دستور .translate با موفقیت اجرا شد به {target_lang} برای: '{text_to_translate}'")
            else:
                await event.edit("خطا در ترجمه متن. پاسخ نامعتبر از سرور یا سرویس ترجمه.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .translate برای '{text_to_translate}': {e}")
        await event.edit(f"خطای ناشناخته در ترجمه: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.carbon(?:@\w+)?$', outgoing=True))
async def carbon_command(event):
    """
    .carbon: متن ریپلای شده را به فرمت "Carbon" تبدیل می‌کند (ارسال لینک Carbon.sh).
    """
    if event.sender_id != OWNER_ID:
        return

    if not event.is_reply:
        await event.edit("برای ایجاد Carbon، روی یک پیام ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        if not replied_message.text:
            await event.edit("پیام ریپلای شده حاوی متن نیست.")
            return

        code_text = replied_message.text
        # URL encode the text
        encoded_code = requests.utils.quote(code_text)
        carbon_url = f"https://carbon.now.sh/?bg=rgba(171,184,195,1)&t=material&wt=none&l=auto&width=680&ds=true&dsyoff=20px&dsblur=68px&wc=true&wa=true&pv=56px&ph=56px&ts=14px&tl=false&ss=true&ssr=false&bs=true&cl=false&code={encoded_code}"
        
        await event.edit(f"کد Carbon شما آماده شد:\n[مشاهده Carbon]({carbon_url})", parse_mode='md', link_preview=False)
        logger.info(f"دستور .carbon با موفقیت اجرا شد برای پیام {replied_message.id}.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .carbon: {e}")
        await event.edit(f"خطا در ایجاد Carbon: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.figlet (.*)(?:@\w+)?$', outgoing=True))
async def figlet_command(event):
    """
    .figlet <متن>: متن شما را به هنر اسکی (ASCII Art) با استفاده از Figlet تبدیل می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return
    if not pyfiglet:
        await event.edit("ماژول 'pyfiglet' نصب نیست. این دستور کار نمی‌کند. `pip install pyfiglet`")
        return

    text = event.pattern_match.group(1).strip()
    if not text:
        await event.edit("لطفاً متنی برای تبدیل به Figlet وارد کنید.")
        return

    try:
        figlet_text = pyfiglet.figlet_format(text)
        if len(figlet_text) > 4096: # محدودیت طول پیام تلگرام
            await event.edit("متن Figlet بیش از حد طولانی است و قابل ارسال نیست.")
            logger.warning(f"متن Figlet برای '{text}' بیش از حد طولانی شد.")
            return
        await event.edit(f'```\n{figlet_text}\n```', parse_mode='md')
        logger.info(f"دستور .figlet با موفقیت اجرا شد برای: '{text}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .figlet برای '{text}': {e}")
        await event.edit(f"خطا در ایجاد Figlet: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.speedtest(?:@\w+)?$', outgoing=True))
async def speedtest_command(event):
    """
    .speedtest: تست سرعت اینترنت (دانلود، آپلود، پینگ) را انجام می‌دهد.
    نیاز به نصب 'speedtest-cli' دارد: `pip install speedtest-cli`
    """
    if event.sender_id != OWNER_ID:
        return
    if not speedtest:
        await event.edit("ماژول 'speedtest-cli' نصب نیست. این دستور کار نمی‌کند. `pip install speedtest-cli`")
        return

    try:
        await event.edit("در حال اجرای تست سرعت اینترنت... این کار ممکن است چند دقیقه طول بکشد. ⏳")
        logger.info("شروع تست سرعت اینترنت...")

        # اجرای speedtest-cli به عنوان یک زیرپروسس
        process = subprocess.Popen(['speedtest', '--simple', '--share'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(timeout=120) # حداکثر 120 ثانیه انتظار

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8').strip()
            logger.error(f"خطا در اجرای speedtest-cli: {error_msg}")
            await event.edit(f"خطا در اجرای تست سرعت: `{error_msg}`")
            return

        result_text = stdout.decode('utf-8').strip()
        
        # استخراج لینک اشتراک‌گذاری اگر وجود داشته باشد
        share_link_match = re.search(r'Share results: (https?://www\.speedtest\.net/result/[^\s]+)', result_text)
        share_link = share_link_match.group(1) if share_link_match else "لینک اشتراک‌گذاری موجود نیست."

        await event.edit(f"**نتایج تست سرعت:**\n"
                         f"```\n{result_text}\n```\n"
                         f"[مشاهده در Speedtest.net]({share_link})", parse_mode='md', link_preview=True)
        logger.info("دستور .speedtest با موفقیت اجرا شد.")
    except subprocess.TimeoutExpired:
        logger.error("تست سرعت به دلیل اتمام زمان متوقف شد.")
        await event.edit("خطا: تست سرعت به دلیل اتمام زمان (۲ دقیقه) متوقف شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .speedtest: {e}")
        await event.edit(f"خطای ناشناخته در تست سرعت: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.ipinfo(?:@\w+)?$', outgoing=True))
async def ip_info_command(event):
    """
    .ipinfo: اطلاعات IP عمومی شما را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return
    if not requests:
        await event.edit("ماژول 'requests' نصب نیست. این دستور کار نمی‌کند. `pip install requests`")
        return

    try:
        await event.edit("در حال دریافت اطلاعات IP... 🌐")
        response = requests.get("https://ipapi.co/json/", timeout=5)
        response.raise_for_status()
        data = response.json()

        ip_address = data.get('ip')
        city = data.get('city')
        region = data.get('region')
        country = data.get('country_name')
        org = data.get('org')
        isp = data.get('asn') # asn معمولاً ISP را نشان می‌دهد

        info_text = (
            f"**اطلاعات IP عمومی شما:**\n"
            f"IP: `{ip_address or 'ناشناس'}`\n"
            f"شهر: `{city or 'ناشناس'}`\n"
            f"استان/منطقه: `{region or 'ناشناس'}`\n"
            f"کشور: `{country or 'ناشناس'}`\n"
            f"سازمان/ISP: `{org or isp or 'ناشناس'}`"
        )
        await event.edit(info_text)
        logger.info(f"دستور .ipinfo با موفقیت اجرا شد. IP: {ip_address}")
    except requests.exceptions.Timeout:
        logger.error("خطا: درخواست ipinfo به دلیل اتمام زمان انجام نشد.")
        await event.edit("خطا: زمان درخواست اطلاعات IP به پایان رسید.")
    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در درخواست ipinfo: {e}")
        await event.edit(f"خطا در اتصال به سرویس اطلاعات IP: `{e}`")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .ipinfo: {e}")
        await event.edit(f"خطای ناشناخته در دریافت اطلاعات IP: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.sysinfo(?:@\w+)?$', outgoing=True))
async def sysinfo_command(event):
    """
    .sysinfo: اطلاعات سیستم عامل، CPU و RAM را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return
    if not psutil:
        await event.edit("ماژول 'psutil' نصب نیست. این دستور کار نمی‌کند. `pip install psutil`")
        return

    try:
        await event.edit("در حال جمع‌آوری اطلاعات سیستم... 💻")
        
        # اطلاعات CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_cores_physical = psutil.cpu_count(logical=False)
        cpu_cores_logical = psutil.cpu_count(logical=True)

        # اطلاعات RAM
        ram = psutil.virtual_memory()
        total_ram = round(ram.total / (1024 ** 3), 2) # GB
        available_ram = round(ram.available / (1024 ** 3), 2) # GB
        used_ram_percent = ram.percent

        # اطلاعات دیسک (برای دیسک ریشه)
        disk = psutil.disk_usage('/')
        total_disk = round(disk.total / (1024 ** 3), 2) # GB
        used_disk = round(disk.used / (1024 ** 3), 2) # GB
        free_disk = round(disk.free / (1024 ** 3), 2) # GB
        disk_percent = disk.percent

        # اطلاعات سیستم عامل
        os_name = os.name
        platform_system = os.sys.platform # 'linux', 'win32', 'darwin'
        
        # زمان فعال بودن سیستم
        boot_time_timestamp = psutil.boot_time()
        boot_datetime = datetime.datetime.fromtimestamp(boot_time_timestamp)
        current_datetime = datetime.datetime.now()
        system_uptime_duration = current_datetime - boot_datetime
        system_uptime_text = human_readable_time(system_uptime_duration.total_seconds())

        info_text = (
            f"**اطلاعات سیستم:**\n"
            f"سیستم عامل: `{platform_system} ({os_name})`\n"
            f"زمان فعال بودن سیستم: `{system_uptime_text}`\n\n"
            f"**CPU:**\n"
            f"استفاده: `{cpu_percent}%`\n"
            f"هسته‌های فیزیکی: `{cpu_cores_physical}`\n"
            f"هسته‌های منطقی: `{cpu_cores_logical}`\n\n"
            f"**RAM:**\n"
            f"کل: `{total_ram} GB`\n"
            f"آزاد: `{available_ram} GB`\n"
            f"استفاده: `{used_ram_percent}%`\n\n"
            f"**فضای دیسک (ریشه):**\n"
            f"کل: `{total_disk} GB`\n"
            f"استفاده شده: `{used_disk} GB`\n"
            f"آزاد: `{free_disk} GB`\n"
            f"درصد استفاده: `{disk_percent}%`"
        )
        await event.edit(info_text)
        logger.info("دستور .sysinfo با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .sysinfo: {e}")
        await event.edit(f"خطا در دریافت اطلاعات سیستم: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.imdb (.*)(?:@\w+)?$', outgoing=True))
async def imdb_search_command(event):
    """
    .imdb <عنوان فیلم/سریال>: اطلاعات یک فیلم یا سریال را از IMDB نمایش می‌دهد.
    نیاز به API Key از OMDb API دارد.
    """
    if event.sender_id != OWNER_ID:
        return
    if not requests:
        await event.edit("ماژول 'requests' نصب نیست. این دستور کار نمی‌کند. `pip install requests`")
        return
    if OMDB_API_KEY == 'YOUR_OMDB_API_KEY_HERE' or not OMDB_API_KEY:
        await event.edit("خطا: API Key برای OMDb API تنظیم نشده است. لطفاً آن را در کد یا متغیر محیطی 'OMDB_API_KEY' تنظیم کنید.")
        return

    title = event.pattern_match.group(1).strip()
    if not title:
        await event.edit("لطفاً عنوان فیلم یا سریال را وارد کنید.")
        return

    url = f"http://www.omdbapi.com/?t={requests.utils.quote(title)}&apikey={OMDB_API_KEY}"
    try:
        await event.edit(f"در حال جستجوی `{title}` در IMDB... 🎬")
        response = requests.get(url, timeout=7)
        response.raise_for_status()
        data = response.json()

        if data.get('Response') == 'True':
            poster_url = data.get('Poster')
            
            # تهیه متن اطلاعات
            info_lines = [
                f"**عنوان:** `{data.get('Title')}`",
                f"**سال:** `{data.get('Year')}`",
                f"**ژانر:** `{data.get('Genre')}`",
                f"**کارگردان:** `{data.get('Director')}`",
                f"**بازیگران:** `{data.get('Actors')}`",
                f"**امتیاز IMDB:** `{data.get('imdbRating')}/10` ({data.get('imdbVotes')} رأی)",
                f"**خلاصه داستان:** `{data.get('Plot')}`",
                f"**لینک IMDB:** [imdb.com/title/{data.get('imdbID')}/](https://www.imdb.com/title/{data.get('imdbID')}/)"
            ]
            info_text = "\n".join(info_lines)

            # اگر پوستر موجود است، آن را ارسال می‌کنیم
            if poster_url and poster_url != "N/A":
                await client.send_file(event.chat_id, poster_url, caption=info_text, parse_mode='md')
                await event.delete() # پاک کردن دستور اصلی
            else:
                await event.edit(info_text, parse_mode='md', link_preview=False)

            logger.info(f"دستور .imdb با موفقیت اجرا شد برای: '{title}'")
        else:
            await event.edit(f"فیلم یا سریال `{title}` در IMDB یافت نشد. {data.get('Error', '')}")
    except requests.exceptions.Timeout:
        logger.error(f"خطا: درخواست IMDB برای '{title}' به دلیل اتمام زمان انجام نشد.")
        await event.edit("خطا: زمان درخواست IMDB به پایان رسید.")
    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در درخواست IMDB برای '{title}': {e}")
        await event.edit(f"خطا در اتصال به سرویس IMDB: `{e}`")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .imdb برای '{title}': {e}")
        await event.edit(f"خطای ناشناخته در IMDB: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.sendfile (.*)(?:@\w+)?$', outgoing=True))
async def send_file_command(event):
    """
    .sendfile <مسیر_فایل>: یک فایل از مسیر مشخص شده را ارسال می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    file_path = event.pattern_match.group(1).strip()
    if not file_path:
        await event.edit("لطفاً مسیر فایل را وارد کنید.")
        return
    
    if not os.path.exists(file_path):
        await event.edit(f"خطا: فایل در مسیر `{file_path}` یافت نشد.")
        return

    try:
        await event.edit(f"در حال ارسال فایل: `{os.path.basename(file_path)}`...")
        await client.send_file(event.chat_id, file_path)
        await event.delete() # پاک کردن دستور اصلی
        logger.info(f"دستور .sendfile با موفقیت اجرا شد. فایل: '{file_path}'")
    except ChatSendMediaForbiddenError:
        logger.error(f"خطا: اجازه ارسال رسانه در این چت وجود ندارد.")
        await event.edit("خطا: اجازه ارسال فایل در این چت را ندارید.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .sendfile برای '{file_path}': {e}")
        await event.edit(f"خطا در ارسال فایل: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.downloadmedia(?:@\w+)?$', outgoing=True))
async def download_media_command(event):
    """
    .downloadmedia: فایل رسانه‌ای (عکس، ویدئو، سند) پیام ریپلای شده را دانلود می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return
    if not event.is_reply:
        await event.edit("برای دانلود رسانه، روی پیامی که حاوی رسانه است ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        if not replied_message.media:
            await event.edit("پیام ریپلای شده حاوی رسانه نیست.")
            return

        await event.edit("در حال دانلود رسانه... 📥")
        download_path = await client.download_media(replied_message)
        if download_path:
            await event.edit(f"✅ رسانه در: `{download_path}` ذخیره شد.")
            logger.info(f"دستور .downloadmedia با موفقیت اجرا شد. رسانه پیام {replied_message.id} در '{download_path}' ذخیره شد.")
        else:
            await event.edit("خطا در دانلود رسانه.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .downloadmedia: {e}")
        await event.edit(f"خطا در دانلود رسانه: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.pin(?:@\w+)?$', outgoing=True))
async def pin_message_command(event):
    """
    .pin: پیامی که روی آن ریپلای شده را پین می‌کند (اگر ادمین باشید).
    """
    if event.sender_id != OWNER_ID:
        return

    if not event.is_reply:
        await event.edit("برای پین کردن پیام، روی آن ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        if event.is_private:
            await client.pin_message(event.chat_id, replied_message.id)
            await event.edit("✅ پیام با موفقیت پین شد.")
            logger.info(f"دستور .pin با موفقیت اجرا شد. پیام ID: {replied_message.id} در چت خصوصی پین شد.")
        elif event.is_group or event.is_channel:
            # بررسی کنیم که آیا کاربر ادمین است و اجازه پین کردن دارد
            can_pin = False
            try:
                my_participant = await client.get_participant(event.chat_id, OWNER_ID)
                if isinstance(my_participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
                    if my_participant.admin_rights and my_participant.admin_rights.pin_messages:
                        can_pin = True
            except (UserNotParticipantError, UserAdminInvalidError, ChannelPrivateError, ValueError):
                pass
            
            if can_pin:
                await client.pin_message(event.chat_id, replied_message.id)
                await event.edit("✅ پیام با موفقیت پین شد.")
                logger.info(f"دستور .pin با موفقیت اجرا شد. پیام ID: {replied_message.id} در چت {event.chat_id} پین شد.")
            else:
                await event.edit("شما اجازه پین کردن پیام در این چت را ندارید (ادمین نیستید یا حق پین کردن ندارید).")
        else:
            await event.edit("این دستور در این نوع چت پشتیبانی نمی‌شود.")

    except ChatAdminRequiredError:
        await event.edit("خطا: شما ادمین این چت نیستید یا دسترسی لازم را ندارید.")
        logger.warning(f"کاربر {OWNER_ID} در چت {event.chat_id} ادمین نیست یا حق پین ندارد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .pin: {e}")
        await event.edit(f"خطا در پین کردن پیام: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.unpin(?:@\w+)?$', outgoing=True))
async def unpin_message_command(event):
    """
    .unpin: آخرین پیام پین شده را از حالت پین خارج می‌کند (اگر ادمین باشید).
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        if event.is_group or event.is_channel:
            # بررسی حقوق ادمین
            can_unpin = False
            try:
                my_participant = await client.get_participant(event.chat_id, OWNER_ID)
                if isinstance(my_participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
                    if my_participant.admin_rights and my_participant.admin_rights.pin_messages: # حق پین برای unpin هم لازم است
                        can_unpin = True
            except (UserNotParticipantError, UserAdminInvalidError, ChannelPrivateError, ValueError):
                pass

            if can_unpin:
                chat_full = await client(GetFullChannelRequest(event.chat_id))
                if chat_full.full_chat.pinned_msg_id:
                    await client.unpin_message(event.chat_id, chat_full.full_chat.pinned_msg_id)
                    await event.edit("✅ آخرین پیام پین شده با موفقیت از حالت پین خارج شد.")
                    logger.info(f"دستور .unpin با موفقیت اجرا شد در چت {event.chat_id}.")
                else:
                    await event.edit("هیچ پیام پین شده‌ای در این چت یافت نشد.")
            else:
                await event.edit("شما اجازه خارج کردن پیام از پین در این چت را ندارید (ادمین نیستید یا حق پین کردن ندارید).")
        elif event.is_private:
            await event.edit("قابلیت unpin برای چت‌های خصوصی در حال حاضر به سادگی قابل دسترسی نیست.")
        else:
            await event.edit("این دستور فقط برای گروه‌ها/کانال‌ها یا چت خصوصی کار می‌کند.")
    except ChatAdminRequiredError:
        await event.edit("خطا: شما ادمین این چت نیستید یا دسترسی لازم را ندارید.")
        logger.warning(f"کاربر {OWNER_ID} در چت {event.chat_id} ادمین نیست یا حق unpin ندارد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .unpin: {e}")
        await event.edit(f"خطا در خارج کردن پیام از پین: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.forward (\d+)(?:@\w+)?$', outgoing=True))
async def forward_last_messages_command(event):
    """
    .forward <تعداد>: N پیام آخر در چت فعلی را به 'Saved Messages' (یا چت پاسخ‌داده شده) فوروارد می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        count_str = event.pattern_match.group(1)
        count = int(count_str) if count_str else 1 # پیش‌فرض یک پیام

        if count <= 0:
            await event.edit("لطفاً یک عدد مثبت برای تعداد پیام‌ها وارد کنید.")
            return

        target_chat = await client.get_entity('me') # پیش‌فرض: Saved Messages
        if event.is_reply:
            replied_message = await event.get_reply_message()
            # اگر روی یک کاربر/ربات ریپلای شده باشد، به آن چت خصوصی فوروارد می‌کند.
            # اگر روی پیام در یک گروه/کانال ریپلای شده باشد، به آن گروه/کانال فوروارد می‌کند.
            target_entity_from_reply = await get_target_entity(event)
            if target_entity_from_reply:
                target_chat = target_entity_from_reply


        messages_to_forward = []
        # iter_messages با offset_id به عقب برمی‌گردد.
        # ابتدا خود دستور forward را حذف می‌کنیم تا در لیست پیام‌های فوروارد نباشد.
        await event.delete() 

        async for msg in client.iter_messages(event.chat_id, limit=count, offset_id=event.message.id):
            messages_to_forward.append(msg)
        
        # فوروارد از قدیمی به جدید
        messages_to_forward.reverse() 
        
        if messages_to_forward:
            await client.send_message(event.chat_id, f"در حال فوروارد {len(messages_to_forward)} پیام به {target_chat.title if hasattr(target_chat, 'title') else target_chat.first_name}...", delete_in=3)
            # اگر target_chat یک کاربر باشد
            if isinstance(target_chat, User):
                # با استفاده از forward_messages
                await client.forward_messages(target_chat, messages_to_forward, from_peer=event.chat_id)
            else: # اگر گروه یا کانال باشد
                await client.forward_messages(target_chat, messages_to_forward, from_peer=event.chat_id)

            logger.info(f"دستور .forward با موفقیت اجرا شد. {len(messages_to_forward)} پیام فوروارد شد به {target_chat.id}.")
        else:
            await client.send_message(event.chat_id, "هیچ پیامی برای فوروارد کردن پیدا نشد.", delete_in=3)
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .forward: {e}")
        await client.send_message(event.chat_id, f"خطا در فوروارد کردن پیام‌ها: `{e}`", delete_in=5)


@client.on(events.NewMessage(pattern=r'^\.kick(?:@\w+)?$', outgoing=True))
async def kick_command(event):
    """
    .kick: کاربری که روی پیامش ریپلای شده را از گروه بیرون می‌کند (اگر ادمین باشید و حق حذف داشته باشید).
    """
    if event.sender_id != OWNER_ID:
        return
    if not event.is_group and not event.is_channel:
        await event.edit("این دستور فقط در گروه‌ها/کانال‌ها کار می‌کند.")
        return
    if not event.is_reply:
        await event.edit("برای کیک کردن کاربر، روی پیام او ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        target_user = await get_target_entity(event)

        if not target_user or not isinstance(target_user, User):
            await event.edit("نتوانستم کاربر مورد نظر را پیدا کنم.")
            return

        if target_user.id == OWNER_ID:
            await event.edit("شما نمی‌توانید خودتان را کیک کنید!")
            return
        
        # بررسی حقوق ادمین
        my_rights = await get_admin_rights(event.chat_id, OWNER_ID)
        if not my_rights or not my_rights.ban_users:
            await event.edit("شما ادمین نیستید یا حق حذف کاربر را ندارید.")
            return

        # کیک کردن کاربر
        await client.kick_participant(event.chat_id, target_user.id)
        await event.edit(f"✅ کاربر [{target_user.first_name}](tg://user?id={target_user.id}) با موفقیت کیک شد.")
        await event.delete(replied_message) # پاک کردن پیام ریپلای شده
        logger.info(f"کاربر {target_user.id} توسط {OWNER_ID} از چت {event.chat_id} کیک شد.")
    except UserAdminRightsForbiddenError:
        await event.edit("من اجازه کیک کردن این کاربر را ندارم (ممکن است ادمین یا سازنده باشد).")
        logger.warning(f"ربات نتوانست کاربر {target_user.id} را کیک کند (حقوق ادمین کافی نیست).")
    except ChatAdminRequiredError:
        await event.edit("من ادمین این چت نیستم یا حق لازم را ندارم.")
        logger.warning(f"ربات در چت {event.chat_id} ادمین نیست.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .kick: {e}")
        await event.edit(f"خطا در کیک کردن کاربر: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.ban(?:@\w+)?$', outgoing=True))
async def ban_command(event):
    """
    .ban: کاربری که روی پیامش ریپلای شده را از گروه بن می‌کند (اگر ادمین باشید و حق بن داشته باشید).
    """
    if event.sender_id != OWNER_ID:
        return
    if not event.is_group and not event.is_channel:
        await event.edit("این دستور فقط در گروه‌ها/کانال‌ها کار می‌کند.")
        return
    if not event.is_reply:
        await event.edit("برای بن کردن کاربر، روی پیام او ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        target_user = await get_target_entity(event)

        if not target_user or not isinstance(target_user, User):
            await event.edit("نتوانستم کاربر مورد نظر را پیدا کنم.")
            return

        if target_user.id == OWNER_ID:
            await event.edit("شما نمی‌توانید خودتان را بن کنید!")
            return
        
        my_rights = await get_admin_rights(event.chat_id, OWNER_ID)
        if not my_rights or not my_rights.ban_users:
            await event.edit("شما ادمین نیستید یا حق بن کردن کاربر را ندارید.")
            return

        # بن کردن کاربر
        await client.edit_permissions(event.chat_id, target_user.id, view_messages=False) # ban = cannot view messages
        await event.edit(f"✅ کاربر [{target_user.first_name}](tg://user?id={target_user.id}) با موفقیت بن شد.")
        await event.delete(replied_message)
        logger.info(f"کاربر {target_user.id} توسط {OWNER_ID} از چت {event.chat_id} بن شد.")
    except UserAdminRightsForbiddenError:
        await event.edit("من اجازه بن کردن این کاربر را ندارم (ممکن است ادمین یا سازنده باشد).")
        logger.warning(f"ربات نتوانست کاربر {target_user.id} را بن کند (حقوق ادمین کافی نیست).")
    except ChatAdminRequiredError:
        await event.edit("من ادمین این چت نیستم یا حق لازم را ندارم.")
        logger.warning(f"ربات در چت {event.chat_id} ادمین نیست.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .ban: {e}")
        await event.edit(f"خطا در بن کردن کاربر: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.unban(?:@\w+)?$', outgoing=True))
async def unban_command(event):
    """
    .unban: کاربری که روی پیامش ریپلای شده را از بن خارج می‌کند (اگر ادمین باشید و حق بن داشته باشید).
    """
    if event.sender_id != OWNER_ID:
        return
    if not event.is_group and not event.is_channel:
        await event.edit("این دستور فقط در گروه‌ها/کانال‌ها کار می‌کند.")
        return
    if not event.is_reply:
        await event.edit("برای خارج کردن کاربر از بن، روی پیام او ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        target_user = await get_target_entity(event)

        if not target_user or not isinstance(target_user, User):
            await event.edit("نتوانستم کاربر مورد نظر را پیدا کنم.")
            return
        
        my_rights = await get_admin_rights(event.chat_id, OWNER_ID)
        if not my_rights or not my_rights.ban_users:
            await event.edit("شما ادمین نیستید یا حق بن/آن‌بن کردن کاربر را ندارید.")
            return

        # آن‌بن کردن کاربر
        await client.edit_permissions(event.chat_id, target_user.id, view_messages=True, send_messages=True, send_media=True, send_stickers=True, send_gifs=True, send_games=True, send_inline=True, embed_links=True)
        await event.edit(f"✅ کاربر [{target_user.first_name}](tg://user?id={target_user.id}) با موفقیت آن‌بن شد.")
        await event.delete(replied_message)
        logger.info(f"کاربر {target_user.id} توسط {OWNER_ID} در چت {event.chat_id} آن‌بن شد.")
    except UserAdminRightsForbiddenError:
        await event.edit("من اجازه آن‌بن کردن این کاربر را ندارم (ممکن است ادمین یا سازنده باشد).")
        logger.warning(f"ربات نتوانست کاربر {target_user.id} را آن‌بن کند (حقوق ادمین کافی نیست).")
    except ChatAdminRequiredError:
        await event.edit("من ادمین این چت نیستم یا حق لازم را ندارم.")
        logger.warning(f"ربات در چت {event.chat_id} ادمین نیست.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .unban: {e}")
        await event.edit(f"خطا در آن‌بن کردن کاربر: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.mute(?: (\d+[smhd])?)?(?:@\w+)?$', outgoing=True))
async def mute_command(event):
    """
    .mute [مدت زمان]: کاربری که روی پیامش ریپلای شده را در گروه میوت می‌کند.
    مدت زمان: s=ثانیه, m=دقیقه, h=ساعت, d=روز. مثال: .mute 1h
    """
    if event.sender_id != OWNER_ID:
        return
    if not event.is_group and not event.is_channel:
        await event.edit("این دستور فقط در گروه‌ها/کانال‌ها کار می‌کند.")
        return
    if not event.is_reply:
        await event.edit("برای میوت کردن کاربر، روی پیام او ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        target_user = await get_target_entity(event)

        if not target_user or not isinstance(target_user, User):
            await event.edit("نتوانستم کاربر مورد نظر را پیدا کنم.")
            return

        if target_user.id == OWNER_ID:
            await event.edit("شما نمی‌توانید خودتان را میوت کنید!")
            return

        my_rights = await get_admin_rights(event.chat_id, OWNER_ID)
        if not my_rights or not my_rights.ban_users: # حق بن برای میوت کردن هم لازم است
            await event.edit("شما ادمین نیستید یا حق میوت کردن کاربر را ندارید.")
            return

        duration_str = event.pattern_match.group(1)
        until_date = None
        mute_reason = "بی‌دلیل"

        if duration_str:
            match = re.match(r'(\d+)([smhd])', duration_str)
            if match:
                value = int(match.group(1))
                unit = match.group(2)
                
                if unit == 's':
                    until_date = datetime.datetime.now() + datetime.timedelta(seconds=value)
                    mute_reason = f"{value} ثانیه"
                elif unit == 'm':
                    until_date = datetime.datetime.now() + datetime.timedelta(minutes=value)
                    mute_reason = f"{value} دقیقه"
                elif unit == 'h':
                    until_date = datetime.datetime.now() + datetime.timedelta(hours=value)
                    mute_reason = f"{value} ساعت"
                elif unit == 'd':
                    until_date = datetime.datetime.now() + datetime.timedelta(days=value)
                    mute_reason = f"{value} روز"
            else:
                await event.edit("فرمت مدت زمان نامعتبر است. مثال: `1h`, `30m`, `5d`")
                return
        
        # میوت کردن کاربر (فقط cannot send messages)
        await client.edit_permissions(event.chat_id, target_user.id, send_messages=False, until_date=until_date)
        
        await event.edit(f"✅ کاربر [{target_user.first_name}](tg://user?id={target_user.id}) به مدت **{mute_reason}** میوت شد.")
        await event.delete(replied_message)
        logger.info(f"کاربر {target_user.id} توسط {OWNER_ID} در چت {event.chat_id} میوت شد برای {mute_reason}.")
    except UserAdminRightsForbiddenError:
        await event.edit("من اجازه میوت کردن این کاربر را ندارم (ممکن است ادمین یا سازنده باشد).")
        logger.warning(f"ربات نتوانست کاربر {target_user.id} را میوت کند (حقوق ادمین کافی نیست).")
    except ChatAdminRequiredError:
        await event.edit("من ادمین این چت نیستم یا حق لازم را ندارم.")
        logger.warning(f"ربات در چت {event.chat_id} ادمین نیست.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .mute: {e}")
        await event.edit(f"خطا در میوت کردن کاربر: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.unmute(?:@\w+)?$', outgoing=True))
async def unmute_command(event):
    """
    .unmute: کاربری که روی پیامش ریپلای شده را از میوت خارج می‌کند.
    """
    if event.sender_id != OWNER_ID:
        return
    if not event.is_group and not event.is_channel:
        await event.edit("این دستور فقط در گروه‌ها/کانال‌ها کار می‌کند.")
        return
    if not event.is_reply:
        await event.edit("برای آن‌میوت کردن کاربر، روی پیام او ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        target_user = await get_target_entity(event)

        if not target_user or not isinstance(target_user, User):
            await event.edit("نتوانستم کاربر مورد نظر را پیدا کنم.")
            return

        my_rights = await get_admin_rights(event.chat_id, OWNER_ID)
        if not my_rights or not my_rights.ban_users: # حق بن برای آن‌میوت کردن هم لازم است
            await event.edit("شما ادمین نیستید یا حق آن‌میوت کردن کاربر را ندارید.")
            return

        # آن‌میوت کردن کاربر (بازگرداندن همه دسترسی‌های ارسال پیام)
        await client.edit_permissions(event.chat_id, target_user.id, send_messages=True, send_media=True, send_stickers=True, send_gifs=True, send_games=True, send_inline=True, embed_links=True)
        await event.edit(f"✅ کاربر [{target_user.first_name}](tg://user?id={target_user.id}) با موفقیت آن‌میوت شد.")
        await event.delete(replied_message)
        logger.info(f"کاربر {target_user.id} توسط {OWNER_ID} در چت {event.chat_id} آن‌میوت شد.")
    except UserAdminRightsForbiddenError:
        await event.edit("من اجازه آن‌میوت کردن این کاربر را ندارم (ممکن است ادمین یا سازنده باشد).")
        logger.warning(f"ربات نتوانست کاربر {target_user.id} را آن‌میوت کند (حقوق ادمین کافی نیست).")
    except ChatAdminRequiredError:
        await event.edit("من ادمین این چت نیستم یا حق لازم را ندارم.")
        logger.warning(f"ربات در چت {event.chat_id} ادمین نیست.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .unmute: {e}")
        await event.edit(f"خطا در آن‌میوت کردن کاربر: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.promote(?:@\w+)?$', outgoing=True))
async def promote_command(event):
    """
    .promote: کاربر ریپلای شده را به ادمین گروه/کانال ارتقا می‌دهد (فقط سازنده).
    **هشدار: این دستور فقط توسط مالک (سازنده) چت قابل اجراست و بسیار قدرتمند است.**
    """
    if event.sender_id != OWNER_ID:
        return
    if not event.is_group and not event.is_channel:
        await event.edit("این دستور فقط در گروه‌ها/کانال‌ها کار می‌کند.")
        return
    if not event.is_reply:
        await event.edit("برای ارتقا به ادمین، روی پیام کاربر ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        target_user = await get_target_entity(event)

        if not target_user or not isinstance(target_user, User):
            await event.edit("نتوانستم کاربر مورد نظر را پیدا کنم.")
            return
        
        if target_user.id == OWNER_ID:
            await event.edit("شما نمی‌توانید خودتان را ارتقا دهید (شما از قبل مالک هستید یا بالاترین دسترسی را دارید).")
            return

        # بررسی اینکه آیا خود کاربر (صاحب ربات) سازنده چت است
        try:
            my_participant = await client.get_participant(event.chat_id, OWNER_ID)
            if not isinstance(my_participant, ChannelParticipantCreator):
                await event.edit("این دستور فقط توسط سازنده چت قابل اجراست.")
                return
        except (UserNotParticipantError, ChannelPrivateError):
            await event.edit("شما عضو این چت نیستید یا چت خصوصی است.")
            return

        # ارتقا کاربر به ادمین با تمام حقوق (مثلاً)
        full_rights = ChatBannedRights(
            until_date=None,
            view_messages=False, send_messages=False, send_media=False, send_stickers=False,
            send_gifs=False, send_games=False, send_inline=False, embed_links=False,
            send_polls=False, change_info=True, edit_messages=True, delete_messages=True,
            ban_users=True, invite_users=True, pin_messages=True, add_admins=False, # add_admins فقط توسط سازنده
            manage_call=True
        )
        await client.edit_admin(event.chat_id, target_user.id, change_info=True, post_messages=True, edit_messages=True, delete_messages=True,
                                ban_users=True, invite_users=True, pin_messages=True, add_admins=False, anonymous=False, title='ادمین')
        
        await event.edit(f"✅ کاربر [{target_user.first_name}](tg://user?id={target_user.id}) با موفقیت به ادمین ارتقا یافت.")
        await event.delete(replied_message)
        logger.info(f"کاربر {target_user.id} توسط {OWNER_ID} در چت {event.chat_id} به ادمین ارتقا یافت.")
    except UserAdminRightsForbiddenError:
        await event.edit("من اجازه ارتقا این کاربر را ندارم.")
        logger.warning(f"ربات نتوانست کاربر {target_user.id} را ارتقا دهد (حقوق ادمین کافی نیست).")
    except ChatAdminRequiredError:
        await event.edit("من ادمین این چت نیستم یا حق لازم را ندارم.")
        logger.warning(f"ربات در چت {event.chat_id} ادمین نیست.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .promote: {e}")
        await event.edit(f"خطا در ارتقا کاربر: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.demote(?:@\w+)?$', outgoing=True))
async def demote_command(event):
    """
    .demote: کاربر ریپلای شده را از ادمینی خارج می‌کند (فقط سازنده).
    **هشدار: این دستور فقط توسط مالک (سازنده) چت قابل اجراست و بسیار قدرتمند است.**
    """
    if event.sender_id != OWNER_ID:
        return
    if not event.is_group and not event.is_channel:
        await event.edit("این دستور فقط در گروه‌ها/کانال‌ها کار می‌کند.")
        return
    if not event.is_reply:
        await event.edit("برای خارج کردن از ادمینی، روی پیام کاربر ریپلای کنید.")
        return

    try:
        replied_message = await event.get_reply_message()
        target_user = await get_target_entity(event)

        if not target_user or not isinstance(target_user, User):
            await event.edit("نتوانستم کاربر مورد نظر را پیدا کنم.")
            return

        if target_user.id == OWNER_ID:
            await event.edit("شما نمی‌توانید خودتان را از ادمینی خارج کنید!")
            return

        # بررسی اینکه آیا خود کاربر (صاحب ربات) سازنده چت است
        try:
            my_participant = await client.get_participant(event.chat_id, OWNER_ID)
            if not isinstance(my_participant, ChannelParticipantCreator):
                await event.edit("این دستور فقط توسط سازنده چت قابل اجراست.")
                return
        except (UserNotParticipantError, ChannelPrivateError):
            await event.edit("شما عضو این چت نیستید یا چت خصوصی است.")
            return

        # خارج کردن کاربر از ادمینی (با تنظیم حقوق به None)
        await client.edit_admin(event.chat_id, target_user.id, is_admin=False)
        
        await event.edit(f"✅ کاربر [{target_user.first_name}](tg://user?id={target_user.id}) با موفقیت از ادمینی خارج شد.")
        await event.delete(replied_message)
        logger.info(f"کاربر {target_user.id} توسط {OWNER_ID} در چت {event.chat_id} از ادمینی خارج شد.")
    except UserAdminRightsForbiddenError:
        await event.edit("من اجازه خارج کردن این کاربر از ادمینی را ندارم.")
        logger.warning(f"ربات نتوانست کاربر {target_user.id} را از ادمینی خارج کند (حقوق ادمین کافی نیست).")
    except ChatAdminRequiredError:
        await event.edit("من ادمین این چت نیستم یا حق لازم را ندارم.")
        logger.warning(f"ربات در چت {event.chat_id} ادمین نیست.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .demote: {e}")
        await event.edit(f"خطا در خارج کردن کاربر از ادمینی: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.uptime(?:@\w+)?$', outgoing=True))
async def uptime_command(event):
    """
    .uptime: مدت زمان فعال بودن اسکریپت را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    global SCRIPT_START_TIME
    if 'SCRIPT_START_TIME' not in globals():
        SCRIPT_START_TIME = datetime.datetime.now() # اگر به دلیلی تنظیم نشده بود، اینجا تنظیم شود.

    uptime_duration = datetime.datetime.now() - SCRIPT_START_TIME
    uptime_text = human_readable_time(uptime_duration.total_seconds())

    try:
        await event.edit(f"اسکریپت به مدت: `{uptime_text}` فعال است.")
        logger.info(f"دستور .uptime با موفقیت اجرا شد. Uptime: {uptime_text}")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .uptime: {e}")
        await event.edit(f"خطا در دریافت زمان فعالیت: `{e}`")

@client.on(events.NewMessage(pattern=r'^\.restart(?:@\w+)?$', outgoing=True))
async def restart_command(event):
    """
    .restart: اسکریپت را ری‌استارت می‌کند (با استفاده از os.execv).
    **توجه: این دستور اسکریپت را به طور کامل قطع کرده و دوباره از ابتدا اجرا می‌کند.
    ممکن است نیاز به اجرای مجدد از ترمینال باشد.**
    """
    if event.sender_id != OWNER_ID:
        return

    try:
        await event.edit("🔄 در حال ری‌استارت کردن اسکریپت...")
        logger.warning("اسکریپت در حال ری‌استارت شدن است.")
        # این باعث می‌شود پایتون یک پروسه جدید از خودش را با آرگومان‌های فعلی اجرا کند.
        # این تنها راه نسبتاً تمیز برای ری‌استارت کردن یک اسکریپت پایتون است.
        python = os.sys.executable
        os.execv(python, [python] + os.sys.argv)
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .restart: {e}")
        await event.edit(f"خطا در ری‌استارت کردن اسکریپت: `{e}`")


@client.on(events.NewMessage(pattern=r'^\.exec (.*)(?:@\w+)?$', outgoing=True))
async def exec_command(event):
    """
    .exec <کد پایتون>: یک خط کد پایتون را اجرا می‌کند.
    **هشدار: این دستور بسیار خطرناک است!** فقط کدهای مورد اعتماد خود را اجرا کنید.
    اجرای کدهای مخرب می‌تواند به سیستم شما آسیب برساند یا حساب تلگرام شما را به خطر بیندازد.
    """
    if event.sender_id != OWNER_ID:
        return

    code_to_execute = event.pattern_match.group(1)
    try:
        # برای امنیت، یک دیکشنری خالی به عنوان locals و globals فراهم می‌کنیم.
        # البته، این هنوز کامل نیست و امکان دسترسی به برخی توابع built-in وجود دارد.
        # استفاده از exec با دقت فراوان و فقط برای کدهای مطمئن توصیه می‌شود.
        # eval برای عبارات ساده امن‌تر است. exec برای دستورات چند خطی یا پیچیده‌تر.
        
        # بهتر است از یک Sandbox (محیط ایزوله) برای اجرای کد استفاده شود
        # اما پیاده‌سازی Sandbox از پیچیدگی این فایل فراتر می‌رود.
        
        # اجرای کد در یک محیط محدود شده
        output_buffer = io.StringIO()
        exec(
            code_to_execute,
            {"client": client, "event": event, "logger": logger, "__builtins__": {}}, # دسترسی محدود
            {"_result": None, "_print_capture": output_buffer}
        )
        result = output_buffer.getvalue()
        if not result: # اگر کدی چیزی چاپ نکرد، ممکن است متغیری را تنظیم کرده باشد
            result = "کد اجرا شد (خروجی متنی ندارد)."
        
        await event.edit(f"**خروجی اجرای کد:**\n```python\n{result}\n```")
        logger.info(f"دستور .exec با موفقیت اجرا شد. کد: '{code_to_execute}'")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .exec: {e}")
        await event.edit(f"**خطا در اجرای کد:**\n```\n{e}\n```")

# برای دستور .exec نیاز به import io داریم
import io


# --- لیست جامع دستورات برای نمایش در .help ---
COMMANDS_LIST = {
    ".ping": "تست می‌کند که ربات فعال است.",
    ".echo <متن>": "متن شما را بازتاب می‌دهد.",
    ".myid": "آیدی کاربری شما را نمایش می‌دهد.",
    ".chatid": "آیدی چت فعلی را نمایش می‌دهد.",
    ".info": "اطلاعات حساب شما را نشان می‌دهد.",
    ".del": "پیام ریپلای شده را پاک می‌کند (اگر خودتان یا ادمین با حق حذف باشید).",
    ".purge [تعداد]": "N پیام آخر ارسالی شما را پاک می‌کند (پیش‌فرض: ۱۰).",
    ".readall": "تمام پیام‌های خوانده نشده را به عنوان خوانده شده علامت می‌زند.",
    ".type <متن>": "شبیه‌سازی می‌کند که در حال تایپ متنی هستید و سپس آن را ارسال می‌کند.",
    ".afk [دلیل]": "حالت AFK (دور از کیبورد) را فعال می‌کند. به پیام‌های خصوصی و گروه‌ها پاسخ می‌دهد.",
    ".unafk": "حالت AFK را غیرفعال می‌کند.",
    ".afkignore": "AFK را در چت فعلی نادیده می‌گیرد (برای جلوگیری از اسپم در گروه‌های بزرگ).",
    ".afkunignore": "نادیده گرفتن AFK را در چت فعلی غیرفعال می‌کند.",
    ".shrug": "شانه بالا انداختن (¯\\\\\\_(ツ)\\_/¯).",
    ".owo": "ارسال 'OwO'.",
    ".cp <قدیمی> ; <جدید>": "متن قدیمی را در پیام ریپلای شده با متن جدید جایگزین می‌کند.",
    ".reverse <متن>": "متن ارسالی را برعکس می‌کند.",
    ".upcase <متن>": "متن را به حروف بزرگ تبدیل می‌کند.",
    ".lowcase <متن>": "متن را به حروف کوچک تبدیل می‌کند.",
    ".calc <عبارت>": "یک عبارت ریاضی ساده را محاسبه می‌کند (مثال: .calc 2+2*2).",
    ".quote": "یک نقل قول تصادفی نمایش می‌دهد.",
    ".dice": "یک تاس مجازی پرتاب می‌کند (۱ تا ۶).",
    ".coin": "یک سکه مجازی پرتاب می‌کند (شیر یا خط).",
    ".roll": "یک عدد تصادفی بین ۱ تا ۱۰۰ ایجاد می‌کند.",
    ".choose <گزینه۱, گزینه۲, ...>": "از بین گزینه‌های داده شده یکی را انتخاب می‌کند.",
    ".gm": "ارسال پیام 'صبح بخیر'.",
    ".gn": "ارسال پیام 'شب بخیر'.",
    ".time": "زمان فعلی را نمایش می‌دهد.",
    ".google <عبارت>": "یک لینک جستجوی گوگل برای عبارت مورد نظر ایجاد می‌کند.",
    ".ddg <عبارت>": "یک لینک جستجوی DuckDuckGo برای عبارت مورد نظر ایجاد می‌کند.",
    ".id": "آیدی کاربر ریپلای شده یا چت فعلی را نمایش می‌دهد.",
    ".username": "یوزرنیم کاربر ریپلای شده یا خودتان را نمایش می‌دهد.",
    ".whois [یوزرنیم/آیدی/ریپلای]": "اطلاعات یک کاربر را نمایش می‌دهد.",
    ".chatinfo [یوزرنیم/آیدی/ریپلای]": "اطلاعات یک چت (گروه/کانال) را نمایش می‌دهد.",
    ".pfp": "عکس پروفایل کاربر ریپلای شده یا خودتان را ارسال می‌کند.",
    ".setpfp <مسیر/لینک>": "عکس پروفایل شما را تنظیم می‌کند.",
    ".delpfp": "آخرین عکس پروفایل شما را حذف می‌کند.",
    ".react <اموجی>": "به پیامی که روی آن ریپلای شده، با اموجی واکنش نشان می‌دهد.",
    ".ud <کلمه>": "معنی یک کلمه را از Urban Dictionary جستجو می‌کند.",
    ".weather <شهر>": "آب و هوای یک شهر را نمایش می‌دهد (نیاز به OWM API Key).",
    ".wiki <عبارت>": "خلاصه‌ای از ویکی‌پدیا را برای عبارت مورد نظر نمایش می‌دهد.",
    ".translate <کد_زبان> <متن>": "متن را به زبان مقصد ترجمه می‌کند (مثال: .translate en سلام).",
    ".carbon": "متن ریپلای شده را به فرمت 'Carbon' تبدیل می‌کند (ارسال لینک Carbon.sh).",
    ".figlet <متن>": "متن شما را به هنر اسکی (ASCII Art) با استفاده از Figlet تبدیل می‌کند.",
    ".speedtest": "تست سرعت اینترنت (دانلود، آپلود، پینگ) را انجام می‌دهد.",
    ".ipinfo": "اطلاعات IP عمومی شما را نمایش می‌دهد.",
    ".sysinfo": "اطلاعات سیستم عامل، CPU و RAM را نمایش می‌دهد.",
    ".imdb <عنوان>": "اطلاعات یک فیلم/سریال را از IMDB نمایش می‌دهد (نیاز به OMDb API Key).",
    ".sendfile <مسیر_فایل>": "یک فایل از مسیر مشخص شده را ارسال می‌کند.",
    ".downloadmedia": "فایل رسانه‌ای پیام ریپلای شده را دانلود می‌کند.",
    ".pin": "پیام ریپلای شده را پین می‌کند (نیاز به دسترسی ادمین).",
    ".unpin": "آخرین پیام پین شده را از حالت پین خارج می‌کند (نیاز به دسترسی ادمین).",
    ".forward <تعداد>": "N پیام آخر را به Saved Messages یا چت ریپلای شده فوروارد می‌کند.",
    ".kick": "کاربر ریپلای شده را از گروه بیرون می‌کند (نیاز به ادمین بودن و حق بن).",
    ".ban": "کاربر ریپلای شده را از گروه بن می‌کند (نیاز به ادمین بودن و حق بن).",
    ".unban": "کاربر ریپلای شده را از بن خارج می‌کند (نیاز به ادمین بودن و حق بن).",
    ".mute [مدت زمان]": "کاربر ریپلای شده را در گروه میوت می‌کند (نیاز به ادمین بودن و حق بن).",
    ".unmute": "کاربر ریپلای شده را از میوت خارج می‌کند (نیاز به ادمین بودن و حق بن).",
    ".promote": "کاربر ریپلای شده را به ادمین گروه/کانال ارتقا می‌دهد (فقط سازنده).",
    ".demote": "کاربر ریپلای شده را از ادمینی خارج می‌کند (فقط سازنده).",
    ".uptime": "مدت زمان فعال بودن اسکریپت را نمایش می‌دهد.",
    ".restart": "اسکریپت را ری‌استارت می‌کند (ممکن است نیاز به اجرای مجدد از ترمینال باشد).",
    ".exec <کد پایتون>": "**بسیار خطرناک!** یک خط کد پایتون را اجرا می‌کند. فقط کدهای مورد اعتماد را اجرا کنید."
}


@client.on(events.NewMessage(pattern=r'^\.help(?:@\w+)?$', outgoing=True))
async def help_command(event):
    """
    .help: لیستی از دستورات موجود را نمایش می‌دهد.
    """
    if event.sender_id != OWNER_ID:
        return

    help_text_parts = []
    help_text_parts.append("**📜 راهنمای دستورات سلف-اکانت 📜**\n\n")
    help_text_parts.append("این لیست شامل دستوراتی است که می‌توانید با پیشوند `.` استفاده کنید. (مثال: `.ping`)\n")
    help_text_parts.append("اکثر دستورات فقط توسط شما قابل اجرا هستند (outgoing=True).\n\n")

    current_length = sum(len(part) for part in help_text_parts)
    current_page_commands = []
    page_number = 1
    
    # تقسیم دستورات به صفحات اگر خیلی طولانی شوند
    # تلگرام محدودیت ۴۰۹۶ کاراکتر برای هر پیام دارد.
    MAX_MESSAGE_LENGTH = 4000 

    for cmd, desc in sorted(COMMANDS_LIST.items()):
        cmd_line = f"`{cmd}`: {desc}\n"
        if current_length + len(cmd_line) > MAX_MESSAGE_LENGTH - 200: # 200 کاراکتر برای هشدار و ادامه پیام
            help_text_parts.append("\n**...ادامه در پیام بعدی...**\n")
            
            # ارسال صفحه فعلی و شروع صفحه جدید
            final_help_text = "".join(help_text_parts)
            await event.edit(final_help_text, parse_mode='md')
            
            help_text_parts = []
            page_number += 1
            help_text_parts.append(f"**📜 راهنمای دستورات - صفحه {page_number} 📜**\n\n")
            current_length = sum(len(part) for part in help_text_parts)
            
        help_text_parts.append(cmd_line)
        current_length += len(cmd_line)

    help_text_parts.append("\n**⚠️ هشدار مهم:**\n")
    help_text_parts.append("استفاده از اسکریپت‌های سلف-اکانت می‌تواند منجر به نقض شرایط خدمات تلگرام شود و ")
    help_text_parts.append("حساب کاربری شما را در معرض مسدود شدن دائمی قرار دهد. ")
    help_text_parts.append("لطفاً با مسئولیت خود و با رعایت کامل قوانین از آن استفاده کنید.")
    
    final_help_text = "".join(help_text_parts)

    try:
        await event.edit(final_help_text, parse_mode='md')
        logger.info("دستور .help با موفقیت اجرا شد.")
    except Exception as e:
        logger.error(f"خطا در اجرای دستور .help: {e}")
        await event.edit(f"خطا در نمایش راهنما: `{e}`")


# --- شروع به کار کلاینت ---
SCRIPT_START_TIME = datetime.datetime.now() # زمان شروع اسکریپت را ثبت می‌کند

async def main():
    """
    تابع اصلی برای راه‌اندازی و اجرای کلاینت تلگرام.
    """
    print("--- 🚀 در حال راه‌اندازی سلف-اکانت تلگرام 🚀 ---")
    print("در حال اتصال به تلگرام...")

    # بررسی تنظیمات حیاتی
    if API_ID == 'YOUR_API_ID_HERE' or API_HASH == 'YOUR_API_HASH_HERE' or OWNER_ID == 0:
        print("\n--- ❌ خطای تنظیمات حیاتی! ❌ ---")
        print("لطفاً مقادیر 'API_ID', 'API_HASH' و 'OWNER_ID' را در کد یا متغیرهای محیطی خود تنظیم کنید.")
        print("`API_ID` و `API_HASH` را از my.telegram.org دریافت کنید.")
        print("`OWNER_ID` را با ارسال پیام به @userinfobot در تلگرام پیدا کنید.")
        print("اسکریپت بدون تنظیم صحیح این مقادیر کار نخواهد کرد.")
        input("کلید Enter را فشار دهید تا خارج شوید...")
        return

    try:
        # اتصال به تلگرام
        await client.start()
        user_me = await client.get_me()
        print(f"✅ متصل شد! حساب: @{user_me.username or user_me.first_name} (ID: {user_me.id})")
        print(f"✅ مالک (Owner ID) تنظیم شده: `{OWNER_ID}`")
        if user_me.id != OWNER_ID:
            print("\n--- ⚠️ هشدار: User ID شما با OWNER_ID تنظیم شده در کد مطابقت ندارد! ---")
            print(f"لطفاً 'OWNER_ID' را به `{user_me.id}` تغییر دهید تا از امنیت کامل اطمینان حاصل کنید.")
            print("در غیر این صورت، ربات فقط به پیام‌های کاربر با ID فعلی 'OWNER_ID' پاسخ خواهد داد.")

        print("اسکریپت در حال گوش دادن به دستورات است. (پیشوند دستورات: .)")
        print("برای دستورات بیشتر، در تلگرام `.help` را ارسال کنید.")
        print("\n** ⚠️ هشدار جدی: این اسکریپت به شدت در تضاد با شرایط استفاده از تلگرام است. مسئولیت کامل و عواقب احتمالی با شماست. ⚠️ **")

        # برای بار اول که اجرا می‌کنید، باید شماره تلفن خود را وارد کنید و کد تأیید را دریافت کنید.
        # Telethon اطلاعات سشن را در فایلی به نام 'my_userbot_session.session' ذخیره می‌کند.

        # حلقه اصلی که کلاینت را زنده نگه می‌دارد
        await client.run_until_disconnected()

    except SessionPasswordNeededError:
        print("\n--- 🔐 رمز عبور دو مرحله‌ای (2FA) مورد نیاز است! 🔐 ---")
        print("لطفاً رمز عبور خود را وارد کنید.")
        password = input("رمز عبور: ")
        try:
            await client.start(password=password)
            print("✅ رمز عبور پذیرفته شد. متصل شد!")
            await client.run_until_disconnected()
        except Exception as e:
            logger.critical(f"خطا در ورود با رمز عبور دو مرحله‌ای: {e}")
            print(f"❌ خطای ورود با رمز عبور دو مرحله‌ای: {e}")
            print("لطفاً بررسی کنید که رمز عبور صحیح است.")
            input("کلید Enter را فشار دهید تا خارج شوید...")
    except Exception as e:
        logger.critical(f"خطای بحرانی در راه‌اندازی کلاینت: {e}")
        print(f"\n--- ❌ خطای بحرانی در راه‌اندازی کلاینت: {e} ❌ ---")
        print("مطمئن شوید API ID و API Hash صحیح هستند و اتصال به اینترنت برقرار است.")
        print("اگر برای اولین بار است که اجرا می‌کنید، ممکن است به دلیل مشکلات احراز هویت باشد.")
        print("فایل سشن (.session) را حذف کرده و مجدداً امتحان کنید.")
        input("کلید Enter را فشار دهید تا خارج شوید...")

if __name__ == '__main__':
    # Telethon و asyncio با هم کار می‌کنند
    asyncio.run(main())
