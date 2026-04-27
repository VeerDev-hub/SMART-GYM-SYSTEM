# Smart Gym Controller

Use the Python controller to start and stop the complete Smart Gym demo from one place.

## Files

- `controller/smart_gym_controller.py`

## What the start script launches

1. FastAPI backend on `http://localhost:8000`
2. Demo simulator
3. YOLO AI vision app
4. Static dashboard server on `http://localhost:8080`

## Start everything

```powershell
cd F:\Projects\IoT
python .\controller\smart_gym_controller.py start
```

## Start everything and rebuild the database

Use this when you changed backend models and want a clean demo database.

```powershell
cd F:\Projects\IoT
python .\controller\smart_gym_controller.py start --recreate-db
```

## Stop everything

```powershell
cd F:\Projects\IoT
python .\controller\smart_gym_controller.py stop
```

## Check status

```powershell
cd F:\Projects\IoT
python .\controller\smart_gym_controller.py status
```

## Notes

- You need Python installed and available as `python`
- Install backend dependencies first from `backend/requirements.txt`
- Install AI vision dependencies such as `opencv-python`, `ultralytics`, `numpy`, and `requests`
- On Windows, each service opens in its own console window
