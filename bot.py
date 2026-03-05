import telebot
from telebot import types
from pymongo import MongoClient
from bson.objectid import ObjectId

# --- Տվյալներ ---
TOKEN = '8569660174:AAHvzCs5EV9_YmA1ESTkoZC57JxBy_1H5VU'
# Քո MongoDB կապի հղումը
MONGO_URI = "mongodb+srv://amirarmen2009_db_user:SSI4Q3zHq6Qxzm2G@cluster0.pvfo75w.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

bot = telebot.TeleBot(TOKEN)
SUPER_ADMIN_ID = 1437869354 

# --- MongoDB Միացում ---
client = MongoClient(MONGO_URI)
db = client['homework_bot']
users_col = db['users']
subjects_col = db['subjects']
homework_col = db['homework']
pending_col = db['pending_hw']

# --- Օժանդակ Ֆունկցիաներ ---
def get_user_data(user_id):
    if user_id == SUPER_ADMIN_ID: return 'super', 'active'
    user = users_col.find_one({"user_id": user_id})
    if user:
        return user.get('role'), user.get('status', 'active')
    return None, 'active'

def get_subjects():
    return [s['name'] for s in subjects_col.find()]

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
    users_col.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"username": message.from_user.username, "status": "active"}},
        upsert=True
    )
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    bot.send_message(message.chat.id, "🔄 Բոտը պատրաստ է (MongoDB-ն միացված է):", reply_markup=main_menu_markup(message.from_user.id))

@bot.message_handler(func=lambda message: message.text in ["🚫 Չեղարկել / Մենյու", "🏠 Մենյու"])
def back_to_menu(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    bot.send_message(message.chat.id, "Վերադարձ գլխավոր մենյու:", reply_markup=main_menu_markup(message.from_user.id))

# --- ԱՌԱՐԿԱՆԵՐԻ ԿԱՌԱՎԱՐՈՒՄ ---
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
    subjects_col.update_one({"name": message.text}, {"$set": {"name": message.text}}, upsert=True)
    bot.send_message(message.chat.id, f"✅ '{message.text}' ավելացվեց:")
    subjects_menu(message)

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
    subjects_col.delete_one({"name": sname})
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
        res = pending_col.insert_one({
            "sub": sub, "dead": dead, "title": title, "desc": desc, 
            "link": link, "fid": fid, "admin_id": message.from_user.id
        })
        pending_id = str(res.inserted_id)

        bot.send_message(message.chat.id, "⏳ Ուղարկվեց հաստատման:", reply_markup=main_menu_markup(message.from_user.id))

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Հաստատել", callback_data=f"ap_y_{pending_id}"),
                   types.InlineKeyboardButton("❌ Մերժել", callback_data=f"ap_n_{pending_id}"))

        info = f"🆕 **Հաստատման հարցում (@{message.from_user.username}):**\n\n📚 {sub}\n⏰ {dead}\n📌 {title}\n📝 {desc}\n🔗 {link}"
        bot.send_message(SUPER_ADMIN_ID, info, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('ap_'))
def handle_approval(call):
    _, decision, pid = call.data.split('_')
    row = pending_col.find_one({"_id": ObjectId(pid)})

    if decision == 'y' and row:
        save_hw_to_main(row['sub'], row['dead'], row['title'], row['desc'], row['link'], row['fid'])
        bot.edit_message_text(f"✅ Հաստատված է: {row['title']}", call.message.chat.id, call.message.message_id)
        bot.send_message(row['admin_id'], f"✅ Ձեր ավելացրած տնայինը ({row['title']}) հաստատվեց:")
    else:
        bot.edit_message_text("❌ Մերժված է:", call.message.chat.id, call.message.message_id)
        if row: bot.send_message(row['admin_id'], f"❌ Ձեր ավելացրած տնայինը ({row['title']}) մերժվեց:")

    pending_col.delete_one({"_id": ObjectId(pid)})

def save_hw_to_main(sub, dead, title, desc, link, fid):
    homework_col.insert_one({
        "subject": sub, "deadline": dead, "title": title, 
        "description": desc, "link": link, "file_id": fid
    })

# --- ՕԳՏԱՏԵՐԵՐ, ԴԻՏՈՒՄ, ՋՆՋՈՒՄ ---
@bot.message_handler(func=lambda message: message.text == "👤 Օգտատերերի կառավարում")
def manage_users_start(message):
    if message.from_user.id != SUPER_ADMIN_ID: return
    users = list(users_col.find())
    text = "👥 **Օգտատերեր:**\n"
    markup = types.InlineKeyboardMarkup()
    for u in users:
        d_name = f"@{u['username']}" if u.get('username') else f"ID: {u['user_id']}"
        icon = "🔴" if u.get('status') == 'blocked' else "🟢"
        text += f"{icon} {d_name} | {u.get('role') if u.get('role') else 'guest'}\n"
        markup.add(types.InlineKeyboardButton(text=f"⚙️ {d_name}", callback_data=f"u_{u['user_id']}"))
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
    uid = int(uid)
    if act == 'r': users_col.update_one({"user_id": uid}, {"$set": {"role": val}})
    else: users_col.update_one({"user_id": uid}, {"$set": {"status": val}})
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
    rows = list(homework_col.find({"subject": sub}))
    if not rows:
        bot.edit_message_text(f"❌ {sub} տնային չկա:", call.message.chat.id, call.message.message_id)
        return
    markup = types.InlineKeyboardMarkup()
    for r in rows: markup.add(types.InlineKeyboardButton(text=r['title'], callback_data=f"hd_{r['_id']}"))
    bot.edit_message_text(f"📖 {sub}:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('hd_'))
def show_details(call):
    hid = call.data.split('_')[1]
    row = homework_col.find_one({"_id": ObjectId(hid)})
    if not row: return
    text = f"📘 **{row['title']}**\n⏰ Ժամկետ: {row['deadline']}\n📌 {row['subject']}\n📝 {row['description']}\n🔗 {row['link']}"
    if row['file_id'] != "չկա":
        try: bot.send_document(call.message.chat.id, row['file_id'], caption=text, parse_mode="Markdown")
        except: bot.send_photo(call.message.chat.id, row['file_id'], caption=text, parse_mode="Markdown")
    else: bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🗑️ Ջնջել տնային")
def del_hw_init(message):
    role, _ = get_user_data(message.from_user.id)
    if message.from_user.id != SUPER_ADMIN_ID and role != 'admin': return
    hws = list(homework_col.find())
    if not hws:
        bot.send_message(message.chat.id, "Տնայիններ չկան:")
        return
    markup = types.InlineKeyboardMarkup()
    for h in hws: markup.add(types.InlineKeyboardButton(text=f"{h['subject']}: {h['title']}", callback_data=f"dh_{h['_id']}"))
    bot.send_message(message.chat.id, "Ջնջել տնայինը.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dh_'))
def del_hw_done(call):
    hid = call.data.split('_')[1]
    homework_col.delete_one({"_id": ObjectId(hid)})
    bot.edit_message_text("✅ Ջնջված է:", call.message.chat.id, call.message.message_id)

if __name__ == '__main__':
    bot.infinity_polling()
