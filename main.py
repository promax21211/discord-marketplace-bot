import discord from discord.ext import commands import os from dotenv import load_dotenv from db_utils import ( get_stock, get_stock_item, add_stock_item, update_stock_item, clear_stock_item, create_order, update_order, get_order_by_id, get_orders_by_user, cancel_order_by_id )

Load secrets

load_dotenv() TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all() bot = commands.Bot(command_prefix="-", intents=intents)

whitelisted_roles = ["Admin", "Bot Staff"] log_channel_id = None

def is_whitelisted(member): return any(role.name in whitelisted_roles for role in member.roles)

def make_embed(title, desc, color=0x00ffcc): return discord.Embed(title=title, description=desc, color=color)

async def log_event(message): if log_channel_id: channel = bot.get_channel(log_channel_id) if channel: await channel.send(message)

@bot.event async def on_ready(): print(f"✅ Logged in as {bot.user}")

@bot.command() async def stock(ctx, item=None): if item: s = get_stock_item(item) if s: embed = make_embed(f"{item.title()} Stock", f"Type: {s['type']}\nPrice: ${s['price']}\nAvailable: {s.get('qty', '∞')}") return await ctx.send(embed=embed) return await ctx.send("❌ Item not found.") desc = "" for s in get_stock(): desc += f"{s['name']} — ${s['price']} — {s['type']}\n" embed = make_embed("🗃️ Available Stock", desc) await ctx.send(embed=embed)

@bot.command() async def addstock(ctx, item: str, qty: int): if not is_whitelisted(ctx.author): return await ctx.send("❌ Not authorized.") add_stock_item(item, 0, qty) await ctx.send(f"✅ Added {qty} to {item}.")

@bot.command() async def setprice(ctx, item: str, price: float): if not is_whitelisted(ctx.author): return await ctx.send("❌ Not authorized.") update_stock_item(item, {"price": price}) await ctx.send(f"✅ Price for {item} set to ${price}.")

@bot.command() async def buy(ctx, item: str, qty: int = 1): stock = get_stock_item(item) if not stock: return await ctx.send("❌ Invalid item.") if stock["type"] != "instant": return await ctx.send("❌ Must use -order.") if stock.get("qty") and qty > stock["qty"]: return await ctx.send("❌ Not enough stock.") total = qty * stock["price"] order = { "user": ctx.author.id, "item": item, "qty": qty, "paid": False, "type": "buy" } oid = create_order(order) embed = make_embed("💰 Payment Instructions", f"Please pay {total}$ via Tip.cc:\n\n$tip @YourBot {total}$ sol\nThen run -paid. Order ID: {oid}") await ctx.send(embed=embed) await log_event(f"🛒 New order #{oid} by {ctx.author} for {qty} x {item}")

@bot.command() async def paid(ctx): orders = get_orders_by_user(ctx.author.id) unpaid = next((o for o in orders if not o["paid"]), None) if not unpaid: return await ctx.send("❌ No unpaid order found.") update_order(unpaid["_id"], {"paid": True}) await ctx.send(embed=make_embed("✅ Payment Confirmed", f"Order #{unpaid['_id']} marked as paid.")) if unpaid["type"] == "buy": stock = get_stock_item(unpaid["item"]) update_stock_item(unpaid["item"], {"qty": stock["qty"] - unpaid["qty"]}) await ctx.author.send(f"🎁 You received your item: {unpaid['item']} x{unpaid['qty']}")

@bot.command() async def deliver(ctx, oid, *, content): if not is_whitelisted(ctx.author): return await ctx.send("❌ Not authorized.") order = get_order_by_id(oid) if not order: return await ctx.send("❌ Order not found.") try: user = await bot.fetch_user(order["user"]) await user.send(f"📦 Delivery for order #{oid}:\n{content}") await ctx.send("✅ Delivered.") except: await ctx.send("⚠️ Could not send DM.")

@bot.command(name="commands") async def commands_list(ctx): cmds = { "Clients": "-stock, -buy <item>, -order <item> <desc>, -paid, -cancel, -orderlist, -help, -report", "Staff": "-addstock, -setprice, -deliver <id> <msg>, -logchannel, -forwardim <type>, -sendlogs", "Whitelist": "-bal, -withdraw <amt> <coin>, -whitelist <@role>, -unwhitelist <@role>, -setprefix <prefix>" } embed = make_embed("📖 Bot Commands", "") for k, v in cmds.items(): embed.add_field(name=k, value=v, inline=False) await ctx.send(embed=embed)

@bot.command() async def logchannel(ctx, channel: discord.TextChannel): global log_channel_id if not is_whitelisted(ctx.author): return await ctx.send("❌ Not authorized.") log_channel_id = channel.id update_order("log_channel", {"value": channel.id}) await ctx.send(f"✅ Logs will be sent to {channel.mention}")

@bot.command() async def report(ctx, *, message): await log_event(f"📝 Report from {ctx.author}: {message}") await ctx.send("✅ Report sent to staff.")

bot.run(TOKEN)

