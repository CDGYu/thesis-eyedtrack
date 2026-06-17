# EyeDTrack Backend

Backend server for **EyeDTrack**, a real-time driver attention monitoring system designed to enhance road safety by detecting driver drowsiness and inattentiveness.

---

## Overview  
This backend processes real-time video input to analyze driver attention using computer vision.  
It communicates with the Kotlin-based mobile frontend through REST APIs and detects drowsiness, yawning,
and distraction using **dlib** 68-point facial landmarks — Eye Aspect Ratio (EAR), Mouth Aspect Ratio (MAR),
and geometric head-pose estimation.

---

## Features  
- Real-time facial and eye tracking  
- Drowsiness and attention detection  
- REST API for mobile app integration  
- Environment-based configuration  

---

## Tech Stack  
- **Language:** Python 3.14  
- **Frameworks:** Flask, Flask-CORS, Flask-Compress  
- **Libraries:** OpenCV, dlib, NumPy, SciPy  
- **Detection:** dlib 68-point facial landmarks (EAR / MAR / head-pose)  
- **Persistence:** append-only JSON logs today; optional MySQL via SQLAlchemy + PyMySQL (see `CLEANUP_PLAN.md` §12)  

---

## Installation  

```bash
# Clone the repository
git clone https://github.com/RVBCosme/thesis-eyedtrack-backend.git
cd eyedtrack-backend

# Install dependencies
pip install -r requirements.txt

# Run the server
py -3.14 main.py
```

---

## Configuration
To change API call targets, update the backend integration URL in your configuration file:
```bash
# Path: config.yaml
integration:
  base_url: "http://<your-private-IP-address>"
```
**Tip**: Your private IP address will be displayed in the terminal when you run the server.

---

## Contributors 
- Rene Vincent Cosme
- Pamela Lapiña
- Samantha Nicole Maturan
- Charles Derick Yu

