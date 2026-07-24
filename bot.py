#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import sqlite3
import time
import re
from datetime import datetime
import jdatetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== توکن =====
BOT_TOKEN = "8092823571:AAHnuu9ff32CUSQe1p9axBlmvHXKJ4WCGW4"

if not BOT_TOKEN:
    print("❌ توکن ربات پیدا نشد!")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
bot.parse_mode = 'HTML'

print(f"✅ توکن: {BOT_TOKEN[:10]}...")
print("✅ ربات شروع به کار کرد...")

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
        name TEXT
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
        status TEXT DEFAULT 'pending',
        date TEXT
    )
''')

conn.commit()
print("✅ دیتابیس آماده است")

# ===== توابع دیتابیس =====
def get_welcome(group_id):
    c.execute('SELECT welcome_text FROM groups WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    if r and r[0]:
        return r[0]
    return 'به گروه خوش آمدی {user}'

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

def get_filter_setting(group_id, filter_name):
    c.execute(f'SELECT {filter_name} FROM groups WHERE group_id = ?', (group_id,))
    r = c.fetchone()
    return r[0] if r else 1

def set_filter_setting(group_id, filter_name, value):
    c.execute(f'UPDATE groups SET {filter_name} = ? WHERE group_id = ?', (value, group_id))
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

def add_mute(group_id, user_id):
    c.execute('UPDATE members SET muted = 1 WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    conn.commit()

def remove_mute(group_id, user_id):
    c.execute('UPDATE members SET muted = 0 WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    conn.commit()

def add_ban(group_id, user_id):
    c.execute('UPDATE members SET banned = 1 WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    conn.commit()

def remove_ban(group_id, user_id):
    c.execute('UPDATE members SET banned = 0 WHERE group_id = ? AND user_id = ?', (group_id, user_id))
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

# ===== توابع کمکی =====
def is_group_admin(group_id, user_id):
    try:
        m = bot.get_chat_member(group_id, user_id)
        return m.status in ['administrator', 'creator']
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
        InlineKeyboardButton("پاک‌سازی", callback_data="clearwarn")
    )
    kb.add(
        InlineKeyboardButton("تگ ادمین‌ها", callback_data="tagadmins"),
        InlineKeyboardButton("تگ همه", callback_data="tagall")
    )
    kb.add(
        InlineKeyboardButton("فیلترها", callback_data="filters"),
        InlineKeyboardButton("آمار", callback_data="stats")
    )
    kb.add(
        InlineKeyboardButton("تنظیمات", callback_data="settings")
    )
    return kb

def filters_keyboard(group_id):
    kb = InlineKeyboardMarkup(row_width=2)
    
    link = get_filter_setting(group_id, 'filter_link')
    gif = get_filter_setting(group_id, 'filter_gif')
    sticker = get_filter_setting(group_id, 'filter_sticker')
    forward = get_filter_setting(group_id, 'filter_forward')
    photo = get_filter_setting(group_id, 'filter_photo')
    video = get_filter_setting(group_id, 'filter_video')
    audio = get_filter_setting(group_id, 'filter_audio')
    voice = get_filter_setting(group_id, 'filter_voice')
    
    kb.add(
        InlineKeyboardButton(f"لینک: {'فعال' if link else 'خاموش'}", callback_data=f"flink_{group_id}"),
        InlineKeyboardButton(f"گیف: {'فعال' if gif else 'خاموش'}", callback_data=f"fgif_{group_id}")
    )
    kb.add(
        InlineKeyboardButton(f"استیکر: {'فعال' if sticker else 'خاموش'}", callback_data=f"fsticker_{group_id}"),
        InlineKeyboardButton(f"فوروارد: {'فعال' if forward else 'خاموش'}", callback_data=f"fforward_{group_id}")
    )
    kb.add(
        InlineKeyboardButton(f"عکس: {'فعال' if photo else 'خاموش'}", callback_data=f"fphoto_{group_id}"),
        InlineKeyboardButton(f"ویدیو: {'فعال' if video else 'خاموش'}", callback_data=f"fvideo_{group_id}")
    )
    kb.add(
        InlineKeyboardButton(f"آهنگ: {'فعال' if audio else 'خاموش'}", callback_data=f"faudio_{group_id}"),
        InlineKeyboardButton(f"ویس: {'فعال' if voice else 'خاموش'}", callback_data=f"fvoice_{group_id}")
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
    if msg.chat.type == 'private':
        bot.send_message(msg.chat.id, 
            "به ربات مدیریت گروه خوش آمدید\n\n"
            "ربات را به گروه اضافه کنید و ادمین کنید",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("افزودن به گروه", url=f"https://t.me/{bot.get_me().username}?startgroup=botstart")
            )
        )

# ===== خوش‌آمدگویی =====
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
        
        welcome_text = get_welcome(group_id)
        welcome_text = welcome_text.replace('{user}', f"<a href='tg://user?id={m.id}'>{m.first_name}</a>")
        welcome_text = welcome_text.replace('{time}', get_time())
        welcome_text = welcome_text.replace('{date}', get_date())
        
        bot.send_message(group_id, welcome_text, parse_mode='HTML')

# ===== حذف پیام خروج =====
@bot.message_handler(content_types=['left_chat_member'])
def member_left(msg):
    group_id = msg.chat.id
    try:
        bot.delete_message(group_id, msg.message_id)
    except:
        pass

# ===== فیلتر محتوا (فقط برای کاربران عادی) =====
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'], content_types=['text', 'photo', 'video', 'audio', 'voice', 'document', 'sticker', 'animation'])
def filter_content(msg):
    group_id = msg.chat.id
    user_id = msg.from_user.id
    
    add_user(user_id, msg.from_user.first_name)
    add_member(group_id, user_id)
    add_msg(group_id, user_id)
    
    # اگه کاربر ادمین باشه، فیلتر نمیشه
    if is_group_admin(group_id, user_id):
        return
    
    # اگه پیام متنی هست و دستور هست، فیلتر نشه
    if msg.text and msg.text.startswith(('بن', 'رفع بن', 'سکوت', 'رفع سکوت', 'پین', 'حذف پین', 'اخطار', 'پاک‌سازی', 'پنل', 'آمار', 'راهنما', 'تگ همه', 'تنظیم خوشامد', 'تنظیم اخطار', 'گزارش')):
        return
    
    content_type = None
    filter_name = None
    
    if msg.text:
        link_pattern = r'(https?://\S+)|(www\.\S+)|(t\.me/\S+)|(@\w+)'
        if re.search(link_pattern, msg.text, re.IGNORECASE):
            filter_name = 'filter_link'
            content_type = 'لینک'
    
    elif msg.photo:
        filter_name = 'filter_photo'
        content_type = 'عکس'
    
    elif msg.video:
        filter_name = 'filter_video'
        content_type = 'ویدیو'
    
    elif msg.audio:
        filter_name = 'filter_audio'
        content_type = 'آهنگ'
    
    elif msg.voice:
        filter_name = 'filter_voice'
        content_type = 'ویس'
    
    elif msg.sticker:
        filter_name = 'filter_sticker'
        content_type = 'استیکر'
    
    elif msg.animation:
        filter_name = 'filter_gif'
        content_type = 'گیف'
    
    elif msg.forward_date:
        filter_name = 'filter_forward'
        content_type = 'فوروارد'
    
    if filter_name and get_filter_setting(group_id, filter_name):
        try:
            bot.delete_message(group_id, msg.message_id)
            bot.send_message(
                group_id,
                f"⛔ {get_user_link(msg.from_user)} ارسال {content_type} در گروه ممنوع است",
                parse_mode='HTML'
            )
        except:
            pass

# ===== هندلر اصلی پیام‌ها =====
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'], content_types=['text'])
def handle(msg):
    group_id = msg.chat.id
    user_id = msg.from_user.id
    text = msg.text.strip() if msg.text else ""
    
    add_user(user_id, msg.from_user.first_name)
    add_member(group_id, user_id)
    add_msg(group_id, user_id)
    
    admin = is_group_admin(group_id, user_id)
    
    # ===== کاربر عادی =====
    if not admin:
        if msg.reply_to_message and text == 'گزارش':
            reported = msg.reply_to_message.from_user
            if reported.id == user_id:
                bot.send_message(group_id, "نمی‌توانید خود را گزارش کنید")
                return
            
            report_id = add_report(group_id, user_id, reported.id, msg.reply_to_message.message_id)
            
            admins = get_admins_mention(group_id)
            admin_text = " ".join(admins) if admins else ""
            
            report_msg = f"{admin_text}\n\n" if admin_text else ""
            report_msg += f"📋 گزارش جدید\n\n"
            report_msg += f"👤 گزارش دهنده: {get_user_link(msg.from_user)}\n"
            report_msg += f"👤 گزارش شده: {get_user_link(reported)}\n"
            report_msg += f"📝 متن: {msg.reply_to_message.text or 'متن نیست'}"
            
            bot.send_message(
                group_id,
                report_msg,
                parse_mode='HTML',
                reply_markup=report_keyboard(report_id)
            )
            bot.send_message(group_id, "✅ گزارش شما برای مدیران ارسال شد")
        return
    
    # ===== دستورات ادمین =====
    
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
    
    replied = msg.reply_to_message.from_user
    rid = replied.id
    
    # ===== تگ همه کاربران =====
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
            
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        return
    
    # ===== بن =====
    if text == 'بن':
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید خود را بن کنید")
            return
        if is_group_admin(group_id, rid):
            bot.send_message(group_id, "❌ نمی‌توانید ادمین را بن کنید")
            return
        try:
            bot.ban_chat_member(group_id, rid)
            add_ban(group_id, rid)
            bot.send_message(group_id, f"🚫 کاربر {get_user_link(replied)} بن شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    # ===== رفع بن =====
    elif text == 'رفع بن':
        try:
            bot.unban_chat_member(group_id, rid)
            remove_ban(group_id, rid)
            bot.send_message(group_id, f"✅ بن کاربر {get_user_link(replied)} برداشته شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    # ===== سکوت =====
    elif text.startswith('سکوت'):
        if rid == user_id:
            bot.send_message(group_id, "❌ نمی‌توانید خود را سکوت کنید")
            return
        if is_group_admin(group_id, rid):
            bot.send_message(group_id, "❌ نمی‌توانید ادمین را سکوت کنید")
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
                add_mute(group_id, rid)
                bot.send_message(group_id, f"🔇 کاربر {get_user_link(replied)} به مدت {minutes} دقیقه سکوت شد", parse_mode='HTML')
            else:
                bot.restrict_chat_member(group_id, rid, can_send_messages=False)
                add_mute(group_id, rid)
                bot.send_message(group_id, f"🔇 کاربر {get_user_link(replied)} سکوت شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    # ===== رفع سکوت =====
    elif text == 'رفع سکوت':
        try:
            bot.restrict_chat_member(group_id, rid, can_send_messages=True, can_send_media_messages=True)
            remove_mute(group_id, rid)
            bot.send_message(group_id, f"🔊 سکوت کاربر {get_user_link(replied)} برداشته شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    # ===== پین =====
    elif text == 'پین':
        try:
            bot.pin_chat_message(group_id, msg.reply_to_message.message_id)
            bot.send_message(group_id, "📌 پیام پین شد")
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    # ===== حذف پین =====
    elif text == 'حذف پین':
        try:
            bot.unpin_chat_message(group_id)
            bot.send_message(group_id, "📌 پین حذف شد")
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
    
    # ===== اخطار =====
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
                add_ban(group_id, rid)
                bot.send_message(group_id, f"🚫 کاربر {get_user_link(replied)} بعد از {max_w} اخطار بن شد", parse_mode='HTML')
            except Exception as e:
                bot.send_message(group_id, f"❌ خطا در بن خودکار: {e}")
        else:
            remaining = max_w - warns
            bot.send_message(group_id, f"⚠️ اخطار {warns} از {max_w} برای {get_user_link(replied)}\n{remaining} اخطار تا بن شدن", parse_mode='HTML')
    
    # ===== پاک‌سازی =====
    elif text == 'پاک‌سازی':
        clear_warn(group_id, rid)
        bot.send_message(group_id, f"✅ اخطارهای {get_user_link(replied)} پاک شد", parse_mode='HTML')

# ===== دکمه‌ها =====
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = call.from_user.id
    group_id = call.message.chat.id
    
    if not is_group_admin(group_id, user_id):
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
    
    elif data == 'filters':
        bot.edit_message_text(
            "🔧 تنظیمات فیلترها\n\nروی هر دکمه کلیک کنید تا فعال/غیرفعال شود",
            group_id, call.message.message_id,
            reply_markup=filters_keyboard(group_id)
        )
        bot.answer_callback_query(call.id)
    
    elif data.startswith('flink_'):
        group_id = int(data.replace('flink_', ''))
        current = get_filter_setting(group_id, 'filter_link')
        set_filter_setting(group_id, 'filter_link', 0 if current else 1)
        bot.edit_message_reply_markup(group_id, call.message.message_id, reply_markup=filters_keyboard(group_id))
        bot.answer_callback_query(call.id, f"فیلتر لینک {'غیرفعال' if current else 'فعال'} شد")
    
    elif data.startswith('fgif_'):
        group_id = int(data.replace('fgif_', ''))
        current = get_filter_setting(group_id, 'filter_gif')
        set_filter_setting(group_id, 'filter_gif', 0 if current else 1)
        bot.edit_message_reply_markup(group_id, call.message.message_id, reply_markup=filters_keyboard(group_id))
        bot.answer_callback_query(call.id, f"فیلتر گیف {'غیرفعال' if current else 'فعال'} شد")
    
    elif data.startswith('fsticker_'):
        group_id = int(data.replace('fsticker_', ''))
        current = get_filter_setting(group_id, 'filter_sticker')
        set_filter_setting(group_id, 'filter_sticker', 0 if current else 1)
        bot.edit_message_reply_markup(group_id, call.message.message_id, reply_markup=filters_keyboard(group_id))
        bot.answer_callback_query(call.id, f"فیلتر استیکر {'غیرفعال' if current else 'فعال'} شد")
    
    elif data.startswith('fforward_'):
        group_id = int(data.replace('fforward_', ''))
        current = get_filter_setting(group_id, 'filter_forward')
        set_filter_setting(group_id, 'filter_forward', 0 if current else 1)
        bot.edit_message_reply_markup(group_id, call.message.message_id, reply_markup=filters_keyboard(group_id))
        bot.answer_callback_query(call.id, f"فیلتر فوروارد {'غیرفعال' if current else 'فعال'} شد")
    
    elif data.startswith('fphoto_'):
        group_id = int(data.replace('fphoto_', ''))
        current = get_filter_setting(group_id, 'filter_photo')
        set_filter_setting(group_id, 'filter_photo', 0 if current else 1)
        bot.edit_message_reply_markup(group_id, call.message.message_id, reply_markup=filters_keyboard(group_id))
        bot.answer_callback_query(call.id, f"فیلتر عکس {'غیرفعال' if current else 'فعال'} شد")
    
    elif data.startswith('fvideo_'):
        group_id = int(data.replace('fvideo_', ''))
        current = get_filter_setting(group_id, 'filter_video')
        set_filter_setting(group_id, 'filter_video', 0 if current else 1)
        bot.edit_message_reply_markup(group_id, call.message.message_id, reply_markup=filters_keyboard(group_id))
        bot.answer_callback_query(call.id, f"فیلتر ویدیو {'غیرفعال' if current else 'فعال'} شد")
    
    elif data.startswith('faudio_'):
        group_id = int(data.replace('faudio_', ''))
        current = get_filter_setting(group_id, 'filter_audio')
        set_filter_setting(group_id, 'filter_audio', 0 if current else 1)
        bot.edit_message_reply_markup(group_id, call.message.message_id, reply_markup=filters_keyboard(group_id))
        bot.answer_callback_query(call.id, f"فیلتر آهنگ {'غیرفعال' if current else 'فعال'} شد")
    
    elif data.startswith('fvoice_'):
        group_id = int(data.replace('fvoice_', ''))
        current = get_filter_setting(group_id, 'filter_voice')
        set_filter_setting(group_id, 'filter_voice', 0 if current else 1)
        bot.edit_message_reply_markup(group_id, call.message.message_id, reply_markup=filters_keyboard(group_id))
        bot.answer_callback_query(call.id, f"فیلتر ویس {'غیرفعال' if current else 'فعال'} شد")
    
    elif data == 'back_main':
        bot.edit_message_text(
            "🛠 پنل مدیریت\n\nروی پیام کاربر ریپلای کنید",
            group_id, call.message.message_id,
            reply_markup=admin_keyboard()
        )
        bot.answer_callback_query(call.id)
    
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
            "⚙️ تنظیمات گروه\n\n"
            "برای تنظیم متن خوش‌آمدگویی:\n"
            "تنظیم خوشامد متن جدید\n\n"
            "برای تنظیم تعداد اخطارها:\n"
            "تنظیم اخطار عدد\n\n"
            "متن خوش‌آمدگویی پیش‌فرض:\n"
            "به گروه خوش آمدی {user}",
            group_id, call.message.message_id
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
    print("=" * 50)
    print("ربات مدیریت گروه")
    print("=" * 50)
    print(f"نام کاربری: @{bot.get_me().username}")
    print("=" * 50)
    print("✅ ربات شروع به کار کرد...")
    print("=" * 50)
    
    while True:
        try:
            bot.infinity_polling(timeout=10)
        except Exception as e:
            print(f"❌ خطا: {e}")
            print("🔄 راه‌اندازی مجدد در 5 ثانیه...")
            time.sleep(5)
