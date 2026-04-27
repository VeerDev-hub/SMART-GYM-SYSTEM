# Smart Gym Intelligence System

A real-time gym monitoring system using Computer Vision (YOLO) and IoT simulation for instant form correction and rep tracking. A local Flask hub ensures sub-second updates.

## Run the Demo

### Open 3 terminals:

```bash
# 1. Start Local Hub
python server.py

# 2. Start Hardware Simulator
python demo-simulator/simulator.py

# 3. Start AI Vision Engine
python ai-vision/main.py
```

### Open in browser:

web-dashboard/index.html

### Install Dependencies

```bash
pip install flask flask-cors requests opencv-python ultralytics numpy
```