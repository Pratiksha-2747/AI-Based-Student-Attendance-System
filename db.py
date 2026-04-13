import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
import certifi

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "attendance_system")

print("DB:", MONGO_DB)
print("URI startswith:", (MONGO_URI or "")[:25])

if not MONGO_URI:
    raise ValueError("MONGO_URI missing in .env")

# single client with TLS (fixes handshake issues)
client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=30000
)

# connectivity check
client.admin.command("ping")

db = client[MONGO_DB]

students_col = db["students"]
photos_col = db["photos"]
attendance_col = db["attendance"]
users_col = db["users"]  # needed by auth modules

students_col.create_index([("enrollment", ASCENDING)], unique=True)
photos_col.create_index([("enrollment", ASCENDING), ("captured_at", ASCENDING)])
attendance_col.create_index(
    [("enrollment", ASCENDING), ("subject", ASCENDING), ("date", ASCENDING)],
    unique=True
)
users_col.create_index([("email", ASCENDING)], unique=True)


def upsert_student(enrollment: int, name: str):
    students_col.update_one(
        {"enrollment": enrollment},
        {
            "$set": {"name": name, "updated_at": datetime.utcnow()},
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True
    )


def save_photo_meta(enrollment: int, name: str, photo_path: str):
    photos_col.insert_one({
        "enrollment": enrollment,
        "name": name,
        "photo_path": photo_path,
        "captured_at": datetime.utcnow()
    })


def save_attendance(enrollment: int, name: str, subject: str, dt: datetime):
    enrollment = int(enrollment)
    subject = subject.strip().upper()
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M:%S")

    attendance_col.update_one(
        {"enrollment": enrollment, "subject": subject, "date": date_str},
        {
            "$set": {
                "name": name,
                "time": time_str,
                "status": "present",
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow(),
                "date": date_str,
                "subject": subject,
                "enrollment": enrollment,
            },
        },
        upsert=True
    )