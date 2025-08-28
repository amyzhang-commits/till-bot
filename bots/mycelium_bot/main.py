import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Mycelium Till - Database disabled for testing"

@app.route('/health', methods=['GET']) 
def health():
    return jsonify({'status': 'healthy'})

if __name__ == "__main__":
    print("Starting without database...")
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
