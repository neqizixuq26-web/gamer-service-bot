# -*- coding: utf-8 -*-
"""
Gamer Service Buy & Sell Telegram Bot
Runs as a Render "Web Service" using webhook mode (python-telegram-bot v21).
"""
import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# ---------------- constants: menu button labels ----------------
BTN_BUY = "🎮 Gamer Service Buy"
BTN_SELL = "📤 Gamer Service Sell"
BTN_BALANCE = "💰 Balance"
BTN_DEPOSIT = "💳 Deposit"
BTN_WITHDRAW = "💸 Withdraw"
BTN_ORDERS = "📦 My Orders"
BTN_DETAILS = "📋 Details"
BTN_REFERRAL = "👥 Referral"
BTN_SUPPORT = "👨‍💻 Support"
BTN_ADMIN = "⚙️ Admin Panel"
BTN_CANCEL = "❌ Cancel"


def is_admin(user_id):
    return user_id == ADMIN_ID


def money(x):
    return f"{x:,.2f}"


def main_menu_keyboard(user_id):
    rows = [
        [KeyboardButton(BTN_BUY), KeyboardButton(BTN_SELL)],
        [KeyboardButton(BTN_BALANCE), KeyboardButton(BTN_DEPOSIT)],
        [KeyboardButton(BTN_WITHDRAW), KeyboardButton(BTN_ORDERS)],
        [KeyboardButton(BTN_DETAILS), KeyboardButton(BTN_REFERRAL)],
        [KeyboardButton(BTN_SUPPORT)],
    ]
    if is_admin(user_id):
        rows.append([KeyboardButton(BTN_ADMIN)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton(BTN_CANCEL)]], resize_keyboard=True)


async def check_membership(bot, user_id):
    channel = db.get_setting("channel_username")
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except (BadRequest, Forbidden) as e:
        logger.warning("membership check failed: %s", e)
        # If the bot cannot check (not admin in channel, wrong username, etc.)
        # fail safe by blocking access and logging - admin should fix channel settings.
        return False


def join_keyboard():
    link = db.get_setting("channel_link")
    kb = [
        [InlineKeyboardButton("📢 Join Channel", url=link)],
        [InlineKeyboardButton("🔄 Verify / Joined", callback_data="verify_join")],
    ]
    return InlineKeyboardMarkup(kb)


WELCOME_TEXT = (
    "⚡ *WELCOME TO GAMER SERVICE* ⚡\n\n"
    "🤖 Bot ব্যবহার করতে হলে প্রথমে আমাদের Telegram Channel-এ Join করুন।\n\n"
    "✅ Channel-এ Join করার পর নিচের *Verify* বাটনে চাপুন।"
)


# ==================================================================
# /start
# ==================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None
    if context.args:
        arg = context.args[0]
        if arg.isdigit() and int(arg) != user.id:
            referred_by = int(arg)
    db.get_or_create_user(user.id, user.username or user.first_name, referred_by)
    context.user_data.pop("flow", None)

    ok = await check_membership(context.bot, user.id)
    if not ok:
        await update.message.reply_text(
            WELCOME_TEXT, parse_mode="Markdown", reply_markup=join_keyboard()
        )
        return
    await update.message.reply_text(
        f"স্বাগতম, {user.first_name}! 🎮\n\nনিচের মেনু থেকে পছন্দ বেছে নিন।",
        reply_markup=main_menu_keyboard(user.id),
    )


async def verify_join_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    ok = await check_membership(context.bot, user.id)
    if ok:
        await query.message.edit_text("✅ ধন্যবাদ! আপনি Channel-এ Join করেছেন।")
        await context.bot.send_message(
            chat_id=user.id,
            text="নিচের মেনু থেকে পছন্দ বেছে নিন।",
            reply_markup=main_menu_keyboard(user.id),
        )
    else:
        await query.answer("❌ আপনি এখনও Channel-এ Join করেননি!", show_alert=True)


# ==================================================================
# generic cancel
# ==================================================================
async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("flow", None)
    await update.message.reply_text(
        "❌ বাতিল করা হয়েছে।", reply_markup=main_menu_keyboard(update.effective_user.id)
    )


# ==================================================================
# BUY SERVICE (user)
# ==================================================================
async def show_buy_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    services = db.get_buy_services(active_only=True)
    if not services:
        await update.message.reply_text("⚠️ এই মুহূর্তে কোনো Buy Service উপলব্ধ নেই।")
        return
    kb = [
        [InlineKeyboardButton(f"🎮 {s['name']} - ৳{s['price']}", callback_data=f"buy:view:{s['id']}")]
        for s in services
    ]
    await update.message.reply_text(
        "🛒 *Gamer Service Buy*\n\nনিচে থেকে একটি Service নির্বাচন করুন:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def buy_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split(":")[2])
    s = db.get_buy_service(sid)
    if not s or not s["status"]:
        await query.answer("Service পাওয়া যায়নি বা বন্ধ আছে।", show_alert=True)
        return
    text = (
        f"🎮 *{s['name']}*\n\n"
        f"{s['description']}\n\n"
        f"💰 Price: ৳{s['price']} / unit\n"
        f"🔢 Min Qty: {s['min_qty']}  |  Max Qty: {s['max_qty']}\n\n"
        f"ℹ️ {s['instruction']}"
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Buy Now", callback_data=f"buy:start:{sid}")]]
    )
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def buy_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split(":")[2])
    s = db.get_buy_service(sid)
    if not s or not s["status"]:
        await query.answer("Service পাওয়া যায়নি বা বন্ধ আছে।", show_alert=True)
        return
    context.user_data["flow"] = {"type": "buy_qty", "service_id": sid}
    await query.message.reply_text(
        f"🔢 Quantity লিখুন (Min: {s['min_qty']}, Max: {s['max_qty']}):",
        reply_markup=cancel_keyboard(),
    )


async def handle_buy_qty(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    s = db.get_buy_service(flow["service_id"])
    txt = update.message.text.strip()
    if not txt.isdigit():
        await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন।")
        return
    qty = int(txt)
    if qty < s["min_qty"] or qty > s["max_qty"]:
        await update.message.reply_text(
            f"⚠️ Quantity {s['min_qty']} থেকে {s['max_qty']}-এর মধ্যে হতে হবে।"
        )
        return
    flow["qty"] = qty
    flow["amount"] = round(qty * s["price"], 2)
    flow["type"] = "buy_details"
    context.user_data["flow"] = flow
    await update.message.reply_text(
        f"📋 প্রয়োজনীয় তথ্য লিখুন:\n\n{s['instruction']}", reply_markup=cancel_keyboard()
    )


async def handle_buy_details(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    details = update.message.text.strip()
    s = db.get_buy_service(flow["service_id"])
    user = db.get_user(update.effective_user.id)
    amount = flow["amount"]
    if user["balance"] < amount:
        context.user_data.pop("flow", None)
        await update.message.reply_text(
            f"❌ আপনার Balance যথেষ্ট নয়।\nProduct Price: ৳{money(amount)}\n"
            f"আপনার Balance: ৳{money(user['balance'])}\n\nদয়া করে Deposit করুন।",
            reply_markup=main_menu_keyboard(update.effective_user.id),
        )
        return
    db.update_balance(user["user_id"], -amount, "total_spent")
    order_id = db.create_order(
        user["user_id"], s["id"], s["name"], flow["qty"], amount, details
    )
    context.user_data.pop("flow", None)
    await update.message.reply_text(
        f"✅ আপনার Order Submit হয়েছে!\n\n🆔 Order ID: #{order_id}\n"
        f"🎮 Service: {s['name']}\n💰 Amount: ৳{money(amount)}\n⏳ Status: Pending",
        reply_markup=main_menu_keyboard(update.effective_user.id),
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚙️ Processing", callback_data=f"adm:ord:Processing:{order_id}"),
                InlineKeyboardButton("✅ Completed", callback_data=f"adm:ord:Completed:{order_id}"),
            ],
            [InlineKeyboardButton("❌ Cancel Order", callback_data=f"adm:ord:Cancelled:{order_id}")],
        ]
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🛒 *NEW BUY ORDER*\n\n"
            f"👤 User: @{user['username']} (ID: {user['user_id']})\n"
            f"🆔 Order ID: #{order_id}\n"
            f"🎮 Service: {s['name']}\n"
            f"🔢 Qty: {flow['qty']}\n"
            f"💰 Amount: ৳{money(amount)}\n"
            f"📋 Details:\n{details}\n\n"
            f"⏳ Status: Pending"
        ),
        parse_mode="Markdown",
        reply_markup=kb,
    )


# ==================================================================
# SELL SERVICE (user)
# ==================================================================
async def show_sell_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    services = db.get_sell_services(active_only=True)
    if not services:
        await update.message.reply_text("⚠️ এই মুহূর্তে কোনো Sell Service উপলব্ধ নেই।")
        return
    kb = [
        [InlineKeyboardButton(f"📤 {s['name']} - ৳{s['price']}", callback_data=f"sell:view:{s['id']}")]
        for s in services
    ]
    await update.message.reply_text(
        "📤 *Gamer Service Sell*\n\nনিচে থেকে একটি Service নির্বাচন করুন:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def sell_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split(":")[2])
    s = db.get_sell_service(sid)
    if not s or not s["status"]:
        await query.answer("Service পাওয়া যায়নি বা বন্ধ আছে।", show_alert=True)
        return
    text = (
        f"📤 *{s['name']}*\n\n"
        f"{s['description']}\n\n"
        f"💰 Rate: ৳{s['price']} / unit\n"
        f"🔢 Min Qty: {s['min_qty']}\n\n"
        f"ℹ️ {s['instruction']}"
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Sell Now", callback_data=f"sell:start:{sid}")]]
    )
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def sell_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split(":")[2])
    s = db.get_sell_service(sid)
    if not s or not s["status"]:
        await query.answer("Service পাওয়া যায়নি বা বন্ধ আছে।", show_alert=True)
        return
    context.user_data["flow"] = {"type": "sell_qty", "service_id": sid}
    await query.message.reply_text(
        f"🔢 Quantity লিখুন (Min: {s['min_qty']}):", reply_markup=cancel_keyboard()
    )


async def handle_sell_qty(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    s = db.get_sell_service(flow["service_id"])
    txt = update.message.text.strip()
    if not txt.isdigit():
        await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন।")
        return
    qty = int(txt)
    if qty < s["min_qty"]:
        await update.message.reply_text(f"⚠️ Quantity কমপক্ষে {s['min_qty']} হতে হবে।")
        return
    flow["qty"] = qty
    flow["type"] = "sell_details"
    context.user_data["flow"] = flow
    await update.message.reply_text(
        f"📋 প্রয়োজনীয় তথ্য লিখুন:\n\n{s['instruction']}", reply_markup=cancel_keyboard()
    )


async def handle_sell_details(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    details = update.message.text.strip()
    s = db.get_sell_service(flow["service_id"])
    user = update.effective_user
    req_id = db.create_sell_request(user.id, s["id"], s["name"], flow["qty"], details)
    context.user_data.pop("flow", None)
    await update.message.reply_text(
        f"✅ আপনার Sell Request Submit হয়েছে!\n\n🆔 Request ID: #{req_id}\n"
        f"🎮 Service: {s['name']}\n⏳ Status: Pending",
        reply_markup=main_menu_keyboard(user.id),
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"adm:sr:Approved:{req_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"adm:sr:Rejected:{req_id}"),
            ]
        ]
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📤 *NEW SELL REQUEST*\n\n"
            f"👤 User: @{user.username} (ID: {user.id})\n"
            f"🆔 Request ID: #{req_id}\n"
            f"🎮 Service: {s['name']}\n"
            f"🔢 Qty: {flow['qty']}\n"
            f"📋 Details:\n{details}\n\n"
            f"⏳ Status: Pending"
        ),
        parse_mode="Markdown",
        reply_markup=kb,
    )


# ==================================================================
# BALANCE / DEPOSIT / WITHDRAW / MY ORDERS / DETAILS / REFERRAL / SUPPORT
# ==================================================================
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = db.get_user(update.effective_user.id)
    await update.message.reply_text(
        f"💰 *Current Balance:* ৳{money(u['balance'])}\n"
        f"📥 Total Deposit: ৳{money(u['total_deposit'])}\n"
        f"📤 Total Spent: ৳{money(u['total_spent'])}\n"
        f"💸 Total Withdraw: ৳{money(u['total_withdraw'])}\n"
        f"👥 Referral Earnings: ৳{money(u['referral_earnings'])}",
        parse_mode="Markdown",
    )


async def start_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    min_dep = db.get_setting("min_deposit")
    context.user_data["flow"] = {"type": "deposit_amount"}
    await update.message.reply_text(
        f"💳 *Deposit*\n\nMinimum Deposit: ৳{min_dep}\n\nAmount লিখুন (৳):",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


async def handle_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    txt = update.message.text.strip()
    try:
        amount = float(txt)
    except ValueError:
        await update.message.reply_text("⚠️ সঠিক Amount লিখুন।")
        return
    min_dep = float(db.get_setting("min_deposit"))
    if amount < min_dep:
        await update.message.reply_text(f"⚠️ Minimum Deposit ৳{min_dep}। আবার লিখুন।")
        return
    flow["amount"] = amount
    flow["type"] = "deposit_txn"
    context.user_data["flow"] = flow
    await update.message.reply_text(
        "💵 টাকা পাঠানোর পর Transaction ID / Reference লিখুন:", reply_markup=cancel_keyboard()
    )


async def handle_deposit_txn(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    txn = update.message.text.strip()
    user = update.effective_user
    dep_id = db.create_deposit(user.id, "Manual", flow["amount"], txn)
    context.user_data.pop("flow", None)
    await update.message.reply_text(
        f"✅ আপনার Deposit Request Submit হয়েছে!\n\n🆔 Request ID: #{dep_id}\n"
        f"💰 Amount: ৳{money(flow['amount'])}\n⏳ Status: Pending (Admin অনুমোদনের অপেক্ষায়)",
        reply_markup=main_menu_keyboard(user.id),
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"adm:dep:approve:{dep_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"adm:dep:reject:{dep_id}"),
            ]
        ]
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"💳 *NEW DEPOSIT REQUEST*\n\n"
            f"👤 User: @{user.username} (ID: {user.id})\n"
            f"🆔 Request ID: #{dep_id}\n"
            f"💰 Amount: ৳{money(flow['amount'])}\n"
            f"🧾 Txn ID: {txn}"
        ),
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def start_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["flow"] = {"type": "wd_method"}
    await update.message.reply_text(
        "💸 *Withdraw*\n\nPayment Method লিখুন (যেমন: bKash/Nagad):",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


async def handle_wd_method(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    flow["method"] = update.message.text.strip()
    flow["type"] = "wd_account"
    context.user_data["flow"] = flow
    await update.message.reply_text("🔢 Account Number লিখুন:", reply_markup=cancel_keyboard())


async def handle_wd_account(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    flow["account"] = update.message.text.strip()
    flow["type"] = "wd_amount"
    context.user_data["flow"] = flow
    u = db.get_user(update.effective_user.id)
    await update.message.reply_text(
        f"💰 Amount লিখুন (আপনার Balance: ৳{money(u['balance'])}):",
        reply_markup=cancel_keyboard(),
    )


async def handle_wd_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    txt = update.message.text.strip()
    try:
        amount = float(txt)
    except ValueError:
        await update.message.reply_text("⚠️ সঠিক Amount লিখুন।")
        return
    user = update.effective_user
    u = db.get_user(user.id)
    if amount <= 0 or amount > u["balance"]:
        await update.message.reply_text("⚠️ Amount সঠিক নয় বা আপনার Balance-এর চেয়ে বেশি।")
        return
    # reserve the amount immediately so it can't be double-spent while pending
    db.update_balance(user.id, -amount)
    wid = db.create_withdrawal(user.id, flow["method"], flow["account"], amount)
    context.user_data.pop("flow", None)
    await update.message.reply_text(
        f"✅ আপনার Withdraw Request Submit হয়েছে!\n\n🆔 Request ID: #{wid}\n"
        f"💰 Amount: ৳{money(amount)}\n⏳ Status: Pending",
        reply_markup=main_menu_keyboard(user.id),
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"adm:wd:approve:{wid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"adm:wd:reject:{wid}"),
            ]
        ]
    )
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"💸 *NEW WITHDRAW REQUEST*\n\n"
            f"👤 User: @{user.username} (ID: {user.id})\n"
            f"🆔 Request ID: #{wid}\n"
            f"💳 Method: {flow['method']}\n"
            f"🔢 Account: {flow['account']}\n"
            f"💰 Amount: ৳{money(amount)}"
        ),
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    orders = db.get_user_orders(uid)
    sells = db.get_user_sell_requests(uid)
    if not orders and not sells:
        await update.message.reply_text("📦 আপনার কোনো Order/Request নেই।")
        return
    lines = ["📦 *আপনার Orders / Requests:*\n"]
    for o in orders:
        lines.append(
            f"🆔 #{o['id']} (Buy) | 🎮 {o['service_name']} | 💰 ৳{money(o['amount'])} | 📌 {o['status']}"
        )
    for s in sells:
        lines.append(f"🆔 #{s['id']} (Sell) | 🎮 {s['service_name']} | 📌 {s['status']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def show_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Details*\n\n" + db.get_setting("details_text"), parse_mode="Markdown"
    )


async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = db.get_user(uid)
    cnt = db.get_referral_stats(uid)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={uid}"
    await update.message.reply_text(
        f"👥 *Referral Program*\n\n"
        f"💰 Referral Bonus: ৳{db.get_setting('referral_bonus')} / successful referral\n\n"
        f"👥 Total Referral: {cnt}\n"
        f"💰 Referral Earnings: ৳{money(u['referral_earnings'])}\n\n"
        f"🔗 আপনার Referral Link:\n{link}",
        parse_mode="Markdown",
    )


async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👨‍💻 *Support*\n\nযেকোনো সমস্যায় যোগাযোগ করুন:\n{db.get_setting('support_link')}",
        parse_mode="Markdown",
    )


# ==================================================================
# ADMIN PANEL
# ==================================================================
def admin_menu_kb():
    kb = [
        [InlineKeyboardButton("📊 Dashboard", callback_data="adm:dashboard")],
        [
            InlineKeyboardButton("🛒 Buy Services", callback_data="adm:bsvc:list"),
            InlineKeyboardButton("📤 Sell Services", callback_data="adm:ssvc:list"),
        ],
        [
            InlineKeyboardButton("📦 Buy Orders", callback_data="adm:ord:list"),
            InlineKeyboardButton("📋 Sell Requests", callback_data="adm:sr:list"),
        ],
        [
            InlineKeyboardButton("💳 Deposits", callback_data="adm:dep:list"),
            InlineKeyboardButton("💸 Withdrawals", callback_data="adm:wd:list"),
        ],
        [
            InlineKeyboardButton("📢 Channel Settings", callback_data="adm:channel"),
            InlineKeyboardButton("📝 Details Settings", callback_data="adm:details"),
        ],
        [InlineKeyboardButton("⚙️ Bot Settings", callback_data="adm:settings")],
    ]
    return InlineKeyboardMarkup(kb)


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("⚙️ *Admin Panel*", parse_mode="Markdown", reply_markup=admin_menu_kb())


async def admin_dashboard_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    s = db.get_stats()
    text = (
        "📊 *Dashboard*\n\n"
        f"👥 Users: {s['users']}\n"
        f"🛒 Buy Services: {s['buy_services']}\n"
        f"📤 Sell Services: {s['sell_services']}\n"
        f"📦 Total Orders: {s['orders']}\n"
        f"📋 Total Sell Requests: {s['sell_requests']}\n"
        f"💳 Pending Deposits: {s['pending_deposits']}\n"
        f"💸 Pending Withdrawals: {s['pending_withdrawals']}\n"
        f"💰 Total Deposited (approved): ৳{money(s['total_deposit'])}"
    )
    await query.message.reply_text(text, parse_mode="Markdown")


# ---------- Buy Service management ----------
async def admin_bsvc_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    services = db.get_buy_services()
    kb = []
    for s in services:
        mark = "🟢" if s["status"] else "🔴"
        kb.append(
            [InlineKeyboardButton(f"{mark} {s['name']}", callback_data=f"adm:bsvc:view:{s['id']}")]
        )
    kb.append([InlineKeyboardButton("➕ Add Service", callback_data="adm:bsvc:add")])
    await query.message.reply_text(
        "🛒 *Buy Services*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
    )


async def admin_bsvc_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split(":")[3])
    s = db.get_buy_service(sid)
    text = (
        f"🎮 *{s['name']}*\n{s['description']}\n\n"
        f"💰 Price: ৳{s['price']}\n🔢 Min/Max: {s['min_qty']}/{s['max_qty']}\n"
        f"ℹ️ {s['instruction']}\n📌 Status: {'ON' if s['status'] else 'OFF'}"
    )
    kb = [
        [
            InlineKeyboardButton("✏️ Edit Name", callback_data=f"adm:bsvc:edit:{sid}:name"),
            InlineKeyboardButton("✏️ Edit Desc", callback_data=f"adm:bsvc:edit:{sid}:description"),
        ],
        [
            InlineKeyboardButton("✏️ Edit Price", callback_data=f"adm:bsvc:edit:{sid}:price"),
            InlineKeyboardButton("✏️ Edit Instruction", callback_data=f"adm:bsvc:edit:{sid}:instruction"),
        ],
        [
            InlineKeyboardButton("✏️ Edit Min", callback_data=f"adm:bsvc:edit:{sid}:min_qty"),
            InlineKeyboardButton("✏️ Edit Max", callback_data=f"adm:bsvc:edit:{sid}:max_qty"),
        ],
        [
            InlineKeyboardButton("🔄 Toggle ON/OFF", callback_data=f"adm:bsvc:toggle:{sid}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"adm:bsvc:delete:{sid}"),
        ],
    ]
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def admin_bsvc_toggle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sid = int(query.data.split(":")[3])
    db.toggle_buy_service(sid)
    await query.answer("✅ Status পরিবর্তন হয়েছে")


async def admin_bsvc_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sid = int(query.data.split(":")[3])
    db.delete_buy_service(sid)
    await query.answer("🗑️ Delete করা হয়েছে")
    await query.message.reply_text("🗑️ Service Delete করা হয়েছে।")


async def admin_bsvc_edit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, _, sid, field = query.data.split(":")
    context.user_data["flow"] = {"type": "adm_bsvc_edit", "id": int(sid), "field": field}
    await query.message.reply_text(f"✏️ নতুন মান লিখুন ({field}):", reply_markup=cancel_keyboard())


async def admin_bsvc_add_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["flow"] = {"type": "adm_bsvc_add_name", "data": {}}
    await query.message.reply_text("➕ *Add Buy Service*\n\nService Name লিখুন:", parse_mode="Markdown", reply_markup=cancel_keyboard())


# ---------- Sell Service management ----------
async def admin_ssvc_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    services = db.get_sell_services()
    kb = []
    for s in services:
        mark = "🟢" if s["status"] else "🔴"
        kb.append(
            [InlineKeyboardButton(f"{mark} {s['name']}", callback_data=f"adm:ssvc:view:{s['id']}")]
        )
    kb.append([InlineKeyboardButton("➕ Add Service", callback_data="adm:ssvc:add")])
    await query.message.reply_text(
        "📤 *Sell Services*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
    )


async def admin_ssvc_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split(":")[3])
    s = db.get_sell_service(sid)
    text = (
        f"📤 *{s['name']}*\n{s['description']}\n\n"
        f"💰 Rate: ৳{s['price']}\n🔢 Min Qty: {s['min_qty']}\n"
        f"ℹ️ {s['instruction']}\n📌 Status: {'ON' if s['status'] else 'OFF'}"
    )
    kb = [
        [
            InlineKeyboardButton("✏️ Edit Name", callback_data=f"adm:ssvc:edit:{sid}:name"),
            InlineKeyboardButton("✏️ Edit Desc", callback_data=f"adm:ssvc:edit:{sid}:description"),
        ],
        [
            InlineKeyboardButton("✏️ Edit Rate", callback_data=f"adm:ssvc:edit:{sid}:price"),
            InlineKeyboardButton("✏️ Edit Instruction", callback_data=f"adm:ssvc:edit:{sid}:instruction"),
        ],
        [InlineKeyboardButton("✏️ Edit Min Qty", callback_data=f"adm:ssvc:edit:{sid}:min_qty")],
        [
            InlineKeyboardButton("🔄 Toggle ON/OFF", callback_data=f"adm:ssvc:toggle:{sid}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"adm:ssvc:delete:{sid}"),
        ],
    ]
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def admin_ssvc_toggle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sid = int(query.data.split(":")[3])
    db.toggle_sell_service(sid)
    await query.answer("✅ Status পরিবর্তন হয়েছে")


async def admin_ssvc_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sid = int(query.data.split(":")[3])
    db.delete_sell_service(sid)
    await query.answer("🗑️ Delete করা হয়েছে")
    await query.message.reply_text("🗑️ Service Delete করা হয়েছে।")


async def admin_ssvc_edit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, _, sid, field = query.data.split(":")
    context.user_data["flow"] = {"type": "adm_ssvc_edit", "id": int(sid), "field": field}
    await query.message.reply_text(f"✏️ নতুন মান লিখুন ({field}):", reply_markup=cancel_keyboard())


async def admin_ssvc_add_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["flow"] = {"type": "adm_ssvc_add_name", "data": {}}
    await query.message.reply_text("➕ *Add Sell Service*\n\nService Name লিখুন:", parse_mode="Markdown", reply_markup=cancel_keyboard())


# ---------- Orders management ----------
async def admin_ord_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    orders = db.get_orders_by_status("Pending")
    if not orders:
        await query.message.reply_text("📦 কোনো Pending Order নেই।")
        return
    kb = [
        [InlineKeyboardButton(f"#{o['id']} {o['service_name']} ৳{o['amount']}", callback_data=f"adm:ord:view:{o['id']}")]
        for o in orders
    ]
    await query.message.reply_text("📦 *Pending Orders*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def admin_ord_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    oid = int(query.data.split(":")[3])
    o = db.get_order(oid)
    text = (
        f"🆔 Order #{o['id']}\n👤 User ID: {o['user_id']}\n🎮 {o['service_name']}\n"
        f"🔢 Qty: {o['qty']}\n💰 ৳{money(o['amount'])}\n📋 {o['details']}\n📌 {o['status']}"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚙️ Processing", callback_data=f"adm:ord:Processing:{oid}"),
                InlineKeyboardButton("✅ Completed", callback_data=f"adm:ord:Completed:{oid}"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"adm:ord:Cancelled:{oid}")],
        ]
    )
    await query.message.reply_text(text, reply_markup=kb)


async def admin_ord_setstatus_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")  # adm:ord:<status>:<id>
    status, oid = parts[2], int(parts[3])
    o = db.get_order(oid)
    if not o:
        await query.answer("পাওয়া যায়নি", show_alert=True)
        return
    if status == "Cancelled" and o["status"] != "Cancelled":
        # refund
        db.update_balance(o["user_id"], o["amount"])
    db.update_order_status(oid, status)
    await query.answer(f"✅ Status: {status}")
    try:
        await context.bot.send_message(
            chat_id=o["user_id"],
            text=f"📦 আপনার Order #{oid} ({o['service_name']}) এর Status: {status}",
        )
    except Exception:
        pass


# ---------- Sell Requests management ----------
async def admin_sr_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reqs = db.get_sell_requests_by_status("Pending")
    if not reqs:
        await query.message.reply_text("📋 কোনো Pending Sell Request নেই।")
        return
    kb = [
        [InlineKeyboardButton(f"#{r['id']} {r['service_name']}", callback_data=f"adm:sr:view:{r['id']}")]
        for r in reqs
    ]
    await query.message.reply_text("📋 *Pending Sell Requests*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def admin_sr_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rid = int(query.data.split(":")[3])
    r = db.get_sell_request(rid)
    text = (
        f"🆔 Request #{r['id']}\n👤 User ID: {r['user_id']}\n🎮 {r['service_name']}\n"
        f"🔢 Qty: {r['qty']}\n📋 {r['details']}\n📌 {r['status']}"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"adm:sr:Approved:{rid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"adm:sr:Rejected:{rid}"),
            ],
            [
                InlineKeyboardButton("⚙️ Processing", callback_data=f"adm:sr:Processing:{rid}"),
                InlineKeyboardButton("✔️ Completed", callback_data=f"adm:sr:Completed:{rid}"),
            ],
        ]
    )
    await query.message.reply_text(text, reply_markup=kb)


async def admin_sr_setstatus_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")  # adm:sr:<status>:<id>
    status, rid = parts[2], int(parts[3])
    r = db.get_sell_request(rid)
    if not r:
        await query.answer("পাওয়া যায়নি", show_alert=True)
        return
    db.update_sell_request_status(rid, status)
    await query.answer(f"✅ Status: {status}")
    if status == "Approved":
        context.user_data["flow"] = {"type": "adm_sr_msg", "id": rid, "user_id": r["user_id"]}
        await query.message.reply_text(
            "✅ Approve করা হয়েছে। User-কে Instruction/Payment Info পাঠাতে চাইলে এখন লিখুন "
            "(না চাইলে /skip লিখুন):",
            reply_markup=cancel_keyboard(),
        )
    else:
        try:
            await context.bot.send_message(
                chat_id=r["user_id"],
                text=f"📋 আপনার Sell Request #{rid} ({r['service_name']}) এর Status: {status}",
            )
        except Exception:
            pass


# ---------- Deposits management ----------
async def admin_dep_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    deps = db.get_pending_deposits()
    if not deps:
        await query.message.reply_text("💳 কোনো Pending Deposit নেই।")
        return
    kb = [
        [InlineKeyboardButton(f"#{d['id']} ৳{d['amount']} (UID {d['user_id']})", callback_data=f"adm:dep:view:{d['id']}")]
        for d in deps
    ]
    await query.message.reply_text("💳 *Pending Deposits*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def admin_dep_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    did = int(query.data.split(":")[3])
    d = db.get_deposit(did)
    text = (
        f"🆔 Deposit #{d['id']}\n👤 User ID: {d['user_id']}\n💰 ৳{money(d['amount'])}\n"
        f"🧾 Txn: {d['txn_id']}\n📌 {d['status']}"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"adm:dep:approve:{did}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"adm:dep:reject:{did}"),
            ]
        ]
    )
    await query.message.reply_text(text, reply_markup=kb)


async def admin_dep_action_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")  # adm:dep:approve/reject:<id>
    action, did = parts[2], int(parts[3])
    d = db.get_deposit(did)
    if not d or d["status"] != "Pending":
        await query.answer("এই Deposit আগেই Process হয়েছে।", show_alert=True)
        return
    if action == "approve":
        db.update_balance(d["user_id"], d["amount"], "total_deposit")
        db.update_deposit_status(did, "Approved")
        await query.answer("✅ Approved")
        try:
            await context.bot.send_message(
                chat_id=d["user_id"],
                text=f"✅ আপনার Deposit #{did} (৳{money(d['amount'])}) Approve হয়েছে। Balance যোগ হয়েছে।",
            )
        except Exception:
            pass
        # referral bonus on first approved deposit
        ref = db.get_unpaid_referral(d["user_id"])
        if ref:
            bonus = float(db.get_setting("referral_bonus"))
            db.update_balance(ref["referrer_id"], bonus, "referral_earnings")
            db.mark_referral_paid(ref["id"])
            try:
                await context.bot.send_message(
                    chat_id=ref["referrer_id"],
                    text=f"🎉 আপনার Referral সফল হয়েছে! ৳{bonus} Bonus যোগ হয়েছে।",
                )
            except Exception:
                pass
    else:
        db.update_deposit_status(did, "Rejected")
        await query.answer("❌ Rejected")
        try:
            await context.bot.send_message(
                chat_id=d["user_id"], text=f"❌ আপনার Deposit #{did} Reject করা হয়েছে।"
            )
        except Exception:
            pass


# ---------- Withdrawals management ----------
async def admin_wd_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    wds = db.get_pending_withdrawals()
    if not wds:
        await query.message.reply_text("💸 কোনো Pending Withdraw নেই।")
        return
    kb = [
        [InlineKeyboardButton(f"#{w['id']} ৳{w['amount']} (UID {w['user_id']})", callback_data=f"adm:wd:view:{w['id']}")]
        for w in wds
    ]
    await query.message.reply_text("💸 *Pending Withdrawals*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def admin_wd_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    wid = int(query.data.split(":")[3])
    w = db.get_withdrawal(wid)
    text = (
        f"🆔 Withdraw #{w['id']}\n👤 User ID: {w['user_id']}\n💳 {w['method']}\n"
        f"🔢 Account: {w['account']}\n💰 ৳{money(w['amount'])}\n📌 {w['status']}"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"adm:wd:approve:{wid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"adm:wd:reject:{wid}"),
            ]
        ]
    )
    await query.message.reply_text(text, reply_markup=kb)


async def admin_wd_action_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")  # adm:wd:approve/reject:<id>
    action, wid = parts[2], int(parts[3])
    w = db.get_withdrawal(wid)
    if not w or w["status"] != "Pending":
        await query.answer("এই Withdraw আগেই Process হয়েছে।", show_alert=True)
        return
    if action == "approve":
        db.update_balance(w["user_id"], 0, "total_withdraw")  # amount already deducted at request time
        db.update_withdrawal_status(wid, "Approved")
        await query.answer("✅ Approved")
        try:
            await context.bot.send_message(
                chat_id=w["user_id"],
                text=f"✅ আপনার Withdraw #{wid} (৳{money(w['amount'])}) Approve করা হয়েছে ও পাঠানো হয়েছে।",
            )
        except Exception:
            pass
    else:
        db.update_balance(w["user_id"], w["amount"])  # refund
        db.update_withdrawal_status(wid, "Rejected")
        await query.answer("❌ Rejected, টাকা ফেরত দেওয়া হয়েছে")
        try:
            await context.bot.send_message(
                chat_id=w["user_id"],
                text=f"❌ আপনার Withdraw #{wid} Reject করা হয়েছে। Balance ফেরত দেওয়া হয়েছে।",
            )
        except Exception:
            pass


# ---------- Channel / Details / Bot settings ----------
async def admin_channel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ Edit Username", callback_data="adm:set:channel_username")],
            [InlineKeyboardButton("✏️ Edit Link", callback_data="adm:set:channel_link")],
        ]
    )
    await query.message.reply_text(
        f"📢 *Channel Settings*\n\nUsername: {db.get_setting('channel_username')}\n"
        f"Link: {db.get_setting('channel_link')}",
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def admin_details_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["flow"] = {"type": "adm_set", "key": "details_text"}
    await query.message.reply_text(
        f"📝 বর্তমান Details:\n\n{db.get_setting('details_text')}\n\nনতুন Details Text লিখুন:",
        reply_markup=cancel_keyboard(),
    )


async def admin_settings_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ Min Deposit", callback_data="adm:set:min_deposit")],
            [InlineKeyboardButton("✏️ Referral Bonus", callback_data="adm:set:referral_bonus")],
            [InlineKeyboardButton("✏️ Support Link", callback_data="adm:set:support_link")],
        ]
    )
    await query.message.reply_text(
        f"⚙️ *Bot Settings*\n\nMin Deposit: ৳{db.get_setting('min_deposit')}\n"
        f"Referral Bonus: ৳{db.get_setting('referral_bonus')}\n"
        f"Support Link: {db.get_setting('support_link')}",
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def admin_set_key_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[2]
    context.user_data["flow"] = {"type": "adm_set", "key": key}
    await query.message.reply_text(f"✏️ নতুন মান লিখুন ({key}):", reply_markup=cancel_keyboard())


# ==================================================================
# CALLBACK QUERY ROUTER
# ==================================================================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "verify_join":
        return await verify_join_cb(update, context)
    if data.startswith("buy:view:"):
        return await buy_view_cb(update, context)
    if data.startswith("buy:start:"):
        return await buy_start_cb(update, context)
    if data.startswith("sell:view:"):
        return await sell_view_cb(update, context)
    if data.startswith("sell:start:"):
        return await sell_start_cb(update, context)

    if not is_admin(update.effective_user.id):
        await update.callback_query.answer("⛔ Access Denied", show_alert=True)
        return

    if data == "adm:dashboard":
        return await admin_dashboard_cb(update, context)
    if data == "adm:bsvc:list":
        return await admin_bsvc_list_cb(update, context)
    if data.startswith("adm:bsvc:view:"):
        return await admin_bsvc_view_cb(update, context)
    if data.startswith("adm:bsvc:toggle:"):
        return await admin_bsvc_toggle_cb(update, context)
    if data.startswith("adm:bsvc:delete:"):
        return await admin_bsvc_delete_cb(update, context)
    if data.startswith("adm:bsvc:edit:"):
        return await admin_bsvc_edit_cb(update, context)
    if data == "adm:bsvc:add":
        return await admin_bsvc_add_cb(update, context)

    if data == "adm:ssvc:list":
        return await admin_ssvc_list_cb(update, context)
    if data.startswith("adm:ssvc:view:"):
        return await admin_ssvc_view_cb(update, context)
    if data.startswith("adm:ssvc:toggle:"):
        return await admin_ssvc_toggle_cb(update, context)
    if data.startswith("adm:ssvc:delete:"):
        return await admin_ssvc_delete_cb(update, context)
    if data.startswith("adm:ssvc:edit:"):
        return await admin_ssvc_edit_cb(update, context)
    if data == "adm:ssvc:add":
        return await admin_ssvc_add_cb(update, context)

    if data == "adm:ord:list":
        return await admin_ord_list_cb(update, context)
    if data.startswith("adm:ord:view:"):
        return await admin_ord_view_cb(update, context)
    if data.startswith("adm:ord:Processing:") or data.startswith("adm:ord:Completed:") or data.startswith("adm:ord:Cancelled:"):
        return await admin_ord_setstatus_cb(update, context)

    if data == "adm:sr:list":
        return await admin_sr_list_cb(update, context)
    if data.startswith("adm:sr:view:"):
        return await admin_sr_view_cb(update, context)
    if (
        data.startswith("adm:sr:Approved:")
        or data.startswith("adm:sr:Rejected:")
        or data.startswith("adm:sr:Processing:")
        or data.startswith("adm:sr:Completed:")
    ):
        return await admin_sr_setstatus_cb(update, context)

    if data == "adm:dep:list":
        return await admin_dep_list_cb(update, context)
    if data.startswith("adm:dep:view:"):
        return await admin_dep_view_cb(update, context)
    if data.startswith("adm:dep:approve:") or data.startswith("adm:dep:reject:"):
        return await admin_dep_action_cb(update, context)

    if data == "adm:wd:list":
        return await admin_wd_list_cb(update, context)
    if data.startswith("adm:wd:view:"):
        return await admin_wd_view_cb(update, context)
    if data.startswith("adm:wd:approve:") or data.startswith("adm:wd:reject:"):
        return await admin_wd_action_cb(update, context)

    if data == "adm:channel":
        return await admin_channel_cb(update, context)
    if data == "adm:details":
        return await admin_details_cb(update, context)
    if data == "adm:settings":
        return await admin_settings_cb(update, context)
    if data.startswith("adm:set:"):
        return await admin_set_key_cb(update, context)


# ==================================================================
# TEXT MESSAGE ROUTER (menu buttons + multi-step flows)
# ==================================================================
async def admin_flow_text(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    """Handles all admin multi-step text flows."""
    txt = update.message.text.strip()
    ftype = flow["type"]

    if ftype == "adm_bsvc_edit":
        field = flow["field"]
        value = float(txt) if field in ("price",) else int(txt) if field in ("min_qty", "max_qty") else txt
        db.update_buy_service_field(flow["id"], field, value)
        context.user_data.pop("flow", None)
        await update.message.reply_text("✅ Update সম্পন্ন হয়েছে।", reply_markup=main_menu_keyboard(update.effective_user.id))
        return

    if ftype == "adm_ssvc_edit":
        field = flow["field"]
        value = float(txt) if field == "price" else int(txt) if field == "min_qty" else txt
        db.update_sell_service_field(flow["id"], field, value)
        context.user_data.pop("flow", None)
        await update.message.reply_text("✅ Update সম্পন্ন হয়েছে।", reply_markup=main_menu_keyboard(update.effective_user.id))
        return

    if ftype == "adm_set":
        db.set_setting(flow["key"], txt)
        context.user_data.pop("flow", None)
        await update.message.reply_text("✅ Setting Update হয়েছে।", reply_markup=main_menu_keyboard(update.effective_user.id))
        return

    if ftype == "adm_sr_msg":
        if txt != "/skip":
            try:
                await context.bot.send_message(chat_id=flow["user_id"], text=f"📩 Admin থেকে বার্তা:\n\n{txt}")
            except Exception:
                pass
        context.user_data.pop("flow", None)
        await update.message.reply_text("✅ সম্পন্ন হয়েছে।", reply_markup=main_menu_keyboard(update.effective_user.id))
        return

    # Add Buy Service wizard
    if ftype == "adm_bsvc_add_name":
        flow["data"]["name"] = txt
        flow["type"] = "adm_bsvc_add_desc"
        context.user_data["flow"] = flow
        await update.message.reply_text("Description লিখুন:")
        return
    if ftype == "adm_bsvc_add_desc":
        flow["data"]["description"] = txt
        flow["type"] = "adm_bsvc_add_price"
        context.user_data["flow"] = flow
        await update.message.reply_text("Price (৳) লিখুন:")
        return
    if ftype == "adm_bsvc_add_price":
        try:
            flow["data"]["price"] = float(txt)
        except ValueError:
            await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন।")
            return
        flow["type"] = "adm_bsvc_add_min"
        context.user_data["flow"] = flow
        await update.message.reply_text("Minimum Quantity লিখুন:")
        return
    if ftype == "adm_bsvc_add_min":
        if not txt.isdigit():
            await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন।")
            return
        flow["data"]["min_qty"] = int(txt)
        flow["type"] = "adm_bsvc_add_max"
        context.user_data["flow"] = flow
        await update.message.reply_text("Maximum Quantity লিখুন:")
        return
    if ftype == "adm_bsvc_add_max":
        if not txt.isdigit():
            await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন।")
            return
        flow["data"]["max_qty"] = int(txt)
        flow["type"] = "adm_bsvc_add_instr"
        context.user_data["flow"] = flow
        await update.message.reply_text("প্রয়োজনীয় Instruction লিখুন (User যা দেখবে):")
        return
    if ftype == "adm_bsvc_add_instr":
        flow["data"]["instruction"] = txt
        d = flow["data"]
        db.add_buy_service(d["name"], d["description"], d["price"], d["min_qty"], d["max_qty"], d["instruction"])
        context.user_data.pop("flow", None)
        await update.message.reply_text("✅ নতুন Buy Service যোগ হয়েছে!", reply_markup=main_menu_keyboard(update.effective_user.id))
        return

    # Add Sell Service wizard
    if ftype == "adm_ssvc_add_name":
        flow["data"]["name"] = txt
        flow["type"] = "adm_ssvc_add_desc"
        context.user_data["flow"] = flow
        await update.message.reply_text("Description লিখুন:")
        return
    if ftype == "adm_ssvc_add_desc":
        flow["data"]["description"] = txt
        flow["type"] = "adm_ssvc_add_price"
        context.user_data["flow"] = flow
        await update.message.reply_text("Rate/Price (৳) লিখুন:")
        return
    if ftype == "adm_ssvc_add_price":
        try:
            flow["data"]["price"] = float(txt)
        except ValueError:
            await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন।")
            return
        flow["type"] = "adm_ssvc_add_min"
        context.user_data["flow"] = flow
        await update.message.reply_text("Minimum Quantity লিখুন:")
        return
    if ftype == "adm_ssvc_add_min":
        if not txt.isdigit():
            await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন।")
            return
        flow["data"]["min_qty"] = int(txt)
        flow["type"] = "adm_ssvc_add_instr"
        context.user_data["flow"] = flow
        await update.message.reply_text("Sell Instruction লিখুন (User যা দেখবে):")
        return
    if ftype == "adm_ssvc_add_instr":
        flow["data"]["instruction"] = txt
        d = flow["data"]
        db.add_sell_service(d["name"], d["description"], d["price"], d["min_qty"], d["instruction"])
        context.user_data.pop("flow", None)
        await update.message.reply_text("✅ নতুন Sell Service যোগ হয়েছে!", reply_markup=main_menu_keyboard(update.effective_user.id))
        return


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip() if update.message.text else ""

    if txt == BTN_CANCEL:
        return await cancel_flow(update, context)

    flow = context.user_data.get("flow")
    if flow:
        ftype = flow["type"]
        if ftype.startswith("adm_"):
            return await admin_flow_text(update, context, flow)
        if ftype == "buy_qty":
            return await handle_buy_qty(update, context, flow)
        if ftype == "buy_details":
            return await handle_buy_details(update, context, flow)
        if ftype == "sell_qty":
            return await handle_sell_qty(update, context, flow)
        if ftype == "sell_details":
            return await handle_sell_details(update, context, flow)
        if ftype == "deposit_amount":
            return await handle_deposit_amount(update, context, flow)
        if ftype == "deposit_txn":
            return await handle_deposit_txn(update, context, flow)
        if ftype == "wd_method":
            return await handle_wd_method(update, context, flow)
        if ftype == "wd_account":
            return await handle_wd_account(update, context, flow)
        if ftype == "wd_amount":
            return await handle_wd_amount(update, context, flow)
        return

    # not in a flow -> must be a member first
    ok = await check_membership(context.bot, update.effective_user.id)
    if not ok:
        await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=join_keyboard())
        return

    if txt == BTN_BUY:
        return await show_buy_list(update, context)
    if txt == BTN_SELL:
        return await show_sell_list(update, context)
    if txt == BTN_BALANCE:
        return await show_balance(update, context)
    if txt == BTN_DEPOSIT:
        return await start_deposit(update, context)
    if txt == BTN_WITHDRAW:
        return await start_withdraw(update, context)
    if txt == BTN_ORDERS:
        return await show_my_orders(update, context)
    if txt == BTN_DETAILS:
        return await show_details(update, context)
    if txt == BTN_REFERRAL:
        return await show_referral(update, context)
    if txt == BTN_SUPPORT:
        return await show_support(update, context)
    if txt == BTN_ADMIN and is_admin(update.effective_user.id):
        return await show_admin_panel(update, context)

    await update.message.reply_text(
        "মেনু থেকে একটি Option বেছে নিন 👇", reply_markup=main_menu_keyboard(update.effective_user.id)
    )


# ==================================================================
# MAIN
# ==================================================================
def main():
    db.init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    port = int(os.environ.get("PORT", "8443"))
    external_url = os.environ.get("RENDER_EXTERNAL_URL")

    if external_url:
        # Webhook mode - required for Render Web Service (free plan)
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=f"{external_url}/{BOT_TOKEN}",
        )
    else:
        # Local testing fallback
        application.run_polling()


if __name__ == "__main__":
    main()
