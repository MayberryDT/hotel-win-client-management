import sqlite3
import os

# Define the path for the database relative to this script
DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'database')
DB_PATH = os.path.join(DB_FOLDER, 'todo_app.db')

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    os.makedirs(DB_FOLDER, exist_ok=True) # Ensure the database folder exists
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Return rows as dictionaries
    conn.execute("PRAGMA foreign_keys = ON") # Ensure foreign key constraints are enforced
    return conn

def initialize_database():
    """Initializes the database by creating tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create clients table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        client_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create tasks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        due_date DATE,
        is_completed BOOLEAN DEFAULT 0,
        completed_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
    )
    """)

    # Add potential indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_client_id ON tasks(client_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_is_completed ON tasks(is_completed)")

    conn.commit()
    conn.close()
    print(f"Database initialized/verified at {DB_PATH}")

if __name__ == '__main__':
    initialize_database() 