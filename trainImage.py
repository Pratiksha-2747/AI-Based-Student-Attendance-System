import os, cv2
import numpy as np
from PIL import Image


# Train Image
def TrainImage(haarcasecade_path, trainimage_path, trainimagelabel_path, message, text_to_speech):
    recognizer = cv2.face.LBPHFaceRecognizer_create()

    faces, ids = getImagesAndLables(trainimage_path)

    if len(faces) == 0 or len(ids) == 0:
        res = "No valid training images found. Please capture images first."
        message.configure(text=res)
        text_to_speech(res)
        return

    recognizer.train(faces, np.array(ids))

    # Ensure label directory exists
    label_dir = os.path.dirname(trainimagelabel_path)
    os.makedirs(label_dir, exist_ok=True)

    recognizer.save(trainimagelabel_path)
    res = "Image Trained Successfully"
    if message is not None:
        message.configure(text=res)
    if text_to_speech is not None:
        text_to_speech(res)


def getImagesAndLables(path):
    faces = []
    ids = []

    if not os.path.exists(path):
        return faces, ids

    # Traverse all student folders
    for student_dir in os.listdir(path):
        student_dir_path = os.path.join(path, student_dir)
        if not os.path.isdir(student_dir_path):
            continue

        for file_name in os.listdir(student_dir_path):
            if not file_name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            image_path = os.path.join(student_dir_path, file_name)

            try:
                pil_image = Image.open(image_path).convert("L")
                image_np = np.array(pil_image, "uint8")

                # Folder format: <Name>_<Enrollment>
                folder_parts = student_dir.rsplit("_", 1)
                if len(folder_parts) != 2:
                    continue

                enrollment_str = folder_parts[1]
                if not enrollment_str.isdigit():
                    continue

                student_id = int(enrollment_str)

                faces.append(image_np)
                ids.append(student_id)

            except Exception:
                # Skip corrupted/bad files
                continue

    return faces, ids