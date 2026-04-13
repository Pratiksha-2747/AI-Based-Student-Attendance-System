import csv
import os, cv2
from datetime import datetime

# Mongo helpers
from db import upsert_student, save_photo_meta


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