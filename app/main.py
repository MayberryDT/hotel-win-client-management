import psycopg2
from flask import Flask, request, jsonify, render_template
from datetime import datetime, date

from app.db_setup import get_db_connection

# Explicitly set template and static folder paths relative to the project root
app = Flask(__name__, template_folder='app/templates', static_folder='app/static')

# Ensure database is initialized when the app starts
from app.db_setup import initialize_database
initialize_database()

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
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients ORDER BY name')
    clients = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([row_to_dict(client) for client in clients])

@app.route('/api/clients', methods=['POST'])
def add_client():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "Missing 'name' field"}), 400

    name = data['name']
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO clients (name) VALUES (%s) RETURNING client_id', (name,))
        new_client_id = cursor.fetchone()['client_id']
        conn.commit()
        cursor.execute('SELECT * FROM clients WHERE client_id = %s', (new_client_id,))
        new_client = cursor.fetchone()
        cursor.close()
        conn.close()
        if new_client:
            return jsonify(row_to_dict(new_client)), 201
        else:
             # Should not happen if insert succeeded, but good practice
            return jsonify({"error": "Failed to retrieve created client"}), 500
    except psycopg2.IntegrityError as e:
         conn.rollback()
         cursor.close()
         conn.close()
         # Handle potential future integrity constraints (e.g., unique name)
         print(f"Database integrity error: {e}")
         return jsonify({"error": "Database integrity error", "message": str(e)}), 400
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise e # Re-raise for generic error handler


@app.route('/api/clients/<int:client_id>', methods=['PUT'])
def update_client(client_id):
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "Missing 'name' field"}), 400

    name = data['name']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE clients SET name = %s WHERE client_id = %s', (name, client_id))
    if cursor.rowcount == 0:
        cursor.close()
        conn.close()
        return jsonify({"error": "Client not found"}), 404

    conn.commit()
    cursor.execute('SELECT * FROM clients WHERE client_id = %s', (client_id,))
    updated_client = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(row_to_dict(updated_client))

@app.route('/api/clients/<int:client_id>', methods=['DELETE'])
def delete_client(client_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM clients WHERE client_id = %s', (client_id,))
    if cursor.rowcount == 0:
        cursor.close()
        conn.close()
        return jsonify({"error": "Client not found"}), 404

    conn.commit()
    cursor.close()
    conn.close()
    return '', 204 # No Content


# --- Task Endpoints ---

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    client_id = request.args.get('client_id', type=int)
    conn = get_db_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM tasks WHERE is_completed = FALSE'
    params = []
    if client_id:
        query += ' AND client_id = %s'
        params.append(client_id)
    query += ' ORDER BY due_date ASC NULLS LAST'

    cursor.execute(query, params)
    tasks = cursor.fetchall()
    cursor.close()
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
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT client_id FROM clients WHERE client_id = %s', (client_id,))
        client = cursor.fetchone()
        if not client:
            cursor.close()
            conn.close()
            return jsonify({"error": f"Client with id {client_id} not found"}), 400

        cursor.execute(
            'INSERT INTO tasks (client_id, description, due_date) VALUES (%s, %s, %s) RETURNING task_id',
            (client_id, description, due_date)
        )
        new_task_id = cursor.fetchone()['task_id']
        conn.commit()
        cursor.execute('SELECT * FROM tasks WHERE task_id = %s', (new_task_id,))
        new_task = cursor.fetchone()
        cursor.close()
        conn.close()
        if new_task:
             return jsonify(row_to_dict(new_task)), 201
        else:
             return jsonify({"error": "Failed to retrieve created task"}), 500
    except psycopg2.IntegrityError as e:
        conn.rollback()
        cursor.close()
        conn.close()
        print(f"Database integrity error: {e}")
        return jsonify({"error": "Database integrity error, likely invalid client_id", "message": str(e)}), 400
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise e

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json()
    description = data.get('description')
    due_date_provided = 'due_date' in data
    due_date_str = data.get('due_date')

    if description is None and not due_date_provided:
        return jsonify({"error": "Missing 'description' or 'due_date' field to update"}), 400

    due_date = None
    if due_date_provided and due_date_str:
        try:
            due_date = date.fromisoformat(due_date_str)
        except ValueError:
            return jsonify({"error": "Invalid 'due_date' format. Use YYYY-MM-DD."}), 400
    elif due_date_provided and due_date_str is None:
        due_date = None
    elif due_date_provided:
         return jsonify({"error": "Invalid 'due_date' format. Use YYYY-MM-DD string or null."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE task_id = %s', (task_id,))
    task = cursor.fetchone()
    if not task:
        cursor.close()
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    params_list = []
    set_clauses = []

    if description is not None:
        set_clauses.append("description = %s")
        params_list.append(description)

    if due_date_provided:
        set_clauses.append("due_date = %s")
        params_list.append(due_date)

    if not set_clauses:
        cursor.close()
        conn.close()
        return jsonify({"error": "No valid fields provided for update"}), 400

    set_clause = ", ".join(set_clauses)
    params_list.append(task_id)
    params = tuple(params_list)

    query = f'UPDATE tasks SET {set_clause} WHERE task_id = %s'

    cursor.execute(query, params)
    if cursor.rowcount == 0:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": "Task not found during update or no change made"}), 404

    conn.commit()
    cursor.execute('SELECT * FROM tasks WHERE task_id = %s', (task_id,))
    updated_task = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(row_to_dict(updated_task))


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE task_id = %s', (task_id,))
    if cursor.rowcount == 0:
        cursor.close()
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    conn.commit()
    cursor.close()
    conn.close()
    return '', 204 # No Content

@app.route('/api/tasks/<int:task_id>/complete', methods=['PATCH'])
def complete_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    cursor.execute(
        'UPDATE tasks SET is_completed = TRUE, completed_at = %s WHERE task_id = %s',
        (now, task_id)
    )
    if cursor.rowcount == 0:
        cursor.close()
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    conn.commit()
    cursor.execute('SELECT * FROM tasks WHERE task_id = %s', (task_id,))
    updated_task = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(row_to_dict(updated_task))

@app.route('/api/tasks/<int:task_id>/incomplete', methods=['PATCH'])
def incomplete_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE tasks SET is_completed = FALSE, completed_at = NULL WHERE task_id = %s',
        (task_id,)
    )
    if cursor.rowcount == 0:
        cursor.close()
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    conn.commit()
    cursor.execute('SELECT * FROM tasks WHERE task_id = %s', (task_id,))
    updated_task = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(row_to_dict(updated_task))

# --- History Endpoint ---

@app.route('/api/tasks/history', methods=['GET'])
def get_task_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM tasks WHERE is_completed = TRUE ORDER BY completed_at DESC'
    )
    tasks = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([row_to_dict(task) for task in tasks])


# --- Consolidated Data Endpoint ---

@app.route('/api/data', methods=['GET'])
def get_all_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients ORDER BY name')
    clients = cursor.fetchall()
    cursor.execute(
        'SELECT * FROM tasks WHERE is_completed = FALSE ORDER BY client_id, due_date ASC NULLS LAST'
    )
    tasks = cursor.fetchall()
    cursor.close()
    conn.close()

    client_dict = {client['client_id']: row_to_dict(client) for client in clients}
    for client_id in client_dict:
        client_dict[client_id]['tasks'] = []

    for task in tasks:
        task_dict = row_to_dict(task)
        client_id = task_dict['client_id']
        if client_id in client_dict:
            client_dict[client_id]['tasks'].append(task_dict)

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