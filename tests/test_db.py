import pytest
import sqlite3
import os

# Assume db_setup.py is in the 'app' directory relative to the project root
from app.db_setup import initialize_database, get_db_connection, DB_PATH, DB_FOLDER

@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    """Fixture to set up and tear down the database for tests."""
    # Ensure a clean slate
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # Initialize the database using the script
    initialize_database()

    yield # Tests run here

    # Teardown: remove the database file after tests
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists(DB_FOLDER) and not os.listdir(DB_FOLDER):
         os.rmdir(DB_FOLDER)

def test_database_file_created():
    """Test if the database file is created."""
    assert os.path.exists(DB_PATH), f"Database file {DB_PATH} should exist after initialization."

def test_tables_exist():
    """Test if the required tables (clients, tasks) are created."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients'")
    result = cursor.fetchone()
    assert result is not None, "Table 'clients' should exist."

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    result = cursor.fetchone()
    assert result is not None, "Table 'tasks' should exist."

    conn.close()

def test_clients_table_schema():
    """Test the schema of the 'clients' table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(clients)")
    columns = {row['name']: row for row in cursor.fetchall()}
    conn.close()

    assert 'client_id' in columns
    assert columns['client_id']['pk'] == 1 # Primary Key
    assert 'INTEGER' in columns['client_id']['type']

    assert 'name' in columns
    assert columns['name']['notnull'] == 1
    assert 'TEXT' in columns['name']['type']

    assert 'created_at' in columns
    assert 'TIMESTAMP' in columns['created_at']['type']
    # Note: Checking default values like CURRENT_TIMESTAMP is complex with PRAGMA

def test_tasks_table_schema():
    """Test the schema of the 'tasks' table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(tasks)")
    columns = {row['name']: row for row in cursor.fetchall()}

    # Check foreign key
    cursor.execute("PRAGMA foreign_key_list(tasks)")
    fks = cursor.fetchall()
    conn.close()

    assert 'task_id' in columns
    assert columns['task_id']['pk'] == 1
    assert 'INTEGER' in columns['task_id']['type']

    assert 'client_id' in columns
    assert columns['client_id']['notnull'] == 1
    assert 'INTEGER' in columns['client_id']['type']

    assert 'description' in columns
    assert columns['description']['notnull'] == 1
    assert 'TEXT' in columns['description']['type']

    assert 'due_date' in columns
    assert 'DATE' in columns['due_date']['type']

    assert 'is_completed' in columns
    assert 'BOOLEAN' in columns['is_completed']['type']
    # Default value check might be tricky

    assert 'completed_at' in columns
    assert 'TIMESTAMP' in columns['completed_at']['type']

    assert 'created_at' in columns
    assert 'TIMESTAMP' in columns['created_at']['type']

    # Verify Foreign Key Constraint
    assert len(fks) == 1, "Should have one foreign key defined for tasks table."
    fk = fks[0]
    assert fk['table'] == 'clients', "Foreign key should reference the 'clients' table."
    assert fk['from'] == 'client_id', "Foreign key should be on the 'client_id' column."
    assert fk['to'] == 'client_id', "Foreign key should reference the 'client_id' column in clients."
    assert fk['on_delete'] == 'CASCADE', "Foreign key ON DELETE action should be CASCADE." 