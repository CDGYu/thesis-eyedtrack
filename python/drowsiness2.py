import cv2
import dlib
import numpy as np
import time
from scipy.spatial import distance

# Load Haar Cascade for face detection
haar_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Load face detector and shape predictor
detector = dlib.get_frontal_face_detector()
predictor_path = r"C:\Users\Samantha\Desktop\School\2nd Sem\Thesis\python\shape_predictor_68_face_landmarks.dat"
predictor = dlib.shape_predictor(predictor_path)

# EAR calculation function
def eye_aspect_ratio(eye):
    A = distance.euclidean(eye[1], eye[5])  # Vertical distance
    B = distance.euclidean(eye[2], eye[4])  # Vertical distance
    C = distance.euclidean(eye[0], eye[3])  # Horizontal distance
    ear = (A + B) / (2.0 * C)
    return ear

# MAR calculation function
def mouth_aspect_ratio(mouth):
    A = distance.euclidean(mouth[2], mouth[10])  # Vertical distance
    B = distance.euclidean(mouth[4], mouth[8])   # Vertical distance
    C = distance.euclidean(mouth[0], mouth[6])   # Horizontal distance
    mar = (A + B) / (2.0 * C)
    return mar

# Thresholds for EAR and MAR
EAR_THRESHOLD = 0.21
MAR_THRESHOLD = 0.6  
ALERT_TIME = 3 

drowsy_start_time = None  
yawn_start_time = None

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture image")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE for contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Haar Cascade face detection
    haar_faces = haar_face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(30, 30))

    if len(haar_faces) == 0:
        cv2.putText(frame, "NO FACE DETECTED!", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        print("ALERT! NO FACE DETECTED")

    for (x, y, w, h) in haar_faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)  # Blue box for Haar face

    # Dlib face detection
    faces = detector(gray)

    for face in faces:
        landmarks = predictor(gray, face)

        # Extract eye landmarks (left and right)
        left_eye = np.array([(landmarks.part(n).x, landmarks.part(n).y) for n in range(36, 42)])
        right_eye = np.array([(landmarks.part(n).x, landmarks.part(n).y) for n in range(42, 48)])

        # Extract mouth landmarks
        mouth = np.array([(landmarks.part(n).x, landmarks.part(n).y) for n in range(48, 68)])

        # Compute EAR and MAR
        left_ear = eye_aspect_ratio(left_eye)
        right_ear = eye_aspect_ratio(right_eye)
        avg_ear = (left_ear + right_ear) / 2.0
        mar = mouth_aspect_ratio(mouth)

        # Draw eyes and mouth landmarks
        for (x, y) in left_eye:
            cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)
        for (x, y) in right_eye:
            cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)
        for (x, y) in mouth:
            cv2.circle(frame, (x, y), 2, (255, 0, 0), -1)

        # Display EAR and MAR
        cv2.putText(frame, f"EAR: {avg_ear:.2f}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"MAR: {mar:.2f}", (50, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        # Drowsiness detection
        if avg_ear < EAR_THRESHOLD:
            if drowsy_start_time is None:
                drowsy_start_time = time.time()  
            
            elapsed_time = time.time() - drowsy_start_time  

            if elapsed_time >= ALERT_TIME:
                cv2.putText(frame, "DROWSINESS DETECTED", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                print("DROWSINESS DETECTED")
        else:
            drowsy_start_time = None 

        # Yawning detection
        if mar > MAR_THRESHOLD:
            if yawn_start_time is None:
                yawn_start_time = time.time()
            
            elapsed_time = time.time() - yawn_start_time
            if elapsed_time >= ALERT_TIME:
                cv2.putText(frame, "YAWNING DETECTED!", (50, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                print("YAWNING DETECTED!")
        else:
            yawn_start_time = None
    
    cv2.imshow('Driver Monitoring - EAR & MAR Detection', frame)

    if cv2.waitKey(1) & 0xFF == ord('x'):
        break

cap.release()
cv2.destroyAllWindows()
