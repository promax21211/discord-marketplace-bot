
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load secrets
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="-", intents=intents)

# Example stock and user order tracking (normally from DB)
stock_data = {
    "owo": {"price": 0.25, "qty": 100, "type": "order"},
    "keys": {"price": 0.5, "qty": 3, "type": "instant"},
    "thumbnail": {"price": 1.0, "qty": None, "type": "custom"},
}
orders = {}
order_id = 0
whitelisted_roles = ["Admin", "Bot Staff"]

def is_whitelisted(member):
    return any(role.name in whitelisted_roles for role in member.roles)

def make_embed(title, desc, color=0x00ffcc):
    return discord.Embed(title=title, description=desc, color=color)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def stock(ctx, item=None):
    if item and item in stock_data:
        s = stock_data[item]
        embed = make_embed(
            f"{item.title()} Stock",
            f"Type: {s['type']}\nPrice: ${s['price']}\nAvailable: {s['qty'] or '∞'}"
        )
        return await ctx.send(embed=embed)
    desc = ""
    for k, v in stock_data.items():
        desc += f"{k} — ${v['price']} — {v['type']}\n"
    embed = make_embed("🗃️ Available Stock", desc)
    await ctx.send(embed=embed)

@bot.command()
async def buy(ctx, item: str, qty: int = 1):
    global order_id

    if item not in stock_data:
        return await ctx.send("❌ Invalid item.")

    s = stock_data[item]

    if s["type"] != "instant":
        return await ctx.send("❌ This item must be ordered with `-order`.")

    if s["qty"] is not None and qty > s["qty"]:
        return await ctx.send("❌ Not enough stock available.")

    total = qty * s["price"]
    order_id += 1
    orders[order_id] = {"user": ctx.author.id, "item": item, "qty": qty, "paid": False}

    embed = make_embed("💰 Payment Instructions",
                       f"Please pay `{total}$` to the bot via Tip.cc:\n\n"
                       f"`$tip @YourBot {total}$ sol`\nThen run `-paid`.")
    await ctx.send(embed=embed)

@bot.command()
async def order(ctx, item: str, *, desc: str):
    global order_id
    if item not in stock_data or stock_data[item]["type"] not in ["order", "custom"]:
        return await ctx.send("❌ Invalid custom item.")

    order_id += 1
    orders[order_id] = {
        "user": ctx.author.id,
        "item": item,
        "desc": desc,
        "status": "pending",
        "paid": False
    }

    embed = make_embed("📦 Custom Order Received",
                       f"Type: `{item}`\nDescription: `{desc}`\n\nA staff member will accept this soon.")
    await ctx.send(embed=embed)

@bot.command()
async def paid(ctx):
    matched = False
    for oid, data in orders.items():
        if data["user"] == ctx.author.id and not data["paid"]:
            data["paid"] = True
            matched = True
            await ctx.send(embed=make_embed("✅ Payment Confirmed", f"Order #{oid} marked as paid."))
            if stock_data[data["item"]]["type"] == "instant":
                await ctx.author.send(f"🎁 You received your item: {data['item']} x{data['qty']}")
                stock_data[data["item"]]["qty"] -= data["qty"]
            break
    if not matched:
        await ctx.send("❌ No unpaid order found.")

@bot.command()
async def deliver(ctx, oid: int, *, content: str):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    if oid in orders:
        try:
            user = await bot.fetch_user(orders[oid]["user"])
            await user.send(f"📦 Your delivery for order #{oid}:\n{content}")
            await ctx.send("✅ Delivered.")
        except:
            await ctx.send("⚠️ Could not send DM.")
    else:
        await ctx.send("❌ Order not found.")

@bot.command(name="commands")
async def commands_list(ctx):
    cmds = {
        "Clients": "-stock, -buy <item>, -order <item> <desc>, -paid, -cancel, -orderlist",
        "Staff": "-deliver <id> <data> (Whitelist Only)"
    }
    embed = make_embed("📖 Bot Commands", "")
    for k, v in cmds.items():
        embed.add_field(name=k, value=v, inline=False)
    await ctx.send(embed=embed)

bot.run(TOKEN)
