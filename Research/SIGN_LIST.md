# Curated List of Campus Signs for YOLO Dataset

## Objective

This document provides a curated list of campus signs for Person.B to collect images for. The goal is to build a diverse dataset to train a robust YOLO model, enabling the robot to accurately detect and respond to signs crucial for campus navigation and delivery.

**Aim for 50-100 images per distinct sign category**, focusing on variety in lighting, angles, and distances.

## Key Sign Categories to Collect Images For

1.  **Stop Signs**
    *   **Description**: Standard red octagonal signs with white \"STOP\" text.
    *   **Importance**: Critical for safe navigation at intersections and pedestrian crossings. The robot must come to a complete stop.

2.  **Yield Signs**
    *   **Description**: Red and white inverted triangular signs with \"YIELD\" text.
    *   **Importance**: The robot needs to slow down and be prepared to stop for other traffic or pedestrians.

3.  **Crosswalk Signs / Pedestrian Crossing Signs**
    *   **Description**: Typically yellow/green diamond-shaped or rectangular signs with a pedestrian symbol.
    *   **Importance**: Alerts the robot to pedestrian areas where it must exercise extreme caution and yield right-of-way.

4.  **No Entry / Do Not Enter Signs**
    *   **Description**: Red circle with a horizontal white bar or text \"DO NOT ENTER\".
    *   **Importance**: Defines restricted areas (e.g., one-way streets, maintenance zones) that the robot should not enter.

5.  **Directional / Arrow Signs (e.g., \"Library,\" \"Student Union,\" \"Building Name\")**
    *   **Description**: Rectangular signs with text indicating a location and often an arrow. These can be mounted on poles or buildings.
    *   **Importance**: Essential for the robot to identify and navigate towards specific delivery destinations or points of interest on campus.
    *   **Note**: If text recognition becomes too complex for the capstone, focus on the *presence* of a directional sign and its general direction if a prominent arrow is present.

6.  **Speed Limit Signs (e.g., \"15 MPH,\" \"25 MPH\")**
    *   **Description**: White rectangular signs with black numerals indicating the maximum allowed speed.
    *   **Importance**: The robot must adhere to campus speed regulations for safety.

7.  **Delivery Zone / Pickup Point Signs**
    *   **Description**: Custom signs or visual markers that define designated areas for food delivery or package pickup. These might be less standard, so Person.B should look for common visual cues or areas that *could* be designated as such (e.g., a specific bench, a building entrance with a clear identifying feature).
    *   **Importance**: These are the ultimate target destinations for successful deliveries.
    *   **Recommendation**: If no explicit \"delivery zone\" signs exist, collect images of common building entrances, main campus drop-off points, or distinctive landmarks that could serve as virtual delivery markers.

## Tips for Image Collection (for Person.B)

*   **Maximize Variety**: Capture images under different conditions:
    *   **Lighting**: Sunny days, cloudy days, dawn/dusk.
    *   **Angles**: Straight on, from left, from right, high angle, low angle.
    *   **Distances**: Far away (where the sign is still clearly visible), medium distance, up close.
*   **Background Diversity**: Capture signs against different backgrounds (trees, buildings, sky, other signs).
*   **Obstructions**: Include some images where parts of the sign are slightly obscured (e.g., by a tree branch, another object), but still recognizable.
*   **Quality**: Use a good quality camera (a modern smartphone is usually sufficient) and ensure images are in focus and well-lit. High resolution is generally better.
*   **Organization**: Organize images into folders named after their sign category (e.g., `Stop_Sign/`, `Delivery_Zone_Main_Bldg/`).

---

**Last Updated**: September 4, 2025
**Status**: Curated Sign List for Dataset Collection 📋
