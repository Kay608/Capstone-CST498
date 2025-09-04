# Cloud Hosting Research for Flask API and Streamlit App

## Overview

Deploying your Flask API and Streamlit web application to a cloud server will make your project accessible from anywhere, enabling your professor to review it and facilitating your live campus demo. This document outlines suitable cloud hosting options, focusing on ease of deployment, cost-effectiveness, and suitability for a capstone project.

## Key Considerations for Cloud Hosting

1.  **Ease of Deployment**: How quickly can we get both the Flask API and Streamlit app up and running?
2.  **Cost**: Are there free tiers or low-cost options suitable for a student project?
3.  **Scalability**: Can the platform handle potential user load (though likely low for a capstone)?
4.  **Integration**: Can both Python applications (Flask & Streamlit) be hosted and communicate effectively?
5.  **Robot Accessibility**: Can the Flask API, when hosted, be easily accessed by the Raspberry Pi robot (mDNS won't work across the internet, so a public IP or DNS will be needed)?

## Cloud Hosting Options

### 1. Heroku (Recommended for Simplicity and Integration)

*   **Type**: Platform-as-a-Service (PaaS)
*   **Pros**:
    *   **Ease of Deployment**: Known for its developer-friendly deployment process, especially for Python apps (Flask, Streamlit).
    *   **Single Platform**: Can potentially host both your Flask API and Streamlit app within the same Heroku application (using a Procfile for multiple processes or separate dynos).
    *   **Git Integration**: Simple deployment via `git push`.
    *   **Free Tier**: Offers a free tier for basic usage, though it has limitations (e.g., dyno sleeps after inactivity, limited hours).
    *   **Scalability**: Easy to scale up if needed (though paid tiers would be required).
*   **Cons**:
    *   Free tier limitations can lead to slow wake-up times for the app.
    *   More complex configurations for inter-app communication if hosted on separate dynos.
*   **Suitability**: **Highly Recommended** for capstone projects due to its balance of ease-of-use and flexibility.

### 2. Streamlit Community Cloud (Excellent for Streamlit App Only)

*   **Type**: Specialized Platform-as-a-Service for Streamlit apps.
*   **Pros**:
    *   **Extremely Easy Deployment**: Directly integrates with GitHub repositories for one-click deployment of Streamlit apps.
    *   **Free**: Completely free for public apps.
    *   **Performance**: Optimized specifically for Streamlit.
*   **Cons**:
    *   **Streamlit Only**: Primarily designed for hosting Streamlit applications. Hosting your Flask API directly on Streamlit Community Cloud would be challenging or not supported.
    *   **Separate Backend**: Would require your Flask API to be hosted on a *separate* platform (e.g., Heroku, Render, a simple VPS), adding complexity.
*   **Suitability**: **Recommended for the Streamlit frontend** if you choose a dual-deployment strategy, where the Flask API lives elsewhere.

### 3. Render (Emerging PaaS Alternative to Heroku)

*   **Type**: Platform-as-a-Service
*   **Pros**:
    *   **Ease of Use**: Very similar to Heroku in terms of simplified deployment for web services and static sites.
    *   **Generous Free Tier**: Often has a more generous free tier compared to Heroku, making it attractive for student projects.
    *   **Database Support**: Can easily integrate with managed databases.
*   **Cons**:
    *   Newer platform, so less community documentation compared to Heroku.
*   **Suitability**: A **strong alternative to Heroku**, especially if Heroku's free tier limitations become an issue.

### 4. General Cloud Providers (AWS, Google Cloud Platform, Azure)

*   **Type**: Infrastructure-as-a-Service (IaaS) / Platform-as-a-Service (PaaS) options (e.g., AWS Elastic Beanstalk, GCP App Engine, Azure App Service, AWS EC2, GCP Compute Engine).
*   **Pros**:
    *   **Maximum Control & Scalability**: Offers the most flexibility and power for complex deployments.
    *   **Wide Range of Services**: Access to extensive ecosystems for databases, machine learning, and more.
*   **Cons**:
    *   **Steeper Learning Curve**: Requires more in-depth knowledge of cloud infrastructure and services.
    *   **Cost**: Free tiers are often limited, and costs can quickly accumulate if not managed carefully.
    *   **Setup Complexity**: Initial setup and configuration can be time-consuming for both Flask and Streamlit apps.
*   **Suitability**: **Less Recommended for a capstone** given your timeline and the primary focus on the robot's functionality, unless your team already has significant experience with one of these platforms.

## Recommended Deployment Strategy

Given the need to host both a Flask API (which the robot will also communicate with) and a Streamlit app, I recommend either:

1.  **Primary Recommendation: Heroku for both API & App**:
    *   Simpler management as both services are on one platform.
    *   You would deploy your Flask API as a web dyno and potentially the Streamlit app as another web dyno or integrate them using a single Procfile and routing.
    *   This keeps your Flask API publicly accessible for the robot.

2.  **Alternative: Streamlit Community Cloud (App) + Render/Heroku (API)**:
    *   Leverages the absolute ease of Streamlit Community Cloud for the frontend.
    *   Your Flask API would be hosted separately (e.g., on Render or Heroku) and its public URL would be configured in the Streamlit app.
    *   This might be slightly more complex to set up initially due to managing two services but could offer a better free tier experience for the API.

## Next Steps

1.  **Install Streamlit and Requests**: Install these libraries in your virtual environment (if you haven't already done so from the `STREAMLIT_RESEARCH.md` steps).
2.  **Choose a Cloud Provider**: Discuss these options with your team and decide on a preferred cloud hosting provider (likely Heroku or Render for the API, with Streamlit Community Cloud as an option for the app).
3.  **Prepare for Deployment**: Start creating the necessary configuration files (e.g., `Procfile`, `requirements.txt`, `runtime.txt`) for your chosen platform.

## Resources

*   **Heroku Dev Center**: [https://devcenter.heroku.com/](https://devcenter.heroku.com/)
*   **Render Documentation**: [https://render.com/docs](https://render.com/docs)
*   **Streamlit Community Cloud**: [https://docs.streamlit.io/deploy/streamlit-community-cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud)

---

**Last Updated**: September 4, 2025
**Status**: Research Complete, Ready for Decision 📋
