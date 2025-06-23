# db_utils.py

from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load env and connect
load_dotenv()
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["marketplace"]

# Collections
stock_collection = db["stock"]
orders_collection = db["orders"]
log_collection = db["logs"]
failed_dm_collection = db["failed_dms"]
hidden_collection = db["hidden_stock"]
config_collection = db["config"]
discount_collection = db["discounts"]
reward_collection = db["rewards"]
payment_collection = db["payments"]  # For payment tracking

# ---------------------
# 📦 STOCK MANAGEMENT
# ---------------------

def get_stock():
    return list(stock_collection.find())

def get_stock_item(name):
    return stock_collection.find_one({"name": name})

def update_stock_item(name, updates):
    return stock_collection.update_one({"name": name}, {"$set": updates})

def add_stock_item(name, price, qty, type="instant"):
    return stock_collection.update_one({"name": name}, {
        "$set": {"price": price, "type": type},
        "$inc": {"qty": qty}
    }, upsert=True)

def clear_stock_item(name):
    return stock_collection.update_one({"name": name}, {"$set": {"qty": 0}})

# ---------------------
# 📋 ORDER MANAGEMENT
# ---------------------

def create_order(order):
    return orders_collection.insert_one(order).inserted_id

def get_order_by_id(oid):
    return orders_collection.find_one({"_id": oid})

def update_order(oid, updates):
    return orders_collection.update_one({"_id": oid}, {"$set": updates})

def get_orders_by_user(user_id):
    return list(orders_collection.find({"user": user_id}))

def cancel_order_by_id(oid):
    return orders_collection.delete_one({"_id": oid})

def get_unpaid_orders():
    return list(orders_collection.find({"paid": False}))

# ---------------------
# 🪵 LOGGING
# ---------------------

def log_event_to_db(entry):
    return log_collection.insert_one({"log": entry})

def get_logs():
    return list(log_collection.find())

# ---------------------
# ❌ DM FAILURES
# ---------------------

def log_failed_dm(oid, user_id):
    return failed_dm_collection.insert_one({"order": oid, "user": user_id})

def get_failed_deliveries():
    return list(failed_dm_collection.find())

def delete_failed_dm(oid):
    return failed_dm_collection.delete_one({"order": oid})

# ---------------------
# 🔒 HIDDEN STOCK
# ---------------------

def add_hidden_stock(name, price):
    return hidden_collection.insert_one({"name": name, "price": price, "items": []})

def add_item_to_hidden(name, content):
    return hidden_collection.update_one({"name": name}, {"$push": {"items": content}})

def get_hidden_stock():
    return list(hidden_collection.find())

def get_hidden_item(name):
    item = hidden_collection.find_one({"name": name})
    if item and item["items"]:
        content = item["items"].pop(0)
        hidden_collection.update_one({"name": name}, {"$set": {"items": item["items"]}})
        return content
    return None

# ---------------------
# ⚙️ CONFIG SYSTEM
# ---------------------

def set_config(key, value):
    config_collection.update_one({"name": key}, {"$set": {"value": value}}, upsert=True)

def get_config(key):
    doc = config_collection.find_one({"name": key})
    return doc["value"] if doc else None

# ---------------------
# 🎁 DISCOUNTS & REWARDS
# ---------------------

def create_discount(code, percent, uses):
    discount_collection.insert_one({"code": code, "percent": percent, "uses": uses})

def use_discount(code):
    return discount_collection.update_one({"code": code, "uses": {"$gt": 0}}, {"$inc": {"uses": -1}})

def get_discount(code):
    return discount_collection.find_one({"code": code})

def set_reward_trigger(orders, percent, uses):
    reward_collection.update_one({"trigger": True}, {
        "$set": {"orders": orders, "percent": percent, "uses": uses}
    }, upsert=True)

def get_reward_trigger():
    return reward_collection.find_one({"trigger": True})

def get_user_order_count(user_id):
    return orders_collection.count_documents({"user": user_id})

# ---------------------
# 💰 PAYMENT MATCHING (Orphaned)
# ---------------------

def log_payment(user_id, amount, coin, matched=False):
    payment_collection.insert_one({
        "user": user_id,
        "amount": amount,
        "coin": coin,
        "matched": matched
    })

def get_unmatched_payments():
    return list(payment_collection.find({"matched": False}))

def mark_payment_matched(payment_id):
    return payment_collection.update_one({"_id": payment_id}, {"$set": {"matched": True}})
