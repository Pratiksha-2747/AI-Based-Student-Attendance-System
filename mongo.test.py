from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# paste your URI from Atlas here (replace <db_password>)
uri = "mongodb+srv://pratikshajani70_db_user:OESKWrOsMwLzdF5P@attendance-system.oggo2zd.mongodb.net/?retryWrites=true&w=majority&appName=attendance-system"

client = MongoClient(uri, server_api=ServerApi("1"))

try:
    client.admin.command("ping")
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print("❌ Connection failed:")
    print(e)