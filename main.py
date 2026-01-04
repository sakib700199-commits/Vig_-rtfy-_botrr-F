import asyncio, json, os, uuid, logging, aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, Message, CallbackQuery
from aiohttp import web

# --- 🛠 CONFIGURATION ---
API_TOKEN = '8090436930:AAEIIa_7qfUsr9qgU9Q_V6zX4c-HwbCS0dE'
ADMIN_ID = 8128852482
PORT = int(os.environ.get("PORT", 8080))
DB_FILE = "premium_users.json"
MAX_THREADS = 5  # Speed boost factor

# --- 🚀 INITIALIZE BOT & DISPATCHER FIRST ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- 🧠 UI HELPERS ---
def get_fancy(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fancy  = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘqʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘqʀꜱᴛᴜᴠᴡxʏᴢ₀₁₂₃₄₅₆₇₈₉"
    return text.translate(str.maketrans(normal, fancy))

def progress_bar(current, total, length=10):
    percent = min(1.0, float(current) / total)
    bar = '█' * int(round(percent * length))
    spaces = '░' * (length - len(bar))
    return f"[{bar}{spaces}] {int(percent * 100)}%"

class Setup(StatesGroup):
    waiting_for_url = State()
    waiting_for_amt = State()

# --- 📊 DATABASE ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: pass
    return {"users": {}, "global_stats": {"total_views": 0, "total_likes": 0}}

db = load_db()
def save_db():
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=4)

# --- ⚡ ZEFAME ENGINE (Original Name Ke Saath) ---
class ZefameEngine:
    def __init__(self, url, s_type):
        self.url = url
        self.service_id = 237 if s_type == 'views' else 234 
        self.endpoint = "https://zefame-free.com/api_free.php?action=order" 
        self.headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded",
            "referrer": "https://zefame.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        }

    async def request_boost(self, session, sem):
        async with sem:
            try:
                # PostID extraction logic
                parts = self.url.strip("/").split("/")
                pid = parts[4] if len(parts) > 4 else ""
                
                data = {"service": self.service_id, "link": self.url, "uuid": str(uuid.uuid4()), "postId": pid}
                async with session.post(self.endpoint, data=data, headers=self.headers, timeout=15) as r:
                    if r.status == 200:
                        res = await r.json()
                        if res.get('success'): return "OK", None
                        if 'data' in res and isinstance(res['data'], dict):
                            return "WAIT", res['data'].get('timeLeft', 30)
                return "FAIL", None
            except:
                return "ERR", None

# --- 🕹️ KEYBOARD ---
def main_menu(uid):
    u = db["users"].get(str(uid), {"type": "views", "amt": 10})
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"🚀 {get_fancy('start boosting')}", callback_data="run"))
    kb.row(InlineKeyboardButton(text=f"🔗 {get_fancy('set url')}", callback_data="set_url"), 
           InlineKeyboardButton(text=f"🔢 {get_fancy('set amount')}", callback_data="set_amt"))
    mode_label = "👁️ ᴠɪᴇᴡꜱ" if u['type'] == 'views' else "❤️ ʟɪᴋᴇꜱ"
    kb.row(InlineKeyboardButton(text=f"⚙️ {get_fancy('mode')}: {mode_label}", callback_data="toggle"))
    kb.row(InlineKeyboardButton(text=f"👤 {get_fancy('profile')}", callback_data="me"),
           InlineKeyboardButton(text=f"🌍 {get_fancy('global stats')}", callback_data="gstats"))
    return kb.as_markup()

# --- 🤖 HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(m: Message):
    uid = str(m.from_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"url": "None", "type": "views", "amt": 10, "sent": 0}
        save_db()
    await m.answer(f"👋 **{get_fancy('insta-booster premium')}**", reply_markup=main_menu(uid), parse_mode="Markdown")

@dp.callback_query(F.data == "run")
async def start_task(c: CallbackQuery):
    uid = str(c.from_user.id)
    u = db["users"][uid]
    if u["url"] == "None": return await c.answer("❌ Set URL first!", show_alert=True)
    
    msg = await c.message.answer(f"🛰️ **{get_fancy('initiating turbo mode')}...**")
    engine = ZefameEngine(u["url"], u["type"])
    sem = asyncio.Semaphore(MAX_THREADS)
    
    done = 0
    total = u["amt"]
    
    async with aiohttp.ClientSession() as session:
        while done < total:
            batch = min(total - done, MAX_THREADS)
            tasks = [engine.request_boost(session, sem) for _ in range(batch)]
            results = await asyncio.gather(*tasks) # Multi-threading boost
            
            wait_needed = 0
            for status, data in results:
                if status == "OK":
                    done += 1
                    u["sent"] += (500 if u["type"] == "views" else 20)
                    if u["type"] == "views": db["global_stats"]["total_views"] += 500
                    else: db["global_stats"]["total_likes"] += 20
                elif status == "WAIT":
                    wait_needed = max(wait_needed, int(data))
            
            save_db()
            
            # Real-time UI Update
            try:
                await msg.edit_text(
                    f"⚡ **{get_fancy('boosting active')}**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📈 Progress: `{progress_bar(done, total)}`\n"
                    f"✅ Batches: `{done}/{total}`\n"
                    f"📊 Total Sent: `{u['sent']}`",
                    parse_mode="Markdown"
                )
            except: pass

            if wait_needed > 0:
                for i in range(wait_needed, 0, -5):
                    try: await msg.edit_text(f"⏳ **{get_fancy('api limit')}**\nResuming in `{i}s`...")
                    except: pass
                    await asyncio.sleep(5)
            else:
                await asyncio.sleep(1)

    await msg.edit_text(f"🏆 **{get_fancy('task completed')}!**")

@dp.callback_query(F.data == "set_url")
async def ask_url(c: CallbackQuery, state: FSMContext):
    await state.set_state(Setup.waiting_for_url) # Original State
    await c.message.answer(f"🔗 {get_fancy('send instagram link')}:")
    await c.answer()

@dp.message(Setup.waiting_for_url) # Handling reply
async def save_url(m: Message, state: FSMContext):
    if "instagram.com" in m.text:
        db["users"][str(m.from_user.id)]["url"] = m.text
        save_db()
        await m.answer(f"✅ {get_fancy('url saved')}", reply_markup=main_menu(m.from_user.id))
        await state.clear()
    else:
        await m.answer("❌ Invalid URL!")

@dp.callback_query(F.data == "set_amt")
async def ask_amt(c: CallbackQuery, state: FSMContext):
    await state.set_state(Setup.waiting_for_amt) # Original State
    await c.message.answer(f"🔢 {get_fancy('how many batches')}?")
    await c.answer()

@dp.message(Setup.waiting_for_amt) # Handling reply
async def save_amt(m: Message, state: FSMContext):
    if m.text.isdigit():
        db["users"][str(m.from_user.id)]["amt"] = int(m.text)
        save_db()
        await m.answer(f"✅ {get_fancy('amount updated')}", reply_markup=main_menu(m.from_user.id))
        await state.clear()
    else:
        await m.answer("⚠️ Send a number!")

@dp.callback_query(F.data == "toggle")
async def toggle(c: CallbackQuery):
    uid = str(c.from_user.id)
    db["users"][uid]["type"] = "likes" if db["users"][uid]["type"] == "views" else "views"
    save_db()
    await c.message.edit_reply_markup(reply_markup=main_menu(uid))

# --- 🌐 SERVER ---
async def handle_health(request): return web.Response(text="Running")
async def start_web():
    app = web.Application()
    app.router.add_get('/', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

async def main():
    asyncio.create_task(start_web())
    print("💎 God Level Turbo Bot Online!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
                
