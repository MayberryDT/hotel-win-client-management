# Collaborative To-Do List - Implementation Plan

This document outlines the steps required to build the collaborative to-do list web application as specified.

## Phase 1: Backend Setup & Database Design

-   [X] **Choose Backend Technology:**
    -   Selected Python/Flask.
-   [X] **Project Structure:**
    -   Set up `app/`, `static/`, `templates/`, `database/`.
-   [X] **Initialize SQLite Database:**
    -   Created `database/todo_app.db` via script.
-   [X] **Database Schema Design:**
    -   Defined `clients` and `tasks` tables in `app/db_setup.py`.
    -   Added basic indexes.
-   [X] **Database Connection Module:**
    -   Created `get_db_connection` in `app/db_setup.py`.

## Phase 2: Backend API Endpoints

-   [X] **Base API Setup:**
    -   Configure the chosen framework to serve API endpoints.
-   [X] **Client Endpoints:**
    -   `GET /api/clients`: Fetch all clients.
    -   `POST /api/clients`: Create a new client (requires `name`).
    -   `PUT /api/clients/<client_id>`: Update a client's name.
    -   `DELETE /api/clients/<client_id>`: Delete a client and all associated tasks (handle cascade).
-   [X] **Task Endpoints:**
    -   `GET /api/tasks`: Fetch all active tasks, optionally filtered by `client_id`. Should return tasks sorted by `due_date`.
    -   `POST /api/tasks`: Create a new task (requires `client_id`, `description`, `due_date`).
    -   `PUT /api/tasks/<task_id>`: Update a task's details (`description`, `due_date`).
    -   `DELETE /api/tasks/<task_id>`: Delete a task.
    -   `PATCH /api/tasks/<task_id>/complete`: Mark a task as completed (`is_completed = 1`, set `completed_at`).
    -   `PATCH /api/tasks/<task_id>/incomplete`: Mark a task as incomplete (`is_completed = 0`, clear `completed_at`).
-   [X] **History Endpoint:**
    -   `GET /api/tasks/history`: Fetch all completed tasks (`is_completed = 1`), sorted by `completed_at` (descending).
-   [X] **Consolidated Data Endpoint (Optional but recommended for initial load/polling):**
    -   `GET /api/data`: Fetch all necessary data in one go (e.g., all clients and their *active* tasks, sorted). This reduces requests for initial load and polling.

## Phase 3: Frontend Structure & Basic UI

-   [X] **HTML Structure (`index.html`):**
    -   Set up the main HTML file.
    -   Defined main layout sections: Editing, Client List, Task Display, History.
-   [X] **CSS Foundation:**
    -   Basic styling for layout, typography, readability.
-   [X] **JavaScript Setup:**
    -   Included `app.js`.
    -   Basic event listeners and functions.

## Phase 4: Client Management Implementation (UI + Logic)

-   [X] **Display Clients:** Fetched and rendered dynamically.
-   [X] **Add Client:** Implemented via form and API.
-   [X] **Edit Client:** Implemented via form and API.
-   [X] **Delete Client:** Implemented with confirmation and API.
-   [X] **Client Selection:** Implemented with highlighting and task loading trigger.

## Phase 5: Task Management Implementation (UI + Logic)

-   [X] **Display Tasks:** Fetched and rendered for selected client, sorted by due date.
-   [X] **Add Task:** Implemented via unified form and API.
-   [X] **Edit Task:** Implemented via unified form and API.
-   [X] **Delete Task:** Implemented with confirmation and API.

## Phase 6: Task Completion & History (UI + Logic)

-   [X] **Mark Task Complete/Incomplete:** Implemented via checkbox and API.
-   [X] **Display Completed Task History:** Implemented history section with fetch and render.
-   [X] **Undo Completion (from History):** Implemented via button and API.

## Phase 7: Real-time Synchronization (Polling)

-   [X] **Implement Data Polling:** Used `setInterval` with `GET /api/data`.
-   [X] **UI Refresh Logic:** Implemented data comparison and selective UI refresh.
-   [X] **Handle Editing Conflicts:** Used `isUserEditing` flag to prevent polling disruption.
-   [ ] **Alternative: WebSocket/SSE (Optional Enhancement):** *(Not implemented)*

## Phase 8: Styling, UI Refinement & Optimization

-   [X] **Compact UI Styling:**
    -   Refined CSS (`style.css`) for a more compact, modern look (system fonts, reduced padding/margins, softer borders, improved layout).
    -   Used flexbox for main layout and form elements.
-   [X] **Cross-Device/Browser Styling:**
    -   Added basic responsive design using media queries (`@media`) for tablet and mobile screen sizes.
    -   Adjusted layout (stacking), font sizes, and padding for smaller screens.
    -   *(Manual cross-browser testing still recommended)*.
-   [X] **Performance Optimization:**
    -   Optimized database queries (Added indexes for `client_id`, `due_date`, `is_completed` in `db_setup.py`).
    -   Minimized JavaScript execution (Cached DOM elements, refined polling logic to skip when tab hidden).
    -   Optimized frontend rendering (Cleared lists before rendering, used placeholders, avoided unnecessary full re-renders during polling if data hasn't changed).
-   [X] **Usability Improvements:**
    -   Added clear visual feedback for actions (loading/success/error messages via `status-message` div).
    -   Refined focus management (basic focus set on form inputs during edit/add).
    -   Added `required` attribute to form inputs.
    -   Improved history toggle button text ('Show'/'Hide').
    -   Added click propagation stop for action buttons inside list items.

## Phase 9: Testing & Deployment

-   [ ] **Manual Testing:**
    -   Test all core functionalities thoroughly with simulated concurrent use (two browser windows).
    -   Test edge cases (deleting clients with tasks, editing rapidly, empty states).
    -   Test on different browsers and devices.
-   [ ] **Backend Deployment:**
    -   Choose a hosting provider/method.
    -   Configure the server.
-   [ ] **Frontend Deployment:**
    -   Serve static files efficiently.
-   [ ] **Single URL Configuration:**
    -   Ensure the application is accessible via one fixed URL.

## Phase 10: Documentation

-   [ ] **README.md:**
    -   Add setup, run, and deployment instructions.
    -   Describe architecture.