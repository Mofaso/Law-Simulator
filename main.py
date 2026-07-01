import eel
import threading
from app import app  # Import your Flask app

# Initialize Eel
eel.init('templates')  # Point to your templates folder

# Run Flask in a separate thread
def run_flask():
    app.run(port=5000, debug=False)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# Open a native window pointing to your Flask login page
eel.start('login.html', size=(1024, 768), block=True)  # Opens login.html in a window
