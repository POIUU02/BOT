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

# ===== توکن =====
BOT_TOKEN = "8379881886:AAHi3knG32h9Q1fxEsXp6sSSvqyQEBRkh-M"
ADMIN_ID = 6443963679

bot = telebot.TeleBot(BOT_TOKEN)
bot.parse_mode = 'HTML'

# ===== دیتابیس =====
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        welcome_text TEXT,
        max_warnings INTEGER DEFAULT 3
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
def is_admin(user_id):
    return user_id == ADMIN_ID

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

def get_user_mention(user):
    if user.username:
        return f"@{user.username}"
    return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

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
        InlineKeyboardButton("تگ همه", callback_data="tagall"),
        InlineKeyboardButton("آمار", callback_data="stats")
    )
    kb.add(
        InlineKeyboardButton("تنظیمات", callback_data="settings")
    )
    return kb

def report_keyboard(report_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("بررسی شد", callback_data=f"res_{report_id}"),
        InlineKeyboardButton("حذف", callback_data=f"del_{report_id}")
    )
    return kb

# ===== هندلر استارت =====
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
        welcome_text = welcome_text.replace('{user}', get_user_mention(m))
        welcome_text = welcome_text.replace('{time}', get_time())
        welcome_text = welcome_text.replace('{date}', get_date())
        
        bot.send_message(group_id, welcome_text, parse_mode='HTML')

# ===== خروج عضو =====
@bot.message_handler(content_types=['left_chat_member'])
def member_left(msg):
    group_id = msg.chat.id
    try:
        bot.delete_message(group_id, msg.message_id)
    except:
        pass

# ===== هندلر اصلی - همه پیام‌های متنی =====
@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_all_messages(msg):
    # فقط در گروه
    if msg.chat.type not in ['group', 'supergroup']:
        return
    
    group_id = msg.chat.id
    user_id = msg.from_user.id
    text = msg.text.strip() if msg.text else ""
    
    print(f"📩 پیام: '{text}' از {user_id} در گروه {group_id}")
    
    # ذخیره کاربر
    add_user(user_id, msg.from_user.first_name)
    add_member(group_id, user_id)
    add_msg(group_id, user_id)
    
    # بررسی ادمین
    is_admin_user = is_admin(user_id) or is_group_admin(group_id, user_id)
    print(f"👤 ادمین: {is_admin_user}")
    
    # ===== کاربر عادی =====
    if not is_admin_user:
        print("🔹 کاربر عادی")
        if msg.reply_to_message and text == 'گزارش':
            reported = msg.reply_to_message.from_user
            if reported.id == user_id:
                bot.send_message(group_id, "نمی‌توانید خود را گزارش کنید")
                return
            
            report_id = add_report(group_id, user_id, reported.id, msg.reply_to_message.message_id)
            
            report_msg = f"📋 گزارش جدید\n\n"
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
    print("🔹 ادمین - پردازش دستور")
    
    # پنل
    if text == 'پنل':
        bot.send_message(group_id, "🛠 پنل مدیریت", reply_markup=admin_keyboard())
        print("✅ پنل ارسال شد")
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
        print("✅ آمار ارسال شد")
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
            "• راهنما - نمایش این راهنما"
        )
        bot.send_message(group_id, help_text)
        return
    
    # اگر ریپلای نداره، کاری نکن
    if not msg.reply_to_message:
        return
    
    replied = msg.reply_to_message.from_user
    rid = replied.id
    
    # ===== تگ همه =====
    if text == 'تگ همه':
        try:
            all_members = []
            admins = bot.get_chat_administrators(group_id)
            for a in admins:
                if not a.user.is_bot:
                    all_members.append(f"<a href='tg://user?id={a.user.id}'>{a.user.first_name}</a>")
            
            if not all_members:
                bot.send_message(group_id, "❌ هیچ کاربری برای تگ کردن وجود ندارد")
                return
            
            msg_text = "🔔 تگ همه کاربران\n\n" + " ".join(all_members[:50])
            bot.send_message(group_id, msg_text, parse_mode='HTML')
            
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
            bot.send_message(group_id, f"🚫 کاربر {get_user_link(replied)} بن شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        return
    
    # ===== رفع بن =====
    if text == 'رفع بن':
        try:
            bot.unban_chat_member(group_id, rid)
            bot.send_message(group_id, f"✅ بن کاربر {get_user_link(replied)} برداشته شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        return
    
    # ===== سکوت =====
    if text.startswith('سکوت'):
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
                bot.send_message(group_id, f"🔇 کاربر {get_user_link(replied)} به مدت {minutes} دقیقه سکوت شد", parse_mode='HTML')
            else:
                bot.restrict_chat_member(group_id, rid, can_send_messages=False)
                bot.send_message(group_id, f"🔇 کاربر {get_user_link(replied)} سکوت شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        return
    
    # ===== رفع سکوت =====
    if text == 'رفع سکوت':
        try:
            bot.restrict_chat_member(group_id, rid, can_send_messages=True, can_send_media_messages=True)
            bot.send_message(group_id, f"🔊 سکوت کاربر {get_user_link(replied)} برداشته شد", parse_mode='HTML')
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        return
    
    # ===== پین =====
    if text == 'پین':
        try:
            bot.pin_chat_message(group_id, msg.reply_to_message.message_id)
            bot.send_message(group_id, "📌 پیام پین شد")
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        return
    
    # ===== حذف پین =====
    if text == 'حذف پین':
        try:
            bot.unpin_chat_message(group_id)
            bot.send_message(group_id, "📌 پین حذف شد")
        except Exception as e:
            bot.send_message(group_id, f"❌ خطا: {e}")
        return
    
    # ===== اخطار =====
    if text == 'اخطار':
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
        return
    
    # ===== پاک‌سازی =====
    if text == 'پاک‌سازی':
        clear_warn(group_id, rid)
        bot.send_message(group_id, f"✅ اخطارهای {get_user_link(replied)} پاک شد", parse_mode='HTML')
        return

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
    elif data == 'clearwarn':
        bot.answer_callback_query(call.id, "روی پیام ریپلای کنید و 'پاک‌سازی' بنویسید")
    
    elif data == 'tagall':
        try:
            admins = bot.get_chat_administrators(group_id)
            mentions = []
            for a in admins[:30]:
                if not a.user.is_bot:
                    if a.user.username:
                        mentions.append(f"@{a.user.username}")
                    else:
                        mentions.append(f"[{a.user.first_name}](tg://user?id={a.user.id})")
            text = "🔔 توجه همه\n\n" + "\n".join(mentions)
            bot.send_message(group_id, text, parse_mode='Markdown')
            bot.answer_callback_query(call.id, "تگ انجام شد")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}")
    
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
            "تنظیم خوشامد متن جدید - تنظیم متن خوش‌آمدگویی\n"
            "تنظیم اخطار عدد - تنظیم تعداد اخطارها\n\n"
            "مثال:\n"
            "تنظیم خوشامد سلام {user} عزیز!\n"
            "تنظیم اخطار 5",
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
    print("🤖 ربات مدیریت گروه")
    print("=" * 50)
    print(f"👑 ادمین: {ADMIN_ID}")
    print(f"📱 نام کاربری: @{bot.get_me().username}")
    print("=" * 50)
    print("✅ دستورات:")
    print("• پنل - نمایش پنل مدیریت")
    print("• آمار - نمایش آمار")
    print("• راهنما - نمایش راهنما")
    print("• بن/رفع بن - با ریپلای")
    print("• سکوت 10 - سکوت ۱۰ دقیقه‌ای")
    print("• اخطار - اخطار به کاربر")
    print("• تگ همه - تگ همه کاربران")
    print("• گزارش - کاربران عادی (با ریپلای)")
    print("=" * 50)
    print("📝 منتظر درخواست‌ها...")
    print("-" * 50)
    
    try:
        bot.infinity_polling(timeout=10)
    except Exception as e:
        print(f"❌ خطا: {e}")
