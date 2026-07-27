#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import sqlite3
import requests
from datetime import datetime
import jdatetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ===== تنظیمات session =====
session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry, pool_connections=100, pool_maxsize=100)
session.mount('https://', adapter)
session.mount('http://', adapter)

# ===== توکن =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6443963679"))

if not BOT_TOKEN:
    print("❌ توکن ربات پیدا نشد!")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN, timeout=60)
bot.session = session

print("=" * 50)
print("ربات مدیریت گروه")
print("=" * 50)
print(f"ادمین: {ADMIN_ID}")

try:
    bot_info = bot.get_me()
    print(f"نام کاربری: @{bot_info.username}")
except Exception as e:
    print(f"⚠️ خطا: {e}")
    print("ربات همچنان اجرا میشود...")

print("=" * 50)

# ===== دیتابیس =====
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        welcome_text TEXT,
        max_warnings INTEGER DEFAULT 3,
        lock_sticker INTEGER DEFAULT 0,
        lock_gif INTEGER DEFAULT 0,
        lock_voice INTEGER DEFAULT 0,
        lock_video INTEGER DEFAULT 0,
        lock_photo INTEGER DEFAULT 0,
        lock_file INTEGER DEFAULT 0,
        lock_all INTEGER DEFAULT 0
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        join_date TEXT
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        user_id INTEGER,
        warnings INTEGER DEFAULT 0,
        muted INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0,
        messages INTEGER DEFAULT 0,
        UNIQUE(group_id, user_id)
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        reporter_id INTEGER,
        reported_id INTEGER,
        message_id INTEGER,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        date TEXT
    )
''')

try:
    c.execute("ALTER TABLE groups ADD COLUMN lock_sticker INTEGER DEFAULT 0")
except:
    pass
try:
    c.execute("ALTER TABLE groups ADD COLUMN lock_gif INTEGER DEFAULT 0")
except:
    pass
try:
    c.execute("ALTER TABLE groups ADD COLUMN lock_voice INTEGER DEFAULT 0")
except:
    pass
try:
    c.execute("ALTER TABLE groups ADD COLUMN lock_video INTEGER DEFAULT 0")
except:
    pass
try:
    c.execute("ALTER TABLE groups ADD COLUMN lock_photo INTEGER DEFAULT 0")
except:
    pass
try:
    c.execute("ALTER TABLE groups ADD COLUMN lock_file INTEGER DEFAULT 0")
except:
    pass
try:
    c.execute("ALTER TABLE groups ADD COLUMN lock_all INTEGER DEFAULT 0")
except:
    pass

conn.commit()
print("✅ دیتابیس راه‌اندازی شد")

# ===== توابع دیتابیس =====
def get_welcome(group_id):
    c.execute('SELECT welcome_text FROM groups WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    return r[0] if r and r[0] else None

def set_welcome(group_id, text):
    c.execute('INSERT OR REPLACE INTO groups (group_id, welcome_text) VALUES (?, ?)', (group_id, text))
    conn.commit()

def get_max_warn(group_id):
    c.execute('SELECT max_warnings FROM groups WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    return r[0] if r else 3

def set_max_warn(group_id, count):
    c.execute('INSERT OR REPLACE INTO groups (group_id, max_warnings) VALUES (?, ?)', (group_id, count))
    conn.commit()

def get_lock_settings(group_id):
    c.execute('SELECT lock_sticker, lock_gif, lock_voice, lock_video, lock_photo, lock_file, lock_all FROM groups WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    if r:
        return {
            'sticker': r[0] if r[0] is not None else 0,
            'gif': r[1] if r[1] is not None else 0,
            'voice': r[2] if r[2] is not None else 0,
            'video': r[3] if r[3] is not None else 0,
            'photo': r[4] if r[4] is not None else 0,
            'file': r[5] if r[5] is not None else 0,
            'all': r[6] if r[6] is not None else 0
        }
    return {'sticker': 0, 'gif': 0, 'voice': 0, 'video': 0, 'photo': 0, 'file': 0, 'all': 0}

def update_lock_setting(group_id, setting, value):
    c.execute(f'UPDATE groups SET {setting} = ? WHERE group_id = ?', (value, group_id))
    conn.commit()

def add_user(user_id, name):
    c.execute('INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)', (user_id, name))
    conn.commit()

def add_member(group_id, user_id):
    c.execute('INSERT OR IGNORE INTO members (group_id, user_id) VALUES (?, ?)', (group_id, user_id))
    conn.commit()

def add_msg(group_id, user_id):
    c.execute('UPDATE members SET messages = messages + 1 WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    conn.commit()

def add_warn(group_id, user_id):
    c.execute('UPDATE members SET warnings = warnings + 1 WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    conn.commit()
    c.execute('SELECT warnings FROM members WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    r = c.fetchone()
    return r[0] if r else 1

def clear_warn(group_id, user_id):
    c.execute('UPDATE members SET warnings = 0 WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    conn.commit()

def remove_one_warn(group_id, user_id):
    c.execute('UPDATE members SET warnings = warnings - 1 WHERE group_id = ? AND user_id = ? AND warnings > 0', (group_id, user_id))
    conn.commit()
    c.execute('SELECT warnings FROM members WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    r = c.fetchone()
    return r[0] if r else 0

def mute_user(group_id, user_id):
    c.execute('UPDATE members SET muted = 1 WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    conn.commit()

def unmute_user(group_id, user_id):
    c.execute('UPDATE members SET muted = 0 WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    conn.commit()

def is_muted(group_id, user_id):
    c.execute('SELECT muted FROM members WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    r = c.fetchone()
    return r[0] == 1 if r else False

def get_top(group_id, limit=5):
    c.execute('''SELECT u.name, m.messages FROM members m 
                 JOIN users u ON m.user_id = u.user_id 
                 WHERE m.group_id = ? ORDER BY m.messages DESC LIMIT ?''', (group_id, limit))
    return c.fetchall()

def get_total_msgs(group_id):
    c.execute('SELECT SUM(messages) FROM members WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    return r[0] if r and r[0] else 0

def add_report(group_id, reporter_id, reported_id, msg_id, reason):
    c.execute('''INSERT INTO reports (group_id, reporter_id, reported_id, message_id, reason, date) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (group_id, reporter_id, reported_id, msg_id, reason, str(datetime.now())))
    conn.commit()
    return c.lastrowid

def upd_report(report_id, status):
    c.execute('UPDATE reports SET status = ? WHERE id = ?', (status, report_id))
    conn.commit()

# ===== توابع کمکی =====
def is_admin(user_id):
    return user_id == ADMIN_ID

def is_group_admin(group_id, user_id):
    if user_id == 1087968824:
        try:
            admins = bot.get_chat_administrators(group_id)
            return bool(admins)
        except:
            return False
    try:
        m = bot.get_chat_member(group_id, user_id)
        return m.status in ['administrator', 'creator']
    except:
        return False

def get_persian_date():
    now = jdatetime.datetime.now()
    weekdays = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه']
    months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
              'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
    return f"{weekdays[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"

def get_admins_mention(group_id):
    mentions = []
    try:
        admins = bot.get_chat_administrators(group_id)
        for a in admins:
            if not a.user.is_bot:
                if a.user.username:
                    mentions.append(f"@{a.user.username}")
                else:
                    mentions.append(f"<a href='tg://user?id={a.user.id}'>{a.user.first_name}</a>")
    except:
        pass
    return mentions

def get_user_link(user):
    return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

# ===== کیبوردها =====
def admin_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("بن", callback_data="ban"),
        InlineKeyboardButton("رفع بن", callback_data="unban")
    )
    kb.add(
        InlineKeyboardButton("سکوت", callback_data="mute"),
        InlineKeyboardButton("رفع سکوت", callback_data="unmute")
    )
    kb.add(
        InlineKeyboardButton("پین", callback_data="pin"),
        InlineKeyboardButton("حذف پین", callback_data="unpin")
    )
    kb.add(
        InlineKeyboardButton("اخطار", callback_data="warn"),
        InlineKeyboardButton("حذف اخطار", callback_data="removewarn"),
        InlineKeyboardButton("پاک‌سازی", callback_data="clearwarn")
    )
    kb.add(
        InlineKeyboardButton("تگ ادمین‌ها", callback_data="tagadmins"),
        InlineKeyboardButton("تگ همه", callback_data="tagall")
    )
    kb.add(
        InlineKeyboardButton("قفل سرویس‌ها", callback_data="lock_menu"),
        InlineKeyboardButton("آمار", callback_data="stats")
    )
    kb.add(
        InlineKeyboardButton("تنظیمات", callback_data="settings")
    )
    return kb

def lock_menu_keyboard(group_id):
    locks = get_lock_settings(group_id)
    kb = InlineKeyboardMarkup(row_width=2)
    status = "روشن" if locks['all'] else "خاموش"
    kb.add(InlineKeyboardButton(f"قفل همه: {status}", callback_data=f"lock_all_{group_id}"))
    kb.add(
        InlineKeyboardButton(f"استیکر: {'روشن' if locks['sticker'] else 'خاموش'}", callback_data=f"lock_sticker_{group_id}"),
        InlineKeyboardButton(f"گیف: {'روشن' if locks['gif'] else 'خاموش'}", callback_data=f"lock_gif_{group_id}")
    )
    kb.add(
        InlineKeyboardButton(f"ویس: {'روشن' if locks['voice'] else 'خاموش'}", callback_data=f"lock_voice_{group_id}"),
        InlineKeyboardButton(f"ویدیو: {'روشن' if locks['video'] else 'خاموش'}", callback_data=f"lock_video_{group_id}")
    )
    kb.add(
        InlineKeyboardButton(f"عکس: {'روشن' if locks['photo'] else 'خاموش'}", callback_data=f"lock_photo_{group_id}"),
        InlineKeyboardButton(f"فایل: {'روشن' if locks['file'] else 'خاموش'}", callback_data=f"lock_file_{group_id}")
    )
    kb.add(InlineKeyboardButton("بازگشت", callback_data="back_main"))
    return kb

def report_keyboard(report_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("بررسی شد", callback_data=f"res_{report_id}"),
        InlineKeyboardButton("حذف", callback_data=f"del_{report_id}")
    )
    return kb

# ===== ادامه کد اصلی =====
@bot.message_handler(commands=['start'])
def start(msg):
    if msg.chat.type == 'private':
        bot.send_message(msg.chat.id, 
            "به ربات مدیریت گروه خوش آمدید\n\nربات را به گروه اضافه کنید و ادمین کنید",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("افزودن به گروه", url=f"https://t.me/{bot.get_me().username}?startgroup=botstart")
            )
        )

@bot.message_handler(content_types=['new_chat_members'])
def welcome(msg):
    group_id = msg.chat.id
    c.execute('INSERT OR IGNORE INTO groups (group_id) VALUES (?)', (group_id,))
    conn.commit()
    try:
        bot.delete_message(group_id, msg.message_id)
    except:
        pass
    for m in msg.new_chat_members:
        if m.id == bot.get_me().id:
            bot.send_message(group_id, "ربات با موفقیت به گروه اضافه شد")
            return
        add_user(m.id, m.first_name)
        add_member(group_id, m.id)
        user_link = get_user_link(m)
        group_name = msg.chat.title
        join_date = get_persian_date()
        welcome_msg = f"سلام {user_link} عزیز\nبه گروه {group_name} خوش آمدید 👋\n\n"
        custom_text = get_welcome(group_id)
        if custom_text:
            welcome_msg += f"{custom_text}\n\n"
        welcome_msg += f"تاریخ عضویت: {join_date}"
        bot.send_message(group_id, welcome_msg, parse_mode='HTML')

@bot.message_handler(content_types=['left_chat_member'])
def member_left(msg):
    group_id = msg.chat.id
    try:
        bot.delete_message(group_id, msg.message_id)
    except:
        pass

# ===== چک کردن قفل‌ها =====
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'], content_types=['sticker', 'animation', 'voice', 'video', 'photo', 'document'])
def check_locks(msg):
    group_id = msg.chat.id
    user_id = msg.from_user.id
    if is_admin(user_id) or is_group_admin(group_id, user_id):
        return
    locks = get_lock_settings(group_id)
    if locks['all']:
        try:
            bot.delete_message(group_id, msg.message_id)
        except:
            pass
        return
    content_type = None
    if msg.sticker: content_type = 'sticker'
    elif msg.animation: content_type = 'gif'
    elif msg.voice: content_type = 'voice'
    elif msg.video: content_type = 'video'
    elif msg.photo: content_type = 'photo'
    elif msg.document: content_type = 'file'
    if content_type and locks.get(content_type, 0):
        try:
            bot.delete_message(group_id, msg.message_id)
        except:
            pass

@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'], content_types=['text'])
def handle(msg):
    group_id = msg.chat.id
    user_id = msg.from_user.id
    text = msg.text.strip() if msg.text else ""
    c.execute('INSERT OR IGNORE INTO groups (group_id) VALUES (?)', (group_id,))
    conn.commit()
    add_user(user_id, msg.from_user.first_name)
    add_member(group_id, user_id)
    add_msg(group_id, user_id)
    admin = is_admin(user_id) or is_group_admin(group_id, user_id)
    
    if not admin:
        if msg.reply_to_message and text == 'گزارش':
            reported = msg.reply_to_message.from_user
            if reported.id == user_id:
                bot.send_message(group_id, "❌ نمی‌توانید خود را گزارش کنید")
                return
            if is_group_admin(group_id, reported.id):
                bot.send_message(group_id, "❌ نمی‌توانید ادمین را گزارش کنید")
                return
            reason = "بدون دلیل"
            if len(msg.text.split()) > 1:
                reason = msg.text.replace('گزارش', '').strip()
            report_id = add_report(group_id, user_id, reported.id, msg.reply_to_message.message_id, reason)
            admin_mentions = get_admins_mention(group_id)
            admin_text = " ".join(admin_mentions) if admin_mentions else ""
            report_msg = f"{admin_text}\n\n" if admin_text else ""
            report_msg += f"📋 گزارش جدید\n\n"
            report_msg += f"👤 گزارش دهنده: {get_user_link(msg.from_user)}\n"
            report_msg += f"👤 گزارش شده: {get_user_link(reported)}\n"
            report_msg += f"📝 دلیل: {reason}"
            bot.send_message(group_id, report_msg, parse_mode='HTML', reply_markup=report_keyboard(report_id))
            bot.send_message(group_id, "• گزارش شما برای مدیران گروه ارسال شد!​")
        return
    
    if text == 'پنل':
        bot.send_message(group_id, "🛠 پنل مدیریت\n\nروی پیام کاربر ریپلای کنید", reply_markup=admin_keyboard())
        return
    
    if text == 'آمار':
        top = get_top(group_id, 5)
        total = get_total_msgs(group_id)
        date = get_persian_date()
        t = f"📊 فعالیت های امروز:\n\n"
        t += f"📅 تاریخ: {date}\n\n"
        t += f"💬 کل پیام ها: {total}\n\n"
        t += "🏆 فعال ترین اعضا:\n"
        if top:
            medals = ['🥇', '🥈', '🥉', '😍', '😍']
            for i, (name, msgs) in enumerate(top):
                t += f"{medals[i]} {name}: {msgs} پیام\n"
        else:
            t += "❌ هیچ فعالیتی ثبت نشده است"
        bot.send_message(group_id, t)
        return
    
    # ===== قفل سرویس‌ها =====
    if text == 'قفل استیکر روشن':
        update_lock_setting(group_id, 'lock_sticker', 1)
        bot.send_message(group_id, "🔒 قفل استیکر روشن شد")
        return
    if text == 'قفل استیکر خاموش':
        update_lock_setting(group_id, 'lock_sticker', 0)
        bot.send_message(group_id, "🔓 قفل استیکر خاموش شد")
        return
    if text == 'قفل گیف روشن':
        update_lock_setting(group_id, 'lock_gif', 1)
        bot.send_message(group_id, "🔒 قفل گیف روشن شد")
        return
    if text == 'قفل گیف خاموش':
        update_lock_setting(group_id, 'lock_gif', 0)
        bot.send_message(group_id, "🔓 قفل گیف خاموش شد")
        return
    if text == 'قفل ویس روشن':
        update_lock_setting(group_id, 'lock_voice', 1)
        bot.send_message(group_id, "🔒 قفل ویس روشن شد")
        return
    if text == 'قفل ویس خاموش':
        update_lock_setting(group_id, 'lock_voice', 0)
        bot.send_message(group_id, "🔓 قفل ویس خاموش شد")
        return
    if text == 'قفل ویدیو روشن':
        update_lock_setting(group_id, 'lock_video', 1)
        bot.send_message(group_id, "🔒 قفل ویدیو روشن شد")
        return
    if text == 'قفل ویدیو خاموش':
        update_lock_setting(group_id, 'lock_video', 0)
        bot.send_message(group_id, "🔓 قفل ویدیو خاموش شد")
        return
    if text == 'قفل عکس روشن':
        update_lock_setting(group_id, 'lock_photo', 1)
        bot.send_message(group_id, "🔒 قفل عکس روشن شد")
        return
    if text == 'قفل عکس خاموش':
        update_lock_setting(group_id, 'lock_photo', 0)
        bot.send_message(group_id, "🔓 قفل عکس خاموش شد")
        return
    if text == 'قفل فایل روشن':
        update_lock_setting(group_id, 'lock_file', 1)
        bot.send_message(group_id, "🔒 قفل فایل روشن شد")
        return
    if text == 'قفل فایل خاموش':
        update_lock_setting(group_id, 'lock_file', 0)
        bot.send_message(group_id, "🔓 قفل فایل خاموش شد")
        return
    if text == 'قفل همه روشن':
        update_lock_setting(group_id, 'lock_all', 1)
        bot.send_message(group_id, "🔒 قفل همه روشن شد")
        return
    if text == 'قفل همه خاموش':
        update_lock_setting(group_id, 'lock_all', 0)
        bot.send_message(group_id, "🔓 قفل همه خاموش شد")
        return
    
    # ===== تنظیمات =====
    if text.startswith('تنظیم خوشامد'):
        new = text.replace('تنظیم خوشامد', '').strip()
        if new:
            set_welcome(group_id, new)
            bot.send_message(group_id, f"✅ متن اضافی خوش‌آمدگویی تنظیم شد:\n\n{new}")
        else:
            bot.send_message(group_id, "❌ لطفاً متن را وارد کنید")
        return
    
    if text.startswith('تنظیم اخطار'):
        try:
            n = int(text.replace('تنظیم اخطار', '').strip())
            if n < 1:
                bot.send_message(group_id, "❌ حداقل 1")
                return
            set_max_warn(group_id, n)
            bot.send_message(group_id, f"✅ تعداد اخطارها به {n} تنظیم شد")
        except:
            bot.send_message(group_id, "❌ عدد معتبر وارد کنید")
        return
    
    if text == 'راهنما':
        help_text = (
            "📖 راهنمای ربات:\n\n"
            "🔹 دستورات ادمین (با ریپلای):\n"
            "• بن - اخراج کاربر\n"
            "• رفع بن - برگرداندن کاربر\n"
            "• سکوت - سکوت نامحدود\n"
            "• سکوت 10 - سکوت 10 دقیقه‌ای\n"
            "• رفع سکوت - برداشتن سکوت\n"
            "• پین - پین کردن پیام\n"
            "• حذف پین - حذف پین\n"
            "• اخطار - اخطار به کاربر\n"
            "• حذف اخطار - حذف یک اخطار\n"
            "• پاک‌سازی - پاک کردن همه اخطارها\n\n"
            "🔹 کاربران عادی:\n"
            "• گزارش - گزارش پیام (با ریپلای)\n\n"
            "🔹 دستورات:\n"
            "• پنل - نمایش پنل مدیریت\n"
            "• آمار - نمایش آمار\n"
            "• راهنما - نمایش این راهنما\n"
            "• تنظیم خوشامد متن - تنظیم متن اضافی\n"
            "• تنظیم اخطار عدد - تنظیم تعداد اخطارها"
        )
        bot.send_message(group_id, help_text)
        return
    
    if not msg.reply_to_message:
        return
    
    replied = msg.reply_to_message.from_user
    rid = replied.id
    
    if text == 'تگ همه':
        try:
            all_members = []
            admins = bot.get_chat_administrators(group_id)
            for a in admins:
                if not a.user.is_bot:
                    all_members.append(f"<a href='tg://user?id={a.user.id}'>{a.user.first_name}</a>")
            try:
                offset = 0
                while len(all_members) < 50:
                    members = bot.get_chat_members(group_id, offset=offset)
                    if not members:
                        break
                    for m in members:
                        if not m.user.is_bot and m.user.id not in [a.user.id for a in admins]:
                            all_members.append(f"<a href='tg://user?id={m.user.id}'>{m.user.first_name}</a>")
                    offset += 50
            except:
                pass
            if not all_members:
                bot.send_message(group_id, "❌ هیچ کاربری برای تگ کردن وجود ندارد")
                return
            msg_text = f"🔔 تگ همه کاربران\n\n" + " ".join(all_members[:50])
            bot.send_message(group_id, msg_text, parse_mode='HTML', reply_to_message_id=msg.reply_to_message.message_id)
            if len(all_members) > 50:
                bot.send_message(group_id, f"✅ {len(all_members[:50])} کاربر از {len(all_members)} تگ شدند")
            else:
                bot.send_message(group_id, f"✅ {len(all_members)} کاربر تگ شدند")
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        return
    
    if text == 'بن':
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید خود را بن کنید")
            return
        if is_group_admin(group_id, rid):
            bot.send_message(group_id, "❌ نمی‌توانید ادمین را بن کنید")
            return
        try:
            bot.ban_chat_member(group_id, rid)
            bot.send_message(group_id, f"🚫 کاربر {get_user_link(replied)} بن شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    elif text == 'رفع بن':
        try:
            bot.unban_chat_member(group_id, rid)
            bot.send_message(group_id, f"✅ بن کاربر {get_user_link(replied)} برداشته شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    elif text.startswith('سکوت'):
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید خود را سکوت کنید")
            return
        if is_group_admin(group_id, rid):
            bot.send_message(group_id, "❌ نمی‌توانید ادمین را سکوت کنید")
            return
        if is_muted(group_id, rid):
            bot.send_message(group_id, f"ℹ️ کاربر {get_user_link(replied)} قبلاً سکوت است", parse_mode='HTML')
            return
        minutes = 0
        parts = text.split()
        if len(parts) > 1:
            try:
                minutes = int(parts[1])
            except:
                pass
        try:
            if minutes > 0:
                until = int(time.time()) + (minutes * 60)
                bot.restrict_chat_member(group_id, rid, can_send_messages=False, until_date=until)
                mute_user(group_id, rid)
                bot.send_message(group_id, f"🔇 کاربر {get_user_link(replied)} به مدت {minutes} دقیقه سکوت شد", parse_mode='HTML')
            else:
                bot.restrict_chat_member(group_id, rid, can_send_messages=False)
                mute_user(group_id, rid)
                bot.send_message(group_id, f"🔇 کاربر {get_user_link(replied)} سکوت شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    elif text == 'رفع سکوت':
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید خود را رفع سکوت کنید")
            return
        if not is_muted(group_id, rid):
            bot.send_message(group_id, f"ℹ️ کاربر {get_user_link(replied)} سکوت نیست", parse_mode='HTML')
            return
        try:
            bot.restrict_chat_member(group_id, rid, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
            unmute_user(group_id, rid)
            bot.send_message(group_id, f"✅ سکوت کاربر {get_user_link(replied)} برداشته شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    elif text == 'پین':
        try:
            bot.pin_chat_message(group_id, msg.reply_to_message.message_id)
            bot.send_message(group_id, "📌 پیام پین شد")
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    elif text == 'حذف پین':
        try:
            bot.unpin_chat_message(group_id)
            bot.send_message(group_id, "📌 پین حذف شد")
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    elif text == 'اخطار':
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید به خود اخطار دهید")
            return
        if is_group_admin(group_id, rid):
            bot.send_message(group_id, "❌ نمی‌توانید به ادمین اخطار دهید")
            return
        max_w = get_max_warn(group_id)
        warns = add_warn(group_id, rid)
        if warns >= max_w:
            try:
                bot.ban_chat_member(group_id, rid)
                clear_warn(group_id, rid)
                bot.send_message(group_id, f"🚫 کاربر {get_user_link(replied)} بعد از {max_w} اخطار بن شد", parse_mode='HTML')
            except Exception as e:
                bot.send_message(group_id, f"❌ خطا در بن خودکار: {e}")
        else:
            remaining = max_w - warns
            bot.send_message(group_id, f"⚠️ اخطار {warns} از {max_w} برای {get_user_link(replied)}\n{remaining} اخطار تا بن شدن", parse_mode='HTML')
    
    elif text == 'حذف اخطار':
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید از خودتان اخطار حذف کنید")
            return
        if is_group_admin(group_id, rid):
            bot.send_message(group_id, "❌ ادمین اخطار ندارد")
            return
        c.execute('SELECT warnings FROM members WHERE group_id = ? AND user_id = ?', (group_id, rid))
        r = c.fetchone()
        current_warns = r[0] if r else 0
        if current_warns <= 0:
            bot.send_message(group_id, f"ℹ️ کاربر {get_user_link(replied)} اخطاری ندارد", parse_mode='HTML')
            return
        new_warns = remove_one_warn(group_id, rid)
        bot.send_message(group_id, f"✅ یک اخطار از {get_user_link(replied)} حذف شد\nتعداد اخطارهای فعلی: {new_warns}", parse_mode='HTML')
    
    elif text == 'پاک‌سازی':
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید اخطارهای خود را پاک کنید")
            return
        if is_group_admin(group_id, rid):
            bot.send_message(group_id, "❌ ادمین اخطار ندارد")
            return
        c.execute('SELECT warnings FROM members WHERE group_id = ? AND user_id = ?', (group_id, rid))
        r = c.fetchone()
        current_warns = r[0] if r else 0
        if current_warns <= 0:
            bot.send_message(group_id, f"ℹ️ کاربر {get_user_link(replied)} اخطاری ندارد", parse_mode='HTML')
            return
        clear_warn(group_id, rid)
        bot.send_message(group_id, f"✅ همه اخطارهای {get_user_link(replied)} پاک شد", parse_mode='HTML')

# ===== دکمه‌ها =====
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = call.from_user.id
    group_id = call.message.chat.id
    if not is_admin(user_id) and not is_group_admin(group_id, user_id):
        return bot.answer_callback_query(call.id, "فقط ادمین‌ها")
    data = call.data
    if data == 'ban':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'بن' بنویسید")
    elif data == 'unban':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'رفع بن' بنویسید")
    elif data == 'mute':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'سکوت' بنویسید")
    elif data == 'unmute':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'رفع سکوت' بنویسید")
    elif data == 'pin':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'پین' بنویسید")
    elif data == 'unpin':
        bot.answer_callback_query(call.id, "'حذف پین' را بنویسید")
    elif data == 'warn':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'اخطار' بنویسید")
    elif data == 'removewarn':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'حذف اخطار' بنویسید")
    elif data == 'clearwarn':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'پاک‌سازی' بنویسید")
    elif data == 'tagadmins':
        admins = get_admins_mention(group_id)
        if admins:
            bot.send_message(group_id, f"🔔 توجه ادمین‌ها\n\n{' '.join(admins)}", parse_mode='HTML')
        else:
            bot.send_message(group_id, "❌ هیچ ادمینی برای تگ کردن وجود ندارد")
        bot.answer_callback_query(call.id, "تگ ادمین‌ها انجام شد")
    elif data == 'tagall':
        try:
            all_members = []
            admins = bot.get_chat_administrators(group_id)
            for a in admins:
                if not a.user.is_bot:
                    all_members.append(f"<a href='tg://user?id={a.user.id}'>{a.user.first_name}</a>")
            try:
                offset = 0
                while len(all_members) < 50:
                    members = bot.get_chat_members(group_id, offset=offset)
                    if not members:
                        break
                    for m in members:
                        if not m.user.is_bot and m.user.id not in [a.user.id for a in admins]:
                            all_members.append(f"<a href='tg://user?id={m.user.id}'>{m.user.first_name}</a>")
                    offset += 50
            except:
                pass
            if not all_members:
                bot.send_message(group_id, "❌ هیچ کاربری برای تگ کردن وجود ندارد")
                bot.answer_callback_query(call.id)
                return
            bot.send_message(group_id, f"🔔 تگ همه کاربران\n\n" + " ".join(all_members[:50]), parse_mode='HTML')
            if len(all_members) > 50:
                bot.send_message(group_id, f"✅ {len(all_members[:50])} کاربر از {len(all_members)} تگ شدند")
            else:
                bot.send_message(group_id, f"✅ {len(all_members)} کاربر تگ شدند")
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        bot.answer_callback_query(call.id, "تگ همه انجام شد")
    elif data == 'lock_menu':
        try:
            bot.edit_message_text("🔒 قفل سرویس‌های گروه\n\nسرویس مورد نظر را انتخاب کنید:", group_id, call.message.message_id, reply_markup=lock_menu_keyboard(group_id))
        except:
            pass
        bot.answer_callback_query(call.id)
    elif data.startswith('lock_'):
        parts = data.split('_')
        setting = parts[1]
        g_id = int(parts[2])
        locks = get_lock_settings(g_id)
        current = locks.get(setting, 0)
        new_value = 0 if current else 1
        update_lock_setting(g_id, f'lock_{setting}', new_value)
        status = "روشن" if new_value else "خاموش"
        name_map = {'all': 'همه', 'sticker': 'استیکر', 'gif': 'گیف', 'voice': 'ویس', 'video': 'ویدیو', 'photo': 'عکس', 'file': 'فایل'}
        try:
            bot.edit_message_text(f"🔒 قفل {name_map.get(setting, setting)} {status} شد", group_id, call.message.message_id, reply_markup=lock_menu_keyboard(g_id))
        except:
            try:
                bot.edit_message_reply_markup(group_id, call.message.message_id, reply_markup=lock_menu_keyboard(g_id))
            except:
                pass
        bot.answer_callback_query(call.id, f"{name_map.get(setting, setting)} {status} شد")
    elif data == 'stats':
        top = get_top(group_id, 5)
        total = get_total_msgs(group_id)
        date = get_persian_date()
        t = f"📊 فعالیت های امروز:\n\n📅 تاریخ: {date}\n\n💬 کل پیام ها: {total}\n\n🏆 فعال ترین اعضا:\n"
        if top:
            medals = ['🥇', '🥈', '🥉', '😍', '😍']
            for i, (name, msgs) in enumerate(top):
                t += f"{medals[i]} {name}: {msgs} پیام\n"
        else:
            t += "❌ هیچ فعالیتی ثبت نشده است"
        bot.edit_message_text(t, group_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    elif data == 'settings':
        bot.edit_message_text("⚙️ تنظیمات گروه\n\nبرای تنظیم متن اضافی خوش‌آمدگویی:\nتنظیم خوشامد متن جدید\n\nبرای تنظیم تعداد اخطارها:\nتنظیم اخطار عدد", group_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    elif data == 'back_main':
        bot.edit_message_text("🛠 پنل مدیریت\n\nروی پیام کاربر ریپلای کنید", group_id, call.message.message_id, reply_markup=admin_keyboard())
        bot.answer_callback_query(call.id)
    elif data.startswith('res_'):
        report_id = int(data.replace('res_', ''))
        upd_report(report_id, 'resolved')
        bot.edit_message_text(call.message.text + "\n\n✅ بررسی شد", group_id, call.message.message_id)
        bot.answer_callback_query(call.id, "گزارش بررسی شد")
    elif data.startswith('del_'):
        report_id = int(data.replace('del_', ''))
        upd_report(report_id, 'deleted')
        bot.delete_message(group_id, call.message.message_id)
        bot.answer_callback_query(call.id, "گزارش حذف شد")

# ===== اجرا =====
if __name__ == '__main__':
    print("=" * 50)
    print("ربات شروع به کار کرد...")
    print("=" * 50)
    try:
        bot.infinity_polling(timeout=60)
    except Exception as e:
        print(f"خطا: {e}")
