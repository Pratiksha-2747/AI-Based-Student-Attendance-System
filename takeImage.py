import csv
import os, cv2
from datetime import datetime

# Mongo helpers
from db import upsert_student, save_photo_meta
import cv2
import os
import time


def TakeImageMultiAngle(enrollment, name, haarcascade_path, trainimage_path, message_label=None):
    enrollment = str(enrollment).strip()
    name = str(name).strip()

    if not enrollment or not name:
        raise ValueError("Enrollment and Name are required")

    if not os.path.exists(trainimage_path):
        os.makedirs(trainimage_path)

    detector = cv2.CascadeClassifier(haarcascade_path)
    cam = cv2.VideoCapture(0)
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")

    folder_name = f"{safe_name}_{enrollment}"
    student_dir = os.path.join(trainimage_path, folder_name)
    os.makedirs(student_dir, exist_ok=True)

    phases = [
        ("FRONT", 20),
        ("LEFT", 15),
        ("RIGHT", 15),
        ("UP", 10),
        ("DOWN", 10),
        ("FAR", 15),
    ]

    sample_num = 0
    phase_idx = 0
    phase_count = 0
    total_required = sum(x[1] for x in phases)

    while True:
        ret, img = cam.read()
        if not ret:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5, minSize=(80, 80))

        phase_name, phase_limit = phases[phase_idx]

        cv2.putText(img, f"Phase: {phase_name}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2)
        cv2.putText(img, f"Captured: {sample_num}/{total_required}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)

        for (x, y, w, h) in faces:
            face = gray[y:y+h, x:x+w]

            # quality checks
            lap_var = cv2.Laplacian(face, cv2.CV_64F).var()    # sharpness
            brightness = face.mean()

            if lap_var < 40:   # too blurry
                continue
            if brightness < 35 or brightness > 220:  # too dark/too bright
                continue

            sample_num += 1
            phase_count += 1

            file_name = f"img_{sample_num:03d}.jpg"
            save_path = os.path.join(student_dir, file_name)
            cv2.imwrite(save_path, face)

            cv2.rectangle(img, (x, y), (x+w, y+h), (0,255,0), 2)
            time.sleep(0.08)

            if phase_count >= phase_limit:
                phase_idx += 1
                phase_count = 0
                break

        cv2.imshow("Signup Face Capture - Press Q to quit", img)

        if sample_num >= total_required:
            break

        if cv2.waitKey(1) & 0xFF in [ord('q'), 27]:
            break

        if phase_idx >= len(phases):
            break

    cam.release()
    cv2.destroyAllWindows()

    if message_label is not None:
        message_label.configure(text=f"Captured {sample_num} samples", fg="green")

    return sample_num


# take Image of user
def TakeImage(
    l1, l2, haarcasecade_path, trainimage_path, message, err_screen, text_to_speech
):
    enrollment = str(l1).strip()
    name = str(l2).strip()

    if enrollment == "" and name == "":
        t = "Please enter your Enrollment Number and Name."
        text_to_speech(t)
        return
    elif enrollment == "":
        t = "Please enter your Enrollment Number."
        text_to_speech(t)
        return
    elif name == "":
        t = "Please enter your Name."
        text_to_speech(t)
        return
    elif not enrollment.isdigit():
        t = "Enrollment number must contain only digits."
        text_to_speech(t)
        return

    try:
        cam = cv2.VideoCapture(0)
        detector = cv2.CascadeClassifier(haarcasecade_path)

        # folder format: Enrollment_Name
        directory = f"{enrollment}_{name.replace(' ', '')}"
        path = os.path.join(trainimage_path, directory)
        os.makedirs(path, exist_ok=False)  # raises FileExistsError if already exists

        sampleNum = 0

        while True:
            ret, img = cam.read()
            if not ret:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in faces:
                cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
                sampleNum += 1

                file_name = f"{name.replace(' ', '')}_{enrollment}_{sampleNum}.jpg"
                file_path = os.path.join(path, file_name)

                # Save cropped grayscale face image
                cv2.imwrite(file_path, gray[y : y + h, x : x + w])
                cv2.imshow("Frame", img)

                # Save photo metadata in MongoDB
                save_photo_meta(
                    enrollment=int(enrollment),
                    name=name,
                    photo_path=file_path,
                )

            # Press q to quit manually
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            # Auto-stop after enough samples
            elif sampleNum >= 60:
                break

        cam.release()
        cv2.destroyAllWindows()

        # Upsert student in MongoDB
        upsert_student(int(enrollment), name)

        # Optional: keep CSV for old flow compatibility
        os.makedirs("StudentDetails", exist_ok=True)
        with open("StudentDetails/studentdetails.csv", "a+", newline="") as csvFile:
            writer = csv.writer(csvFile, delimiter=",")
            writer.writerow([int(enrollment), name])

        res = f"Images Saved for ER No: {enrollment} Name: {name}"
        message.configure(text=res)
        text_to_speech(res)

    except FileExistsError:
        msg = "Student Data already exists."
        message.configure(text=msg)
        text_to_speech(msg)

    except Exception as e:
        msg = f"Error while saving data: {str(e)}"
        message.configure(text=msg)
        text_to_speech("Error while saving data. Please check terminal.")
        print(msg)