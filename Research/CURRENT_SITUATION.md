Another big pivot in the project, but it simplifies things significantly for our timeline! Here's the essential lowdown:

1.  **Frontend Switch**: We're moving from Streamlit (and the old Flutter app) to a **standard HTML/CSS/JavaScript web application**. Person.K, your design skills are now focused on building this traditional web UI.
2.  **Cloud Storage (Critical!)**: Our professor highlighted the need to host our facial recognition data (images, encodings) on the cloud, not just locally. We're now implementing **AWS S3** for this. The robot will pull its `encodings.pkl` from here.
3.  **Yahboom Robot**: We'll be flashing the Raspberry Pi with the **Yahboom factory image**. This means the robot will have its own mobile app for basic remote control, simplifying our immediate hardware integration.
4.  **Autonomous Movement = Stretch Goal**: Our **main priority now is establishing robust connectivity**:
    *   **HTML Web App <---> Cloud-hosted Flask API**
    *   **Cloud-hosted Flask API <---> Raspberry Pi** (for triggering face recognition, status, etc., leveraging Yahboom's built-in functions).
    Autonomous navigation is now a stretch goal, focusing our efforts on getting the core system online and integrated.

**Crucial for Person.B (YOLO Images):**
*   **YES, please continue (and intensify!) your efforts to collect campus sign images.** YOLO is still a critical perception component, and having a good dataset is vital for when we integrate the real robot camera. Refer to `Research/SIGN_LIST.md` for details.

**Next Steps (Me/AI):**
*   Setting up AWS S3 for cloud storage.
*   Deploying our Flask API to Heroku.
*   Building the new HTML/CSS/JS frontend.
*   Preparing for hardware integration once I get the robot.

Read the updated `DEVELOPMENT_SETUP.md` in the main folder for all the details.

Cheers
