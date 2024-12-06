import os
import shutil
import time
import traceback

from flask import Flask, request, jsonify, render_template, Response
import asyncio
import threading
from datetime import datetime
from functools import wraps
import simplematrixbotlib as botlib
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from db_utils import execute_rec_into_task, execute_rec_into_schedule
from app_utils import send_messages
from extensions import db
from models import Message

# Initialize Flask app
app = Flask(__name__, static_folder="static")

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///message.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
admin = Admin(app, name='Message_bot')
admin.add_view(ModelView(Message, db.session))

# Basic Auth Configuration
USERNAME = "Debra999"
PASSWORD = "Bobra999"

# Matrix Configuration
homeserver = "https://matrix.org"
user_id = "@username:matrix.org"
password = "password"


def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def check_auth(username, passw):
    return username == USERNAME and passw == PASSWORD


def authenticate():
    return Response(
        'Authentication Required', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated


@app.route('/')
@requires_auth
def index():
    return render_template("index.html")


# Route to add a new message to the schedule with authorization
@app.route('/add_schedule', methods=['POST'])
@requires_auth
def add_schedule():
    data = request.json
    interval = int(data['interval'])
    always_on = data.get('always_on', False)

    start_time = datetime.strptime(data['start_time'], "%H:%M").time() if not always_on and data.get(
        'start_time') else None
    end_time = datetime.strptime(data['end_time'], "%H:%M").time() if not always_on and data.get('end_time') else None

    # Create the database record first
    db_mess_record = Message(
        name=data['name'],
        room_id=data['group'],
        status="active",
        interval=interval,
        start=str(start_time),
        end=str(end_time),
        message=data['message'],
        always_on=always_on
    )

    db.session.add(db_mess_record)
    db.session.commit()

    # Use the database ID as the task_id
    task_id = str(db_mess_record.id)

    task = {
        "id": task_id,
        "name": data['name'],
        "room_id": data['group'],
        "interval": interval,
        "start_time": start_time,
        "end_time": end_time,
        "message": data['message'],
        "always_on": always_on
    }
    tasks[task_id] = task
    print(f"Added task: {task}")

    # Initialize task status as 'active'
    task_status[task_id] = "active"

    # Schedule the task in the main event loop
    asyncio.run_coroutine_threadsafe(send_messages(bot, task, task_status, task_id), loop)

    return jsonify({"status": "success"})


# Route to get current schedules with authorization
@app.route('/get_schedules', methods=['GET'])
@requires_auth
def get_schedules():
    try:
        messages = db.session.query(Message).filter(Message.status != "deleted").all()
        schedules = [execute_rec_into_schedule(message) for message in messages]
    except Exception as e:
        print(f"Error retrieving schedules: {e}")
        schedules = []
    return jsonify(schedules)


# Route to toggle the activity of a task with authorization
@app.route('/toggle_schedule/<task_id>', methods=['POST'])
@requires_auth
def toggle_schedule(task_id):
    task_id = str(task_id)
    print(f"Toggle request for task: {task_id}")
    print(f"Current task_status: {task_status}")

    if task_id not in task_status:
        return jsonify({"error": f"Task {task_id} not found"}), 404

    current_status = task_status[task_id]
    try:
        if current_status == "active":
            # Switch to 'paused'
            task_status[task_id] = "paused"
            curr_task = db.session.query(Message).filter(Message.id == int(task_id)).with_for_update().first()
            if curr_task:
                curr_task.status = "paused"
                db.session.commit()
                print(f"Task {task_id} paused and database updated.")
            else:
                print(f"Task {task_id} not found in the database.")
        elif current_status == "paused":
            # Switch back to 'active'
            task_status[task_id] = "active"
            curr_task = db.session.query(Message).filter(Message.id == int(task_id)).with_for_update().first()
            if curr_task:
                curr_task.status = "active"
                db.session.commit()
                print(f"Task {task_id} resumed and database updated.")
                # Restart sending messages
                task = tasks.get(task_id)
                if task:
                    asyncio.run_coroutine_threadsafe(send_messages(bot, task, task_status, task_id), loop)
            else:
                print(f"Task {task_id} not found in the database.")
        else:
            print(f"Task {task_id} has unsupported status: {current_status}")
            return jsonify({"error": f"Unsupported status for task {task_id}."}), 400
    except Exception as e:
        print(f"Error toggling task {task_id}: {e}")
        return jsonify({"error": "Internal server error."}), 500

    return jsonify({"status": "success"})


# Route to delete a task with authorization
@app.route('/delete_schedule/<task_id>', methods=['DELETE'])
@requires_auth
def delete_schedule(task_id):
    task_id = str(task_id)
    print(f"Delete request for task: {task_id}")

    if task_id not in task_status:
        return jsonify({"error": f"Task {task_id} not found"}), 404

    try:
        # Remove task from tasks dictionary
        tasks.pop(task_id, None)

        # Remove task status
        task_status.pop(task_id, None)

        # Update status in database
        curr_task = db.session.query(Message).filter(Message.id == int(task_id)).with_for_update().first()
        if curr_task:
            curr_task.status = "deleted"
            db.session.commit()
            print(f"Task {task_id} deleted and database updated.")
        else:
            print(f"Task {task_id} not found in the database.")
    except Exception as e:
        print(f"Error deleting task {task_id}: {e}")
        return jsonify({"error": "Internal server error."}), 500

    return jsonify({"status": "success"})


# Initialize tasks and task_status as dictionaries
tasks = {}
task_status = {}

# Start the Flask app and bot
if __name__ == '__main__':
    if os.environ.get("WERKZEUG_RUN_MAIN") == 'true':  # Only in the main process
        session_path = './session.txt'
        session_exist = os.path.exists(session_path)
        if session_exist:
            try:
                os.remove(session_path)
                print("Session file deleted.")
            except Exception as e:
                print(f"Error deleting session.txt: {e}")

        store_path = "./store"
        store_exists = os.path.exists(store_path)
        if store_exists:
            try:
                shutil.rmtree(store_path)
                print("Store directory deleted.")
            except Exception as e:
                print(f"Error deleting store directory: {e}")

        print("Initializing application...")

        # Initialize event loop and threads
        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=start_loop, args=(loop,), daemon=True)
        loop_thread.start()

        # Initialize the bot
        creds = botlib.Creds(
            homeserver=homeserver,
            username=user_id,
            password=password,
            session_stored_file="session.txt"
        )
        config = botlib.Config()
        config.encryption_enabled = True
        bot = botlib.Bot(creds, config)
        print("Bot initialized.")

        # Run the bot in the event loop
        asyncio.run_coroutine_threadsafe(bot.main(), loop)
        print("Bot started.")

        max_wait_time = 60  # Max wait time in seconds
        wait_interval = 1  # Wait interval in seconds
        total_waited = 0
        while not os.path.exists(session_path) and total_waited < max_wait_time:
            print("Waiting for session.txt to be created...")
            time.sleep(wait_interval)
            total_waited += wait_interval

        if os.path.exists(session_path):
            print("session.txt found. Continuing to load tasks.")
        else:
            print(f"session.txt not found after waiting {max_wait_time} seconds.")
            print("Continuing to load tasks without session.txt confirmation.")

        with app.app_context():
            db.create_all()
            try:
                # Load tasks from the database, skipping those with status 'deleted'
                db_records = db.session.query(Message).filter(Message.status != "deleted").all()
                for rec in db_records:
                    rec_task = execute_rec_into_task(rec)
                    task_id_str = str(rec_task['id'])
                    tasks[task_id_str] = rec_task
                    task_status[task_id_str] = rec.status
                    print(f"Task loaded: {task_id_str} with status {rec.status}")
                    # If task is active or paused, start sending messages
                    if rec.status == "active" or rec.status == "paused":
                        asyncio.run_coroutine_threadsafe(send_messages(bot, rec_task, task_status, task_id_str), loop)
            except Exception as e:
                print(f"Error loading tasks from database: {e}")
                print(traceback.format_exc())

    # Run the Flask app
    app.run(debug=True, host="0.0.0.0", port=1235)
