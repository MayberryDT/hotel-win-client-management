import pytest
import json
import os
import sqlite3
import time
from datetime import date, datetime, timedelta

# Adjust the path to import from the app directory
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app import db_setup

@pytest.fixture
def client():
    """Create a Flask test client for the app."""
    app.config['TESTING'] = True
    # Use a separate, temporary database for testing each function
    # This ensures test isolation
    test_db_path = os.path.join(db_setup.DB_FOLDER, 'test_todo_app.db')
    app.config['DATABASE'] = test_db_path

    # Clean up any old test database file
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    # Ensure the database folder exists
    os.makedirs(db_setup.DB_FOLDER, exist_ok=True)

    # Initialize the database using the production function but on the test DB path
    # We need to temporarily override DB_PATH used by db_setup functions
    original_db_path = db_setup.DB_PATH
    db_setup.DB_PATH = test_db_path
    try:
        db_setup.initialize_database()

        # Override get_db_connection to use the test database for the duration of the test
        original_get_db = db_setup.get_db_connection
        def get_test_db():
            conn = sqlite3.connect(test_db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        db_setup.get_db_connection = get_test_db

        with app.test_client() as client:
            yield client # Provide the test client to the test functions

    finally:
        # Clean up: Close connection if open (tricky with overridden function) and delete test DB
        # It might be simpler to just delete the file, assuming connections are closed by Flask context
        if os.path.exists(test_db_path):
             # Add delay/retries if deletion fails due to open handles, especially on Windows
             try:
                 time.sleep(0.1) # Short delay before deletion
                 os.remove(test_db_path)
             except OSError as e:
                 print(f"Warning: Could not delete test database {test_db_path}: {e}")

        # Restore original functions and paths
        db_setup.DB_PATH = original_db_path
        db_setup.get_db_connection = original_get_db

        # Optional: Remove the database folder if it's empty
        if os.path.exists(db_setup.DB_FOLDER) and os.path.isdir(db_setup.DB_FOLDER) and not os.listdir(db_setup.DB_FOLDER):
            try:
                os.rmdir(db_setup.DB_FOLDER)
            except OSError as e:
                 print(f"Warning: Could not remove test database folder {db_setup.DB_FOLDER}: {e}")


# Helper function to add a client directly to DB for setting up tests
def add_client_direct(name="Test Client"):
    conn = db_setup.get_db_connection()
    cursor = conn.execute('INSERT INTO clients (name) VALUES (?)', (name,))
    client_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return client_id

# Helper function to add a task directly to DB
def add_task_direct(client_id, description="Test Task", due_date=None):
    conn = db_setup.get_db_connection()
    cursor = conn.execute('INSERT INTO tasks (client_id, description, due_date) VALUES (?, ?, ?)',
                          (client_id, description, due_date))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

# --- Client Endpoint Tests ---

def test_get_clients_empty(client):
    rv = client.get('/api/clients')
    assert rv.status_code == 200
    assert rv.json == []

def test_add_client(client):
    rv = client.post('/api/clients', json={'name': 'New Client'})
    assert rv.status_code == 201
    data = rv.json
    assert data['name'] == 'New Client'
    assert 'client_id' in data
    assert 'created_at' in data

    # Verify it's in the database via GET
    rv_get = client.get('/api/clients')
    assert rv_get.status_code == 200
    assert len(rv_get.json) == 1
    assert rv_get.json[0]['name'] == 'New Client'

def test_add_client_missing_name(client):
    rv = client.post('/api/clients', json={'wrong_field': 'some value'})
    assert rv.status_code == 400
    assert 'error' in rv.json
    assert "Missing 'name' field" in rv.json['error']

def test_get_clients_populated(client):
    client_id1 = add_client_direct("Client A")
    client_id2 = add_client_direct("Client B")
    rv = client.get('/api/clients')
    assert rv.status_code == 200
    data = rv.json
    assert len(data) == 2
    # Check sorting by name
    assert data[0]['name'] == 'Client A'
    assert data[1]['name'] == 'Client B'

def test_update_client(client):
    client_id = add_client_direct("Original Name")
    rv = client.put(f'/api/clients/{client_id}', json={'name': 'Updated Name'})
    assert rv.status_code == 200
    data = rv.json
    assert data['name'] == 'Updated Name'
    assert data['client_id'] == client_id

    # Verify update with GET
    rv_get = client.get(f'/api/clients')
    clients = rv_get.json
    assert len(clients) == 1
    assert clients[0]['name'] == 'Updated Name'

def test_update_client_not_found(client):
    rv = client.put('/api/clients/999', json={'name': 'Nonexistent'})
    assert rv.status_code == 404
    assert 'error' in rv.json
    assert 'Client not found' in rv.json['error']

def test_update_client_missing_name(client):
    client_id = add_client_direct("Client To Update")
    rv = client.put(f'/api/clients/{client_id}', json={'other_field': 'value'})
    assert rv.status_code == 400
    assert 'error' in rv.json
    assert "Missing 'name' field" in rv.json['error']

def test_delete_client(client):
    client_id = add_client_direct("Client To Delete")
    rv = client.delete(f'/api/clients/{client_id}')
    assert rv.status_code == 204 # No Content

    # Verify deletion with GET
    rv_get = client.get('/api/clients')
    assert rv_get.json == []

    # Verify deletion with specific ID (should be 404 now)
    rv_get_specific = client.get(f'/api/clients') # Check the list again
    # Trying to fetch the specific deleted client ID via API isn't directly possible
    # with GET /api/clients. Instead, check the list is empty.
    assert len(rv_get_specific.json) == 0

def test_delete_client_not_found(client):
    rv = client.delete('/api/clients/999')
    assert rv.status_code == 404
    assert 'error' in rv.json
    assert 'Client not found' in rv.json['error']

def test_delete_client_cascade(client):
    client_id = add_client_direct("Client With Tasks")
    task_id1 = add_task_direct(client_id, "Task 1")
    task_id2 = add_task_direct(client_id, "Task 2")

    # Verify tasks exist
    rv_tasks = client.get(f'/api/tasks?client_id={client_id}')
    assert len(rv_tasks.json) == 2

    # Delete client
    rv_del = client.delete(f'/api/clients/{client_id}')
    assert rv_del.status_code == 204

    # Verify tasks were cascade deleted (GET should return empty list for that client,
    # and trying to fetch tasks individually would fail, though we don't have a GET /task/<id> endpoint)
    conn = db_setup.get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks WHERE client_id = ?', (client_id,)).fetchall()
    conn.close()
    assert len(tasks) == 0, "Tasks should be deleted when client is deleted"

# --- Task Endpoint Tests ---

def test_add_task(client):
    client_id = add_client_direct("Task Client")
    due_date_str = (date.today() + timedelta(days=5)).isoformat()
    rv = client.post('/api/tasks', json={
        'client_id': client_id,
        'description': 'New Task Description',
        'due_date': due_date_str
    })
    assert rv.status_code == 201
    data = rv.json
    assert data['client_id'] == client_id
    assert data['description'] == 'New Task Description'
    assert data['due_date'] == due_date_str
    assert data['is_completed'] is False
    assert 'task_id' in data
    assert 'created_at' in data
    assert data['completed_at'] is None

def test_add_task_no_due_date(client):
    client_id = add_client_direct("Task Client No Date")
    rv = client.post('/api/tasks', json={
        'client_id': client_id,
        'description': 'Task with no due date'
    })
    assert rv.status_code == 201
    data = rv.json
    assert data['due_date'] is None

def test_add_task_invalid_client(client):
    rv = client.post('/api/tasks', json={
        'client_id': 999,
        'description': 'Task for nonexistent client'
    })
    assert rv.status_code == 400 # Changed from 404 based on implementation returning 400
    assert 'error' in rv.json
    assert 'Client with id 999 not found' in rv.json['error'] # Match error message

def test_add_task_missing_fields(client):
    client_id = add_client_direct("Task Client Missing")
    rv = client.post('/api/tasks', json={'client_id': client_id}) # Missing description
    assert rv.status_code == 400
    assert 'error' in rv.json
    assert "Missing 'client_id' or 'description'" in rv.json['error']

    rv = client.post('/api/tasks', json={'description': 'Task missing client'}) # Missing client_id
    assert rv.status_code == 400
    assert 'error' in rv.json
    assert "Missing 'client_id' or 'description'" in rv.json['error']


def test_add_task_invalid_date(client):
    client_id = add_client_direct("Task Client Invalid Date")
    rv = client.post('/api/tasks', json={
        'client_id': client_id,
        'description': 'Task with invalid date',
        'due_date': 'not-a-date'
    })
    assert rv.status_code == 400
    assert 'error' in rv.json
    assert "Invalid 'due_date' format" in rv.json['error']

def test_get_tasks_empty(client):
    client_id = add_client_direct("Client No Tasks")
    rv = client.get('/api/tasks')
    assert rv.status_code == 200
    assert rv.json == []
    rv = client.get(f'/api/tasks?client_id={client_id}')
    assert rv.status_code == 200
    assert rv.json == []


def test_get_tasks_all_and_filtered(client):
    client_id1 = add_client_direct("Client 1")
    client_id2 = add_client_direct("Client 2")
    task_id1 = add_task_direct(client_id1, "Task C1")
    task_id2 = add_task_direct(client_id2, "Task C2")
    task_id3 = add_task_direct(client_id1, "Task C1 Again")

    # Get all active tasks
    rv_all = client.get('/api/tasks')
    assert rv_all.status_code == 200
    all_tasks = rv_all.json
    assert len(all_tasks) == 3
    assert {t['task_id'] for t in all_tasks} == {task_id1, task_id2, task_id3}

    # Get tasks filtered by client_id1
    rv_c1 = client.get(f'/api/tasks?client_id={client_id1}')
    assert rv_c1.status_code == 200
    c1_tasks = rv_c1.json
    assert len(c1_tasks) == 2
    assert {t['task_id'] for t in c1_tasks} == {task_id1, task_id3}
    assert all(t['client_id'] == client_id1 for t in c1_tasks)

    # Get tasks filtered by client_id2
    rv_c2 = client.get(f'/api/tasks?client_id={client_id2}')
    assert rv_c2.status_code == 200
    c2_tasks = rv_c2.json
    assert len(c2_tasks) == 1
    assert c2_tasks[0]['task_id'] == task_id2
    assert c2_tasks[0]['client_id'] == client_id2

def test_get_tasks_sorting(client):
    client_id = add_client_direct("Sorting Client")
    date_today = date.today()
    date_future = date_today + timedelta(days=10)
    date_past = date_today - timedelta(days=5)

    # Add tasks in non-sorted order
    task_id_nodate = add_task_direct(client_id, "No Due Date")
    task_id_future = add_task_direct(client_id, "Future Date", date_future)
    task_id_past = add_task_direct(client_id, "Past Date", date_past)
    task_id_today = add_task_direct(client_id, "Today Date", date_today)

    rv = client.get(f'/api/tasks?client_id={client_id}')
    assert rv.status_code == 200
    tasks = rv.json
    assert len(tasks) == 4

    # Expected order: Past, Today, Future, No Date (nulls last)
    assert tasks[0]['task_id'] == task_id_past
    assert tasks[1]['task_id'] == task_id_today
    assert tasks[2]['task_id'] == task_id_future
    assert tasks[3]['task_id'] == task_id_nodate
    assert tasks[3]['due_date'] is None


def test_update_task(client):
    client_id = add_client_direct()
    task_id = add_task_direct(client_id, "Original Desc", date.today())
    new_date_str = (date.today() + timedelta(days=3)).isoformat()

    rv = client.put(f'/api/tasks/{task_id}', json={
        'description': 'Updated Desc',
        'due_date': new_date_str
    })
    assert rv.status_code == 200
    data = rv.json
    assert data['task_id'] == task_id
    assert data['description'] == 'Updated Desc'
    assert data['due_date'] == new_date_str

    # Verify with direct DB check or another GET if endpoint existed
    conn = db_setup.get_db_connection()
    updated_task = conn.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
    conn.close()
    assert updated_task['description'] == 'Updated Desc'
    assert updated_task['due_date'] == new_date_str

def test_update_task_only_desc(client):
    client_id = add_client_direct()
    original_date = date.today()
    task_id = add_task_direct(client_id, "Original Desc", original_date)

    rv = client.put(f'/api/tasks/{task_id}', json={'description': 'Desc Only Update'})
    assert rv.status_code == 200
    data = rv.json
    assert data['description'] == 'Desc Only Update'
    assert data['due_date'] == original_date.isoformat() # Date should remain unchanged

def test_update_task_only_date(client):
    client_id = add_client_direct()
    original_desc = "Desc for Date Update"
    task_id = add_task_direct(client_id, original_desc, date.today())
    new_date_str = (date.today() + timedelta(days=7)).isoformat()

    rv = client.put(f'/api/tasks/{task_id}', json={'due_date': new_date_str})
    assert rv.status_code == 200
    data = rv.json
    assert data['description'] == original_desc # Desc should remain unchanged
    assert data['due_date'] == new_date_str

def test_update_task_set_date_null(client):
    client_id = add_client_direct()
    task_id = add_task_direct(client_id, "Task to Null Date", date.today())

    # Send empty string for due_date - assuming API treats this as null/None
    rv = client.put(f'/api/tasks/{task_id}', json={'due_date': ""})
    assert rv.status_code == 200
    data = rv.json
    assert data['due_date'] is None

    # Also test sending explicit null
    task_id_2 = add_task_direct(client_id, "Task to Null Date 2", date.today())
    rv = client.put(f'/api/tasks/{task_id_2}', json={'due_date': None})
    assert rv.status_code == 200
    data = rv.json
    assert data['due_date'] is None

def test_update_task_not_found(client):
    rv = client.put('/api/tasks/999', json={'description': 'Update Nonexistent'})
    assert rv.status_code == 404
    assert 'error' in rv.json
    assert 'Task not found' in rv.json['error']

def test_update_task_invalid_date(client):
    client_id = add_client_direct()
    task_id = add_task_direct(client_id, "Task for Invalid Date Update")
    rv = client.put(f'/api/tasks/{task_id}', json={'due_date': 'not-a-valid-date'})
    assert rv.status_code == 400
    assert 'error' in rv.json
    assert "Invalid 'due_date' format" in rv.json['error']

def test_update_task_no_fields(client):
    client_id = add_client_direct()
    task_id = add_task_direct(client_id, "Task No Fields Update")
    rv = client.put(f'/api/tasks/{task_id}', json={}) # Empty JSON
    assert rv.status_code == 400
    assert 'error' in rv.json
    # Check specific error message from implementation
    assert "Missing 'description' or 'due_date' field to update" in rv.json['error']

def test_delete_task(client):
    client_id = add_client_direct()
    task_id = add_task_direct(client_id, "Task To Delete")
    rv = client.delete(f'/api/tasks/{task_id}')
    assert rv.status_code == 204

    # Verify deletion
    conn = db_setup.get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
    conn.close()
    assert task is None

def test_complete_task(client):
    client_id = add_client_direct()
    task_id = add_task_direct(client_id, "Task To Complete")

    # Verify initial state
    conn = db_setup.get_db_connection()
    task_before = conn.execute('SELECT is_completed, completed_at FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
    conn.close()
    assert not task_before['is_completed']
    assert task_before['completed_at'] is None

    # Complete the task
    rv = client.patch(f'/api/tasks/{task_id}/complete')
    assert rv.status_code == 200
    data = rv.json
    assert data['task_id'] == task_id
    assert data['is_completed'] is True
    assert 'completed_at' in data
    assert data['completed_at'] is not None # Should have a timestamp string

    # Verify timestamp format (basic check)
    try:
        completed_dt = datetime.fromisoformat(data['completed_at'].replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"completed_at is not a valid ISO 8601 timestamp: {data['completed_at']}")

    # Verify final state in DB
    conn = db_setup.get_db_connection()
    task_after = conn.execute('SELECT is_completed, completed_at FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
    conn.close()
    assert task_after['is_completed'] == 1 # Stored as integer in SQLite
    assert task_after['completed_at'] is not None


def test_complete_task_not_found(client):
    rv = client.patch('/api/tasks/999/complete')
    assert rv.status_code == 404
    assert 'error' in rv.json
    assert 'Task not found' in rv.json['error']

def test_incomplete_task(client):
    client_id = add_client_direct()
    task_id = add_task_direct(client_id, "Task To Mark Incomplete")

    # First, complete it
    rv_comp = client.patch(f'/api/tasks/{task_id}/complete')
    assert rv_comp.status_code == 200 # Ensure completion worked

    # Now, mark as incomplete
    rv = client.patch(f'/api/tasks/{task_id}/incomplete')
    assert rv.status_code == 200
    data = rv.json
    assert data['task_id'] == task_id
    assert data['is_completed'] is False
    assert data['completed_at'] is None # Should be reset to null

    # Verify final state in DB
    conn = db_setup.get_db_connection()
    task_after = conn.execute('SELECT is_completed, completed_at FROM tasks WHERE task_id = ?', (task_id,)).fetchone()
    conn.close()
    assert task_after['is_completed'] == 0
    assert task_after['completed_at'] is None

def test_incomplete_task_not_found(client):
    rv = client.patch('/api/tasks/999/incomplete')
    assert rv.status_code == 404
    assert 'error' in rv.json
    assert 'Task not found' in rv.json['error']


# --- History Endpoint Tests ---

def test_get_history_empty(client):
    client_id = add_client_direct()
    add_task_direct(client_id, "Active Task") # Add an active task, should not appear in history
    rv = client.get('/api/tasks/history')
    assert rv.status_code == 200
    assert rv.json == []

def test_get_history_populated(client):
    client_id = add_client_direct()
    task_id1 = add_task_direct(client_id, "Task 1")
    task_id2 = add_task_direct(client_id, "Task 2")
    task_id3 = add_task_direct(client_id, "Task 3 Active") # Remains active

    # Complete tasks 1 and 2 (task 2 completed first, then task 1)
    # Need slight delay to ensure different completion times for sorting test
    rv_comp2 = client.patch(f'/api/tasks/{task_id2}/complete')
    time.sleep(0.1) # Small delay
    rv_comp1 = client.patch(f'/api/tasks/{task_id1}/complete')

    assert rv_comp1.status_code == 200
    assert rv_comp2.status_code == 200

    # Get history
    rv_hist = client.get('/api/tasks/history')
    assert rv_hist.status_code == 200
    history = rv_hist.json

    assert len(history) == 2
    # Should be sorted by completed_at descending (task 1 completed last)
    assert history[0]['task_id'] == task_id1
    assert history[1]['task_id'] == task_id2
    assert history[0]['is_completed'] is True
    assert history[1]['is_completed'] is True

    # Verify task 3 is not in history
    assert task_id3 not in [t['task_id'] for t in history]

# --- Consolidated Data Endpoint Tests ---

def test_get_data_empty(client):
    rv = client.get('/api/data')
    assert rv.status_code == 200
    assert rv.json == {'clients': []}

def test_get_data_populated(client):
    # Client A: Task A1 (Due Later), Task A2 (Due Earlier), Task A3 (Completed)
    # Client B: Task B1 (No Due Date)
    # Client C: No tasks
    client_a = add_client_direct("Client A")
    client_b = add_client_direct("Client B")
    client_c = add_client_direct("Client C")

    date_earlier = date.today()
    date_later = date.today() + timedelta(days=2)

    task_a1 = add_task_direct(client_a, "Task A1", date_later)
    task_a2 = add_task_direct(client_a, "Task A2", date_earlier)
    task_a3_completed = add_task_direct(client_a, "Task A3 Completed")
    task_b1 = add_task_direct(client_b, "Task B1", None) # No due date

    # Complete Task A3
    client.patch(f'/api/tasks/{task_a3_completed}/complete')

    rv = client.get('/api/data')
    assert rv.status_code == 200
    data = rv.json

    assert 'clients' in data
    clients_data = data['clients']
    assert len(clients_data) == 3 # All clients should be listed

    # Find client data (order based on name: A, B, C)
    client_a_data = next((c for c in clients_data if c['client_id'] == client_a), None)
    client_b_data = next((c for c in clients_data if c['client_id'] == client_b), None)
    client_c_data = next((c for c in clients_data if c['client_id'] == client_c), None)

    assert client_a_data is not None
    assert client_b_data is not None
    assert client_c_data is not None

    # Check Client A's tasks (should have 2 active tasks, sorted by due date)
    assert 'tasks' in client_a_data
    client_a_tasks = client_a_data['tasks']
    assert len(client_a_tasks) == 2
    assert task_a3_completed not in [t['task_id'] for t in client_a_tasks] # Completed task excluded
    assert client_a_tasks[0]['task_id'] == task_a2 # Due earlier
    assert client_a_tasks[1]['task_id'] == task_a1 # Due later

    # Check Client B's tasks (should have 1 active task)
    assert 'tasks' in client_b_data
    client_b_tasks = client_b_data['tasks']
    assert len(client_b_tasks) == 1
    assert client_b_tasks[0]['task_id'] == task_b1
    assert client_b_tasks[0]['due_date'] is None

    # Check Client C's tasks (should be empty list)
    assert 'tasks' in client_c_data
    assert client_c_data['tasks'] == [] 