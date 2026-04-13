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
entry_placeholders = {}

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

    name = get_clean_entry_value(name_entry)
    enrollment = get_clean_entry_value(enroll_entry)

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
    name = get_clean_entry_value(name_entry)
    email = get_clean_entry_value(email_entry).lower()
    phone = get_clean_entry_value(phone_entry)
    enrollment = get_clean_entry_value(enroll_entry)
    password = get_clean_entry_value(pass_entry)

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
        signup_otp_btn.config(
            text="Resend OTP",
            bg=THEMES[current_theme]["warn"],
            activebackground=THEMES[current_theme]["warn"],
            fg="white",
            activeforeground="white",
            command=resend_otp,
        )

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
    email = get_clean_entry_value(email_entry).lower()

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
    email = get_clean_entry_value(login_email_entry).lower()
    password = get_clean_entry_value(login_pass_entry)

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

screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()
root.geometry(f"{screen_w}x{screen_h}+0+0")
root.minsize(1000, 680)
root.resizable(True, True)

THEMES = {
    "light": {
        "root_bg": "#eaf7ff",
        "card_bg": "#f6fbff",
        "surface": "#ffffff",
        "text": "#1c2d3f",
        "muted_text": "#5b748e",
        "accent": "#1e88e5",
        "success": "#2e8b57",
        "warn": "#ef8e1a",
        "entry_border": "#bad7ea",
        "placeholder": "#8aa0b5",
        "notebook_tab": "#dbefff",
    },
    "soft_dark": {
        "root_bg": "#0d1218",
        "card_bg": "#121a23",
        "surface": "#1a2633",
        "text": "#e8f2ff",
        "muted_text": "#a9c0d7",
        "accent": "#5bb3ff",
        "success": "#59c38b",
        "warn": "#f3a73d",
        "entry_border": "#2c4158",
        "placeholder": "#7f97ae",
        "notebook_tab": "#213243",
    },
}

current_theme = "light"
root.configure(bg=THEMES[current_theme]["root_bg"])
current_mode = "signup"
is_animating = False


def add_labeled_entry(parent, label_text, placeholder, show=None):
    wrapper = tk.Frame(parent)
    label = tk.Label(wrapper, text=label_text, font=("Segoe UI", 12, "bold"), anchor="w")
    label.pack(fill="x", pady=(0, 4))

    entry_container = tk.Frame(wrapper)
    entry_container.pack(fill="x")

    entry = tk.Entry(entry_container, width=42, relief="flat", bd=0, font=("Segoe UI", 12))
    entry.pack(fill="x", ipady=7, padx=2, pady=2)

    real_show = show if show else ""
    is_placeholder_active = True

    entry_placeholders[str(entry)] = placeholder

    def apply_placeholder(*_):
        nonlocal is_placeholder_active
        if not entry.get().strip():
            entry.delete(0, "end")
            entry.insert(0, placeholder)
            entry.config(fg=THEMES[current_theme]["placeholder"], show="")
            is_placeholder_active = True

    def clear_placeholder(*_):
        nonlocal is_placeholder_active
        if entry.get() == placeholder:
            entry.delete(0, "end")
            entry.config(fg=THEMES[current_theme]["text"], show=real_show)
            is_placeholder_active = False

    def on_focus_in(*_):
        clear_placeholder()
        entry_container.configure(highlightbackground=THEMES[current_theme]["accent"], highlightcolor=THEMES[current_theme]["accent"])

    def on_focus_out(*_):
        apply_placeholder()
        entry_container.configure(highlightbackground=THEMES[current_theme]["entry_border"], highlightcolor=THEMES[current_theme]["entry_border"])

    toggle_btn = None
    is_visible = False
    if show:
        def toggle_password_visibility():
            nonlocal is_visible
            if entry.get() == placeholder:
                return
            is_visible = not is_visible
            entry.config(show="" if is_visible else "*")
            toggle_btn.config(text="🙈" if is_visible else "👁")

        toggle_btn = tk.Button(
            entry_container,
            text="👁",
            command=toggle_password_visibility,
            relief="flat",
            bd=0,
            padx=6,
            pady=2,
            cursor="hand2",
            font=("Segoe UI Emoji", 10),
        )
        toggle_btn.place(relx=1.0, rely=0.5, x=-6, y=0, anchor="e")
        entry.configure(highlightthickness=0)

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)
    apply_placeholder()

    entry_container.configure(highlightthickness=1, bd=0)

    wrapper._label = label
    wrapper._entry = entry
    wrapper._entry_container = entry_container
    wrapper._placeholder = placeholder
    wrapper._is_password = bool(show)
    wrapper._toggle_btn = toggle_btn
    return wrapper


def get_clean_entry_value(entry_widget):
    raw = entry_widget.get().strip()
    placeholder = entry_placeholders.get(str(entry_widget), "")
    if raw == placeholder:
        return ""
    return raw


root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

main_wrap = tk.Frame(root, padx=12, pady=12)
main_wrap.grid(row=0, column=0, sticky="nsew")
main_wrap.grid_rowconfigure(0, weight=1)
main_wrap.grid_columnconfigure(0, weight=1)

shadow = tk.Frame(main_wrap, bd=0)
shadow.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.88, relheight=0.92, x=8, y=8)

card = tk.Frame(main_wrap, padx=20, pady=16, relief="flat", bd=0)
card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.88, relheight=0.92)

card.grid_rowconfigure(0, weight=1)
card.grid_columnconfigure(0, weight=2)
card.grid_columnconfigure(1, weight=3)

side_panel = tk.Frame(card, padx=20, pady=20)
side_panel.grid(row=0, column=0, sticky="nsew")

forms_host = tk.Frame(card, padx=12, pady=12)
forms_host.grid(row=0, column=1, sticky="nsew")
forms_host.grid_rowconfigure(1, weight=1)
forms_host.grid_columnconfigure(0, weight=1)

forms_header = tk.Frame(forms_host)
forms_header.grid(row=0, column=0, sticky="ew", pady=(0, 8))

forms_viewport = tk.Frame(forms_host, bd=0, highlightthickness=0)
forms_viewport.grid(row=1, column=0, sticky="nsew")
forms_viewport.grid_propagate(False)

signup_tab = tk.Frame(forms_viewport, padx=14, pady=12)
login_tab = tk.Frame(forms_viewport, padx=14, pady=12)

# Scroll only the signup content area when it overflows.
signup_canvas = tk.Canvas(signup_tab, bd=0, highlightthickness=0)
signup_scrollbar = ttk.Scrollbar(signup_tab, orient="vertical", command=signup_canvas.yview)
signup_canvas.configure(yscrollcommand=signup_scrollbar.set)
signup_canvas.pack(side="left", fill="both", expand=True)
signup_scrollbar.pack(side="right", fill="y")
signup_content = tk.Frame(signup_canvas)
signup_canvas_window = signup_canvas.create_window((0, 0), window=signup_content, anchor="nw")


def update_signup_scroll_region(_=None):
    signup_canvas.configure(scrollregion=signup_canvas.bbox("all"))
    signup_canvas.itemconfig(signup_canvas_window, width=signup_canvas.winfo_width())
    bbox = signup_canvas.bbox("all")
    needs_scroll = bool(bbox and bbox[3] > signup_canvas.winfo_height() + 1)
    if needs_scroll:
        if not signup_scrollbar.winfo_ismapped():
            signup_scrollbar.pack(side="right", fill="y")
    else:
        if signup_scrollbar.winfo_ismapped():
            signup_scrollbar.pack_forget()
        signup_canvas.yview_moveto(0)


def on_signup_mousewheel(event):
    if not signup_tab.winfo_ismapped():
        return
    signup_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


signup_canvas.bind("<Configure>", update_signup_scroll_region)
signup_content.bind("<Configure>", update_signup_scroll_region)
signup_canvas.bind("<MouseWheel>", on_signup_mousewheel)
signup_content.bind("<MouseWheel>", on_signup_mousewheel)

overlay_panel = tk.Frame(side_panel, padx=20, pady=20)
overlay_panel.place(relx=0.0, rely=0.0, relwidth=0.98, relheight=0.98)

overlay_title = tk.Label(overlay_panel, font=("Segoe UI", 24, "bold"), anchor="w", justify="left")
overlay_title.pack(fill="x", pady=(4, 8))

overlay_desc = tk.Label(overlay_panel, font=("Segoe UI", 12), anchor="w", justify="left", wraplength=360)
overlay_desc.pack(fill="x", pady=(0, 14))

overlay_switch_btn = tk.Button(overlay_panel, padx=12, pady=8, relief="flat", cursor="hand2")
overlay_switch_btn.pack(anchor="w")

theme_btn = tk.Button(forms_header, text="Switch to Dark", padx=10, pady=6, relief="flat")
theme_btn.pack(anchor="e")

def toggle_theme():
    global current_theme
    current_theme = "soft_dark" if current_theme == "light" else "light"
    apply_theme()


def set_overlay_content(mode):
    if mode == "signup":
        overlay_title.config(text="Welcome Back")
        overlay_desc.config(text="Already have an account? Sign in to continue tracking and managing your attendance.")
        overlay_switch_btn.config(text="Go To Login", command=lambda: slide_to_mode("login"))
    else:
        overlay_title.config(text="Create Account")
        overlay_desc.config(text="Join the attendance platform and register with your details to get started.")
        overlay_switch_btn.config(text="Go To Signup", command=lambda: slide_to_mode("signup"))


def place_form_panels(mode):
    width = max(1, forms_viewport.winfo_width())
    height = max(1, forms_viewport.winfo_height())
    if mode == "signup":
        signup_tab.place(x=0, y=0, width=width, height=height)
        login_tab.place(x=width, y=0, width=width, height=height)
    else:
        signup_tab.place(x=-width, y=0, width=width, height=height)
        login_tab.place(x=0, y=0, width=width, height=height)


def slide_to_mode(target_mode):
    global current_mode, is_animating

    if is_animating or target_mode == current_mode:
        return

    width = forms_viewport.winfo_width()
    height = forms_viewport.winfo_height()
    if width <= 1 or height <= 1:
        root.after(50, lambda: slide_to_mode(target_mode))
        return

    is_animating = True
    start_signup = signup_tab.winfo_x()
    start_login = login_tab.winfo_x()
    end_signup = 0 if target_mode == "signup" else -width
    end_login = width if target_mode == "signup" else 0

    steps = 28
    delay = 12

    def animate(step=0):
        global current_mode, is_animating
        nonlocal start_signup, start_login
        t = step / steps
        eased = (3 * t * t) - (2 * t * t * t)  # smoothstep ease-in-out
        x_signup = int(start_signup + (end_signup - start_signup) * eased)
        x_login = int(start_login + (end_login - start_login) * eased)
        signup_tab.place(x=x_signup, y=0, width=width, height=height)
        login_tab.place(x=x_login, y=0, width=width, height=height)

        if step < steps:
            root.after(delay, lambda: animate(step + 1))
            return

        current_mode = target_mode
        set_overlay_content(current_mode)
        is_animating = False

    animate(0)


def on_forms_resize(_):
    if not is_animating:
        place_form_panels(current_mode)


forms_viewport.bind("<Configure>", on_forms_resize)


theme_btn.configure(command=toggle_theme)

# ---- Signup Form ----
signup_title = tk.Label(signup_content, text="Sign Up", font=("Segoe UI", 20, "bold"), anchor="w")
signup_title.pack(fill="x", pady=(0, 6))

name_field = add_labeled_entry(signup_content, "Full Name", "Enter your full name")
name_field.pack(fill="x", pady=5)
name_entry = name_field._entry

email_field = add_labeled_entry(signup_content, "Email", "Enter your email address")
email_field.pack(fill="x", pady=5)
email_entry = email_field._entry

phone_field = add_labeled_entry(signup_content, "Phone", "Enter your phone number")
phone_field.pack(fill="x", pady=5)
phone_entry = phone_field._entry

enroll_field = add_labeled_entry(signup_content, "Enrollment Number", "Enter enrollment number")
enroll_field.pack(fill="x", pady=5)
enroll_entry = enroll_field._entry

pass_field = add_labeled_entry(signup_content, "Password", "Create a password", show="*")
pass_field.pack(fill="x", pady=5)
pass_entry = pass_field._entry

image_row = tk.Frame(signup_content)
image_row.pack(fill="x", pady=(8, 6))

choose_img_btn = tk.Button(image_row, text="Choose Profile Image", command=choose_image, padx=10, pady=6, relief="flat")
choose_img_btn.pack(side="left")

img_label = tk.Label(image_row, text="No image selected", anchor="w", font=("Segoe UI", 9))
img_label.pack(side="left", padx=10)

face_btn = tk.Button(signup_content, text="Face Recognition (Compulsory)", command=capture_face_now, padx=10, pady=7, relief="flat")
face_btn.pack(fill="x", pady=(4, 8))

otp_actions = tk.Frame(signup_content)
otp_actions.pack(fill="x", pady=(0, 6))

signup_otp_btn = tk.Button(otp_actions, text="Sign Up + Send OTP", command=signup, padx=10, pady=8, relief="flat")
signup_otp_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

verify_btn = tk.Button(otp_actions, text="Verify OTP", command=verify_otp_ui, padx=10, pady=8, relief="flat")
verify_btn.pack(side="left", fill="x", expand=True)

otp_field = add_labeled_entry(signup_content, "OTP", "Enter OTP")
otp_field.pack(fill="x", pady=(2, 2))
otp_entry = otp_field._entry

# ---- Login Form ----
login_title = tk.Label(login_tab, text="Login", font=("Segoe UI", 20, "bold"), anchor="w")
login_title.pack(fill="x", pady=(0, 10))

login_email_field = add_labeled_entry(login_tab, "Email", "Enter your email")
login_email_field.pack(fill="x", pady=6)
login_email_entry = login_email_field._entry

login_pass_field = add_labeled_entry(login_tab, "Password", "Enter your password", show="*")
login_pass_field.pack(fill="x", pady=6)
login_pass_entry = login_pass_field._entry

login_btn = tk.Button(login_tab, text="Login", command=login, padx=10, pady=9, relief="flat")
login_btn.pack(fill="x", pady=(10, 4))


set_overlay_content(current_mode)


def apply_theme():
    colors = THEMES[current_theme]
    root.configure(bg=colors["root_bg"])
    main_wrap.configure(bg=colors["root_bg"])
    shadow.configure(bg="#97abc2" if current_theme == "light" else "#070b0f")
    card.configure(bg=colors["card_bg"], highlightbackground=colors["entry_border"], highlightthickness=1)

    side_panel.configure(bg=colors["card_bg"])
    forms_host.configure(bg=colors["card_bg"])
    forms_header.configure(bg=colors["card_bg"])
    forms_viewport.configure(bg=colors["card_bg"])
    overlay_panel.configure(bg=colors["accent"])
    overlay_title.configure(bg=colors["accent"], fg="white")
    overlay_desc.configure(bg=colors["accent"], fg="#e8f4ff")
    overlay_switch_btn.configure(
        bg="white",
        fg=colors["accent"],
        activebackground="#ecf5ff",
        activeforeground=colors["accent"],
        font=("Segoe UI", 10, "bold"),
        bd=0,
        highlightthickness=0,
    )

    signup_tab.configure(bg=colors["surface"])
    login_tab.configure(bg=colors["surface"])
    image_row.configure(bg=colors["surface"])
    otp_actions.configure(bg=colors["surface"])
    signup_title.configure(bg=colors["surface"], fg=colors["text"])
    login_title.configure(bg=colors["surface"], fg=colors["text"])

    form_fields = [
        name_field, email_field, phone_field, enroll_field, pass_field,
        otp_field, login_email_field, login_pass_field,
    ]
    for field in form_fields:
        field.configure(bg=colors["surface"])
        field._label.configure(bg=colors["surface"], fg=colors["text"])
        field._entry_container.configure(
            bg="#ffffff" if current_theme == "light" else "#0f1720",
            highlightbackground=colors["entry_border"],
            highlightcolor=colors["accent"],
            highlightthickness=1,
        )
        field._entry.configure(
            bg="#ffffff" if current_theme == "light" else "#0f1720",
            fg=colors["text"],
            insertbackground=colors["text"],
            bd=0,
            relief="flat",
        )
        if field._entry.get() == field._placeholder:
            field._entry.configure(fg=colors["placeholder"], show="")
        elif field._is_password:
            field._entry.configure(show="*")
        if field._toggle_btn is not None:
            field._toggle_btn.configure(
                bg="#ffffff" if current_theme == "light" else "#0f1720",
                fg=colors["muted_text"],
                activebackground="#ffffff" if current_theme == "light" else "#0f1720",
                activeforeground=colors["accent"],
            )

    choose_img_btn.configure(bg=colors["accent"], fg="white", activebackground=colors["accent"], activeforeground="white")
    face_btn.configure(bg=colors["warn"], fg="white", activebackground=colors["warn"], activeforeground="white")
    signup_btn_color = colors["warn"] if signup_otp_btn.cget("text") == "Resend OTP" else colors["success"]
    signup_otp_btn.configure(bg=signup_btn_color, fg="white", activebackground=signup_btn_color, activeforeground="white")
    verify_btn.configure(bg=colors["accent"], fg="white", activebackground=colors["accent"], activeforeground="white")
    login_btn.configure(bg=colors["accent"], fg="white", activebackground=colors["accent"], activeforeground="white")
    theme_btn.configure(
        bg=colors["surface"],
        fg=colors["text"],
        activebackground=colors["surface"],
        activeforeground=colors["text"],
        highlightbackground=colors["entry_border"],
        highlightthickness=1,
    )
    theme_btn.config(text="Switch to Light" if current_theme == "soft_dark" else "Switch to Dark")

    img_label.configure(bg=colors["surface"], fg=colors["muted_text"])

    # Visual polish: rounded-feel controls and clipping-safe containers.
    rounded_buttons = [
        choose_img_btn, face_btn, signup_otp_btn, verify_btn,
        login_btn, overlay_switch_btn, theme_btn,
    ]
    for b in rounded_buttons:
        b.configure(relief="flat", bd=0, highlightthickness=0, cursor="hand2")

    signup_tab.configure(highlightbackground=colors["entry_border"], highlightthickness=1)
    login_tab.configure(highlightbackground=colors["entry_border"], highlightthickness=1)


apply_theme()
place_form_panels(current_mode)

root.mainloop()