#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import time
import re
from datetime import datetime
import jdatetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== گرفتن توکن از متغیر محیطی =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6443963679"))

if not BOT_TOKEN:
    print("❌ توکن ربات پیدا نشد! متغیر BOT_TOKEN را تنظیم کنید.")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
bot.parse_mode = 'HTML'

# ===== دیتابیس =====
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        welcome_text TEXT,
        max_warnings INTEGER DEFAULT 3,
        filter_link INTEGER DEFAULT 1,
        filter_gif INTEGER DEFAULT 1,
        filter_sticker INTEGER DEFAULT 1,
        filter_forward INTEGER DEFAULT 1,
        filter_photo INTEGER DEFAULT 1,
        filter_video INTEGER DEFAULT 1,
        filter_audio INTEGER DEFAULT 1,
        filter_voice INTEGER DEFAULT 1
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        is_owner INTEGER DEFAULT 0
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        user_id INTEGER,
        warnings INTEGER DEFAULT 0,
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
        status TEXT DEFAULT 'pending',
        date TEXT
    )
''')

conn.commit()

# ===== توابع دیتابیس =====
def get_welcome(group_id):
    c.execute('SELECT welcome_text FROM groups WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    return r[0] if r and r[0] else 'به گروه خوش آمدی {user}'

def set_welcome(group_id, text):
    c.execute('INSERT OR REPLACE INTO groups (group_id, welcome_text) VALUES (?, ?)', (group_id, text))
    conn.commit()

def get_max_warn(group_id):
    c.execute('SELECT max_warnings FROM groups WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    return r[0] if r else 3

def set_max_warn(group_id, count):
    c.execute('UPDATE groups SET max_warnings = ? WHERE group_id = ?', (count, group_id))
    conn.commit()

def get_filter_settings(group_id):
    c.execute('SELECT filter_link, filter_gif, filter_sticker, filter_forward, filter_photo, filter_video, filter_audio, filter_voice FROM groups WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    if r:
        return {
            'link': bool(r[0]),
            'gif': bool(r[1]),
            'sticker': bool(r[2]),
            'forward': bool(r[3]),
            'photo': bool(r[4]),
            'video': bool(r[5]),
            'audio': bool(r[6]),
            'voice': bool(r[7])
        }
    return {'link': True, 'gif': True, 'sticker': True, 'forward': True, 'photo': True, 'video': True, 'audio': True, 'voice': True}

def toggle_filter(group_id, filter_name):
    c.execute(f'UPDATE groups SET filter_{filter_name} = NOT filter_{filter_name} WHERE group_id = ?', (group_id,))
    conn.commit()

def add_user(user_id, name):
    c.execute('INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)', (user_id, name))
    conn.commit()

def set_user_owner(user_id):
    c.execute('UPDATE users SET is_owner = 1 WHERE user_id = ?', (user_id,))
    conn.commit()

def is_user_owner(user_id):
    c.execute('SELECT is_owner FROM users WHERE user_id = ?', (user_id,))
    r = c.fetchone()
    return r[0] == 1 if r else False

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

def get_top(group_id, limit=5):
    c.execute('''SELECT u.name, m.messages FROM members m 
                 JOIN users u ON m.user_id = u.user_id 
                 WHERE m.group_id = ? ORDER BY m.messages DESC LIMIT ?''', (group_id, limit))
    return c.fetchall()

def get_total_msgs(group_id):
    c.execute('SELECT SUM(messages) FROM members WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    return r[0] if r and r[0] else 0

def add_report(group_id, reporter_id, reported_id, msg_id):
    c.execute('INSERT INTO reports (group_id, reporter_id, reported_id, message_id, date) VALUES (?, ?, ?, ?, ?)',
              (group_id, reporter_id, reported_id, msg_id, str(datetime.now())))
    conn.commit()
    return c.lastrowid

def upd_report(report_id, status):
    c.execute('UPDATE reports SET status = ? WHERE id = ?', (status, report_id))
    conn.commit()

# ===== دیباگ =====
def debug_log(message, title="📝 درخواست جدید"):
    """لاگ کردن درخواست‌ها با جزئیات کامل"""
    try:
        group_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0
        user_name = message.from_user.first_name if message.from_user else "ناشناس"
        username = message.from_user.username if message.from_user and message.from_user.username else "ندارد"
        text = message.text if message.text else "[غیرمتنی]"
        
        # تشخیص نوع کاربر
        user_type = "👤 کاربر عادی"
        
        if user_id == ADMIN_ID:
            user_type = "👑 ادمین اصلی"
        elif is_user_owner(user_id):
            user_type = "👑 مالک گروه"
        elif is_group_admin_or_creator(group_id, user_id):
            user_type = "🛡️ ادمین گروه"
        
        # تشخیص حالت ناشناس
        is_anon = is_anonymous_message(message)
        if is_anon:
            user_type = "🕵️ ناشناس"
            user_name = "ناشناس"
            user_id = "????"
        
        # لاگ
        print("=" * 60)
        print(f"{title}")
        print("=" * 60)
        print(f"📱 کاربر: {user_name} (@{username})")
        print(f"🆔 آیدی: {user_id}")
        print(f"👤 نقش: {user_type}")
        print(f"🏠 گروه: {message.chat.title} ({group_id})")
        print(f"📝 متن: {text[:100]}{'...' if len(text) > 100 else ''}")
        print(f"🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔄 ناشناس: {'✅' if is_anon else '❌'}")
        print(f"📎 ریپلای: {'✅' if message.reply_to_message else '❌'}")
        print("=" * 60)
    except Exception as e:
        print(f"❌ خطا در دیباگ: {e}")

# ===== توابع کمکی =====
def is_admin(user_id):
    return user_id == ADMIN_ID

def is_group_admin_or_creator(group_id, user_id):
    """بررسی ادمین یا مالک بودن در گروه"""
    try:
        m = bot.get_chat_member(group_id, user_id)
        return m.status in ['administrator', 'creator']
    except:
        return False

def is_group_creator(group_id, user_id):
    try:
        m = bot.get_chat_member(group_id, user_id)
        return m.status == 'creator'
    except:
        return False

def get_name(user):
    return user.first_name or user.username or 'کاربر'

def get_date():
    now = jdatetime.datetime.now()
    weekdays = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه']
    months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
              'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
    return f"{weekdays[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"

def get_time():
    return datetime.now().strftime('%H:%M')

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

def get_user_mention(user):
    if user.username:
        return f"@{user.username}"
    return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

def get_user_link(user):
    return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

def is_anonymous_message(message):
    """بررسی اینکه پیام از حالت ناشناس ارسال شده"""
    try:
        if message.sender_chat:
            return True
        if message.from_user and hasattr(message.from_user, 'is_anonymous'):
            if message.from_user.is_anonymous:
                return True
        return False
    except:
        return False

def get_real_sender(message):
    """دریافت فرستنده واقعی در حالت ناشناس"""
    try:
        if message.sender_chat:
            return message.sender_chat
        return message.from_user
    except:
        return message.from_user

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
        InlineKeyboardButton("پاک‌سازی", callback_data="clearwarn")
    )
    kb.add(
        InlineKeyboardButton("تگ ادمین‌ها", callback_data="tagadmins"),
        InlineKeyboardButton("تگ همه", callback_data="tagall")
    )
    kb.add(
        InlineKeyboardButton("آمار", callback_data="stats"),
        InlineKeyboardButton("تنظیمات", callback_data="settings")
    )
    return kb

def settings_keyboard(group_id):
    settings = get_filter_settings(group_id)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"لینک: {'✅' if settings['link'] else '❌'}", callback_data=f"toggle_link"),
        InlineKeyboardButton(f"گیف: {'✅' if settings['gif'] else '❌'}", callback_data=f"toggle_gif")
    )
    kb.add(
        InlineKeyboardButton(f"استیکر: {'✅' if settings['sticker'] else '❌'}", callback_data=f"toggle_sticker"),
        InlineKeyboardButton(f"فوروارد: {'✅' if settings['forward'] else '❌'}", callback_data=f"toggle_forward")
    )
    kb.add(
        InlineKeyboardButton(f"عکس: {'✅' if settings['photo'] else '❌'}", callback_data=f"toggle_photo"),
        InlineKeyboardButton(f"ویدیو: {'✅' if settings['video'] else '❌'}", callback_data=f"toggle_video")
    )
    kb.add(
        InlineKeyboardButton(f"آهنگ: {'✅' if settings['audio'] else '❌'}", callback_data=f"toggle_audio"),
        InlineKeyboardButton(f"ویس: {'✅' if settings['voice'] else '❌'}", callback_data=f"toggle_voice")
    )
    kb.add(
        InlineKeyboardButton("تنظیم خوش‌آمدگویی", callback_data="set_welcome"),
        InlineKeyboardButton("تنظیم اخطارها", callback_data="set_warnings")
    )
    kb.add(
        InlineKeyboardButton("بازگشت", callback_data="back_main")
    )
    return kb

def report_keyboard(report_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("بررسی شد", callback_data=f"res_{report_id}"),
        InlineKeyboardButton("حذف", callback_data=f"del_{report_id}")
    )
    return kb

# ===== دستورات =====
@bot.message_handler(commands=['start'])
def start(msg):
    debug_log(msg, "🚀 استارت ربات")
    if msg.chat.type == 'private':
        bot.send_message(msg.chat.id, 
            "به ربات مدیریت گروه خوش آمدید\n\n"
            "ربات را به گروه اضافه کنید و ادمین کنید",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("افزودن به گروه", url=f"https://t.me/{bot.get_me().username}?startgroup=botstart")
            )
        )

# ===== خوش‌آمدگویی و تشخیص مالک =====
@bot.message_handler(content_types=['new_chat_members'])
def welcome(msg):
    debug_log(msg, "🎉 عضو جدید")
    group_id = msg.chat.id
    
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
        
        # بررسی مالک گروه
        if is_group_creator(group_id, m.id):
            set_user_owner(m.id)
            print(f"👑 مالک گروه شناسایی شد: {m.first_name} ({m.id})")
        
        welcome_text = get_welcome(group_id)
        welcome_text = welcome_text.replace('{user}', get_user_mention(m))
        welcome_text = welcome_text.replace('{time}', get_time())
        welcome_text = welcome_text.replace('{date}', get_date())
        
        bot.send_message(group_id, welcome_text, parse_mode='HTML')

@bot.message_handler(content_types=['left_chat_member'])
def member_left(msg):
    debug_log(msg, "🚪 خروج عضو")
    group_id = msg.chat.id
    try:
        bot.delete_message(group_id, msg.message_id)
    except:
        pass

# ===== فیلتر کردن پیام‌ها =====
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'], content_types=['text', 'photo', 'video', 'audio', 'voice', 'document', 'sticker', 'animation'])
def filter_messages(msg):
    group_id = msg.chat.id
    
    # دیباگ
    debug_log(msg, "🔍 بررسی فیلتر")
    
    # تشخیص فرستنده واقعی در حالت ناشناس
    if is_anonymous_message(msg):
        print("🕵️ پیام از حالت ناشناس - رد شدن از فیلتر")
        return
    
    user_id = msg.from_user.id if msg.from_user else 0
    
    if user_id == 0:
        return
    
    # بررسی ادمین یا مالک بودن
    is_admin_user = is_admin(user_id) or is_group_admin_or_creator(group_id, user_id) or is_user_owner(user_id)
    
    # اگر ادمین یا مالک باشه، فیلتر نمی‌شه
    if is_admin_user:
        print(f"✅ کاربر {user_id} ادمین/مالک است - رد شدن از فیلتر")
        return
    
    # ذخیره آمار
    add_user(user_id, msg.from_user.first_name if msg.from_user else 'ناشناس')
    add_member(group_id, user_id)
    add_msg(group_id, user_id)
    
    settings = get_filter_settings(group_id)
    should_delete = False
    reason = ""
    
    # بررسی لینک
    if settings['link'] and msg.text:
        link_pattern = r'(https?://\S+)|(t\.me/\S+)|(telegram\.me/\S+)|(@\w+)'
        if re.search(link_pattern, msg.text, re.IGNORECASE):
            should_delete = True
            reason = "ارسال لینک ممنوع است"
    
    # بررسی فوروارد
    elif settings['forward'] and msg.forward_date:
        should_delete = True
        reason = "فوروارد پیام ممنوع است"
    
    # بررسی گیف
    elif settings['gif'] and msg.animation:
        should_delete = True
        reason = "ارسال گیف ممنوع است"
    
    # بررسی استیکر
    elif settings['sticker'] and msg.sticker:
        should_delete = True
        reason = "ارسال استیکر ممنوع است"
    
    # بررسی عکس
    elif settings['photo'] and msg.photo:
        should_delete = True
        reason = "ارسال عکس ممنوع است"
    
    # بررسی ویدیو
    elif settings['video'] and msg.video:
        should_delete = True
        reason = "ارسال ویدیو ممنوع است"
    
    # بررسی آهنگ
    elif settings['audio'] and msg.audio:
        should_delete = True
        reason = "ارسال آهنگ ممنوع است"
    
    # بررسی ویس
    elif settings['voice'] and msg.voice:
        should_delete = True
        reason = "ارسال ویس ممنوع است"
    
    # حذف پیام در صورت نیاز
    if should_delete:
        print(f"🗑️ حذف پیام از {user_id} - دلیل: {reason}")
        try:
            bot.delete_message(group_id, msg.message_id)
            bot.send_message(
                group_id,
                f"⚠️ {get_user_mention(msg.from_user)}\n{reason}",
                parse_mode='HTML'
            )
            
            # اخطار خودکار
            max_w = get_max_warn(group_id)
            warns = add_warn(group_id, user_id)
            
            if warns >= max_w:
                try:
                    bot.ban_chat_member(group_id, user_id)
                    clear_warn(group_id, user_id)
                    bot.send_message(
                        group_id,
                        f"🚫 کاربر {get_user_link(msg.from_user)} بعد از {max_w} اخطار بن شد",
                        parse_mode='HTML'
                    )
                    print(f"🚫 کاربر {user_id} بن شد")
                except Exception as e:
                    print(f"❌ خطا در بن: {e}")
            else:
                remaining = max_w - warns
                bot.send_message(
                    group_id,
                    f"⚠️ اخطار {warns} از {max_w} برای {get_user_link(msg.from_user)}\n{remaining} اخطار تا بن شدن",
                    parse_mode='HTML'
                )
                print(f"⚠️ اخطار {warns}/{max_w} برای {user_id}")
        except Exception as e:
            print(f"❌ خطا در حذف پیام: {e}")

# ===== دستورات متنی =====
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'], content_types=['text'])
def handle(msg):
    debug_log(msg, "📩 دستور دریافتی")
    
    group_id = msg.chat.id
    
    # تشخیص فرستنده واقعی در حالت ناشناس
    if is_anonymous_message(msg):
        print("🕵️ دستور از حالت ناشناس - دسترسی کامل داده شد")
        user_id = ADMIN_ID  # برای دسترسی به دستورات
        is_admin_user = True
    else:
        user_id = msg.from_user.id if msg.from_user else 0
        if user_id == 0:
            return
        is_admin_user = is_admin(user_id) or is_group_admin_or_creator(group_id, user_id) or is_user_owner(user_id)
        print(f"👤 کاربر: {user_id} - ادمین: {is_admin_user}")
    
    text = msg.text.strip() if msg.text else ""
    
    # ذخیره آمار (فقط برای کاربران معمولی)
    if not is_anonymous_message(msg) and user_id != 0:
        add_user(user_id, msg.from_user.first_name if msg.from_user else 'ناشناس')
        add_member(group_id, user_id)
        add_msg(group_id, user_id)
    
    # ===== کاربر عادی =====
    if not is_admin_user:
        print(f"⛔ کاربر عادی - فقط گزارش")
        if msg.reply_to_message and text == 'گزارش':
            # تشخیص فرستنده گزارش شده در حالت ناشناس
            if is_anonymous_message(msg.reply_to_message):
                reported = msg.reply_to_message.sender_chat
                reported_name = "ناشناس"
            else:
                reported = msg.reply_to_message.from_user
                reported_name = get_user_link(reported)
            
            if reported.id == user_id:
                bot.send_message(group_id, "نمی‌توانید خود را گزارش کنید")
                return
            
            report_id = add_report(group_id, user_id, reported.id if not is_anonymous_message(msg.reply_to_message) else 0, msg.reply_to_message.message_id)
            
            admins = get_admins_mention(group_id)
            admin_text = " ".join(admins) if admins else ""
            
            report_msg = f"{admin_text}\n\n" if admin_text else ""
            report_msg += f"📋 گزارش جدید\n\n"
            report_msg += f"👤 گزارش دهنده: {get_user_link(msg.from_user)}\n"
            report_msg += f"👤 گزارش شده: {reported_name}\n"
            report_msg += f"📝 متن: {msg.reply_to_message.text or 'متن نیست'}"
            
            bot.send_message(
                group_id,
                report_msg,
                parse_mode='HTML',
                reply_markup=report_keyboard(report_id)
            )
            bot.send_message(group_id, "✅ گزارش شما برای مدیران ارسال شد")
            print(f"📋 گزارش جدید از {user_id}")
        return
    
    # ===== دستورات ادمین و مالک =====
    print(f"✅ دستورات ادمین/مالک: {text}")
    
    # پنل
    if text == 'پنل':
        bot.send_message(group_id, "🛠 پنل مدیریت\n\nروی پیام کاربر ریپلای کنید", reply_markup=admin_keyboard())
        return
    
    # آمار
    if text == 'آمار':
        top = get_top(group_id, 5)
        total = get_total_msgs(group_id)
        date = get_date()
        time_now = get_time()
        
        t = f"📊 فعالیت های امروز:\n\n"
        t += f"📅 تاریخ: {date}\n"
        t += f"🕐 ساعت: {time_now}\n\n"
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
    
    # تنظیم خوش‌آمدگویی
    if text.startswith('تنظیم خوشامد'):
        new = text.replace('تنظیم خوشامد', '').strip()
        if new:
            set_welcome(group_id, new)
            bot.send_message(group_id, f"✅ متن خوش‌آمدگویی تنظیم شد:\n\n{new}")
        else:
            bot.send_message(group_id, "❌ لطفاً متن را وارد کنید:\nتنظیم خوشامد سلام {user} عزیز!")
        return
    
    # تنظیم تعداد اخطارها
    if text.startswith('تنظیم اخطار'):
        try:
            n = int(text.replace('تنظیم اخطار', '').strip())
            if n < 1:
                bot.send_message(group_id, "❌ تعداد اخطارها باید حداقل 1 باشد")
                return
            set_max_warn(group_id, n)
            bot.send_message(group_id, f"✅ تعداد اخطارها با موفقیت به {n} تنظیم شد")
        except:
            bot.send_message(group_id, "❌ لطفاً یک عدد معتبر وارد کنید:\nتنظیم اخطار 5")
        return
    
    # راهنما
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
            "• پاک‌سازی - پاک کردن اخطارها\n\n"
            "🔹 کاربران عادی:\n"
            "• گزارش - گزارش پیام (با ریپلای)\n\n"
            "🔹 دستورات:\n"
            "• پنل - نمایش پنل مدیریت\n"
            "• آمار - نمایش آمار\n"
            "• راهنما - نمایش این راهنما\n"
            "• تنظیم خوشامد متن - تنظیم خوش‌آمدگویی\n"
            "• تنظیم اخطار عدد - تنظیم تعداد اخطارها"
        )
        bot.send_message(group_id, help_text)
        return
    
    if not msg.reply_to_message:
        return
    
    # تشخیص کاربر ریپلای شده در حالت ناشناس
    if is_anonymous_message(msg.reply_to_message):
        replied = msg.reply_to_message.sender_chat
        rid = replied.id if hasattr(replied, 'id') else 0
        replied_name = "ناشناس"
    else:
        replied = msg.reply_to_message.from_user
        rid = replied.id
        replied_name = get_user_link(replied)
    
    # ===== تگ همه کاربران =====
    if text == 'تگ همه':
        print("🏷️ اجرای تگ همه")
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
            
            msg_text = f"🔔 تگ همه کاربران\n\n"
            msg_text += " ".join(all_members[:50])
            
            bot.send_message(
                group_id,
                msg_text,
                parse_mode='HTML',
                reply_to_message_id=msg.reply_to_message.message_id
            )
            
            if len(all_members) > 50:
                bot.send_message(group_id, f"✅ {len(all_members[:50])} کاربر از {len(all_members)} تگ شدند")
            else:
                bot.send_message(group_id, f"✅ {len(all_members)} کاربر تگ شدند")
            print(f"✅ تگ همه انجام شد - {len(all_members)} کاربر")
            
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
            print(f"❌ خطا در تگ همه: {e}")
        return
    
    # ===== دستورات مدیریتی =====
    if text == 'بن':
        print(f"🚫 اجرای بن برای {rid}")
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید خود را بن کنید")
            return
        if is_group_admin_or_creator(group_id, rid) or is_user_owner(rid):
            bot.send_message(group_id, "❌ نمی‌توانید ادمین یا مالک را بن کنید")
            return
        try:
            bot.ban_chat_member(group_id, rid)
            bot.send_message(group_id, f"🚫 کاربر {replied_name} بن شد", parse_mode='HTML')
            print(f"✅ بن شد: {rid}")
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
            print(f"❌ خطا در بن: {e}")
    
    elif text == 'رفع بن':
        try:
            bot.unban_chat_member(group_id, rid)
            bot.send_message(group_id, f"✅ بن کاربر {replied_name} برداشته شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    elif text.startswith('سکوت'):
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید خود را سکوت کنید")
            return
        if is_group_admin_or_creator(group_id, rid) or is_user_owner(rid):
            bot.send_message(group_id, "❌ نمی‌توانید ادمین یا مالک را سکوت کنید")
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
                bot.send_message(group_id, f"🔇 کاربر {replied_name} به مدت {minutes} دقیقه سکوت شد", parse_mode='HTML')
            else:
                bot.restrict_chat_member(group_id, rid, can_send_messages=False)
                bot.send_message(group_id, f"🔇 کاربر {replied_name} سکوت شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    elif text == 'رفع سکوت':
        try:
            bot.restrict_chat_member(group_id, rid, can_send_messages=True, can_send_media_messages=True)
            bot.send_message(group_id, f"🔊 سکوت کاربر {replied_name} برداشته شد", parse_mode='HTML')
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
        if is_group_admin_or_creator(group_id, rid) or is_user_owner(rid):
            bot.send_message(group_id, "❌ نمی‌توانید به ادمین یا مالک اخطار دهید")
            return
        
        max_w = get_max_warn(group_id)
        warns = add_warn(group_id, rid)
        
        if warns >= max_w:
            try:
                bot.ban_chat_member(group_id, rid)
                clear_warn(group_id, rid)
                bot.send_message(group_id, f"🚫 کاربر {replied_name} بعد از {max_w} اخطار بن شد", parse_mode='HTML')
            except Exception as e:
                bot.send_message(group_id, f"❌ خطا در بن خودکار: {e}")
        else:
            remaining = max_w - warns
            bot.send_message(group_id, f"⚠️ اخطار {warns} از {max_w} برای {replied_name}\n{remaining} اخطار تا بن شدن", parse_mode='HTML')
    
    elif text == 'پاک‌سازی':
        clear_warn(group_id, rid)
        bot.send_message(group_id, f"✅ اخطارهای {replied_name} پاک شد", parse_mode='HTML')

# ===== دکمه‌ها =====
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = call.from_user.id
    group_id = call.message.chat.id
    
    print(f"🔘 دکمه: {call.data} از {user_id}")
    
    if not is_admin(user_id) and not is_group_admin_or_creator(group_id, user_id) and not is_user_owner(user_id):
        return bot.answer_callback_query(call.id, "فقط ادمین‌ها یا مالک گروه")
    
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
    elif data == 'clearwarn':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'پاک‌سازی' بنویسید")
    
    elif data == 'tagadmins':
        admins = get_admins_mention(group_id)
        if admins:
            admin_text = " ".join(admins)
            bot.send_message(group_id, f"🔔 توجه ادمین‌ها\n\n{admin_text}", parse_mode='HTML')
        else:
            bot.send_message(group_id, "هیچ ادمینی برای تگ کردن وجود ندارد")
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
            
            msg_text = f"🔔 تگ همه کاربران\n\n"
            msg_text += " ".join(all_members[:50])
            
            bot.send_message(group_id, msg_text, parse_mode='HTML')
            
            if len(all_members) > 50:
                bot.send_message(group_id, f"✅ {len(all_members[:50])} کاربر از {len(all_members)} تگ شدند")
            else:
                bot.send_message(group_id, f"✅ {len(all_members)} کاربر تگ شدند")
            
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        bot.answer_callback_query(call.id, "تگ همه انجام شد")
    
    elif data == 'stats':
        top = get_top(group_id, 5)
        total = get_total_msgs(group_id)
        date = get_date()
        time_now = get_time()
        
        t = f"📊 فعالیت های امروز:\n\n"
        t += f"📅 تاریخ: {date}\n"
        t += f"🕐 ساعت: {time_now}\n\n"
        t += f"💬 کل پیام ها: {total}\n\n"
        t += "🏆 فعال ترین اعضا:\n"
        
        if top:
            medals = ['🥇', '🥈', '🥉', '😍', '😍']
            for i, (name, msgs) in enumerate(top):
                t += f"{medals[i]} {name}: {msgs} پیام\n"
        else:
            t += "❌ هیچ فعالیتی ثبت نشده است"
        
        bot.edit_message_text(t, group_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    elif data == 'settings':
        bot.edit_message_text(
            "⚙️ تنظیمات فیلترها\n\n"
            "روشن/خاموش کردن هر فیلتر:",
            group_id, call.message.message_id,
            reply_markup=settings_keyboard(group_id)
        )
        bot.answer_callback_query(call.id)
    
    elif data.startswith('toggle_'):
        filter_name = data.replace('toggle_', '')
        toggle_filter(group_id, filter_name)
        bot.edit_message_text(
            "⚙️ تنظیمات فیلترها\n\n"
            "روشن/خاموش کردن هر فیلتر:",
            group_id, call.message.message_id,
            reply_markup=settings_keyboard(group_id)
        )
        bot.answer_callback_query(call.id, f"✅ فیلتر {filter_name} تغییر کرد")
    
    elif data == 'set_welcome':
        bot.edit_message_text(
            "تنظیم متن خوش‌آمدگویی\n\n"
            "دستور: تنظیم خوشامد متن جدید\n\n"
            "مثال: تنظیم خوشامد سلام {user} عزیز!",
            group_id, call.message.message_id
        )
        bot.answer_callback_query(call.id)
    
    elif data == 'set_warnings':
        bot.edit_message_text(
            "تنظیم تعداد اخطارها\n\n"
            "دستور: تنظیم اخطار عدد\n\n"
            "مثال: تنظیم اخطار 5",
            group_id, call.message.message_id
        )
        bot.answer_callback_query(call.id)
    
    elif data == 'back_main':
        bot.edit_message_text(
            "🛠 پنل مدیریت\n\nروی پیام کاربر ریپلای کنید",
            group_id, call.message.message_id,
            reply_markup=admin_keyboard()
        )
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
    print("=" * 60)
    print("🤖 ربات مدیریت گروه - با دیباگ کامل")
    print("=" * 60)
    print(f"👑 ادمین اصلی: {ADMIN_ID}")
    print(f"📱 نام کاربری: @{bot.get_me().username}")
    print("=" * 60)
    print("📊 دیباگ فعال است - همه درخواست‌ها لاگ می‌شوند")
    print("=" * 60)
    print("✅ قابلیت‌ها:")
    print("• تشخیص ادمین‌ها و مالک گروه")
    print("• تشخیص حالت ناشناس")
    print("• فیلتر لینک، گیف، استیکر، فوروارد، عکس، ویدیو، آهنگ، ویس")
    print("• روشن/خاموش کردن هر فیلتر با دکمه")
    print("• سیستم اخطار و بن خودکار")
    print("• سیستم گزارش")
    print("• تگ همه کاربران")
    print("=" * 60)
    print("📝 لاگ‌ها:")
    print("-" * 60)
    
    try:
        bot.infinity_polling(timeout=10)
    except Exception as e:
        print(f"❌ خطا: {e}")
