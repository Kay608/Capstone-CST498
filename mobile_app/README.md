# mobile_app

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

Here’s the correct run order for your project, based on your codebase and architecture:

---

## 1. Start the Backend (Flask API)
**Command:**
```bash
cd flask_api
python app.py
```
- This must be running before you use the Flutter app.
- Handles all REST API requests (face registration, deletion, robot status, etc.).

---

## 2. (If Needed) Start Face Recognition Service
If your backend or robot_controller.py requires ai_facial_recognition.py to be running as a separate process/service, start it:
```bash
python ai_facial_recognition.py
```
- If face recognition is only called as a module, you do not need to run this separately.

---

## 3. Start the Flutter App
**Command:**
```bash
cd mobile_app
flutter run
```
- This can be run on Windows, Android, or iOS.
- Make sure the backend server’s IP/port in main.dart matches your actual backend.

---

## 4. (Optional) Start Robot Navigation Code
If you want to simulate or run robot navigation logic separately (for example, for hardware testing):
```bash
python robot_navigation/robot_controller.py
```
- Only needed if you want to test robot logic outside of Flask.

---

## Summary Table

| Step | Script/Service                  | Required? | Notes                                 |
|------|---------------------------------|-----------|---------------------------------------|
| 1    | app.py                | Yes       | Main backend, must be running first   |
| 2    | ai_facial_recognition.py        | Maybe     | Only if needed as a separate service  |
| 3    | mobile_app (Flutter)            | Yes       | User interface                        |
| 4    | robot_controller.py | Optional  | For direct robot logic testing         |

---

**Tip:**  
- Always start app.py first.
- If you get connection errors, double-check that the backend is running and reachable.
- If the Flutter app won’t close, that’s a Flutter desktop bug—use Task Manager as you have been.

