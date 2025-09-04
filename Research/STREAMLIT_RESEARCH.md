# Streamlit Web App Development Research

## Overview

Streamlit is an open-source Python framework that allows you to create interactive, data-driven web applications using only Python code. It's ideal for quickly building user interfaces for data science projects, machine learning models, and in our case, controlling and monitoring our robot.

## Why Streamlit for This Project?

*   **Python-Centric**: Build the entire UI using Python, eliminating the need for HTML, CSS, or JavaScript. This aligns perfectly with your existing backend codebase.
*   **Rapid Prototyping**: Streamlit's simple API allows for very fast development and iteration of web applications, crucial for your capstone timeline.
*   **Interactive Widgets**: Easily add sliders, buttons, text inputs, and more for user interaction.
*   **Data Visualization**: Seamlessly display robot status, GPS coordinates, and potentially even video feeds (though video might be more complex for live streaming).
*   **Integration with Flask API**: We can use `requests` to make calls from the Streamlit app to your existing Flask API for face registration, setting goals, and getting robot status.

## Core Features for Our Web App

Based on the professor's feedback and our project needs, the Streamlit app should include:

1.  **User Registration (Face Upload)**:
    *   Input field for user's name.
    *   Image upload widget to send face images to the Flask API (`/register_face`).
    *   Feedback on upload success/failure.

2.  **Robot Control (Navigation)**:
    *   Input fields for setting navigation goals (e.g., X, Y coordinates, or a selection of predefined locations).
    *   Button to send goal commands to the Flask API (`/goal`).
    *   Emergency stop/pause button (potentially directly calling a Flask endpoint or through a status change).

3.  **Robot Tracking & Status Display**:
    *   Display of the robot's current state (idle, navigating, arrived, etc.) from the Flask API (`/status`).
    *   Show last set goal, last update timestamp.
    *   Display current coordinates (x, y) and GPS (lat, lon) if available.
    *   Consider a simple map visualization (e.g., using `folium` or `plotly`) if we have time and GPS data.

4.  **Order Management (Optional for UI)**:
    *   Potentially display pending/completed orders from the Flask API (`/orders`). This could be a stretch goal for the UI.

## Integration with Existing Flask API

Streamlit apps run as a separate Python process. Communication with your Flask API will happen via HTTP requests using the `requests` library (already familiar from your mobile app context).

**Example Interaction Flow:**

1.  User inputs name and uploads image in Streamlit app.
2.  Streamlit app uses `requests.post()` to send data to `http://<flask-api-url>/register_face`.
3.  Flask API processes the image, updates `encodings.pkl`.
4.  Flask API returns a JSON response (success/failure).
5.  Streamlit app displays the response to the user.

## Basic Streamlit App Structure

A Streamlit app is essentially a Python script. Here's a conceptual outline:

```python
import streamlit as st
import requests
import json
import os

# Configuration (will be externalized for cloud deployment)
FLASK_API_BASE_URL = "http://localhost:5001" # Or cloud-hosted URL

st.set_page_config(layout="wide")
st.title("🤖 Capstone Delivery Bot Control")

# --- User Registration Section ---
st.header("Face Registration")
user_name = st.text_input("Enter your name:")
uploaded_file = st.file_uploader("Upload your face image (JPG/PNG)", type=["jpg", "png"])

if uploaded_file is not None and user_name:
    if st.button("Register Face"):
        files = {'image': uploaded_file.getvalue()}
        data = {'name': user_name}
        try:
            response = requests.post(f"{FLASK_API_BASE_URL}/register_face", files=files, data=data)
            if response.status_code == 200:
                st.success(f"Face for {user_name} registered successfully!")
            else:
                st.error(f"Failed to register face: {response.json().get('error', response.text)}")
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to Flask API. Is it running?")

# --- Robot Control Section ---
st.header("Robot Navigation & Control")

# Goal setting
col1, col2 = st.columns(2)
with col1:
    goal_x = st.number_input("Goal X Coordinate", value=0.0, step=0.1)
with col2:
    goal_y = st.number_input("Goal Y Coordinate", value=0.0, step=0.1)

if st.button("Set Navigation Goal"):
    goal = [goal_x, goal_y]
    try:
        response = requests.post(f"{FLASK_API_BASE_URL}/goal", json={'goal': goal})
        if response.status_code == 200:
            st.success(f"Goal {goal} sent to robot!")
        else:
            st.error(f"Failed to set goal: {response.json().get('error', response.text)}")
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to Flask API. Is it running?")

# --- Robot Status Section ---
st.header("Robot Status")
if st.button("Refresh Robot Status"):
    try:
        response = requests.get(f"{FLASK_API_BASE_URL}/status")
        if response.status_code == 200:
            status_data = response.json()
            st.json(status_data) # Display raw JSON for now
            # TODO: Format this nicely
        else:
            st.error(f"Failed to fetch status: {response.text}")
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to Flask API. Is it running?")

# To run this app: `streamlit run your_app_name.py`
```

## Local Development & Testing

1.  **Install Streamlit**: `pip install streamlit requests`
2.  **Run Flask API**: Start your Flask app (`python flask_api/app.py`).
3.  **Run Streamlit App**: `streamlit run your_app_name.py` (assuming the above code is saved as `your_app_name.py`).

## Next Steps

1.  **Install Streamlit and Requests**: Install these libraries in your virtual environment.
2.  **Create `streamlit_app.py`**: Create a new file in the project root with the basic structure above.
3.  **Test Local Integration**: Verify that the Streamlit app can communicate with your local Flask API.
4.  **Enhance UI/UX**: Work with Person.K to refine the Streamlit app's design for better usability and visual appeal.

## Resources

*   **Streamlit Official Documentation**: [https://docs.streamlit.io/](https://docs.streamlit.io/)
*   **Streamlit with REST APIs**: [https://docs.streamlit.io/knowledge-base/tutorials/create-apps-with-data-api](https://docs.streamlit.io/knowledge-base/tutorials/create-apps-with-data-api)

---

**Last Updated**: September 4, 2025
**Status**: Research Complete, Ready for Implementation 📋
