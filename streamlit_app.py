import streamlit as st
import requests
import json
import os
import time

# Configuration
# In a real deployment, this URL would be your cloud-hosted Flask API endpoint.
# For local testing, keep it as localhost.
FLASK_API_BASE_URL = "http://localhost:5001"

st.set_page_config(layout="wide", page_title="🤖 Capstone Delivery Bot Control")
st.title("🤖 Capstone Delivery Bot Control")

# --- User Registration Section ---
st.header("Face Registration")

with st.form("face_registration_form"):
    user_name = st.text_input("Enter your name:", key="reg_name_input")
    uploaded_file = st.file_uploader("Upload your face image (JPG/PNG)", type=["jpg", "png"], key="reg_image_uploader")
    submitted = st.form_submit_button("Register Face")

    if submitted:
        if not user_name:
            st.error("Please enter a name.")
        elif uploaded_file is None:
            st.error("Please upload an image.")
        else:
            files = {'image': uploaded_file.getvalue()}
            data = {'name': user_name}
            try:
                response = requests.post(f"{FLASK_API_BASE_URL}/register_face", files=files, data=data, timeout=10)
                if response.status_code == 200:
                    st.success(f"Face for {user_name} registered successfully!")
                else:
                    st.error(f"Failed to register face: {response.json().get('error', response.text)}")
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to Flask API. Please ensure it's running at " + FLASK_API_BASE_URL)
            except requests.exceptions.Timeout:
                st.error("Request to Flask API timed out. Please try again.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

# --- Robot Control Section ---
st.header("Robot Navigation & Control")

with st.form("robot_control_form"):
    col1, col2 = st.columns(2)
    with col1:
        goal_x = st.number_input("Goal X Coordinate", value=0.0, step=0.1, key="goal_x_input")
    with col2:
        goal_y = st.number_input("Goal Y Coordinate", value=0.0, step=0.1, key="goal_y_input")
    
    set_goal_submitted = st.form_submit_button("Set Navigation Goal")

    if set_goal_submitted:
        goal = [goal_x, goal_y]
        try:
            response = requests.post(f"{FLASK_API_BASE_URL}/goal", json={'goal': goal}, timeout=10)
            if response.status_code == 200:
                st.success(f"Goal {goal} sent to robot!")
            else:
                st.error(f"Failed to set goal: {response.json().get('error', response.text)}")
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to Flask API. Please ensure it's running at " + FLASK_API_BASE_URL)
        except requests.exceptions.Timeout:
            st.error("Request to Flask API timed out. Please try again.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

# --- Robot Status Section ---
st.header("Robot Status")

# Use st.empty to update the status in place
status_placeholder = st.empty()

def fetch_and_display_status():
    try:
        response = requests.get(f"{FLASK_API_BASE_URL}/status", timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            with status_placeholder.container():
                st.write("Last Update: ", time.ctime(status_data.get('last_update', time.time())))
                st.write("State: ", status_data.get('state', 'Unknown'))
                st.write("Last Goal: ", status_data.get('last_goal', 'N/A'))
                st.write("Current Coords (x,y): ", status_data.get('coords', 'N/A'))
                st.write("Current GPS (lat,lon): ", status_data.get('gps', 'N/A'))
                # For debugging, show raw JSON:
                # st.json(status_data)
        else:
            with status_placeholder.container():
                st.error(f"Failed to fetch status: {response.status_code} - {response.text}")
    except requests.exceptions.ConnectionError:
        with status_placeholder.container():
            st.error("Could not connect to Flask API. Is it running?")
    except requests.exceptions.Timeout:
        with status_placeholder.container():
            st.warning("Fetching status timed out. Retrying...")
    except Exception as e:
        with status_placeholder.container():
            st.error(f"An unexpected error occurred while fetching status: {e}")

# Automatically refresh status every few seconds
if st.button("Refresh Status Now"): # Manual refresh button
    fetch_and_display_status()

# You can also use st.rerun() to force a refresh on a timer, but that re-executes the whole script.
# For simple status updates, a manual refresh or a less aggressive polling mechanism might be better.
# For this capstone, let's keep it manual or integrate a periodic refresh more carefully later.

# Initial status fetch on load
fetch_and_display_status()
