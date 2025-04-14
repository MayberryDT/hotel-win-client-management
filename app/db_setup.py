import psycopg2
import psycopg2.extras # For DictCursor
import os

# Define the path for the database relative to this script - REMOVED SQLite specific path
# DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'database')
# DB_PATH = os.path.join(DB_FOLDER, 'todo_app.db')

# --- PostgreSQL Setup ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # Provide a default for local development IF NEEDED, or raise an error
    # For now, raise an error if not set when this module is loaded.
    # You might want to use python-dotenv for local .env file handling.
    raise ValueError("DATABASE_URL environment variable not set.")

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    # os.makedirs(DB_FOLDER, exist_ok=True) # Ensure the database folder exists - REMOVED SQLite specific folder creation
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        # conn.row_factory = sqlite3.Row # Return rows as dictionaries - Handled by DictCursor
        # conn.execute("PRAGMA foreign_keys = ON") # Ensure foreign key constraints are enforced - Not needed/different in PG
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to database: {e}")
        # Handle connection error appropriately - maybe raise or exit
        raise

def initialize_database():
    """Initializes the database by creating tables if they don't exist."""
    print("Attempting to initialize PostgreSQL database...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create clients table (PostgreSQL syntax)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            client_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )""")
        print("Clients table checked/created.")

        # Create tasks table (PostgreSQL syntax)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            due_date DATE,
            is_completed BOOLEAN DEFAULT FALSE,
            completed_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        )""")
        print("Tasks table checked/created.")

        # Add potential indexes for performance (PostgreSQL syntax)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_client_id ON tasks(client_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_is_completed ON tasks(is_completed)")
        print("Indexes checked/created.")

        conn.commit()
        cursor.close()
        conn.close()
        # print(f"Database initialized/verified at {DB_PATH}") - Removed SQLite path
        print("PostgreSQL database initialization complete.")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        # Optionally rollback if partial changes were made, though IF NOT EXISTS helps
        # Handle error appropriately
        raise # Re-raise the exception to make the failure visible

if __name__ == '__main__':
    print("Running db_setup directly...")
    initialize_database() 