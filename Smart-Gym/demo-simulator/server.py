from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Local "Cloud" Storage
db = {
    "user_id": "Awaiting Tap...",
    "rep_count": 0,
    "ai_state": 0,
    "history": [] # Stores machineData for the chart and tables
}

@app.route('/update_gym', methods=['POST'])
def update_gym():
    data = request.json
    db["user_id"] = data.get("user_id", db["user_id"])
    db["rep_count"] = data.get("rep_count", db["rep_count"])
    return jsonify({"status": "success"})

@app.route('/update_vision', methods=['POST'])
def update_vision():
    data = request.json
    state = data.get("ai_state", 0)
    db["ai_state"] = state
    
    # Create a record that looks like a ThingSpeak feed
    new_entry = {
        "created_at": datetime.now().isoformat(),
        "field1": db["user_id"],
        "field2": db["rep_count"],
        "field4": state
    }
    db["history"].append(new_entry)
    if len(db["history"]) > 20: db["history"].pop(0)
    return jsonify({"status": "success"})

@app.route('/api/data', methods=['GET'])
def get_data():
    return jsonify({"feeds": db["history"], "current": db})

if __name__ == '__main__':
    print("Local Hub Active: http://localhost:5000")
    app.run(port=5000, debug=False)