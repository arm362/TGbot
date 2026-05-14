import telebot
from telebot import types
import sqlite3

# Տվյալներ
TOKEN = 'токен'
bot = telebot.TeleBot(TOKEN)
SUPER_ADMIN_ID = 1437869354  # Քո ID-ն

# --- Տվյալների Բազայի Սկզբնավորում ---
def init_db():
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS homework
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT, deadline TEXT,
                       title TEXT, description TEXT, link TEXT, file_id TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (user_id INTEGER PRIMARY KEY, username TEXT, role TEXT, status TEXT DEFAULT 'active')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS subjects (name TEXT PRIMARY KEY)''')
    # Նոր աղյուսակ՝ հաստատման սպասող տնայինների համար
    cursor.execute('''CREATE TABLE IF NOT EXISTS pending_hw
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, sub TEXT, dead TEXT, title TEXT,
                       desc TEXT, link TEXT, fid TEXT, admin_id INTEGER)''')
    conn.commit()
    conn.close()

# --- Օժանդակ Ֆունկցիաներ ---
def get_user_data(user_id):
    if user_id == SUPER_ADMIN_ID: return 'super', 'active'
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT role, status FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return (row[0], row[1]) if row else (None, 'active')

def get_subjects():
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM subjects")
    subs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subs

# --- Մենյուների Կառուցում ---
def main_menu_markup(user_id):
    role, status = get_user_data(user_id)
    if status == 'blocked': return None
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📚 Տեսնել տնայինները")
    if user_id == SUPER_ADMIN_ID or role == 'admin':
        markup.add("➕ Ավելացնել տնային", "🗑️ Ջնջել տնային")
    if user_id == SUPER_ADMIN_ID:
        markup.add("👤 Օգտատերերի կառավարում", "📖 Առարկաներ")
    return markup

# --- Հիմնական Հրամաններ ---
@bot.message_handler(commands=['start', 'restart'])
def start_handler(message):
    init_db()
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, role, status) VALUES (?, ?, ?, ?)",
                   (message.from_user.id, message.from_user.username, None, 'active'))
    conn.commit()
    conn.close()
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    bot.send_message(message.chat.id, "🔄 Բոտը պատրաստ է:", reply_markup=main_menu_markup(message.from_user.id))

@bot.message_handler(func=lambda message: message.text in ["🚫 Չեղարկել / Մենյու", "🏠 Մենյու"])
def back_to_menu(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    bot.send_message(message.chat.id, "Վերադարձ գլխավոր մենյու:", reply_markup=main_menu_markup(message.from_user.id))

# --- ԱՌԱՐԿԱՆԵՐԻ ԿԱՌԱՎԱՐՈՒՄ (Ուղղված) ---
@bot.message_handler(func=lambda message: message.text == "📖 Առարկաներ")
def subjects_menu(message):
    if message.from_user.id != SUPER_ADMIN_ID: return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Ավելացնել նոր առարկա", "❌ Ջնջել առարկա")
    markup.add("🏠 Մենյու")
    bot.send_message(message.chat.id, "Առարկաների կառավարում.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "➕ Ավելացնել նոր առարկա")
def add_sub_init(message):
    if message.from_user.id != SUPER_ADMIN_ID: return
    msg = bot.send_message(message.chat.id, "Գրեք նոր առարկան:", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🏠 Մենյու"))
    bot.register_next_step_handler(msg, save_sub)

def save_sub(message):
    if message.text == "🏠 Մենյու": return
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO subjects (name) VALUES (?)", (message.text,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ '{message.text}' ավելացվեց:")
    except: bot.send_message(message.chat.id, "❌ Սխալ:")
    conn.close()
    subjects_menu(message)

# ԱՅՍՏԵՂ ԷՐ ՍԽԱԼԸ - Տեքստը պետք է լինի ճիշտ նույնը
@bot.message_handler(func=lambda message: message.text == "❌ Ջնջել առարկա")
def del_sub_list(message):
    if message.from_user.id != SUPER_ADMIN_ID: return
    subs = get_subjects()
    if not subs:
        bot.send_message(message.chat.id, "Առարկաներ չկան:")
        return
    markup = types.InlineKeyboardMarkup()
    for s in subs: markup.add(types.InlineKeyboardButton(text=f"🗑️ {s}", callback_data=f"ds_{s}"))
    bot.send_message(message.chat.id, "Ընտրեք ջնջվող առարկան.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ds_'))
def del_sub_finish(call):
    sname = call.data.split('_')[1]
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subjects WHERE name = ?", (sname,))
    conn.commit()
    conn.close()
    bot.edit_message_text(f"✅ '{sname}' առարկան ջնջվեց:", call.message.chat.id, call.message.message_id)

# --- ՏՆԱՅԻՆԻ ԱՎԵԼԱՑՈՒՄ (Approval System) ---
@bot.message_handler(func=lambda message: message.text == "➕ Ավելացնել տնային")
def add_hw_init(message):
    role, _ = get_user_data(message.from_user.id)
    if message.from_user.id != SUPER_ADMIN_ID and role != 'admin': return
    subs = get_subjects()
    if not subs:
        bot.send_message(message.chat.id, "❌ Նախ ստեղծեք առարկա:")
        return
    markup = types.InlineKeyboardMarkup()
    for s in subs: markup.add(types.InlineKeyboardButton(text=s, callback_data=f"ah_{s}"))
    bot.send_message(message.chat.id, "Ընտրեք առարկան.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ah_'))
def add_hw_1(call):
    sub = call.data.split('_')[1]
    msg = bot.send_message(call.message.chat.id, f"📅 {sub}: Ժամկետը:", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🏠 Մենյու"))
    bot.register_next_step_handler(msg, add_hw_2, sub)

def add_hw_2(message, sub):
    if message.text == "🏠 Մենյու": return
    msg = bot.send_message(message.chat.id, "📌 Վերնագիրը:")
    bot.register_next_step_handler(msg, add_hw_3, sub, message.text)

def add_hw_3(message, sub, dead):
    if message.text == "🏠 Մենյու": return
    msg = bot.send_message(message.chat.id, "📝 Պահանջը:")
    bot.register_next_step_handler(msg, add_hw_4, sub, dead, message.text)

def add_hw_4(message, sub, dead, title):
    if message.text == "🏠 Մենյու": return
    msg = bot.send_message(message.chat.id, "🔗 Հղում (կամ 'չկա'):")
    bot.register_next_step_handler(msg, add_hw_5, sub, dead, title, message.text)

def add_hw_5(message, sub, dead, title, desc):
    if message.text == "🏠 Մենյու": return
    link = message.text
    msg = bot.send_message(message.chat.id, "📁 Ուղարկեք ֆայլ/նկար (կամ 'չկա'):")
    bot.register_next_step_handler(msg, process_hw_approval, sub, dead, title, desc, link)

def process_hw_approval(message, sub, dead, title, desc, link):
    fid = "չկա"
    if message.document: fid = message.document.file_id
    elif message.photo: fid = message.photo[-1].file_id

    if message.from_user.id == SUPER_ADMIN_ID:
        save_hw_to_main(sub, dead, title, desc, link, fid)
        bot.send_message(message.chat.id, "✅ Տնայինը հրապարակվեց:", reply_markup=main_menu_markup(SUPER_ADMIN_ID))
    else:
        conn = sqlite3.connect('homeworks.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pending_hw (sub, dead, title, desc, link, fid, admin_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (sub, dead, title, desc, link, fid, message.from_user.id))
        pending_id = cursor.lastrowid
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, "⏳ Ուղարկվեց հաստատման:", reply_markup=main_menu_markup(message.from_user.id))

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Հաստատել", callback_data=f"ap_y_{pending_id}"),
                   types.InlineKeyboardButton("❌ Մերժել", callback_data=f"ap_n_{pending_id}"))

        info = f"🆕 **Հաստատման հարցում (@{message.from_user.username}):**\n\n📚 {sub}\n⏰ {dead}\n📌 {title}\n📝 {desc}\n🔗 {link}"
        bot.send_message(SUPER_ADMIN_ID, info, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('ap_'))
def handle_approval(call):
    _, decision, pid = call.data.split('_')
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pending_hw WHERE id = ?", (pid,))
    row = cursor.fetchone()

    if decision == 'y' and row:
        save_hw_to_main(row[1], row[2], row[3], row[4], row[5], row[6])
        bot.edit_message_text(f"✅ Հաստատված է: {row[3]}", call.message.chat.id, call.message.message_id)
        bot.send_message(row[7], f"✅ Ձեր ավելացրած տնայինը ({row[3]}) հաստատվեց:")
    else:
        bot.edit_message_text("❌ Մերժված է:", call.message.chat.id, call.message.message_id)
        if row: bot.send_message(row[7], f"❌ Ձեր ավելացրած տնայինը ({row[3]}) մերժվեց:")

    cursor.execute("DELETE FROM pending_hw WHERE id = ?", (pid,))
    conn.commit()
    conn.close()

def save_hw_to_main(sub, dead, title, desc, link, fid):
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO homework (subject, deadline, title, description, link, file_id) VALUES (?, ?, ?, ?, ?, ?)",
                   (sub, dead, title, desc, link, fid))
    conn.commit()
    conn.close()

# --- ՕԳՏԱՏԵՐԵՐ, ԴԻՏՈՒՄ, ՋՆՋՈՒՄ ---
@bot.message_handler(func=lambda message: message.text == "👤 Օգտատերերի կառավարում")
def manage_users_start(message):
    if message.from_user.id != SUPER_ADMIN_ID: return
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, role, status, user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    text = "👥 **Օգտատերեր:**\n"
    markup = types.InlineKeyboardMarkup()
    for u in users:
        d_name = f"@{u[0]}" if u[0] else f"ID: {u[3]}"
        icon = "🔴" if u[2] == 'blocked' else "🟢"
        text += f"{icon} {d_name} | {u[1] if u[1] else 'guest'}\n"
        markup.add(types.InlineKeyboardButton(text=f"⚙️ {d_name}", callback_data=f"u_{u[3]}"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('u_'))
def user_opts(call):
    uid = call.data.split('_')[1]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👤 User", callback_data=f"r_{uid}_user"),
               types.InlineKeyboardButton("🛠️ Admin", callback_data=f"r_{uid}_admin"))
    markup.add(types.InlineKeyboardButton("🚫 Block", callback_data=f"s_{uid}_blocked"),
               types.InlineKeyboardButton("✅ Unblock", callback_data=f"s_{uid}_active"))
    bot.edit_message_text(f"Կառավարել ID: {uid}", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('r_', 's_')))
def user_apply(call):
    act, uid, val = call.data.split('_')
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    if act == 'r': cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (val, uid))
    else: cursor.execute("UPDATE users SET status = ? WHERE user_id = ?", (val, uid))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Կատարված է")
    manage_users_start(call.message)

@bot.message_handler(func=lambda message: message.text == "📚 Տեսնել տնայինները")
def view_subs(message):
    subs = get_subjects()
    if not subs:
        bot.send_message(message.chat.id, "Դատարկ է:")
        return
    markup = types.InlineKeyboardMarkup()
    for s in subs: markup.add(types.InlineKeyboardButton(text=s, callback_data=f"vs_{s}"))
    bot.send_message(message.chat.id, "Ընտրեք առարկան.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('vs_'))
def view_hws(call):
    sub = call.data.split('_')[1]
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM homework WHERE subject = ?", (sub,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        bot.edit_message_text(f"❌ {sub} տնային չկա:", call.message.chat.id, call.message.message_id)
        return
    markup = types.InlineKeyboardMarkup()
    for r in rows: markup.add(types.InlineKeyboardButton(text=r[1], callback_data=f"hd_{r[0]}"))
    bot.edit_message_text(f"📖 {sub}:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('hd_'))
def show_details(call):
    hid = call.data.split('_')[1]
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM homework WHERE id = ?", (hid,))
    row = cursor.fetchone()
    conn.close()
    text = f"📘 **{row[1]}**\n⏰ Ժամկետ: {row[2]}\n📌 {row[3]}\n📝 {row[4]}\n🔗 {row[5]}"
    if row[6] != "չկա":
        try: bot.send_document(call.message.chat.id, row[6], caption=text, parse_mode="Markdown")
        except: bot.send_photo(call.message.chat.id, row[6], caption=text, parse_mode="Markdown")
    else: bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🗑️ Ջնջել տնային")
def del_hw_init(message):
    role, _ = get_user_data(message.from_user.id)
    if message.from_user.id != SUPER_ADMIN_ID and role != 'admin': return
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, subject, title FROM homework")
    hws = cursor.fetchall()
    conn.close()
    if not hws:
        bot.send_message(message.chat.id, "Տնայիններ չկան:")
        return
    markup = types.InlineKeyboardMarkup()
    for h in hws: markup.add(types.InlineKeyboardButton(text=f"{h[1]}: {h[2]}", callback_data=f"dh_{h[0]}"))
    bot.send_message(message.chat.id, "Ջնջել տնայինը.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dh_'))
def del_hw_done(call):
    hid = call.data.split('_')[1]
    conn = sqlite3.connect('homeworks.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM homework WHERE id = ?", (hid,))
    conn.commit()
    conn.close()
    bot.edit_message_text("✅ Ջնջված է:", call.message.chat.id, call.message.message_id)

if __name__ == '__main__':
    init_db()
    bot.infinity_polling()
