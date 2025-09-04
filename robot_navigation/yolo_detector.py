import cv2
from ultralytics import YOLO
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YOLOSignDetector:
    def __init__(self, model_path: str = 'yolov8n.pt'):
        """
        Initializes the YOLO sign detector with a specified model.
        """
        try:
            self.model = YOLO(model_path)
            logger.info(f"Successfully loaded YOLO model: {model_path}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model {model_path}: {e}")
            raise
        
        # Define sign classes (adjust as you create custom dataset)
        self.sign_classes = {
            0: 'person', # YOLOv8n default classes
            1: 'bicycle',
            2: 'car',
            3: 'motorcycle',
            4: 'airplane',
            5: 'bus',
            6: 'train',
            7: 'truck',
            8: 'boat',
            9: 'traffic light',
            10: 'fire hydrant',
            11: 'stop sign',
            12: 'parking meter',
            13: 'bench',
            14: 'bird',
            15: 'cat',
            16: 'dog',
            17: 'horse',
            18: 'sheep',
            19: 'cow',
            20: 'elephant',
            21: 'bear',
            22: 'zebra',
            23: 'giraffe',
            24: 'backpack',
            25: 'umbrella',
            26: 'handbag',
            27: 'tie',
            28: 'suitcase',
            29: 'frisbee',
            30: 'skis',
            31: 'snowboard',
            32: 'sports ball',
            33: 'kite',
            34: 'baseball bat',
            35: 'baseball glove',
            36: 'skateboard',
            37: 'surfboard',
            38: 'tennis racket',
            39: 'bottle',
            40: 'wine glass',
            41: 'cup',
            42: 'fork',
            43: 'knife',
            44: 'spoon',
            45: 'bowl',
            46: 'banana',
            47: 'apple',
            48: 'sandwich',
            49: 'orange',
            50: 'broccoli',
            51: 'carrot',
            52: 'hot dog',
            53: 'pizza',
            54: 'donut',
            55: 'cake',
            56: 'chair',
            57: 'couch',
            58: 'potted plant',
            59: 'bed',
            60: 'dining table',
            61: 'toilet',
            62: 'tv',
            63: 'laptop',
            64: 'mouse',
            65: 'remote',
            66: 'keyboard',
            67: 'cell phone',
            68: 'microwave',
            69: 'oven',
            70: 'toaster',
            71: 'sink',
            72: 'refrigerator',
            73: 'book',
            74: 'clock',
            75: 'vase',
            76: 'scissors',
            77: 'teddy bear',
            78: 'hair drier',
            79: 'toothbrush'
        }

    def detect_signs(self, image: Any) -> List[Dict[str, Any]]:
        """
        Detects signs in the given image.
        Args:
            image: Input image (e.g., NumPy array from OpenCV).
        Returns:
            A list of dictionaries, each containing 'class', 'confidence', and 'bbox'.
        """
        results = self.model(image, verbose=False) # verbose=False to suppress output
        return self.process_detections(results)

    def process_detections(self, results: List[Any]) -> List[Dict[str, Any]]:
        """
        Processes raw YOLO detection results into a more usable format.
        """
        signs = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                sign_info = {
                    'class': self.sign_classes.get(class_id, f'Unknown-{class_id}'),
                    'confidence': float(box.conf[0]),
                    'bbox': box.xyxy[0].tolist(), # [x1, y1, x2, y2]
                }
                signs.append(sign_info)
        return signs

if __name__ == '__main__':
    # Example usage: Detect signs in a sample image
    # You can replace 'bus.jpg' with any image file you have
    # For real usage, this would come from the robot's camera feed
    sample_image_path = 'uploads/Test_Person.jpg' # Assuming you have a test image here
    
    if not cv2.imread(sample_image_path) is None:
        detector = YOLOSignDetector()
        image = cv2.imread(sample_image_path)
        if image is not None:
            logger.info(f"Detecting signs in {sample_image_path}...")
            detections = detector.detect_signs(image)
            
            if detections:
                logger.info("Detections found:")
                for d in detections:
                    logger.info(f"  Class: {d['class']}, Confidence: {d['confidence']:.2f}, BBox: {d['bbox']}")
                    # Draw bounding box on image
                    x1, y1, x2, y2 = map(int, d['bbox'])
                    cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(image, f"{d['class']} {d['confidence']:.2f}", (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            else:
                logger.info("No detections found.")
            
            # Display the image with detections
            cv2.imshow("YOLO Detections", image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            logger.error(f"Failed to load image from {sample_image_path}")
    else:
        logger.warning(f"Sample image {sample_image_path} not found. Skipping direct YOLO test. Please ensure you have a test image in your 'uploads' folder.")
        logger.info("You can still run the file and integrate YOLOSignDetector into other modules.")
