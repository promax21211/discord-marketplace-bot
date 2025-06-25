# main.py – Part 1

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from db_utils import (
    get_stock, get_stock_item, add_stock_item, update_stock_item, clear_stock_item,
    create_order, update_order, get_order_by_id, get_orders_by_user, cancel_order_by_id,
    add_hidden_stock, add_item_to_hidden, get_hidden_stock, get_hidden_item,
    get_discount, use_discount, create_discount,
    set_reward_trigger, get_reward_trigger, get_user_order_count,
    log_event_to_db, get_logs,
    log_failed_dm, get_failed_deliveries, delete_failed_dm,
    log_payment, get_unmatched_payments, mark_payment_matched,
    set_config, get_config
)

# Load environment
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["marketplace"]
config_collection = db["config"]

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="-", intents=intents)

# Globals
whitelisted_roles = ["Admin", "Bot Staff"]
log_channel_id = None

# Helpers
def is_whitelisted(member):
    return any(role.name in whitelisted_roles for role in member.roles)

def make_embed(title, desc, color=0x00ffcc):
    return discord.Embed(title=title, description=desc, color=color)

async def log_event(message):
    global log_channel_id
    log_event_to_db(message)
    if log_channel_id:
        channel = bot.get_channel(log_channel_id)
        if channel:
            await channel.send(message)

# Bot ready
@bot.event
async def on_ready():
    global log_channel_id
    print(f"✅ Logged in as {bot.user}")
    log_channel_id = get_config("log_channel")
  from bson import ObjectId

@bot.command()
async def stock(ctx, item=None):
    if item:
        s = get_stock_item(item)
        if s:
            embed = make_embed(f"{item.title()} Stock", f"Type: {s['type']}\nPrice: ${s['price']}\nAvailable: {s.get('qty', '∞')}")
            return await ctx.send(embed=embed)
        return await ctx.send("❌ Item not found.")
    desc = ""
    for s in get_stock():
        desc += f"{s['name']} — ${s['price']} — {s['type']}\n"
    embed = make_embed("🗃️ Available Stock", desc)
    await ctx.send(embed=embed)


@bot.command()
async def buy(ctx, item: str, qty: int = 1):
    stock = get_stock_item(item)
    if not stock:
        return await ctx.send("❌ Invalid item.")
    if stock["type"] != "instant":
        return await ctx.send("❌ This item must be ordered with `-order`.")
    if stock.get("qty") and qty > stock["qty"]:
        return await ctx.send("❌ Not enough stock.")
    total = qty * stock["price"]
    order = {
        "user": ctx.author.id,
        "item": item,
        "qty": qty,
        "paid": False,
        "type": "buy"
    }
    oid = create_order(order)
    embed = make_embed("💰 Payment Instructions", f"Pay `{total}$` via Tip.cc:\n\n`$tip @YourBot {total}$ sol`\nThen use `-paid`\nOrder ID: `{oid}`")
    await ctx.send(embed=embed)
    await log_event(f"🛒 New instant order #{oid} by {ctx.author} | {qty}x {item}")


@bot.command()
async def order(ctx, item: str, *, desc: str):
    stock = get_stock_item(item)
    if not stock or stock["type"] not in ["order", "custom", "hidden"]:
        return await ctx.send("❌ Invalid custom/hidden item.")
    order = {
        "user": ctx.author.id,
        "item": item,
        "desc": desc,
        "paid": False,
        "type": "custom"
    }
    oid = create_order(order)
    embed = make_embed("📦 Custom Order Logged", f"Item: `{item}`\nDescription: `{desc}`\nID: `{oid}`\nUse `-paid` after payment.")
    await ctx.send(embed=embed)
    await log_event(f"📝 Custom order #{oid} from {ctx.author}: {desc}")


@bot.command()
async def paid(ctx):
    orders = get_orders_by_user(ctx.author.id)
    unpaid = next((o for o in orders if not o["paid"]), None)
    if not unpaid:
        return await ctx.send("❌ No unpaid order.")
    update_order(unpaid["_id"], {"paid": True})
    await ctx.send(embed=make_embed("✅ Payment Confirmed", f"Order #{unpaid['_id']} marked paid."))
    if unpaid["type"] == "buy":
        stock = get_stock_item(unpaid["item"])
        update_stock_item(unpaid["item"], {"qty": stock["qty"] - unpaid["qty"]})
        await ctx.author.send(f"🎁 You received: `{unpaid['item']}` x{unpaid['qty']}")
    elif unpaid["type"] == "custom":
        await ctx.author.send(f"📦 Your order #{unpaid['_id']} is now marked paid. Staff will deliver it soon.")


@bot.command()
async def cancel(ctx, id: str = None):
    orders = get_orders_by_user(ctx.author.id)
    if id == "all":
        count = 0
        for o in orders:
            if not o["paid"]:
                cancel_order_by_id(o["_id"])
                count += 1
        return await ctx.send(f"✅ Cancelled {count} unpaid orders.")
    if id:
        cancel_order_by_id(ObjectId(id))
        return await ctx.send(f"✅ Cancelled order `{id}`.")
    last = next((o for o in reversed(orders) if not o["paid"]), None)
    if last:
        cancel_order_by_id(last["_id"])
        return await ctx.send(f"✅ Cancelled latest unpaid order #{last['_id']}.")
    await ctx.send("❌ No unpaid orders.")


@bot.command()
async def orderlist(ctx):
    orders = get_orders_by_user(ctx.author.id)
    if not orders:
        return await ctx.send("You have no orders yet.")
    desc = "\n".join([f"#{o['_id']} | {o['item']} x{o.get('qty',1)} | Paid: {o['paid']}" for o in orders])
    await ctx.send(embed=make_embed("📜 Your Orders", desc))


@bot.command()
async def claim(ctx, oid):
    order = get_order_by_id(ObjectId(oid))
    if not order or order["user"] != ctx.author.id:
        return await ctx.send("❌ Invalid order ID.")
    try:
        await ctx.author.send(f"📦 Resent delivery for order #{oid}: {order.get('item')}")
        delete_failed_dm(ObjectId(oid))
        await ctx.send("✅ Delivery retried in DM.")
    except:
        await ctx.send("⚠️ DM failed again. Check your privacy settings.")


@bot.command()
async def report(ctx, *, message):
    await log_event(f"🚨 Report from {ctx.author}: {message}")
    await ctx.send("✅ Report sent to staff.")


@bot.command()
async def test(ctx):
    await ctx.send(f"✅ Bot is online. You are {'whitelisted' if is_whitelisted(ctx.author) else 'a client'}.")


@bot.command()
async def help(ctx):
    await ctx.send("ℹ️ Use `-commands` to see all available commands.")


@bot.command(name="commands")
async def commands_list(ctx):
    cmds = {
        "📋 Clients": "-stock, -buy <item>, -order <item> <desc>, -paid, -cancel, -orderlist, -claim <id>, -report <msg>, -help, -commands, -test"
    }
    embed = make_embed("📖 All Commands", "")
    for k, v in cmds.items():
        embed.add_field(name=k, value=v, inline=False)
    await ctx.send(embed=embed)
  @bot.command()
async def bal(ctx):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    await ctx.send("💰 Use this command in your server:\n```$bals```")

@bot.command()
async def withdraw(ctx, amount: str, coin: str):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    await ctx.send(
        f"💸 To withdraw, copy and paste:\n```$tip {ctx.author.mention} {amount} {coin}```"
)
  # -----------------------------
# 🔐 WHITELIST-ONLY COMMANDS
# -----------------------------

@bot.command()
async def whitelist(ctx, role: discord.Role):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    if role.name not in whitelisted_roles:
        whitelisted_roles.append(role.name)
    await ctx.send(f"✅ `{role.name}` whitelisted.")

@bot.command()
async def unwhitelist(ctx, role: discord.Role):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    if role.name in whitelisted_roles:
        whitelisted_roles.remove(role.name)
    await ctx.send(f"✅ `{role.name}` removed from whitelist.")

@bot.command()
async def setprefix(ctx, prefix: str):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    bot.command_prefix = prefix
    await ctx.send(f"✅ Prefix set to `{prefix}`")


# -----------------------------
# 🎁 DISCOUNTS & REWARDS
# -----------------------------

@bot.command()
async def creatediscount(ctx, code: str, percent: int, uses: int):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    create_discount(code, percent, uses)
    await ctx.send(f"✅ Discount `{code}` created: {percent}% off, {uses} uses.")

@bot.command()
async def usediscount(ctx, code: str):
    disc = get_discount(code)
    if not disc or disc["uses"] <= 0:
        return await ctx.send("❌ Invalid or expired discount.")
    use_discount(code)
    await ctx.send(f"✅ Discount `{code}` applied ({disc['percent']}% off)")

@bot.command()
async def setrewardtrigger(ctx, orders: int, percent: int, uses: int):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    set_reward_trigger(orders, percent, uses)
    await ctx.send(f"✅ Reward trigger set: every `{orders}` orders → {percent}% off x{uses}")

@bot.command()
async def listrewards(ctx):
    rewards = reward_collection.find()
    msg = ""
    for r in rewards:
        msg += f"🎁 {r.get('orders')} orders → {r.get('percent')}% off ({r.get('uses')} uses)\n"
    await ctx.send(embed=make_embed("🎁 Rewards", msg or "No active rewards"))

@bot.command()
async def rewardstatus(ctx, member: discord.Member = None):
    member = member or ctx.author
    count = get_user_order_count(member.id)
    r = get_reward_trigger()
    if not r:
        return await ctx.send("❌ No reward system set.")
    percent = r["percent"]
    orders_needed = r["orders"]
    progress = count % orders_needed
    left = orders_needed - progress
    await ctx.send(embed=make_embed("🎯 Reward Progress",
        f"{member.mention} has completed `{count}` orders.\n"
        f"`{left}` more orders to unlock `{percent}%` discount."))


# -----------------------------
# 🪵 LOGGING COMMANDS
# -----------------------------

@bot.command()
async def forwardim(ctx, type: str):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    set_config(f"forward_{type}", ctx.channel.id)
    await ctx.send(f"✅ `{type}` messages will now be forwarded to {ctx.channel.mention}")

@bot.command()
async def sendlogs(ctx):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    logs = get_logs()
    msg = ""
    for log in logs[-10:]:
        msg += f"📝 {log['log']}\n"
    await ctx.send(embed=make_embed("🪵 Recent Logs", msg or "No logs yet."))
    from db_utils import (
    create_discount, get_discount, use_discount,
    set_reward_trigger, get_reward_trigger,
    get_user_order_count,
    log_event_to_db, get_logs,
    get_failed_deliveries, delete_failed_dm,
    log_payment, get_unmatched_payments,
)

@bot.command()
async def creatediscount(ctx, code: str, percent: int, uses: int):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    create_discount(code, percent, uses)
    await ctx.send(f"🎁 Created discount `{code}` for {percent}% off, usable {uses} times.")

@bot.command()
async def usediscount(ctx, code: str):
    d = get_discount(code)
    if not d or d["uses"] <= 0:
        return await ctx.send("❌ Invalid or expired discount code.")
    use_discount(code)
    await ctx.send(f"✅ Discount `{code}` used. {d['uses'] - 1} uses left.")

@bot.command()
async def setrewardtrigger(ctx, orders: int, percent: int, uses: int):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    set_reward_trigger(orders, percent, uses)
    await ctx.send(f"🎯 Auto-reward set: {percent}% off after {orders} orders, usable {uses} times.")

@bot.command()
async def listrewards(ctx):
    trigger = get_reward_trigger()
    if not trigger:
        return await ctx.send("❌ No rewards configured.")
    await ctx.send(f"🎁 Reward: {trigger['percent']}% after {trigger['orders']} orders, {trigger['uses']} uses.")

@bot.command()
async def rewardstatus(ctx, user: discord.User = None):
    user = user or ctx.author
    count = get_user_order_count(user.id)
    trigger = get_reward_trigger()
    if not trigger:
        return await ctx.send("❌ No reward system.")
    needed = trigger["orders"]
    await ctx.send(f"🎯 {user.mention} has {count} orders. {needed - count} left to get {trigger['percent']}% off.")

# Forward logs
@bot.command()
async def forwardim(ctx, type: str):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    valid_types = ["order", "report", "delivery"]
    if type not in valid_types:
        return await ctx.send("❌ Invalid type. Choose from: " + ", ".join(valid_types))
    set_config(f"forward_{type}", ctx.channel.id)
    await ctx.send(f"📤 Now forwarding `{type}` updates to {ctx.channel.mention}.")

@bot.command()
async def sendlogs(ctx):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    logs = get_logs()
    if not logs:
        return await ctx.send("📭 No logs found.")
    for l in logs[-10:]:  # Send latest 10 logs
        await ctx.send(f"📝 {l['log']}")

@bot.command()
async def failed(ctx):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    failures = get_failed_deliveries()
    if not failures:
        return await ctx.send("✅ No failed DMs.")
    for f in failures:
        await ctx.send(f"❗ Failed DM for order {f['order']} to user <@{f['user']}>")

@bot.command()
async def orphaned(ctx):
    if not is_whitelisted(ctx.author):
        return await ctx.send("❌ Not authorized.")
    payments = get_unmatched_payments()
    if not payments:
        return await ctx.send("✅ No unmatched payments.")
    for p in payments:
        await ctx.send(f"❔ Payment from <@{p['user']}>: {p['amount']} {p['coin']} (Not matched)")
