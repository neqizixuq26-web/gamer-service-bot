# 🎮 Gamer Service Buy & Sell Telegram Bot

একটি Full Functional Telegram Bot — User Buy/Sell Service করতে পারবে, Admin (আপনি) পুরো বট Telegram-এর ভেতর থেকেই (কোনো আলাদা ওয়েবসাইট ছাড়াই) পরিচালনা করতে পারবেন। মোবাইল ফোন দিয়ে GitHub + Render (Free Plan) ব্যবহার করে Deploy করার জন্য তৈরি।

## ফাইল গঠন
```
bot.py            → মূল বট কোড (সব User + Admin Logic)
database.py       → SQLite Database Layer
requirements.txt  → Python Dependencies
render.yaml       → Render Deploy Config
.env.example      → Environment Variable নমুনা
```

## ⚠️ খুব গুরুত্বপূর্ণ দুটি বিষয় (আগে পড়ুন)

**১) Channel Verify করতে বটকে Channel-এর Admin বানাতে হবে**
হ্যাঁ। Telegram-এর নিয়ম অনুযায়ী কোনো User কোনো Channel-এ Join করেছে কিনা তা চেক করতে (`getChatMember` API) বটকে অবশ্যই সেই Channel-এর **Admin** হতে হবে (শুধু Member হলে চলবে না, নিদেনপক্ষে Admin permission লাগবে — "Add Members" permission দিলেই যথেষ্ট, Post করার Permission না দিলেও চলবে)। Channel → Administrators → Add Admin → আপনার বট যোগ করুন।

**২) Render Free Plan-এ Database ও Bot ঘুমিয়ে পড়া (Sleep) নিয়ে সতর্কতা**
- Render Free Web Service ১৫ মিনিট Inactive থাকলে Sleep-এ চলে যায়, নতুন Request এলে আবার জেগে ওঠে (কিছুটা দেরি হয়)।
- এই কোড SQLite (`bot.db` নামে একটা ফাইল) ব্যবহার করে। Render Free Plan-এ Persistent Disk নেই, তাই **Re-deploy করলে বা Service নতুন করে Restart হলে পুরনো Data (User Balance, Order ইত্যাদি) মুছে যেতে পারে।**
- টেস্ট করার জন্য/ছোট পরিসরে চালানোর জন্য এটি ঠিক আছে। কিন্তু আসল টাকা-পয়সার হিসাব রাখতে চাইলে ভবিষ্যতে একটি ফ্রি External Database (যেমন Supabase বা Neon-এর Free PostgreSQL) যোগ করার পরামর্শ থাকলো — এটা আমাকে বললে আমি Database Layer পরে PostgreSQL-এ Migrate করে দিতে পারবো।

---

## 📱 ধাপে ধাপে Deploy করার নিয়ম (শুধু মোবাইল দিয়ে)

### ধাপ ১ — Bot তৈরি করুন
1. Telegram-এ **@BotFather**-কে মেসেজ দিন → `/newbot` → নাম দিন → **BOT_TOKEN** কপি করে রাখুন।
2. **@userinfobot**-কে মেসেজ দিয়ে নিজের **User ID (ADMIN_ID)** বের করুন।
3. আপনার Channel তৈরি করে বটকে সেখানে **Admin** বানান (উপরে ১নং পয়েন্ট দেখুন)।

### ধাপ ২ — GitHub-এ কোড আপলোড (মোবাইল দিয়ে)
1. Play Store / App Store থেকে **GitHub** অ্যাপ ইনস্টল করুন, Login করুন।
2. GitHub App বা [github.com](https://github.com) (মোবাইল ব্রাউজারে) থেকে একটি নতুন **Private Repository** তৈরি করুন (যেমন নাম: `gamer-service-bot`)।
3. এই চ্যাটে যে ফাইলগুলো দেওয়া হয়েছে (bot.py, database.py, requirements.txt, render.yaml, .gitignore) — প্রতিটি ফাইল GitHub Repo-তে **"Add file → Create new file"** দিয়ে নাম ও কনটেন্ট বসিয়ে Upload করুন (মোবাইল ব্রাউজার থেকেই করা যায়, Copy-Paste করে)।
   - সহজ বিকল্প: GitHub Mobile App-এ সরাসরি ফাইল Upload অপশন থাকলে সেটাও ব্যবহার করতে পারেন।
4. `.env` ফাইল GitHub-এ Upload করবেন **না** — Token/ID গুলো Render-এর Environment Variables-এ আলাদাভাবে বসাবেন (নিচে দেখুন)।

### ধাপ ৩ — Render-এ Deploy করুন
1. মোবাইল ব্রাউজারে [render.com](https://render.com) খুলে GitHub দিয়ে Sign Up/Login করুন।
2. **New → Web Service** সিলেক্ট করুন।
3. আপনার `gamer-service-bot` Repository Connect করুন।
4. এই তথ্যগুলো দিন:
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Plan:** Free
5. **Environment Variables** সেকশনে গিয়ে যোগ করুন:
   - `BOT_TOKEN` → আপনার Bot Token
   - `ADMIN_ID` → আপনার User ID
   - `CHANNEL_USERNAME` → `@yourchannel`
   - `CHANNEL_LINK` → `https://t.me/yourchannel`
   - `SUPPORT_LINK` → `https://t.me/yoursupportusername`
6. **Create Web Service** চাপুন। কিছুক্ষণ পর Deploy সম্পন্ন হবে এবং বট Live হয়ে যাবে (`RENDER_EXTERNAL_URL` Render নিজে থেকেই সেট করে, তাই আলাদা করে দিতে হবে না)।
7. Telegram-এ গিয়ে আপনার Bot-কে `/start` দিন।

### ধাপ ৪ — Admin Panel ব্যবহার
- আপনি যেহেতু `ADMIN_ID` দিয়েছেন, তাই মূল মেনুতে **"⚙️ Admin Panel"** বাটন দেখতে পাবেন।
- সেখান থেকেই Buy/Sell Service Add/Edit/Delete/ON-OFF, Orders, Sell Requests, Deposits, Withdrawals Approve/Reject, Channel/Details/Bot Settings — সব পরিচালনা করা যাবে।

---

## Deploy করার পর কোনো Setting পরিবর্তন করলে
Code পরিবর্তন করতে হয় না — সবকিছু Admin Panel থেকেই হয়। কেবল নতুন Feature/Bug Fix লাগলে GitHub-এ ফাইল Update করলে Render নিজে থেকেই Re-deploy করে নেয়।

## সমস্যা হলে
- বট Reply না দিলে: Render Dashboard → আপনার Service → **Logs** দেখুন, Error থাকলে সেটা কপি করে জানাতে পারেন।
- Channel Verify কাজ না করলে: বট Channel-এর Admin কিনা এবং `CHANNEL_USERNAME` ঠিক আছে কিনা চেক করুন।
