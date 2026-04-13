import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
import bcrypt
import certifi

load_dotenv()


MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "attendance_system")

print("DB:", MONGO_DB)
print("URI startswith:", (MONGO_URI or "")[:25])

client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=30000
)
db = client[MONGO_DB]
users_col = db["users"]
attendance_col = db["attendance"]

# keep unique constraints
users_col.create_index([("email", ASCENDING)], unique=True)
users_col.create_index([("phone", ASCENDING)], unique=True)
# optional unique enrollment for one account per student
users_col.create_index(
    [("enrollment", ASCENDING)],
    unique=True,
    partialFilterExpression={"enrollment": {"$type": "int"}}
)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

# keeps compatibility with old call (without enrollment) and new call (with enrollment)
def create_user(name, email, phone, password, profile_image_path, enrollment=None):
    doc = {
        "name": name.strip(),
        "email": email.strip().lower(),
        "phone": phone.strip(),
        "password_hash": hash_password(password),
        "profile_image_path": profile_image_path,
        "is_verified": False,
        "otp_code": None,
        "otp_expiry": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    if enrollment is not None and str(enrollment).strip() != "":
        doc["enrollment"] = int(enrollment)

    users_col.insert_one(doc)

def set_otp(email, otp_code, minutes=5):
    users_col.update_one(
        {"email": email.lower()},
        {
            "$set": {
                "otp_code": str(otp_code),
                "otp_expiry": datetime.utcnow() + timedelta(minutes=minutes),
                "updated_at": datetime.utcnow(),
            }
        },
    )

def verify_otp(email, otp):
    user = users_col.find_one({"email": email.lower()})
    if not user:
        return False, "User not found"
    if not user.get("otp_code") or not user.get("otp_expiry"):
        return False, "OTP not generated"
    if datetime.utcnow() > user["otp_expiry"]:
        return False, "OTP expired"
    if str(user["otp_code"]) != str(otp):
        return False, "Invalid OTP"

    users_col.update_one(
        {"email": email.lower()},
        {
            "$set": {"is_verified": True, "updated_at": datetime.utcnow()},
            "$unset": {"otp_code": "", "otp_expiry": ""},
        },
    )
    return True, "Verified successfully"

def login_user(email, password):
    user = users_col.find_one({"email": email.lower()})
    if not user:
        return False, "User not found"
    if not user.get("is_verified"):
        return False, "Please verify OTP first"
    if not verify_password(password, user["password_hash"]):
        return False, "Invalid password"
    return True, f"Welcome {user['name']}"

def get_user_by_email(email):
    return users_col.find_one({"email": email.lower()})

def get_attendance_summary(enrollment: int):
    e_int = int(enrollment)
    e_str = str(enrollment)

    # fetch all attendance rows for this student (int or str enrollment)
    records = list(
        attendance_col.find({
            "$or": [{"enrollment": e_int}, {"enrollment": e_str}]
        }).sort([("date", -1), ("time", -1)])
    )

    # overall stats
    total = len(records)
    present = sum(1 for r in records if r.get("status", "present") == "present")
    absent = sum(1 for r in records if r.get("status") == "absent")
    percentage = (present / total * 100) if total > 0 else 0.0

    # subject-wise count
    subject_map = {}
    for r in records:
        sub = r.get("subject", "Unknown")
        if sub not in subject_map:
            subject_map[sub] = {"subject": sub, "attended": 0, "absent": 0, "total": 0}
        subject_map[sub]["total"] += 1
        if r.get("status", "present") == "present":
            subject_map[sub]["attended"] += 1
        else:
            subject_map[sub]["absent"] += 1

    subject_summary = sorted(subject_map.values(), key=lambda x: x["subject"].lower())

    return {
        "total": total,
        "present": present,
        "absent": absent,
        "percentage": round(percentage, 2),
        "records": records,
        "subject_summary": subject_summary
    }

def set_face_registered(email: str, value: bool = True):
    users_col.update_one(
        {"email": email.lower().strip()},
        {"$set": {"face_registered": value, "updated_at": datetime.utcnow()}}
    )

students_col = db["students"]

def upsert_student(enrollment: int, name: str, email: str, phone: str):
    students_col.update_one(
        {"enrollment": int(enrollment)},
        {"$set": {
            "enrollment": int(enrollment),
            "name": name.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
            "updated_at": datetime.utcnow()
        }},
        upsert=True
    )