import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import takeImage
import trainImage
from auth_db import set_face_registered

from auth_db import (
    create_user,
    set_otp,
    verify_otp,
    login_user,
    get_user_by_email,
    get_attendance_summary,
)
from otp_service import generate_otp, send_otp_email

selected_image_path = None
pending_email = None
face_capture_done = False
otp_sent = False

def upsert_student_csv(enrollment: int, name: str):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    studentdetail_path = os.path.join(BASE_DIR, "StudentDetails", "studentdetails.csv")
    os.makedirs(os.path.dirname(studentdetail_path), exist_ok=True)

    import csv
    rows = []
    exists = False

    if os.path.exists(studentdetail_path):
        with open(studentdetail_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if str(r.get("Enrollment", "")).strip() == str(enrollment):
                    r["Name"] = str(name).strip()
                    exists = True
                rows.append(r)

    if not exists:
        rows.append({"Enrollment": str(enrollment), "Name": str(name).strip()})

    with open(studentdetail_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Enrollment", "Name"])
        writer.writeheader()
        writer.writerows(rows)

def choose_image():
    global selected_image_path
    path = filedialog.askopenfilename(
        title="Select Profile Image",
        filetypes=[("Image Files", "*.png *.jpg *.jpeg")]
    )
    if path:
        selected_image_path = path
        img_label.config(text=os.path.basename(path))

def capture_face_now():
    global face_capture_done

    name = name_entry.get().strip()
    enrollment = enroll_entry.get().strip()

    if not name or not enrollment:
        messagebox.showerror("Error", "Enter Name and Enrollment first.")
        return
    if not enrollment.isdigit():
        messagebox.showerror("Error", "Enrollment must be numeric.")
        return

    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        haarcasecade_path = os.path.join(BASE_DIR, "haarcascade_frontalface_default.xml")
        trainimage_path = os.path.join(BASE_DIR, "TrainingImage")
        trainimagelabel_path = os.path.join(BASE_DIR, "TrainingImageLabel", "Trainner.yml")

        captured = takeImage.TakeImageMultiAngle(
            enrollment=int(enrollment),
            name=name,
            haarcascade_path=haarcasecade_path,
            trainimage_path=trainimage_path
        )

        if captured < 20:
            face_capture_done = False
            messagebox.showwarning("Warning", f"Only {captured} samples captured. Please retry.")
            return

        dummy_msg = type("obj", (), {"configure": lambda *args, **kwargs: None})()
        trainImage.TrainImage(
            haarcasecade_path,
            trainimage_path,
            trainimagelabel_path,
            dummy_msg,
            lambda x: None
        )

        face_capture_done = True
        messagebox.showinfo("Success", "Face registration completed successfully.")

    except Exception as e:
        face_capture_done = False
        messagebox.showerror("Error", f"Face capture failed: {e}")

def signup():
    global pending_email, otp_sent
    name = name_entry.get().strip()
    email = email_entry.get().strip().lower()
    phone = phone_entry.get().strip()
    enrollment = enroll_entry.get().strip()
    password = pass_entry.get().strip()

    if not all([name, email, phone, enrollment, password, selected_image_path]):
        messagebox.showerror("Error", "Please fill all fields and choose profile image.")
        return

    if not enrollment.isdigit():
        messagebox.showerror("Error", "Enrollment must be numeric.")
        return

    # compulsory face capture check
    if not face_capture_done:
        messagebox.showerror("Error", "Face recognition is compulsory. Please click 'Face Recognition' first.")
        return

    try:
        if not otp_sent:
            # first time signup create user
            create_user(name, email, phone, password, selected_image_path, int(enrollment))
            upsert_student_csv(int(enrollment), name)   # ✅ HERE

        otp = generate_otp()
        set_otp(email, otp)
        send_otp_email(email, otp)
        pending_email = email
        otp_sent = True

        messagebox.showinfo("OTP Sent", f"OTP sent to {email}")

        # change button text to resend
        signup_otp_btn.config(text="Resend OTP", bg="orange", command=resend_otp)

    except Exception as e:
        messagebox.showerror("Error", f"OTP flow failed: {e}")

def verify_otp_ui():
    if not pending_email:
        messagebox.showerror("Error", "Please sign up first.")
        return

    otp = otp_entry.get().strip()
    ok, msg = verify_otp(pending_email, otp)
    if ok:
        messagebox.showinfo("Success", msg)
    else:
        messagebox.showerror("Error", msg)

def resend_otp():
    global pending_email, otp_sent
    email = email_entry.get().strip().lower()

    if not email:
        messagebox.showerror("Error", "Enter email first.")
        return

    if not otp_sent:
        messagebox.showerror("Error", "Please click 'Sign Up + Send OTP' first.")
        return

    try:
        otp = generate_otp()
        set_otp(email, otp)
        send_otp_email(email, otp)
        pending_email = email
        messagebox.showinfo("OTP Sent", f"New OTP sent to {email}")
    except Exception as e:
        messagebox.showerror("Error", f"Resend OTP failed: {e}")


def open_dashboard(email):
    user = get_user_by_email(email)
    if not user:
        messagebox.showerror("Error", "User not found")
        return

    enrollment = user.get("enrollment")
    if not enrollment:
        messagebox.showerror("Error", "Enrollment not linked with this account")
        return

    data = get_attendance_summary(int(enrollment))

    dash = tk.Toplevel(root)
    dash.title("My Attendance Dashboard")
    dash.geometry("980x700")
    dash.configure(bg="#f5f5f5")

    tk.Label(
        dash,
        text=f"Welcome, {user.get('name', 'Student')}",
        font=("Arial", 16, "bold"),
        bg="#f5f5f5"
    ).pack(pady=8)

    tk.Label(dash, text=f"Attendance %: {data['percentage']}%", font=("Arial", 13), bg="#f5f5f5").pack()
    tk.Label(dash, text=f"Attended Classes: {data['present']}", font=("Arial", 12), bg="#f5f5f5").pack()
    tk.Label(dash, text=f"Absent Lectures: {data['absent']}", font=("Arial", 12), bg="#f5f5f5").pack()

    # -------- Subject-wise Summary --------
    tk.Label(
        dash,
        text="Subject-wise Attendance",
        font=("Arial", 12, "bold"),
        bg="#f5f5f5"
    ).pack(pady=(12, 4))

    sub_cols = ("subject", "attended", "absent", "total")
    sub_tree = ttk.Treeview(dash, columns=sub_cols, show="headings", height=6)

    for c in sub_cols:
        sub_tree.heading(c, text=c.capitalize())
        sub_tree.column(c, width=220 if c == "subject" else 120)

    sub_tree.pack(fill="x", padx=12, pady=6)

    for s in data.get("subject_summary", []):
        sub_tree.insert(
            "",
            "end",
            values=(s["subject"], s["attended"], s["absent"], s["total"])
        )

    # -------- Detailed Attendance Records --------
    tk.Label(
        dash,
        text="Detailed Attendance Records (Latest First)",
        font=("Arial", 12, "bold"),
        bg="#f5f5f5"
    ).pack(pady=(10, 4))

    columns = ("subject", "date", "time", "status")
    tree = ttk.Treeview(dash, columns=columns, show="headings", height=12)

    for c in columns:
        tree.heading(c, text=c.capitalize())
        tree.column(c, width=240 if c == "subject" else 160)

    tree.pack(fill="both", expand=True, padx=12, pady=8)

    for r in data["records"]:  # sorted by date/time desc in auth_db.py
        tree.insert(
            "",
            "end",
            values=(
                r.get("subject", ""),
                r.get("date", ""),
                r.get("time", ""),
                r.get("status", "present")
            )
        )

def login():
    email = login_email_entry.get().strip().lower()
    password = login_pass_entry.get().strip()

    if not email or not password:
        messagebox.showerror("Login Failed", "Please enter email and password.")
        return

    ok, msg = login_user(email, password)
    if ok:
        messagebox.showinfo("Login Success", msg)
        open_dashboard(email)
    else:
        messagebox.showerror("Login Failed", msg)


# ---------------- UI ----------------
root = tk.Tk()
root.title("Auth System - Attendance")
root.geometry("720x650")
root.configure(bg="#1c1c1c")

tk.Label(root, text="Sign Up", bg="#1c1c1c", fg="yellow", font=("Verdana", 18, "bold")).pack(pady=10)

name_entry = tk.Entry(root, width=42)
name_entry.pack(pady=5)
name_entry.insert(0, "Name")

email_entry = tk.Entry(root, width=42)
email_entry.pack(pady=5)
email_entry.insert(0, "Email")

phone_entry = tk.Entry(root, width=42)
phone_entry.pack(pady=5)
phone_entry.insert(0, "Phone")

enroll_entry = tk.Entry(root, width=42)
enroll_entry.pack(pady=5)
enroll_entry.insert(0, "Enrollment Number")

pass_entry = tk.Entry(root, width=42, show="*")
pass_entry.pack(pady=5)

tk.Button(root, text="Choose Profile Image", command=choose_image).pack(pady=6)
img_label = tk.Label(root, text="No image selected", bg="#1c1c1c", fg="white")
img_label.pack()

tk.Button(root, text="Face Recognition (Compulsory)", command=capture_face_now, bg="orange", fg="black").pack(pady=8)

signup_otp_btn = tk.Button(root, text="Sign Up + Send OTP", command=signup, bg="green", fg="white")
signup_otp_btn.pack(pady=8)

otp_entry = tk.Entry(root, width=24)
otp_entry.pack(pady=5)
otp_entry.insert(0, "Enter OTP")

tk.Button(root, text="Verify OTP", command=verify_otp_ui, bg="blue", fg="white").pack(pady=8)

tk.Label(root, text="Login", bg="#1c1c1c", fg="yellow", font=("Verdana", 16, "bold")).pack(pady=10)

login_email_entry = tk.Entry(root, width=42)
login_email_entry.pack(pady=5)
login_email_entry.insert(0, "Email")

login_pass_entry = tk.Entry(root, width=42, show="*")
login_pass_entry.pack(pady=5)

tk.Button(root, text="Login", command=login, bg="purple", fg="white").pack(pady=12)

root.mainloop()