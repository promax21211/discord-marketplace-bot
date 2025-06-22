import discord from discord.ext import commands import os from dotenv import load_dotenv from pymongo import MongoClient

Load secrets

load_dotenv() TOKEN = os.getenv("DISCORD_TOKEN") MONGO_URI = os.getenv("MONGO_URI")

intents = discord.Intents.all() bot = commands.Bot(command_prefix="-", intents=intents)

Connect to MongoDB

mongo_client = MongoClient(MONGO_URI) db = mongo_client["marketplace"] stock_collection = db["stock"] orders_collection = db["orders"] config_collection = db["config"]

whitelisted_roles = ["Admin", "Bot Staff"] log_channel_id = None

Helper functions

def is_whitelisted(member): return any(role.name in whitelisted_roles for role in member.roles)

def make_embed(title, desc, color=0x00ffcc): return discord.Embed(title=title, description=desc, color=color)

async def log_event(message): if log_channel_id: channel = bot.get_channel(log_channel_id) if channel: await channel.send(message)

@bot.event async def on_ready(): global log_channel_id print(f"✅ Logged in as {bot.user}") conf = config_collection.find_one({"name": "log_channel"}) if conf: log_channel_id = conf["value"]

@bot.command() async def stock(ctx, item=None): if item: s = stock_collection.find_one({"name": item}) if s: embed = make_embed(f"{item.title()} Stock", f"Type: {s['type']}\nPrice: ${s['price']}\nAvailable: {s.get('qty', '∞')}") return await ctx.send(embed=embed) return await ctx.send("❌ Item not found.") desc = "" for s in stock_collection.find(): desc += f"{s['name']} — ${s['price']} — {s['type']}\n" embed = make_embed("🗃️ Available Stock", desc) await ctx.send(embed=embed)

@bot.command() async def addstock(ctx, item: str, qty: int): if not is_whitelisted(ctx.author): return await ctx.send("❌ Not authorized.") stock_collection.update_one({"name": item}, {"$inc": {"qty": qty}}, upsert=True) await ctx.send(f"✅ Added {qty} to {item}.")

@bot.command() async def setprice(ctx, item: str, price: float): if not is_whitelisted(ctx.author): return await ctx.send("❌ Not authorized.") stock_collection.update_one({"name": item}, {"$set": {"price": price}}, upsert=True) await ctx.send(f"✅ Price for {item} set to ${price}.")

@bot.command() async def buy(ctx, item: str, qty: int = 1): stock = stock_collection.find_one({"name": item}) if not stock: return await ctx.send("❌ Invalid item.") if stock["type"] != "instant": return await ctx.send("❌ Must use -order.") if stock.get("qty") and qty > stock["qty"]: return await ctx.send("❌ Not enough stock.") total = qty * stock["price"] order = { "user": ctx.author.id, "item": item, "qty": qty, "paid": False, "type": "buy" } oid = orders_collection.insert_one(order).inserted_id embed = make_embed("💰 Payment Instructions", f"Please pay {total}$ via Tip.cc:\n\n$tip @YourBot {total}$ sol\nThen run -paid. Order ID: {oid}") await ctx.send(embed=embed) await log_event(f"🛒 New order #{oid} by {ctx.author} for {qty} x {item}")

@bot.command() async def paid(ctx): unpaid = orders_collection.find_one({"user": ctx.author.id, "paid": False}) if not unpaid: return await ctx.send("❌ No unpaid order found.") orders_collection.update_one({"_id": unpaid["_id"]}, {"$set": {"paid": True}}) await ctx.send(embed=make_embed("✅ Payment Confirmed", f"Order #{unpaid['_id']} marked as paid.")) if unpaid["type"] == "buy": stock_collection.update_one({"name": unpaid["item"]}, {"$inc": {"qty": -unpaid["qty"]}}) await ctx.author.send(f"🎁 You received your item: {unpaid['item']} x{unpaid['qty']}")

@bot.command() async def deliver(ctx, oid, *, content): if not is_whitelisted(ctx.author): return await ctx.send("❌ Not authorized.") order = orders_collection.find_one({"_id": oid}) if not order: return await ctx.send("❌ Order not found.") try: user = await bot.fetch_user(order["user"]) await user.send(f"📦 Delivery for order #{oid}:\n{content}") await ctx.send("✅ Delivered.") except: await ctx.send("⚠️ Could not send DM.")

@bot.command(name="commands") async def commands_list(ctx): cmds = { "Clients": "-stock, -buy <item>, -order <item> <desc>, -paid, -cancel, -orderlist, -help, -report", "Staff": "-addstock, -setprice, -deliver <id> <msg>, -logchannel, -forwardim <type>, -sendlogs", "Whitelist": "-bal, -withdraw <amt> <coin>, -whitelist <@role>, -unwhitelist <@role>, -setprefix <prefix>" } embed = make_embed("📖 Bot Commands", "") for k, v in cmds.items(): embed.add_field(name=k, value=v, inline=False) await ctx.send(embed=embed)

@bot.command() async def logchannel(ctx, channel: discord.TextChannel): global log_channel_id if not is_whitelisted(ctx.author): return await ctx.send("❌ Not authorized.") log_channel_id = channel.id config_collection.update_one({"name": "log_channel"}, {"$set": {"value": channel.id}}, upsert=True) await ctx.send(f"✅ Logs will be sent to {channel.mention}")

@bot.command() async def report(ctx, *, message): await log_event(f"📝 Report from {ctx.author}: {message}") await ctx.send("✅ Report sent to staff.")

bot.run(TOKEN)

