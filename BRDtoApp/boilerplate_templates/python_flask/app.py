from flask import Flask, jsonify
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({'message': 'Flask Boilerplate is running!'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', 3002))
