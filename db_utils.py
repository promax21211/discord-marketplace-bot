from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["marketplace"]
stock_col = db["stock"]
orders_col = db["orders"]
rewards_col = db["rewards"]

# --- STOCK FUNCTIONS ---
def get_stock():
    return list(stock_col.find())

def get_stock_item(name):
    return stock_col.find_one({"name": name})

def update_stock_item(name, update):
    return stock_col.update_one({"name": name}, {"$set": update})

def add_stock_item(name, price, qty, stock_type):
    return stock_col.insert_one({
        "name": name,
        "price": price,
        "qty": qty,
        "type": stock_type
    })

def clear_stock_item(name):
    return stock_col.delete_one({"name": name})


# --- ORDER FUNCTIONS ---
def create_order(data):
    return orders_col.insert_one(data)

def update_order(oid, update):
    return orders_col.update_one({"_id": oid}, {"$set": update})

def get_order_by_id(oid):
    return orders_col.find_one({"_id": oid})

def get_orders_by_user(user_id):
    return list(orders_col.find({"user": user_id}))

def cancel_order_by_id(oid):
    return orders_col.delete_one({"_id": oid})
