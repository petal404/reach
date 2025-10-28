from flask import Flask, jsonify, render_template
import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_dashboard_data, Session, User, Log
from config_loader import load_config

app = Flask(__name__)

@app.route('/')
def index():
    settings, criteria = load_config()
    return render_template('index.html', settings=settings, criteria=criteria)

@app.route('/api/data')
def api_data():
    try:
        data = get_dashboard_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)