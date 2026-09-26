# -*- coding: utf-8 -*-
"""
Add-on module: adds a "💬 User-কে মেসেজ" button feature WITHOUT modifying
bot.py or database.py at all.

How it works:
- It imports the existing, unmodified `bot` module.
- It hooks into Application.run_webhook / run_polling (the two functions
  bot.py's main() calls to start the bot) so that, right before the bot
  actually starts, it:
    1) registers two extra handlers (a callback handler + a text handler)
       in an earlier handler group, so they run before bot.py's own
       handlers and don't interfere with them.
    2) wraps the bot's send_message so that any admin notification that
       already contains "... ID: <number>" (every Buy Order / Sell
       Request / Deposit / Withdraw notification and their "view" screens
       already do) automatically gets an extra
       "💬 User-কে মেসেজ" button added to it.
- When the admin taps that button, this module asks for a message and
  relays it to that exact user via the bot — nothing in bot.py changes.

To use this: keep bot.py and database.py exactly as they are, add this
file plus run.py to the project, and change the Start Command on Render
from `python bot.py` to `python run.py`.
"""
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

import bot as botmod  # the existing, untouched bot.py

ADMIN_ID = botmod.ADMIN_ID
_ID_RE = re.compile(r"ID:\s*(\d+)")
_FLOW_TYPE = "adm_msg_user_addon"


# ---------------------------------------------------------------------
# New handlers (do not exist in bot.py)
# ---------------------------------------------------------------------
async def _msg_user_cb(update, context):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(":")[2])
    context.user_data["flow"] = {"type": _FLOW_TYPE, "user_id": target_id}
    await query.message.reply_text(
        f"💬 User (ID: {target_id})-কে যা বলতে চান লিখে পাঠান (বাতিল করতে Cancel চাপুন):",
        reply_markup=botmod.cancel_keyboard(),
    )
    raise ApplicationHandlerStop


async def _msg_user_text(update, context):
    flow = context.user_data.get("flow")
    if not flow or flow.get("type") != _FLOW_TYPE:
        return  # not our flow — let bot.py's own handlers process it normally
    txt = (update.message.text or "").strip()
    if txt == botmod.BTN_CANCEL:
        return  # let bot.py's own Cancel handling run normally
    target_id = flow["user_id"]
    context.user_data.pop("flow", None)
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"👨‍💻 *Admin থেকে বার্তা:*\n\n{txt}",
            parse_mode="Markdown",
        )
        await update.message.reply_text(
            "✅ মেসেজ পাঠানো হয়েছে।",
            reply_markup=botmod.main_menu_keyboard(update.effective_user.id),
        )
    except Exception:
        await update.message.reply_text(
            "❌ মেসেজ পাঠানো যায়নি (User হয়তো বট Block করেছে)।",
            reply_markup=botmod.main_menu_keyboard(update.effective_user.id),
        )
    raise ApplicationHandlerStop


def _install_handlers(application):
    # group=-1 => runs BEFORE bot.py's own handlers (group 0), and only
    # intercepts the update (via ApplicationHandlerStop) when it's
    # actually relevant to this feature.
    application.add_handler(
        CallbackQueryHandler(_msg_user_cb, pattern=r"^adm:msg:"), group=-1
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _msg_user_text), group=-1
    )


# ---------------------------------------------------------------------
# Auto-add the button to existing admin notifications, without touching
# the code in bot.py that sends them.
# ---------------------------------------------------------------------
def _augment_markup(chat_id, text, reply_markup):
    if chat_id != ADMIN_ID or not text or not isinstance(reply_markup, InlineKeyboardMarkup):
        return reply_markup
    m = _ID_RE.search(text)
    if not m:
        return reply_markup
    uid = int(m.group(1))
    rows = [list(row) for row in reply_markup.inline_keyboard]
    already = any(
        getattr(btn, "callback_data", None) == f"adm:msg:{uid}"
        for row in rows
        for btn in row
    )
    if not already:
        rows.append([InlineKeyboardButton("💬 User-কে মেসেজ", callback_data=f"adm:msg:{uid}")])
        reply_markup = InlineKeyboardMarkup(rows)
    return reply_markup


def _patch_send_message(application):
    bot_obj = application.bot
    if getattr(bot_obj, "_contact_admin_patched", False):
        return
    original = bot_obj.send_message

    async def patched(chat_id=None, text=None, reply_markup=None, **kwargs):
        try:
            reply_markup = _augment_markup(chat_id, text, reply_markup)
        except Exception:
            pass
        return await original(chat_id=chat_id, text=text, reply_markup=reply_markup, **kwargs)

    bot_obj.send_message = patched
    bot_obj._contact_admin_patched = True


# ---------------------------------------------------------------------
# Hook into Application.run_webhook / run_polling so we attach to the
# exact Application instance bot.py's main() creates — without editing
# bot.py's main() at all.
# ---------------------------------------------------------------------
def _wrap_run(method_name):
    original_method = getattr(Application, method_name)

    def wrapper(self, *args, **kwargs):
        _install_handlers(self)
        _patch_send_message(self)
        return original_method(self, *args, **kwargs)

    setattr(Application, method_name, wrapper)


_wrap_run("run_webhook")
_wrap_run("run_polling")
