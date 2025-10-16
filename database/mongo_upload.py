"""
This script reads all CSV files from the data/ folder and inserts them into MongoDB.
"""

import os
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB config
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

# Initialize connection
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

def insert_csv_to_mongo(data_folder="../data"):
    """Read CSV files from data folder and insert into MongoDB."""
    csv_files = [f for f in os.listdir(data_folder) if f.endswith(".csv")]
    
    if not csv_files:
        print("⚠️ No CSV files found in the data folder.")
        return
    
    all_docs = []
    for file in csv_files:
        path = os.path.join(data_folder, file)
        print(f"📂 Reading: {path}")
        df = pd.read_csv(path)
        records = df.to_dict(orient="records")
        all_docs.extend(records)
    
    if all_docs:
        collection = db["company_data"]
        collection.insert_many(all_docs)
        print(f"✅ Inserted {len(all_docs)} records into MongoDB collection 'company_data'.")
    else:
        print("⚠️ No data found to insert.")

if __name__ == "__main__":
    insert_csv_to_mongo()
