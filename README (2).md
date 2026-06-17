# EyeDTrack Frontend

Frontend mobile application for **EyeDTrack**, a real-time driver attention monitoring system designed to enhance road safety by detecting driver drowsiness and inattentiveness.

---

## Overview  
This Android-based frontend is built with Kotlin and serves as the user interface for the EyeDTrack system.  
It communicates with the Python-based backend through REST APIs to provide real-time monitoring, visual feedback, and driver alerts.

---

## Features  
- Real-time video streaming and detection feedback  
- Driver alert system for drowsiness and inattention  
- Secure communication with backend APIs  
- User-friendly dashboard and monitoring interface  

---

## Tech Stack  
- **Language:** Kotlin  
- **Platform:** Android (Android Studio)  
- **Build System:** Gradle (Kotlin DSL)  
- **Libraries & Tools:** Retrofit, CameraX, Android Jetpack Components  
- **Backend Integration:** REST API (Flask-based backend)  

---

## Installation  

```bash
# Clone the repository
git clone https://github.com/RVBCosme/thesis-eyedtrack-frontend.git
cd thesis-eyedtrack-frontend
```

---

## Run the App 
1. Open the project in Android Studio.
2. Allow Gradle to sync dependencies automatically.
3. Connect an Android device or start an emulator.
4. Click Run > app to launch EyeDTrack.

---

## Configuration
After completing the “Run the App” steps, configure the API and network settings to connect with your backend server.

### 1. Update API Base URLs
Edit the following files and replace <your-private-IP-address>:<port> with your actual backend address:

**File**
app -> kotlin+java -> com.example.eyedtrack -> api -> ApiClient.kt
```kotlin
private const val BASE_URL = "http://<your-private-IP-address>:<port>/"
```

**File**
app -> kotlin+java -> com.example.eyedtrack -> api -> ApiConstants.kt
```kotlin
const val BASE_URL = "http://<your-private-IP-address>:<port>/"
```

### 2. Update Network Security Configuration
**File**
app -> res -> xml -> network_security_config.xml
Add the following line inside the <domain-config> tag:
```kotlin
private const val BASE_URL = "http://<your-private-IP-address>:<port>/"
```

### 3. Update Alert Log Endpoints
**File**
app -> kotlin+java -> com.example.eyedtrack -> utils -> AlertLogLoader.kt
Search (Ctrl + F) for val endpoints and modify the following lines:
```kotlin
"http://<your-private-IP-address>:<port>/api/alert_history?limit=$maxLogs"
"http://<your-private-IP-address>:<port>/api/latest_behavior"
```

**Tip**: The backend IP address is displayed in the terminal when you run the backend server.

## Contributors
- Rene Vincent Cosme
- Pamela Lapiña
- Samantha Nicole Maturan
- Charles Derick Yu
