import sqlite3
from flask import Flask, request, jsonify, render_template
from datetime import datetime, date

from app.db_setup import get_db_connection

app = Flask(__name__)

# Helper to convert row object to dictionary, handling date/time
def row_to_dict(row):
    d = dict(row)
    for key, value in d.items():
        if isinstance(value, (datetime, date)):
            # Use ISO 8601 format
            d[key] = value.isoformat()
        elif key == 'is_completed':
            # Convert 0/1 to boolean for JSON
            d[key] = bool(value)
    return d

# Error Handling
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Not Found"}), 404

@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({"error": "Bad Request", "message": str(error)}), 400

@app.errorhandler(Exception)
def internal_error(error):
    # Log the error internally? For now, just a generic message.
    print(f"Internal Server Error: {error}") # Log to console for debugging
    return jsonify({"error": "Internal Server Error"}), 500


# --- Client Endpoints ---

@app.route('/api/clients', methods=['GET'])
def get_clients():
    conn = get_db_connection()
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    conn.close()
    return jsonify([row_to_dict(client) for client in clients])

@app.route('/api/clients', methods=['POST'])
def add_client():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "Missing 'name' field"}), 400

    name = data['name']
    conn = get_db_connection()
    try:
        cursor = conn.execute('INSERT INTO clients (name) VALUES (?)', (name,))
        new_client_id = cursor.lastrowid
        conn.commit()
        new_client = conn.execute('SELECT * FROM clients WHERE client_id = ?', (new_client_id,)).fetchone()
        conn.close()
        if new_client:
            return jsonify(row_to_dict(new_client)), 201
        else:
             # Should not happen if insert succeeded, but good practice
            return jsonify({"error": "Failed to retrieve created client"}), 500
    except sqlite3.IntegrityError as e:
         conn.rollback()
         conn.close()
         # Handle potential future integrity constraints (e.g., unique name)
         return jsonify({"error": "Database integrity error", "message": str(e)}), 400
    except Exception as e:
        conn.rollback()
        conn.close()
        raise e # Re-raise for generic error handler


@app.route('/api/clients/<int:client_id>', methods=['PUT'])
def update_client(client_id):
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "Missing 'name' field"}), 400

    name = data['name']
    conn = get_db_connection()
    cursor = conn.execute('UPDATE clients SET name = ? WHERE client_id = ?', (name, client_id))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Client not found"}), 404

    conn.commit()
    updated_client = conn.execute('SELECT * FROM clients WHERE client_id = ?', (client_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(updated_client))

@app.route('/api/clients/<int:client_id>', methods=['DELETE'])
def delete_client(client_id):
    conn = get_db_connection()
    # Foreign key CASCADE should handle tasks, but we check existence first
    cursor = conn.execute('DELETE FROM clients WHERE client_id = ?', (client_id,))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Client not found"}), 404

    conn.commit()
    conn.close()
    return '', 204 # No Content


# --- Task Endpoints ---

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    client_id = request.args.get('client_id', type=int)
    conn = get_db_connection()

    query = 'SELECT * FROM tasks WHERE is_completed = 0'
    params = []
    if client_id:
        query += ' AND client_id = ?'
        params.append(client_id)
    query += ' ORDER BY due_date IS NULL, due_date ASC' # Sort null due dates last

    tasks = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([row_to_dict(task) for task in tasks])

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    client_id = data.get('client_id')
    description = data.get('description')
    due_date_str = data.get('due_date') # Expecting YYYY-MM-DD

    if not all([client_id, description]):
         return jsonify({"error": "Missing 'client_id' or 'description'"}), 400

    # Validate due_date format if provided
    due_date = None
    if due_date_str:
        try:
            due_date = date.fromisoformat(due_date_str)
        except ValueError:
            return jsonify({"error": "Invalid 'due_date' format. Use YYYY-MM-DD."}), 400

    conn = get_db_connection()
    try:
        # Check if client exists
        client = conn.execute('SELECT client_id FROM clients WHERE client_id = ?', (client_id,)).fetchone()
        if not client:
            conn.close()
            return jsonify({"error": f"Client with id {client_id} not found"}), 400

        cursor = conn.execute(
            'INSERT INTO tasks (client_id, description, due_date) VALUES (?, ?, ?)',
            (client_id, description, due_date)
        )
        new_task_id = cursor.lastrowid
        conn.commit()
        new_task = conn.execute('SELECT * FROM tasks WHERE task_id = ?', (new_task_id,)).fetchone()
        conn.close()
        if new_task:
             return jsonify(row_to_dict(new_task)), 201
        else:
             return jsonify({"error": "Failed to retrieve created task"}), 500
    except sqlite3.IntegrityError as e:
        conn.rollback()
        conn.close()
        # This primarily catches the foreign key constraint if client_id is invalid
        # Although we checked above, this is a safeguard.
        return jsonify({"error": "Database integrity error, likely invalid client_id", "message": str(e)}), 400
    except Exception as e:
        conn.rollback()
        conn.close()
        raise e

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json()
    description = data.get('description')
    # Use a different check to see if due_date was included in the request payload
    due_date_provided = 'due_date' in data
    due_date_str = data.get('due_date')

    # Check if at least one field to update was provided in the request
    if description is None and not due_date_provided:
        return jsonify({"error": "Missing 'description' or 'due_date' field to update"}), 400

    due_date = None
    # Validate date format only if a non-null, non-empty string was provided
    if due_date_provided and due_date_str:
        try:
            due_date = date.fromisoformat(due_date_str)
        except ValueError:
            return jsonify({"error": "Invalid 'due_date' format. Use YYYY-MM-DD."}), 400
    elif due_date_provided and due_date_str is not None and not isinstance(due_date_str, str):
         # Handle cases where due_date is provided but not a string (e.g., number, object)
         # Allow None/null explicitly, but reject other non-string types
         return jsonify({"error": "Invalid 'due_date' format. Use YYYY-MM-DD string or null."}), 400

    conn = get_db_connection()
    # Fetch existing task first to only update provided fields
    task = conn.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    # Prepare update fields
    update_fields = {}
    params_list = [] # Use a list for params to maintain order
    set_clauses = []

    if description is not None:
        set_clauses.append("description = ?")
        params_list.append(description)

    if due_date_provided: # Check if 'due_date' key was present in the request
        set_clauses.append("due_date = ?")
        # due_date is already correctly set to None if input was null/empty, or parsed date otherwise
        params_list.append(due_date)

    if not set_clauses: # Should not happen due to the check at the start, but safeguard
        conn.close()
        # This condition might be slightly different now - maybe description was null and due_date was null?
        # The initial check handles the case where *neither* key is present.
        # If description=None and due_date=None ARE present, we should allow the update.
        # Let's refine the check: if BOTH description is None (not provided) AND due_date was not provided.
        # The check at the beginning is correct.
        return jsonify({"error": "No valid fields provided for update"}), 400

    set_clause = ", ".join(set_clauses)
    params_list.append(task_id)

    # Use tuple for params in execute
    params = tuple(params_list)

    cursor = conn.execute(f'UPDATE tasks SET {set_clause} WHERE task_id = ?', params)
    if cursor.rowcount == 0: # Should not happen if fetch worked, but check anyway
        conn.rollback() # Should not commit if update failed
        conn.close()
        return jsonify({"error": "Task not found during update"}), 404

    conn.commit()
    updated_task = conn.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(updated_task))


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    conn = get_db_connection()
    cursor = conn.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    conn.commit()
    conn.close()
    return '', 204 # No Content

@app.route('/api/tasks/<int:task_id>/complete', methods=['PATCH'])
def complete_task(task_id):
    conn = get_db_connection()
    now = datetime.now()
    cursor = conn.execute(
        'UPDATE tasks SET is_completed = 1, completed_at = ? WHERE task_id = ?',
        (now, task_id)
    )
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    conn.commit()
    updated_task = conn.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(updated_task))

@app.route('/api/tasks/<int:task_id>/incomplete', methods=['PATCH'])
def incomplete_task(task_id):
    conn = get_db_connection()
    cursor = conn.execute(
        'UPDATE tasks SET is_completed = 0, completed_at = NULL WHERE task_id = ?',
        (task_id,)
    )
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    conn.commit()
    updated_task = conn.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(updated_task))

# --- History Endpoint ---

@app.route('/api/tasks/history', methods=['GET'])
def get_task_history():
    conn = get_db_connection()
    # Fetch completed tasks, sorted by completion date descending
    tasks = conn.execute(
        'SELECT * FROM tasks WHERE is_completed = 1 ORDER BY completed_at DESC'
    ).fetchall()
    conn.close()
    return jsonify([row_to_dict(task) for task in tasks])


# --- Consolidated Data Endpoint ---

@app.route('/api/data', methods=['GET'])
def get_all_data():
    conn = get_db_connection()
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    # Fetch only active tasks, sorted by due date
    tasks = conn.execute(
        'SELECT * FROM tasks WHERE is_completed = 0 ORDER BY client_id, due_date IS NULL, due_date ASC'
    ).fetchall()
    conn.close()

    # Structure data: list of clients, each with a list of their active tasks
    client_dict = {client['client_id']: row_to_dict(client) for client in clients}
    for client_id in client_dict:
        client_dict[client_id]['tasks'] = [] # Initialize empty task list

    for task in tasks:
        task_dict = row_to_dict(task)
        client_id = task_dict['client_id']
        if client_id in client_dict:
            client_dict[client_id]['tasks'].append(task_dict)

    # Return clients as a list, maintaining the original order
    result_clients = [client_dict[client['client_id']] for client in clients]

    return jsonify({"clients": result_clients})


# --- Frontend Route ---

@app.route('/')
def index():
    # Serve the main HTML page
    return render_template('index.html')


# --- Root Endpoint (Optional - Keep or remove) ---
# @app.route('/')
# def hello_world():
#     return 'Hello, World! Backend is running.'

if __name__ == '__main__':
    # Ensure database is initialized before running the app
    from app.db_setup import initialize_database
    initialize_database()
    # Note: Debug mode should be False in production
    # Use host='0.0.0.0' to make it accessible on the network
    app.run(host='0.0.0.0', port=5000, debug=True) 