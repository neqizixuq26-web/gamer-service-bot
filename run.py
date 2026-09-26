# -*- coding: utf-8 -*-
"""
New entry point — use this instead of bot.py as the Start Command.

bot.py and database.py are NOT changed at all. This file just loads the
contact_admin add-on (which adds the "💬 User-কে মেসেজ" feature) and then
runs the bot exactly the same way bot.py itself would.

Render Start Command:  python run.py   (instead of  python bot.py)
"""
import contact_admin  # noqa: F401  (must be imported before bot.main() runs)
import bot

if __name__ == "__main__":
    bot.main()
