# Flask Boilerplate

A clean, minimal, and production-ready Flask application boilerplate.

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone [repository-url]
   cd [repository-name]
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Unix or MacOS:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

5. Run the application:
   Option 1 - Using Flask CLI:
   ```bash
   # Set environment variables
   export FLASK_APP=app.py
   export FLASK_ENV=development
   # On Windows:
   set FLASK_APP=app.py
   set FLASK_ENV=development

   # Run the app
   flask run
   ```

   Option 2 - Run directly:
   ```bash
   python app.py
   ```

The application will be available at `http://localhost:5000`
