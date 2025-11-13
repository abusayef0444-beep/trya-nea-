import json, re, sys, os, threading, tempfile
import telebot
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
import time # For timestamp in orders

# ========== CONFIG ==========
BOT_TOKEN = "8330157284:AAGRyWnRPUGNhNUnQISUNojr7ojdjThqmto" # আপনার বট টোকেন
ADMIN_ID  = 5830499612# আপনার অ্যাডমিন টেলিগ্রাম ইউজার আইডি
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "bot_data.json")

BOT_ID = int(BOT_TOKEN.split(":")[0]) # <--- এটিই সঠিক লাইন

# --- Define the file_id for your general welcome image here ---
WELCOME_PHOTO_FILE_ID = "AgACAgUAAxkBAANhaP5JbanDLp49uWHygkJdZcpL8P0AAlIMaxvdG_BXlW-fVQWpcPMBAAMCAAN5AAM2BA" # Example file_id, replace with yours!

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

def to_snake_key(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value

def normalize_balances(balances_input):
    normalized = {}
    if isinstance(balances_input, dict):
        for uid, amount in balances_input.items():
            key = str(uid)
            try:
                normalized[key] = float(amount)
            except (TypeError, ValueError):
                normalized[key] = 0.0
    return normalized

def normalize_products(products_input):
    normalized = {}
    if isinstance(products_input, dict):
        for vpn_name, items in products_input.items():
            key = str(vpn_name)
            normalized_items = []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        normalized_items.append({to_snake_key(k): v for k, v in item.items()})
            normalized[key] = normalized_items
    return normalized

def normalize_orders(orders_input):
    normalized = {}
    if isinstance(orders_input, dict):
        for uid, order_list in orders_input.items():
            if not isinstance(order_list, list):
                continue
            clean_orders = []
            for order in order_list:
                if not isinstance(order, dict):
                    continue
                order_copy = dict(order)
                item = order_copy.get("item")
                if isinstance(item, dict):
                    order_copy["item"] = {to_snake_key(k): v for k, v in item.items()}
                clean_orders.append(order_copy)
            normalized[str(uid)] = clean_orders
    return normalized

def normalize_pending_payments(pending_input):
    normalized = {}
    if isinstance(pending_input, dict):
        for trx, uid in pending_input.items():
            normalized[str(trx).lower()] = str(uid)
    return normalized

def normalize_unmatched_payments(unmatched_input):
    normalized = {}
    if isinstance(unmatched_input, dict):
        for trx, amount in unmatched_input.items():
            key = str(trx).lower()
            try:
                normalized[key] = float(amount)
            except (TypeError, ValueError):
                continue
    return normalized

def normalize_free_orders(free_orders_input):
    normalized = {}
    if isinstance(free_orders_input, dict):
        for oid, info in free_orders_input.items():
            if not isinstance(info, dict):
                continue
            entry = dict(info)
            entry["user_id"] = str(entry.get("user_id", ""))
            entry["vpn_name"] = str(entry.get("vpn_name", ""))
            if "price" in entry:
                try:
                    entry["price"] = float(entry["price"])
                except (TypeError, ValueError):
                    entry["price"] = 0.0
            entry["delivered"] = bool(entry.get("delivered", False))
            delivery_details = entry.get("delivery_details")
            if isinstance(delivery_details, dict):
                entry["delivery_details"] = {to_snake_key(k): v for k, v in delivery_details.items()}
            normalized[str(oid)] = entry
    return normalized

def normalize_processed_payments(values):
    normalized_set = set()
    iterable = []
    if isinstance(values, dict):
        iterable = values.keys()
    elif isinstance(values, (list, set, tuple)):
        iterable = values
    for item in iterable:
        if item is None:
            continue
        normalized_set.add(str(item).lower())
    return sorted(normalized_set)

def normalize_total_sales(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

# ========== DATA ==========
def load_data():
    raw = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Failed to load data file: {e}. Using defaults.")
            raw = {}
    data = {}
    data["products"] = normalize_products(raw.get("products", {}))
    data["balances"] = normalize_balances(raw.get("balances", {}))
    data["pending_payments"] = normalize_pending_payments(raw.get("pending_payments", {}))
    data["unmatched_payments"] = normalize_unmatched_payments(raw.get("unmatched_payments", {}))
    data["orders"] = normalize_orders(raw.get("orders", {}))
    data["total_sales"] = normalize_total_sales(raw.get("total_sales", 0.0))
    data["free_orders"] = normalize_free_orders(raw.get("free_orders", {}))
    data["processed_payments"] = normalize_processed_payments(raw.get("processed_payments", []))

    data.setdefault("products", {})
    data.setdefault("balances", {})
    data.setdefault("pending_payments", {})
    data.setdefault("unmatched_payments", {})
    data.setdefault("orders", {})
    data.setdefault("total_sales", 0.0)
    data.setdefault("free_orders", {})
    data.setdefault("processed_payments", [])
    return data

def save_data(d):
    payload = {
        "products": normalize_products(d.get("products", {})),
        "balances": normalize_balances(d.get("balances", {})),
        "pending_payments": normalize_pending_payments(d.get("pending_payments", {})),
        "unmatched_payments": normalize_unmatched_payments(d.get("unmatched_payments", {})),
        "orders": normalize_orders(d.get("orders", {})),
        "total_sales": normalize_total_sales(d.get("total_sales", 0.0)),
        "free_orders": normalize_free_orders(d.get("free_orders", {})),
        "processed_payments": normalize_processed_payments(processed_payments),
    }

    temp_fd, temp_path = tempfile.mkstemp(dir=BASE_DIR, prefix="bot_data.", suffix=".tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as tmp_file:
            json.dump(payload, tmp_file, ensure_ascii=False, indent=2)
        os.replace(temp_path, DATA_FILE)
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise

    # Keep in-memory reference updated for processed_payments list if needed
    d["processed_payments"] = payload["processed_payments"]

data               = load_data()
products           = data["products"]
balances           = data["balances"]
pending_payments   = data["pending_payments"]
unmatched_payments = data["unmatched_payments"]
orders             = data["orders"]
total_sales        = data["total_sales"]
free_orders        = data["free_orders"]
processed_payments = set(data["processed_payments"])

print("DATA_FILE path:", DATA_FILE)
print("Exists:", os.path.exists(DATA_FILE))
print("Balances users count:", len(balances))
print("Total stock items:", sum(len(v) for v in products.values()))

DATA_REPORT_INTERVAL_SECONDS = 3600

# Updated vpn_prices structure based on your provided list
vpn_prices = {
    "Express VPN": {"price": 30, "days": 7},
    "Nord VPN": {"price": 40, "days": 7},
    "PIA VPN": {"price": 30, "days": 7},
    "Surfshark": {"price": 30, "days": 7},
    "HotspotShield VPN": {"price": 30, "days": 7},
    "HMA VPN": {"price": 30, "days": 7},
    "IPVanish VPN": {"price": 30, "days": 7},
    "Cyberghost VPN": {"price": 15, "days": 3}, # Changed to 3 Days
    "Vypr VPN": {"price": 15, "days": 3},    # Changed to 3 Days
    "X VPN": {"price": 30, "days": 7},
    "Pure VPN": {"price": 30, "days": 7},
    "Panda VPN": {"price": 15, "days": 3},   # Changed to 3 Days
    "Turbo VPN": {"price": 30, "days": 7},
    "Sky VPN": {"price": 30, "days": 7},
    "Potato VPN": {"price": 30, "days": 7},
    "Zoog VPN": {"price": 15, "days": 3}
}

# --- NEW: Define expected fields for each VPN type ---
# Keys are the exact keys from vpn_prices.
# Values are lists of required fields in the order they should appear in the input/output.
product_fields = {
    "Express VPN": ["Gmail", "Password", "Activation Key"],  # Express VPN: Gmail + Password + Activation Key
    "HMA VPN": ["Activation Key"], # HMA VPN will only have an activation key
    # Default for others (if not specified here, it falls back to a generic Gmail/Password)
}
# --- END NEW ---

# Payment gateway number (updated to your specified number)
PAYMENT_NUMBER = "01739089344" 

# ========== SMALL DEBUG LOG ==========
def log(msg):
    try:
        print(f"[LOG] {msg}")
    except:
        pass

# Helper functions
def main_menu_markup():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🛒 Buy Products", "💰 Add Balance")
    kb.row("📦 My Orders", "💳 My Balance")
    return kb

def admin_menu_markup():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 Total Sales", "📈 Current Stock")
    kb.row("➕ Add VPN Account", "📩 Free Orders")
    kb.row("⬅️ Main Menu (User)")
    return kb

def norm_text(s): return " ".join(s.strip().split()).lower() if isinstance(s, str) else ""
def ensure_user(uid): balances.setdefault(uid, 0.0); orders.setdefault(uid, [])

def admin_command_help():
    return (
        "📋 Admin Slash Commands:\n"
        "/data – বর্তমান bot_data.json ফাইল পাঠাবে\n"
        "/buyer – মোট ইউজার, বায়ার সংখ্যা ও টপ বায়ার লিস্ট\n"
        "/removebalance <user_id> – নির্দিষ্ট ইউজারের ব্যালেন্স 0 করবে\n"
        "/broadcast – সবার কাছে ম্যাসেজ পাঠাবে\n"
        "/remind_freeorders – Pending free order ইউজারদের রিমাইন্ডার"
    )

def parse_trx_id(text): 
    m_bkash = re.search(r'TrxID[:\s]+([A-Za-z0-9]+)', text, re.I)
    if m_bkash:
        return m_bkash.group(1).lower()
    
    m_nagad = re.search(r'TxnID[:\s]+([A-Za-z0-9]+)', text, re.I)
    if m_nagad:
        return m_nagad.group(1).lower()
        
    return None

def parse_amount(text): 
    m = re.search(r'\bTk\s?([0-9]+(?:\.[0-9]{1,2})?)\b', text.replace(",", ""), re.I)
    return float(m.group(1)) if m else None

def build_buyer_stats_report(max_list=15):
    total_users = len(balances)
    buyer_map = {uid: user_orders for uid, user_orders in orders.items() if user_orders}

    if not buyer_map:
        return (
            "👥 Buyer Overview\n\n"
            f"Total Users: {total_users}\n"
            "Unique Buyers: 0\n"
            "Total Orders: 0\n\n"
            "এখনো কেউ কোনো VPN কেনেনি।"
        )

    total_unique = len(buyer_map)
    total_orders = sum(len(user_orders) for user_orders in buyer_map.values())

    def ts_to_epoch(ts):
        try:
            return time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
        except Exception:
            return 0

    buyer_entries = []
    for uid, user_orders in buyer_map.items():
        order_count = len(user_orders)
        last_timestamp = user_orders[-1].get("timestamp", "N/A")
        buyer_entries.append((uid, order_count, last_timestamp, ts_to_epoch(last_timestamp)))

    buyer_entries.sort(key=lambda item: (-item[1], -item[3], item[0]))

    lines = [
        "👥 Buyer Overview",
        "",
        f"Total Users: {total_users}",
        f"Unique Buyers: {total_unique}",
        f"Total Orders: {total_orders}",
        "",
        "🏆 Top Buyers:",
    ]

    for idx, (uid, count, last_ts, _) in enumerate(buyer_entries[:max_list], start=1):
        lines.append(f"{idx}. `{uid}` — {count} order(s) (last: {last_ts})")

    remaining = len(buyer_entries) - max_list
    if remaining > 0:
        lines.append(f"… এবং আরও {remaining} জন")

    return "\n".join(lines)

def reset_user_balance(admin_chat_id, target_uid):
    target_uid = str(target_uid).strip()
    if not target_uid:
        bot.send_message(admin_chat_id, "❌ ইউজার আইডি প্রদান করুন।")
        return

    if target_uid not in balances:
        bot.send_message(admin_chat_id, f"❌ ইউজার `{target_uid}` পাওয়া যায়নি।", parse_mode="Markdown")
        return

    previous_balance = balances.get(target_uid, 0.0)

    if previous_balance == 0.0:
        bot.send_message(admin_chat_id, f"ℹ️ ইউজার `{target_uid}` এর ব্যালেন্স আগে থেকেই 0 ছিল।", parse_mode="Markdown")
        return

    balances[target_uid] = 0.0
    data["balances"] = balances
    save_data(data)

    bot.send_message(admin_chat_id, f"✅ ইউজার `{target_uid}` এর ব্যালেন্স 0 করা হয়েছে (আগে ছিল {previous_balance:.2f}৳)।", parse_mode="Markdown")

    try:
        bot.send_message(int(target_uid), "⚠️ আপনার ব্যালেন্স এডমিন কর্তৃক 0 করা হয়েছে। যদি কোনো প্রশ্ন থাকে, যোগাযোগ করুন।")
    except Exception as e:
        log(f"Could not notify user {target_uid} about balance reset: {e}")

def generate_data_snapshot_file():
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    safe_timestamp = generated_at.replace(" ", "_").replace(":", "-")
    filename = f"bot_data_snapshot_{safe_timestamp}.json"
    file_path = os.path.join(tempfile.gettempdir(), filename)

    try:
        save_data(data)
    except Exception as e:
        log(f"Failed to persist data before snapshot: {e}")

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as src:
            contents = src.read()
    except FileNotFoundError:
        log("DATA_FILE not found; using in-memory data for snapshot.")
        contents = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Failed to read DATA_FILE: {e}")
        contents = json.dumps(data, ensure_ascii=False, indent=2)

    try:
        with open(file_path, "w", encoding="utf-8") as dst:
            dst.write(contents)
    except Exception as e:
        log(f"Failed to write snapshot file: {e}")
        raise

    return file_path, generated_at

def send_bot_data_snapshot(target_chat_id, reason="Scheduled hourly snapshot"):
    try:
        file_path, generated_at = generate_data_snapshot_file()
    except Exception as e:
        log(f"Unable to create bot data snapshot: {e}")
        return

    caption_lines = [
        "📄 Bot Data Snapshot",
        f"Generated: {generated_at}",
    ]
    if reason:
        caption_lines.append(f"Reason: {reason}")
    caption_lines.append(f"Users tracked: {len(balances)}")
    caption = "\n".join(caption_lines)

    try:
        with open(file_path, "rb") as report_file:
            bot.send_document(
                target_chat_id,
                report_file,
                caption=caption,
                parse_mode="Markdown",
                visible_file_name=os.path.basename(file_path)
            )
    except Exception as e:
        log(f"Failed to send bot data snapshot: {e}")
    finally:
        try:
            os.remove(file_path)
        except Exception:
            pass

def _data_report_worker():
    log("Starting bot data report scheduler thread")
    while True:
        try:
            send_bot_data_snapshot(ADMIN_ID)
        except Exception as e:
            log(f"Scheduler error: {e}")
        time.sleep(DATA_REPORT_INTERVAL_SECONDS)

def start_data_report_scheduler():
    scheduler_thread = threading.Thread(target=_data_report_worker, name="BotDataReportScheduler", daemon=True)
    scheduler_thread.start()

# ========== START COMMANDS ==========
@bot.message_handler(commands=['start', 'admin'])
def start_or_admin(message):
    uid = str(message.from_user.id)
    ensure_user(uid)
    
    # Define your welcome message
    welcome_message = (
        "আসসালামু আলাইকুম ❤️‍🩹 PremiumOne এ আপনাকে স্বাগতম। কোন প্রকার সমস্যা হলে যোগাযোগ করবেন @Abdurrahman0999\n"
        "—ধন্যবাদ 💞\n\n"
        "যেভাবে ব্যালেন্স এড করবেন 💳\n\n"
        "\t└ 💰ADD BALANCE এ ক্লিক করুন\n"
        "\t└ bKash/Nagad সিলেক্ট করুন\n"
        "\t└ নাম্বারটি কপি করে পেমেন্ট করুন\n"
        "\t└ Trx Id কপি করে রাখুন\n"
        "\t└ Payment Done ক্লিক করুন\n"
        "\t└ Trx Id দিন\n"
        "\t└ Balance Add হয়ে যাবে\n\n"
        "যেভাবে Vpn নিবেন 🛍\n\n"
        "\t└ Buy Products এ ক্লিক করুন\n"
        "\t└ VPN সিলেক্ট করুন\n"
        "\t└ Buy Now এ ক্লিক করুন"
    
    )

    if uid == str(ADMIN_ID):
        welcome_text = "👋 Welcome Admin! Choose an option:\n\n" + admin_command_help()
        bot.send_message(message.chat.id, welcome_text, reply_markup=admin_menu_markup())
    else:
        if WELCOME_PHOTO_FILE_ID:
            try:
                bot.send_photo(message.chat.id, WELCOME_PHOTO_FILE_ID, caption=welcome_message, reply_markup=main_menu_markup(), parse_mode="Markdown")
            except Exception as e:
                print(f"Error sending welcome photo with file_id: {e}")
                bot.send_message(message.chat.id, "Error sending welcome image. " + welcome_message, reply_markup=main_menu_markup(), parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, welcome_message, reply_markup=main_menu_markup(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: norm_text(m.text) == "💳 my balance")
def show_balance(message):
    uid = str(message.from_user.id)
    ensure_user(uid)
    bot.send_message(message.chat.id, f"💳 Your current balance: {balances.get(uid, 0.0):.2f}৳", reply_markup=main_menu_markup())

# ========== BUY PRODUCTS ==========
@bot.message_handler(func=lambda m: norm_text(m.text) == "🛒 buy products")
def show_vpn_list(message):
    markup = InlineKeyboardMarkup()
    for name, data_item in vpn_prices.items():
        price = data_item["price"]
        days = data_item["days"]
        stock_count = len(products.get(name, []))
        
        # Use a red dot for out of stock, checkmark for in stock
        status_icon = "✅" if stock_count > 0 else "🔴"
        markup.add(InlineKeyboardButton(f"{name} {days} Days {price}৳ {status_icon}", callback_data=f"vpn|{name}")) 
    bot.send_message(message.chat.id, "🛍 Available VPNs:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("vpn|"))
def vpn_selected(c):
    log(f"callback vpn_selected data={c.data} from={c.from_user.id}")
    vpn_name = c.data.split("|")[1]
    vpn_info = vpn_prices.get(vpn_name)
    if not vpn_info:
        bot.edit_message_text("❌ VPN not found.", c.message.chat.id, c.message.message_id)
        bot.answer_callback_query(c.id, "VPN not found.", show_alert=True)
        return

    price = vpn_info["price"]
    days = vpn_info["days"]
    uid = str(c.from_user.id)
    bal = balances.get(uid, 0.0)
    stock_count = len(products.get(vpn_name, [])) # Stock count for logic, not display to user

    kb = InlineKeyboardMarkup()
    
    # Message for display
    message_text = (
        f"🛍 *{vpn_name}*\n\n"
        f"*🕒 Duration*:  {days} Days\n"
        f"\t└ *Price:* *{price}৳*\n"
        f"\t**Your Balance:** {bal:.2f}৳\n\n"
    )
    
    if stock_count == 0:
        bot.answer_callback_query(c.id, "দুঃখিত ভাই এই Vpn Stock নেই আপনি চাইলে অর্ডার করে রাখতে পারেন 💗", show_alert=True)
        message_text += "*🚫দুঃখিত ভাই এই Vpn Stock নেই*\n\nঅর্ডার করে রাখতে পারেন Account করে আপনাকে দেওয়া হবে 💗 "
        # NEW: Free order request button
        kb.add(InlineKeyboardButton("📩 Request Order", callback_data=f"freeorder|{vpn_name}"))
    elif bal < price:
        bot.answer_callback_query(c.id, "Insufficient balance. Please add funds.", show_alert=True)
        message_text += "💰 Insufficient balance. Please add funds."
        kb.add(InlineKeyboardButton("➕ Add Balance", callback_data="add_balance_shortcut")) # Correct emoji
    else: # Sufficient balance and stock
        message_text += "Ready to purchase!"
        kb.add(InlineKeyboardButton("✅ Buy Now", callback_data=f"buy|{vpn_name}"))
    
    # Always include Cancel and Back to Main Menu
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_vpn_selection"))
    kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main_menu")) # Correct emoji
    
    try:
        bot.edit_message_text(message_text, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        log(f"edit_message_text failed: {e}")
        bot.edit_message_text("Select an option:", c.message.chat.id, c.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "cancel_vpn_selection")
def cancel_vpn_selection(c):
    bot.edit_message_text("Selection cancelled. Returning to main menu.", c.message.chat.id, c.message.message_id)
    bot.send_message(c.message.chat.id, "Choose an option:", reply_markup=main_menu_markup())
    bot.answer_callback_query(c.id, "Cancelled.")

@bot.callback_query_handler(func=lambda c: c.data == "back_to_main_menu")
def back_to_main_menu_callback(c):
    bot.edit_message_text("Returning to main menu.", c.message.chat.id, c.message.message_id)
    bot.send_message(c.message.chat.id, "Choose an option:", reply_markup=main_menu_markup())
    bot.answer_callback_query(c.id, "Back to main menu.")

# ========== BUY NOW HANDLER ==========
@bot.callback_query_handler(func=lambda c: c.data.startswith("buy|"))
def process_buy(c):
    log(f"callback process_buy data={c.data} from={c.from_user.id}")
    vpn_name = c.data.split("|")[1]
    uid = str(c.from_user.id)
    bal = balances.get(uid, 0.0)
    vpn_info = vpn_prices.get(vpn_name)

    if not vpn_info:
        bot.answer_callback_query(c.id, "❌ VPN not found.", show_alert=True)
        return

    price = vpn_info["price"]

    # Check balance
    if bal < price:
        bot.answer_callback_query(c.id, "❌ Insufficient balance.", show_alert=True)
        return

    # Check stock
    stock_list = products.get(vpn_name, [])
    if not stock_list:
        bot.answer_callback_query(c.id, "❌ Out of stock.", show_alert=True)
        return

    # Deduct balance
    balances[uid] = round(bal - price, 2)

    # Pop one VPN account from stock
    item = stock_list.pop(0)

    # Save order
    order = {
        "vpn_name": vpn_name,
        "item": item,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    orders.setdefault(uid, []).append(order)

    # Update total sales
    global total_sales
    total_sales += price

    # Save data
    data["balances"], data["products"], data["orders"], data["total_sales"] = balances, products, orders, total_sales
    save_data(data)

    # Build delivery message
    fields_to_display = product_fields.get(vpn_name, ["Gmail", "Password"])
    delivered_msg = f"🛍 *{vpn_name}* {vpn_info['days']} Days ✅\n\n"
    for field in fields_to_display:
        key = field.lower().replace(" ", "_")
        delivered_msg += f"*{field}* ➡ `{item.get(key, 'N/A')}`\n\n"

    # Send to user
    try:
        bot.edit_message_text(delivered_msg, c.message.chat.id, c.message.message_id, parse_mode="Markdown")
    except Exception as e:
        log(f"delivery edit_message_text failed: {e}")
        bot.edit_message_text(f"{vpn_name} delivered.", c.message.chat.id, c.message.message_id)
    bot.send_message(c.message.chat.id, "⬅️ Back to menu:", reply_markup=main_menu_markup())

    # Notify admin
    bot.send_message(
        ADMIN_ID,
        f"🛒 New Order\nUser: `{uid}`\nVPN: *{vpn_name}*\nPrice: {price}৳",
        parse_mode="Markdown"
    )

    bot.answer_callback_query(c.id, "✅ VPN delivered!", show_alert=True)

# ========== FREE ORDER REQUEST (Out-of-stock purchase) ==========
@bot.callback_query_handler(func=lambda c: c.data.startswith("freeorder|"))
def confirm_free_order(c):
    log(f"callback confirm_free_order data={c.data} from={c.from_user.id}")
    vpn_name = c.data.split("|")[1]
    vpn_info = vpn_prices.get(vpn_name)
    if not vpn_info:
        bot.answer_callback_query(c.id, "VPN not found.", show_alert=True)
        return

    price = vpn_info["price"]
    uid = str(c.from_user.id)
    bal = balances.get(uid, 0.0)

    if bal < price:
        bot.answer_callback_query(c.id, "Insufficient balance.", show_alert=True)
        return

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Done", callback_data=f"confirm_freeorder|{vpn_name}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_freeorder")
    )

    try:
        bot.edit_message_text(
            f"আপনি কি নিশ্চিত যে *{vpn_name}* এর অর্ডার করতে চান?\n\n"
            f"💳 Price: {price}৳\n"
            f"💰 Your Balance: {bal:.2f}৳",
            c.message.chat.id, c.message.message_id,
            parse_mode="Markdown", reply_markup=kb
        )
    except Exception as e:
        log(f"confirm_free_order edit failed: {e}")
        bot.edit_message_text("Confirm free order?", c.message.chat.id, c.message.message_id, reply_markup=kb)
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_freeorder|"))
def request_free_order(c):
    log(f"callback request_free_order data={c.data} from={c.from_user.id}")
    vpn_name = c.data.split("|")[1]
    vpn_info = vpn_prices.get(vpn_name)
    if not vpn_info:
        bot.answer_callback_query(c.id, "VPN not found.", show_alert=True)
        return

    price = vpn_info["price"]
    uid = str(c.from_user.id)
    bal = balances.get(uid, 0.0)

    if bal < price:
        bot.answer_callback_query(c.id, "Insufficient balance.", show_alert=True)
        return

    # Deduct balance and create a free order entry
    balances[uid] = round(bal - price, 2)
    order_id = f"{uid}_{int(time.time())}"
    free_orders[order_id] = {
        "user_id": uid,
        "vpn_name": vpn_name,
        "price": price,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "delivered": False
    }
    data["balances"], data["free_orders"] = balances, free_orders
    save_data(data)

    try:
        bot.edit_message_text(
            f"📩 আপনার *{vpn_name}* এর অর্ডার সাবমিট হয়েছে ✅\n\nOrder ID: `{order_id}`\n\n—ধন্যবাদ 💞",
            c.message.chat.id, c.message.message_id, parse_mode="Markdown"
        )
    except Exception as e:
        log(f"request_free_order edit failed: {e}")
        bot.edit_message_text("Free order submitted.", c.message.chat.id, c.message.message_id)
    bot.send_message(c.message.chat.id, "⬅️ Back to menu:", reply_markup=main_menu_markup())
    bot.send_message(
        ADMIN_ID,
        f"📩 New Free Order Request:\nUser: `{uid}`\nVPN: *{vpn_name}*\nPrice: {price}৳\nOrder ID: `{order_id}`",
        parse_mode="Markdown"
    )
    bot.answer_callback_query(c.id, "Request placed successfully!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "cancel_freeorder")
def cancel_freeorder(c):
    bot.edit_message_text("❌ Request cancelled. Returning to main menu.", c.message.chat.id, c.message.message_id)
    bot.send_message(c.message.chat.id, "Choose an option:", reply_markup=main_menu_markup())
    bot.answer_callback_query(c.id, "Cancelled.")

# ========== MY ORDERS ==========
@bot.message_handler(func=lambda m: norm_text(m.text) == "📦 my orders")
def show_my_orders(message):
    uid = str(message.from_user.id)
    user_orders = orders.get(uid)
    
    if not user_orders:
        bot.send_message(message.chat.id, "You haven't purchased any VPNs yet! Go to '🛒 Buy Products' to get started.", reply_markup=main_menu_markup())
        return
    
    order_list_text = "🛍 Your Recent Orders:\n\n"
    # Show last 5 orders, or fewer if less than 5
    for i, order_item in enumerate(user_orders[-5:]): 
        vpn_name = order_item.get("vpn_name", "N/A")
        item_details = order_item.get("item", {})
        timestamp = order_item.get("timestamp", "N/A")
        
        order_list_text += f"*{i+1}. {vpn_name}* (Purchased: {timestamp})\n"
        
        # --- MODIFIED: Display VPN details in orders based on product_fields ---
        fields_to_display = product_fields.get(vpn_name, ["Gmail", "Password"])
        for field_name in fields_to_display:
            item_key = field_name.replace(" ", "_").lower()
            order_list_text += f"  *{field_name}:* `{item_details.get(item_key, 'N/A')}`\n\n"
        order_list_text += "\n"
        # --- END MODIFIED ---
        
    bot.send_message(message.chat.id, order_list_text, parse_mode="Markdown", reply_markup=main_menu_markup())

# ========== ADD BALANCE ==========
@bot.message_handler(func=lambda m: norm_text(m.text) == "💰 add balance")
def add_balance_ui(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🟣 Bkash", callback_data="add_balance_bkash"))
    kb.add(InlineKeyboardButton("🟠 Nagad", callback_data="add_balance_nagad"))
    bot.send_message(message.chat.id, "Choose your payment method:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "add_balance_shortcut")
def add_balance_shortcut(c):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🟣 Bkash", callback_data="add_balance_bkash"))
    kb.add(InlineKeyboardButton("🟠 Nagad", callback_data="add_balance_nagad"))
    bot.edit_message_text("Choose your payment method:", c.message.chat.id, c.message.message_id, reply_markup=kb)
    bot.answer_callback_query(c.id, "Redirecting to Add Balance section.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("add_balance_"))
def show_payment_details(c):
    method = c.data.split("_")[2].capitalize() # "Bkash" or "Nagad"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Payment Done ✅", callback_data="send_trx"))
    
    bot.edit_message_text(
        f"নিচের দেওয়া {method} নাম্বারে এ সেন্ড মানি করবেন 👇\n\n`{PAYMENT_NUMBER}`\n\n"
        "Trx Id কপি করে রাখবেন\n\nটাকা পাঠানোর পর Payment Done ✅ এ ক্লিক করুন\n └ TRX ID দিন",
        c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=kb
    )
    bot.answer_callback_query(c.id, f"Showing {method} payment details.")

@bot.callback_query_handler(func=lambda c: c.data == "send_trx")
def ask_trx(c):
    msg = bot.send_message(c.message.chat.id, "📥 TRX ID দিন", reply_markup=ForceReply())
    bot.register_next_step_handler(msg, save_trx_id)
    bot.answer_callback_query(c.id, "Please send your TRX ID.")

def save_trx_id(message):
    uid = str(message.from_user.id)
    trx = (message.text or "").strip().lower()

    if not re.fullmatch(r"[A-Za-z0-9]+", trx):
        bot.reply_to(message, "❌ Invalid TRX ID format. Please enter a valid Transaction ID.")
        bot.send_message(message.chat.id, "⬅️ Back to menu:", reply_markup=main_menu_markup())
        return

    if trx in processed_payments:
        bot.reply_to(message, "❌ This TRX ID has already been confirmed. Please use a new one.")
        bot.send_message(message.chat.id, "⬅️ Back to menu:", reply_markup=main_menu_markup())
        return
    
    if trx in pending_payments:
        bot.reply_to(message, "⏳ This TRX ID is already pending admin confirmation.")
        bot.send_message(message.chat.id, "⬅️ Back to menu:", reply_markup=main_menu_markup())
        return

    pending_payments[trx] = uid
    data["pending_payments"] = pending_payments

    if trx in unmatched_payments:
        amt = unmatched_payments.pop(trx)
        balances[uid] = round(balances.get(uid, 0.0) + amt, 2)
        data["balances"], data["unmatched_payments"] = balances, unmatched_payments
        processed_payments.add(trx)
        save_data(data)
        bot.reply_to(message, f"আপনার ব্যালেন্স সফলভাবে যুক্ত হয়েছে! 🎉\n \t└{amt} TK\n\t└ধন্যবাদ! 💖")
        bot.send_message(ADMIN_ID, f"✅ Auto-confirmed TRX `{trx.upper()}` for user `{uid}`. Amount: {amt} TK", parse_mode="Markdown")
    else:
        save_data(data)
        bot.reply_to(message, "✅ TRX ID received. Thank You ❤️‍🩹")
        bot.send_message(ADMIN_ID, f"💳 *Payment Request*\nTRX ID: `{trx.upper()}`\nUser ID: `{uid}`\n\nForward the bKash/Nagad SMS here to confirm.", parse_mode="Markdown")
    
    bot.send_message(message.chat.id, "⬅️ Back to menu:", reply_markup=main_menu_markup())

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text and 
                                     (("trxid" in m.text.lower() or "txnid" in m.text.lower() or "trnx id" in m.text.lower()) and 
                                      "tk" in m.text.lower() and 
                                      ("received" in m.text.lower() or "prepaid" in m.text.lower() or "cash in" in m.text.lower())))
def admin_bkash_nagad_parser(m):
    txt = (m.text or "").strip()
    trx = parse_trx_id(txt)
    amt = parse_amount(txt)

    if not trx or amt is None:
        bot.reply_to(m, "❌ Could not extract TRX ID or amount from the SMS.")
        return

    if trx in processed_payments:
        bot.reply_to(m, f"⚠️ TRX ID `{trx.upper()}` already confirmed before. Ignoring duplicate message.", parse_mode="Markdown")
        return
    
    if trx in pending_payments:
        uid = pending_payments.pop(trx)
        balances[uid] = round(balances.get(uid, 0.0) + amt, 2)
        data["balances"], data["pending_payments"] = balances, pending_payments
        processed_payments.add(trx)
        save_data(data)
        bot.send_message(int(uid), f"আপনার ব্যালেন্স সফলভাবে যুক্ত হয়েছে! 🎉:\n\t└ {amt} TK\n\t└Transaction ID: `{trx.upper()}`\n\t└ধন্যবাদ! 💖", parse_mode="Markdown")
        bot.reply_to(m, f"✅ Auto-confirmed.\nUser: `{uid}`\nAmount: {amt} TK\nTRX: `{trx.upper()}`", parse_mode="Markdown")
    elif trx not in unmatched_payments:
        unmatched_payments[trx] = amt
        data["unmatched_payments"] = unmatched_payments
        save_data(data)
        bot.reply_to(m, f"⚠ SMS saved. No pending user request found for TRX ID: `{trx.upper()}`. Will auto-confirm when user provides TRX ID.\nAmount: {amt} TK", parse_mode="Markdown")
    else:
        bot.reply_to(m, f"ℹ️ This TRX ID `{trx.upper()}` is already in unmatched payments.", parse_mode="Markdown")

# ========== ADMIN: BROADCAST ==========
@bot.message_handler(commands=['broadcast'])
def ask_broadcast_message(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    msg = bot.send_message(message.chat.id, "📢 Send the message you want to broadcast to all users:", reply_markup=ForceReply())
    bot.register_next_step_handler(msg, broadcast_to_all)

@bot.message_handler(commands=['data'])
def send_data_snapshot(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    send_bot_data_snapshot(message.chat.id, "Manual /data request")

def broadcast_to_all(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    broadcast_text = message.text.strip()
    if not broadcast_text:
        bot.send_message(message.chat.id, "❌ Message is empty. Broadcast cancelled.")
        return

    sent_count = 0
    failed_count = 0
    for uid in balances.keys():  # balances dict contains all user IDs
        try:
            bot.send_message(int(uid), f"আসসালামু আলাইকুম ❤️‍🩹\n\n{broadcast_text}")
            sent_count += 1
        except Exception as e:
            failed_count += 1

    bot.send_message(message.chat.id, f"✅ Broadcast complete.\nSent: {sent_count}\nFailed: {failed_count}")

# ========== ADMIN: REMIND PENDING FREE ORDERS ==========
@bot.message_handler(commands=['remind_freeorders'])
def remind_pending_free_orders(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    # Step 1: Group pending orders by user
    user_orders_map = {}
    for oid, od in free_orders.items():
        if not od.get("delivered", False):
            uid = int(od["user_id"])
            vpn_name = od["vpn_name"]
            user_orders_map.setdefault(uid, []).append(vpn_name)
    
    # Step 2: Send one message per user
    pending_count = 0
    for uid, vpn_list in user_orders_map.items():
        # Count each VPN type
        vpn_count_map = {}
        for vpn in vpn_list:
            vpn_count_map[vpn] = vpn_count_map.get(vpn, 0) + 1
        
        # Build message text
        if len(vpn_count_map) == 1 and list(vpn_count_map.values())[0] == 1:
            # Case: Only one VPN order
            vpn_name = list(vpn_count_map.keys())[0]
            msg_text = (
                f"📩 আপনার *{vpn_name}* এর ফ্রি অর্ডার এখনো ডেলিভারি হয়নি।\n\n"
                "দয়া করে অপেক্ষা করুন, খুব শীঘ্রই আপনাকে দেওয়া হবে 💖"
            )
        else:
            # Case: Multiple orders
            vpn_text = "\n".join([f"🔹 {name}/{count}" if count > 1 else f"🔹 {name}" 
                                  for name, count in vpn_count_map.items()])
            msg_text = (
                f"📩 আপনার নিচের VPN অর্ডারগুলো এখনো ডেলিভারি হয়নি:\n\n{vpn_text}\n\n"
                "দয়া করে অপেক্ষা করুন, খুব শীঘ্রই আপনাকে দেওয়া হবে 💖"
            )
        
        try:
            bot.send_message(uid, msg_text, parse_mode="Markdown")
            pending_count += 1
        except Exception as e:
            print(f"Could not send reminder to {uid}: {e}")
    
    bot.send_message(message.chat.id, f"✅ Reminder sent to {pending_count} users with pending orders.")

# ========== ADMIN: FREE ORDERS PANEL ==========
@bot.message_handler(func=lambda m: norm_text(m.text) == "📩 free orders" and str(m.from_user.id) == str(ADMIN_ID))
def show_free_orders(message):
    # Build list of pending free orders
    pending_exist = any(not od.get("delivered", False) for od in free_orders.values())
    if not free_orders or not pending_exist:
        bot.send_message(message.chat.id, "No pending free orders.", reply_markup=admin_menu_markup())
        return
    
    text = "📩 Pending Free Orders:\n\n"
    markup = InlineKeyboardMarkup()
    for oid, od in free_orders.items():
        if not od.get("delivered", False):
            text += (
                f"*Order ID:* `{oid}`\n"
                f"*User:* `{od['user_id']}`\n"
                f"*VPN:* *{od['vpn_name']}*\n"
                f"*Price:* {od['price']}৳\n"
                f"*Time:* {od['timestamp']}\n\n"
            )
            markup.add(InlineKeyboardButton(f"Deliver {oid}", callback_data=f"deliver|{oid}"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("deliver|"))
def deliver_free_order(c):
    log(f"callback deliver_free_order data={c.data} from={c.from_user.id}")
    if str(c.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(c.id, "Unauthorized.", show_alert=True)
        return

    oid = c.data.split("|")[1]
    order = free_orders.get(oid)
    if not order or order.get("delivered", False):
        bot.answer_callback_query(c.id, "Order not found or already delivered.", show_alert=True)
        return
    
    vpn_name = order["vpn_name"]
    # Ask admin to send details in expected format based on product_fields
    prompt_fields = product_fields.get(vpn_name, ["Gmail", "Password"]) # default fields
    prompt_text = f"You are delivering to user `{order['user_id']}` for *{vpn_name}*.\n\nSend details in the format:\n\n"
    format_example = ""
    for field in prompt_fields:
        format_example += f"*{field}*:your_{field.lower().replace(' ', '_')}_value\n"
    prompt_text += f"`{format_example.strip()}`\n\nAfter you send, it will be delivered to the user."
    msg = bot.send_message(c.message.chat.id, prompt_text, parse_mode="Markdown", reply_markup=ForceReply())
    # Register next step with oid and fields to validate
    bot.register_next_step_handler(msg, process_free_order_delivery, oid, prompt_fields)
    bot.answer_callback_query(c.id, "Send VPN details now.")

def process_free_order_delivery(message, oid, prompt_fields):
    # Validate admin
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    order = free_orders.get(oid)
    if not order or order.get("delivered", False):
        bot.reply_to(message, "❌ Order not found or already delivered.")
        return

    uid = int(order["user_id"])
    vpn_name = order["vpn_name"]

    # Parse details from message in key:value lines
    txt = (message.text or "").strip()
    details_dict = {}
    for line in txt.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            standardized_key = k.strip().lower().replace(" ", "_")
            details_dict[standardized_key] = v.strip()

    # Validate required fields
    missing = []
    for field in prompt_fields:
        skey = field.lower().replace(" ", "_")
        if skey not in details_dict or not details_dict[skey]:
            missing.append(field)

    if missing:
        bot.reply_to(message, f"❌ Missing fields: {', '.join(missing)}. Please resend correctly.")
        return

    # Build user-facing message using product_fields order
    delivered_msg = f"✅ Your requested VPN is delivered!\n\n*{vpn_name}*\n\n"
    for field in prompt_fields:
        item_key = field.replace(" ", "_").lower()
        delivered_msg += f"*{field}* ➡ `{details_dict.get(item_key, 'N/A')}`\n\n"

    # Send to user
    try:
        bot.send_message(uid, delivered_msg, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"⚠ Could not deliver to user `{uid}`. Please try again.")
        return

    # Mark delivered and save details
    free_orders[oid]["delivered"] = True
    free_orders[oid]["delivery_details"] = details_dict
    data["free_orders"] = free_orders
    save_data(data)

    bot.reply_to(message, f"✅ Delivered to user `{uid}`.\nOrder ID: `{oid}`", parse_mode="Markdown")

# ========== ADMIN FEATURES ==========
@bot.message_handler(func=lambda m: norm_text(m.text) == "⬅️ main menu (user)" and str(m.from_user.id) == str(ADMIN_ID))
def back_to_main_menu_admin(message):
    bot.send_message(message.chat.id, "Returning to main user menu.", reply_markup=main_menu_markup())

@bot.message_handler(func=lambda m: norm_text(m.text) == "📊 total sales" and str(m.from_user.id) == str(ADMIN_ID))
def show_total_sales(message):
    today_counts = {}
    today_date = time.strftime("%Y-%m-%d")

    for user_orders in orders.values():
        for order in user_orders:
            vpn_name = order.get("vpn_name", "Unknown VPN")

            timestamp = order.get("timestamp", "")
            order_date = timestamp.split(" ")[0] if " " in timestamp else timestamp
            if order_date == today_date:
                today_counts[vpn_name] = today_counts.get(vpn_name, 0) + 1

    def format_counts(title, counts_dict):
        if not counts_dict:
            return f"{title}: 0"
        lines = [title]
        for name, count in sorted(counts_dict.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"🔹 {name}: {count}")
        return "\n".join(lines)

    today_summary = format_counts(f"📆 আজ ({today_date}) Sell", today_counts)
    summary_text = "📈 Sales Summary\n\n" + today_summary

    bot.send_message(message.chat.id, summary_text, parse_mode="Markdown", reply_markup=admin_menu_markup())

@bot.message_handler(func=lambda m: norm_text(m.text) == "📈 current stock" and str(m.from_user.id) == str(ADMIN_ID))
def show_current_stock(message):
    stock_report = "📦 Current VPN Stock:\n\n"
    has_stock = False
    for vpn_name in sorted(vpn_prices.keys()): # Sort for consistent display
        stock_list = products.get(vpn_name, [])
        stock_report += f"*{vpn_name}:* {len(stock_list)} available\n"
        if len(stock_list) > 0:
            has_stock = True
    
    if not has_stock:
        stock_report += "No VPNs currently in stock."
    
    bot.send_message(message.chat.id, stock_report, parse_mode="Markdown", reply_markup=admin_menu_markup())

@bot.message_handler(commands=['buyer'])
def send_buyer_stats(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    ensure_user(str(message.from_user.id))
    report = build_buyer_stats_report()
    bot.send_message(message.chat.id, report, parse_mode="Markdown")

@bot.message_handler(commands=['removebalance', 'removrblance'])
def remove_balance_command(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip():
        reset_user_balance(message.chat.id, parts[1].strip())
        return

    prompt = bot.send_message(message.chat.id, "কোন ইউজারের ব্যালেন্স 0 করতে চান? User ID পাঠান:", reply_markup=ForceReply())
    bot.register_next_step_handler(prompt, remove_balance_followup)

def remove_balance_followup(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    target_uid = (message.text or "").strip()
    if not target_uid:
        bot.send_message(message.chat.id, "❌ ইউজার আইডি খালি থাকতে পারে না। অপারেশন বাতিল।")
        return

    reset_user_balance(message.chat.id, target_uid)

@bot.message_handler(func=lambda m: norm_text(m.text) == "➕ add vpn account" and str(m.from_user.id) == str(ADMIN_ID))
def ask_add_vpn_account(message):
    markup = InlineKeyboardMarkup()
    for name in sorted(vpn_prices.keys()): # Sort for consistent display
        markup.add(InlineKeyboardButton(name, callback_data=f"admin_add_vpn|{name}"))
    msg = bot.send_message(message.chat.id, "Which VPN account do you want to add stock for?", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_add_vpn|"))
def admin_selected_vpn_to_add(c):
    log(f"callback admin_add_vpn data={c.data} from={c.from_user.id}")
    vpn_name = c.data.split("|")[1]
    
    # Adjust prompt based on product_fields
    prompt_fields = product_fields.get(vpn_name, ["Gmail", "Password"]) # Default to Gmail/Password
    
    prompt_text = f"You selected *{vpn_name}*.\n\nPlease send the VPN account details in the following format:\n\n"
    format_example = ""
    for field in prompt_fields:
        format_example += f"*{field}*:your_{field.lower().replace(' ', '_')}_value\n"

    prompt_text += (
        f"`{format_example.strip()}`\n\n"
        "👉 আপনি একই ফরম্যাট বারবার লিখে একসাথে একাধিক একাউন্ট যোগ করতে পারবেন।\n"
        "প্রতিটি একাউন্টের তথ্য আলাদা লাইনে বা ফাঁকা লাইন দিয়ে লিখুন।"
    )

    msg = bot.send_message(c.message.chat.id, prompt_text, parse_mode="Markdown", reply_markup=ForceReply())
    bot.register_next_step_handler(msg, process_add_vpn_account, vpn_name)
    bot.answer_callback_query(c.id, f"Ready to add {vpn_name} account.")

def process_add_vpn_account(message, vpn_name):
    txt = (message.text or "").strip()
    if not txt:
        bot.reply_to(message, "❌ No data received. Please send the account details in the requested format.")
        bot.send_message(message.chat.id, "⬅️ Back to Admin Menu:", reply_markup=admin_menu_markup())
        return

    required_fields_for_vpn = product_fields.get(vpn_name, ["Gmail", "Password"]) # Default to Gmail/Password
    required_keys = [field.lower().replace(" ", "_") for field in required_fields_for_vpn]

    def all_required_present(record):
        return all(record.get(key) for key in required_keys)

    accounts_to_add = []
    current_record = {}

    for raw_line in message.text.splitlines():
        line = (raw_line or "").strip()

        # Treat blank line as separator between accounts
        if not line:
            if current_record:
                if all_required_present(current_record):
                    accounts_to_add.append(current_record.copy())
                    current_record = {}
                else:
                    missing = [required_fields_for_vpn[idx] for idx, key in enumerate(required_keys) if not current_record.get(key)]
                    bot.reply_to(message, f"❌ Missing fields: {', '.join(missing)}. Please resend the data correctly.")
                    bot.send_message(message.chat.id, "⬅️ Back to Admin Menu:", reply_markup=admin_menu_markup())
                    return
            continue

        if ':' not in line:
            continue

        key, value = line.split(':', 1)
        standardized_key = key.strip().lower().replace(" ", "_")
        standardized_value = value.strip()

        # If the admin repeats a required key before finishing current record, assume a new record
        if standardized_key in current_record and standardized_key in required_keys:
            if all_required_present(current_record):
                accounts_to_add.append(current_record.copy())
                current_record = {}
            else:
                missing = [required_fields_for_vpn[idx] for idx, key in enumerate(required_keys) if not current_record.get(key)]
                bot.reply_to(message, f"❌ Missing fields: {', '.join(missing)}. Please resend the data correctly.")
                bot.send_message(message.chat.id, "⬅️ Back to Admin Menu:", reply_markup=admin_menu_markup())
                return

        current_record[standardized_key] = standardized_value

        if all_required_present(current_record):
            accounts_to_add.append(current_record.copy())
            current_record = {}

    # Handle any remaining record at the end
    if current_record:
        if all_required_present(current_record):
            accounts_to_add.append(current_record.copy())
        else:
            missing = [required_fields_for_vpn[idx] for idx, key in enumerate(required_keys) if not current_record.get(key)]
            bot.reply_to(message, f"❌ Missing fields: {', '.join(missing)}. Please resend the data correctly.")
            bot.send_message(message.chat.id, "⬅️ Back to Admin Menu:", reply_markup=admin_menu_markup())
            return

    if not accounts_to_add:
        bot.reply_to(message, "❌ No valid account found. Please follow the provided format and try again.")
        bot.send_message(message.chat.id, "⬅️ Back to Admin Menu:", reply_markup=admin_menu_markup())
        return

    stock_list = products.setdefault(vpn_name, [])
    before_count = len(stock_list)

    for account in accounts_to_add:
        stock_list.append(account)

    data["products"] = products
    save_data(data)

    added_count = len(stock_list) - before_count
    bot.reply_to(message, f"✅ Successfully added {added_count} account(s) for *{vpn_name}* to stock. Current stock: {len(stock_list)}", parse_mode="Markdown")
    bot.send_message(message.chat.id, "⬅️ Back to Admin Menu:", reply_markup=admin_menu_markup())

# ========== ERROR HANDLER ==========

start_data_report_scheduler()

print("Bot polling...")
bot.infinity_polling(
    timeout=60,
    long_polling_timeout=20,
    allowed_updates=["message", "callback_query"]
)
