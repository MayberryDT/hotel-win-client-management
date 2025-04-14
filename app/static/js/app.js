// Main JavaScript file for the Collaborative To-Do List App

// Global state
let clients = [];
let tasks = [];
let selectedClientId = null;
let selectedTask = null; // Added for task editing context
let completedTasks = []; // Added for Phase 6
let pollingIntervalId = null; // Added for Phase 7
const pollingInterval = 5000; // Poll every 5 seconds (Phase 7)
let isUserEditing = false; // Flag to prevent polling refresh during edits (Phase 7)
let currentStatusTimeout = null; // Timeout ID for clearing status messages

// DOM Elements (cache frequently used ones)
let clientListEl, taskListEl, editingForm, editIdInput, editModeInput,
    clientFields, taskFields, clientNameInput, taskDescriptionInput,
    taskDueDateInput, editSubmitBtn, editCancelBtn, editingFormTitle,
    selectedClientNameSpan, completedTaskListEl, historyContainer, toggleHistoryBtn,
    statusMessageEl; // Added statusMessageEl

// Function to display status messages
function showStatusMessage(message, type = 'info', duration = 3000) {
    if (!statusMessageEl) return;

    // Clear any existing timeout
    if (currentStatusTimeout) {
        clearTimeout(currentStatusTimeout);
        currentStatusTimeout = null;
    }

    statusMessageEl.textContent = message;
    statusMessageEl.className = ``; // Clear existing classes
    statusMessageEl.classList.add(type); // Add type class (success, error, loading, info)
    statusMessageEl.style.display = 'block';

    // Trigger reflow for transition
    void statusMessageEl.offsetWidth;

    statusMessageEl.style.opacity = '1';

    // Auto-hide after duration (unless type is 'loading')
    if (type !== 'loading' && duration > 0) {
        currentStatusTimeout = setTimeout(() => {
            hideStatusMessage();
        }, duration);
    }
}

// Function to hide status message
function hideStatusMessage() {
     if (!statusMessageEl) return;

    if (currentStatusTimeout) {
        clearTimeout(currentStatusTimeout);
        currentStatusTimeout = null;
    }

    statusMessageEl.style.opacity = '0';
    // Wait for transition to finish before hiding
    setTimeout(() => {
        statusMessageEl.style.display = 'none';
        statusMessageEl.className = ''; // Clear classes
    }, 500); // Match CSS transition duration
}

// Utility for API calls
async function apiCall(url, method = 'GET', body = null) {
    // Show loading indicator immediately for relevant actions
    const isMutation = method !== 'GET';
    if (isMutation) {
        showStatusMessage('Processing...', 'loading', 0); // Show loading indefinitely
    }

    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            let errorData = { message: `HTTP error ${response.status}` };
            try {
                errorData = await response.json();
            } catch (e) {
                console.warn("Could not parse error response JSON");
            }
            const errorMessage = errorData.message || response.statusText || `HTTP error ${response.status}`;
            console.error(`API Error (${response.status}):`, errorMessage);
            showStatusMessage(`Error: ${errorMessage}`, 'error'); // Show specific error
            return null;
        }
        // Handle 204 No Content specifically (e.g., for DELETE)
        if (response.status === 204) {
             if (isMutation) hideStatusMessage(); // Hide loading on success
            return true;
        }
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            const data = await response.json();
             if (isMutation) hideStatusMessage(); // Hide loading on success
            return data;
        } else {
             if (isMutation) hideStatusMessage(); // Hide loading on success
            return true;
        }
    } catch (error) {
        console.error('Network or API call error:', error);
        showStatusMessage('Network Error: Failed to communicate with the server.', 'error');
        return null;
    } finally {
         // Ensure loading message is hidden if it wasn't already by success/error path
         // But only if it was a mutation that showed it
         if (isMutation && statusMessageEl && statusMessageEl.classList.contains('loading')) {
             hideStatusMessage();
         }
    }
}

// --- Rendering Functions ---
function renderClientList() {
    clientListEl.innerHTML = ''; // Clear existing list

    if (clients.length === 0) {
        clientListEl.innerHTML = '<li class="placeholder">No clients found. Add one!</li>';
        return;
    }

    clients.forEach(client => {
        // Add check for valid client ID (using client_id)
        if (typeof client.client_id === 'undefined' || client.client_id === null) {
            console.error("renderClientList: Skipping client with missing or invalid ID:", client);
            return; // Skip this client
        }

        const li = document.createElement('li');
        li.dataset.clientId = client.client_id; // Use client_id
        if (client.client_id === selectedClientId) { // Use client_id
            li.classList.add('selected');
        }

        // Client Name Span
        const nameSpan = document.createElement('span');
        nameSpan.classList.add('client-name');
        nameSpan.textContent = client.name;
        li.appendChild(nameSpan);

        // Click to select client (attach to li, but check target)
        li.addEventListener('click', (event) => {
            if (!event.target.closest('button')) { // Don't select if clicking buttons
                 selectClient(client.client_id); // Use client_id
            }
        });

        // Action buttons container
        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('client-actions');

        // Edit button
        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.classList.add('edit-btn', 'action-btn');
        editBtn.addEventListener('click', (e) => { e.stopPropagation(); startEditClient(client); }); // Pass the whole client object

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.classList.add('delete-btn', 'action-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const listItem = e.target.closest('li'); // Find the parent <li>
            if (listItem && listItem.dataset.clientId) {
                const clientIdToDelete = listItem.dataset.clientId;
                deleteClient(clientIdToDelete); // Pass the ID from the dataset
            } else {
                console.error("Could not find client ID for deletion in DOM.");
                showStatusMessage("Error: Could not determine client to delete.", "error");
            }
        });

        actionsDiv.appendChild(editBtn);
        actionsDiv.appendChild(deleteBtn);
        li.appendChild(actionsDiv);

        clientListEl.appendChild(li);
    });
}

function renderTaskList() {
    taskListEl.innerHTML = ''; // Clear existing list

    const selectedClient = clients.find(c => c.client_id === selectedClientId); // Use client_id
    selectedClientNameSpan.textContent = selectedClient ? selectedClient.name : 'Selected Client';

    if (!selectedClientId) {
        taskListEl.innerHTML = '<li class="placeholder">Select a client to view tasks.</li>';
        return;
    }

    // Filter only ACTIVE tasks for the selected client
    const clientTasks = tasks.filter(task => task.client_id === selectedClientId && !task.is_completed)
                            .sort((a, b) => new Date(a.due_date || Infinity) - new Date(b.due_date || Infinity)); // Handle null dates

    if (clientTasks.length === 0) {
        taskListEl.innerHTML = '<li class="placeholder">No active tasks for this client.</li>';
        return;
    }

    clientTasks.forEach(task => {
        const li = document.createElement('li');
        li.dataset.taskId = task.id;

        // Completion Checkbox Div
        const completionDiv = document.createElement('div');
        completionDiv.classList.add('task-completion');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = false; // Always unchecked in active list
        checkbox.title = 'Mark task as complete';
        checkbox.addEventListener('change', () => toggleTaskCompletion(task.id, true));
        completionDiv.appendChild(checkbox);
        li.appendChild(completionDiv);

        // Task Details Div
        const detailsDiv = document.createElement('div');
        detailsDiv.classList.add('task-details');

        const descriptionSpan = document.createElement('span');
        descriptionSpan.classList.add('task-description');
        descriptionSpan.textContent = task.description;
        detailsDiv.appendChild(descriptionSpan);

        const dueDateSpan = document.createElement('span');
        dueDateSpan.classList.add('task-due-date');
        dueDateSpan.textContent = `Due: ${task.due_date ? new Date(task.due_date + 'T00:00:00').toLocaleDateString() : 'N/A'}`; // Ensure local date interpretation
        detailsDiv.appendChild(dueDateSpan);

        li.appendChild(detailsDiv);

        // Action buttons container
        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('task-actions');

        // Edit button
        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.classList.add('edit-btn', 'action-btn');
        editBtn.addEventListener('click', () => startEditTask(task));

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.classList.add('delete-btn', 'action-btn');
        deleteBtn.addEventListener('click', () => deleteTask(task.id));

        actionsDiv.appendChild(editBtn);
        actionsDiv.appendChild(deleteBtn);
        li.appendChild(actionsDiv);

        taskListEl.appendChild(li);
    });
}

function renderHistoryList() {
    completedTaskListEl.innerHTML = ''; // Clear existing list

    const sortedHistory = completedTasks.sort((a, b) => new Date(b.completed_at) - new Date(a.completed_at));

    if (sortedHistory.length === 0) {
        completedTaskListEl.innerHTML = '<li class="placeholder">No completed tasks found.</li>';
        return;
    }

    sortedHistory.forEach(task => {
        const li = document.createElement('li');
        li.dataset.taskId = task.id;

        // Completed Task Details Div
        const detailsDiv = document.createElement('div');
        detailsDiv.classList.add('completed-task-details');

        const descriptionSpan = document.createElement('span');
        descriptionSpan.classList.add('task-description');
        descriptionSpan.textContent = task.description;
        detailsDiv.appendChild(descriptionSpan);

        const completedDateSpan = document.createElement('span');
        completedDateSpan.classList.add('task-completed-date');
        completedDateSpan.textContent = `Completed: ${task.completed_at ? new Date(task.completed_at).toLocaleString() : 'N/A'}`;
        detailsDiv.appendChild(completedDateSpan);

        li.appendChild(detailsDiv);

        // Action buttons container
        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('completed-task-actions');

        // Undo button
        const undoBtn = document.createElement('button');
        undoBtn.textContent = 'Undo';
        undoBtn.classList.add('undo-btn', 'action-btn');
        undoBtn.title = 'Mark task as incomplete';
        undoBtn.addEventListener('click', () => toggleTaskCompletion(task.id, false));

        actionsDiv.appendChild(undoBtn);
        li.appendChild(actionsDiv);

        completedTaskListEl.appendChild(li);
    });
}

// --- Data Fetching ---
async function fetchInitialData(showLoading = true) {
    console.log('Fetching initial data...');
    if (showLoading) {
        showStatusMessage('Loading data...', 'loading', 0);
    }
    stopPolling();

    const data = await apiCall('/api/data');

    if (data && data.clients) {
        clients = data.clients || [];
        // Standardize task IDs to `.id` when fetching
        tasks = clients.flatMap(client => client.tasks || [])
                       .map(task => ({ ...task, id: task.task_id || task.id }));

        console.log('Data fetched:', { clients, tasks }); // Log the processed data

        const currentSelectedId = selectedClientId;
        selectedClientId = null;

        renderClientList();

        if (currentSelectedId && clients.some(c => c.client_id === currentSelectedId)) { // Use client_id
            selectedClientId = currentSelectedId;
            const selectedLi = clientListEl.querySelector(`li[data-client-id="${selectedClientId}"]`);
            if (selectedLi) selectedLi.classList.add('selected');
            renderTaskList();
            if (!isUserEditing) {
                setupTaskForm('add');
            }
        } else {
            selectedClientId = null;
            renderTaskList();
            if (!isUserEditing) {
                 resetForm();
            }
        }

        completedTasks = []; // Clear potentially stale history
        if (historyContainer.style.display !== 'none') {
             await fetchHistoryData(false); // Fetch history if visible, without showing loading
        } else {
             renderHistoryList(); // Render empty history list
        }

        if (showLoading) hideStatusMessage();
        startPolling();

    } else {
        console.error('Failed to fetch initial data.');
        showStatusMessage('Error loading initial data.', 'error');
        clientListEl.innerHTML = '<li class="placeholder">Error loading clients.</li>';
        taskListEl.innerHTML = '<li class="placeholder">Error loading tasks.</li>';
        completedTaskListEl.innerHTML = '<li class="placeholder">Error loading history.</li>';
        resetForm();
    }
}

async function fetchHistoryData(showLoading = true) {
    console.log('Fetching completed task history...');
    if (showLoading) {
         showStatusMessage('Loading history...', 'loading', 0);
    }
    const historyData = await apiCall('/api/tasks/history');
    if (historyData) {
        // Standardize history task IDs to `.id`
        completedTasks = historyData.map(task => ({ ...task, id: task.task_id || task.id })) || [];
        console.log('History data fetched:', completedTasks); // Log the processed data
        renderHistoryList();
         if (showLoading) hideStatusMessage();
    } else {
        console.error('Failed to fetch history data.');
         showStatusMessage('Error loading history.', 'error');
        completedTaskListEl.innerHTML = '<li class="placeholder">Error loading history.</li>';
    }
}

// --- Polling Logic (Phase 7 - Adjusted for less console noise) ---
function startPolling() {
    stopPolling();
    if (!pollingIntervalId) {
        // console.log(`Starting polling every ${pollingInterval / 1000} seconds.`);
        pollingIntervalId = setInterval(pollForUpdates, pollingInterval);
    }
}

function stopPolling() {
    if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
        // console.log('Polling stopped.');
    }
}

async function pollForUpdates() {
    if (isUserEditing || document.hidden) { // Don't poll if user editing or tab hidden
        // console.log('Polling skipped: User editing or tab hidden.');
        return;
    }

    // console.log('Polling for updates...');
    const data = await apiCall('/api/data');

    if (data && data.clients) {
        // Compare raw data first, then process if changed
        const currentRawClients = clients; // Keep the current raw data for comparison if needed
        const newRawClients = data.clients;

        // Simple string comparison of raw data for quick check
        if (JSON.stringify(currentRawClients) !== JSON.stringify(newRawClients)) {
            console.log('Polling: Data change detected, refreshing UI...');

            const currentSelectedId = selectedClientId;
            const historyVisible = historyContainer.style.display !== 'none';

            // Update data and standardize task IDs
            clients = newRawClients || [];
            tasks = clients.flatMap(client => client.tasks || [])
                           .map(task => ({ ...task, id: task.task_id || task.id }));

            renderClientList();

            if (currentSelectedId && clients.some(c => c.client_id === currentSelectedId)) { // Use client_id
                 selectedClientId = currentSelectedId;
                 const selectedLi = clientListEl.querySelector(`li[data-client-id="${selectedClientId}"]`);
                 if (selectedLi) selectedLi.classList.add('selected');
            } else {
                 selectedClientId = null;
                 if (!isUserEditing) {
                    resetForm();
                 }
            }
            renderTaskList();

            if (historyVisible) {
                  console.log("Polling detected change, refreshing visible history...");
                  // Don't await, let it update in background
                  fetchHistoryData(false).catch(err => console.error("Background history refresh failed:", err));
             }

            console.log('Polling refresh complete.');
        } else {
            // console.log('No changes detected during poll.');
        }
    } else if (data === null) {
         console.error("Polling failed to fetch data. Stopping polling.");
         showStatusMessage("Connection error. Real-time updates paused.", "error", 5000);
         stopPolling();
    }
}


// --- Task Completion Logic (Phase 6 - Integrated status messages) ---
async function toggleTaskCompletion(taskId, markComplete) {
    const action = markComplete ? 'complete' : 'incomplete';
    console.log(`Attempting to mark task ${taskId} as ${action}`);

    stopPolling(); // Pause polling during update
    // showStatusMessage('Updating task status...', 'loading', 0); // Handled by apiCall
    const result = await apiCall(`/api/tasks/${taskId}/${action}`, 'PATCH');

    if (result) {
        console.log(`Task ${taskId} marked as ${action} successfully.`);
        showStatusMessage(`Task marked as ${action}.`, 'success');
        // Refresh ALL data to ensure consistency, don't show loading for refresh
        await fetchInitialData(false);

        // After toggling, if we are marking incomplete,
        // ensure the form isn't stuck editing the task we just moved.
        if (!markComplete && selectedTask && selectedTask.id === taskId) {
            if (selectedClientId) {
                 setupTaskForm('add');
            } else {
                 resetForm();
            }
        }
    } else {
        console.error(`Failed to mark task ${taskId} as ${action}.`);
        // Error message shown by apiCall
        startPolling(); // Restart polling even on failure
    }
}

// --- Client & Task Selection ---
function selectClient(clientId) {
    console.log(`Selecting client: ${clientId}`);
    if (selectedClientId === clientId && !isUserEditing) return; // clientId should be correct here

    if (isUserEditing) {
        console.log("Client selected while editing, resetting edit state.");
        isUserEditing = false;
        hideStatusMessage(); // Hide any lingering status
    }

    selectedClientId = clientId;
    selectedTask = null;

    renderClientList();
    renderTaskList();

    resetForm();
    setupTaskForm('add');
    isUserEditing = false;
    hideStatusMessage(); // Clear status on selection change
}

// --- Unified Form Management ---
function resetForm() {
    // console.log("[DEBUG] Entering resetForm");
    editingForm.reset();
    editIdInput.value = '';
    editModeInput.value = 'client';
    selectedTask = null;

    clientFields.style.display = 'block';
    taskFields.style.display = 'none';

    // Explicitly set required/disabled for client mode
    clientNameInput.required = true;
    clientNameInput.disabled = false;
    taskDescriptionInput.required = false;
    taskDescriptionInput.disabled = true;
    taskDueDateInput.disabled = true;

    // console.log(`[DEBUG] resetForm: Set mode to 'client'. Hiding task fields, showing client fields.`);
    // console.log(`[DEBUG] resetForm: taskDescriptionInput state - required=${taskDescriptionInput.required}, disabled=${taskDescriptionInput.disabled}`);
    // console.log(`[DEBUG] resetForm: clientNameInput state - required=${clientNameInput.required}, disabled=${clientNameInput.disabled}`); // Added for comparison

    editingFormTitle.textContent = 'Add Client';
    editSubmitBtn.textContent = 'Add Client';
    editCancelBtn.style.display = 'none';

    // Reset validation states (simple)
    clientNameInput.classList.remove('invalid');
    hideStatusMessage(); // Hide any status on reset
}

function setupTaskForm(mode = 'add', task = null) {
    // console.log(`[DEBUG] Entering setupTaskForm with mode: ${mode}`, task ? `and task ID: ${task.id}` : '');
    if (!selectedClientId && mode === 'add') {
        // console.warn("[DEBUG] setupTaskForm: Cannot setup task form - No client selected. Resetting.");
        resetForm();
        return;
    }
     if (!selectedClientId && mode === 'edit') {
        // console.error("[DEBUG] setupTaskForm: Cannot edit task: No client selected (should not happen).");
        resetForm();
        return;
    }

    // console.log(`Setting up form for ${mode} task`, task || '');
    // console.log(`[DEBUG] setupTaskForm: Setting mode to 'task' (${mode}). Showing task fields, hiding client fields.`);
    editModeInput.value = 'task';
    selectedTask = (mode === 'edit' && task) ? task : null;
    editIdInput.value = (mode === 'edit' && task) ? task.id : '';

    clientFields.style.display = 'none';
    taskFields.style.display = 'block';

    // Explicitly set required/disabled for task mode
    clientNameInput.required = false;
    clientNameInput.disabled = true;
    taskDescriptionInput.required = true;
    taskDescriptionInput.disabled = false;
    taskDueDateInput.disabled = false; // Enable due date input

    // console.log(`[DEBUG] setupTaskForm (${mode}): taskDescriptionInput state - required=${taskDescriptionInput.required}, disabled=${taskDescriptionInput.disabled}`);
    // console.log(`[DEBUG] setupTaskForm (${mode}): clientNameInput state - required=${clientNameInput.required}, disabled=${clientNameInput.disabled}`); // Added for comparison

    editingFormTitle.textContent = mode === 'edit' ? 'Edit Task' : 'Add Task';
    editSubmitBtn.textContent = mode === 'edit' ? 'Save Task' : 'Add Task';
    editCancelBtn.style.display = 'inline-block';

    if (mode === 'edit' && task) {
        taskDescriptionInput.value = task.description || '';
        taskDueDateInput.value = task.due_date ? task.due_date.split('T')[0] : '';
    } else {
        taskDescriptionInput.value = '';
        taskDueDateInput.value = '';
    }

     // Reset validation states
    taskDescriptionInput.classList.remove('invalid');
    hideStatusMessage();
    taskDescriptionInput.focus();
}

function startEditClient(client) {
    // Use client.client_id here
    if (!client || typeof client.client_id === 'undefined') {
        console.error("[DEBUG] startEditClient called with invalid client object:", client);
        return;
    }
    // console.log('[DEBUG] Entering startEditClient for client:', client);
    isUserEditing = true;
    stopPolling();
    editModeInput.value = 'client';
    editIdInput.value = client.client_id; // Use client_id
    selectedTask = null;

    clientFields.style.display = 'block';
    taskFields.style.display = 'none';

    clientNameInput.value = client.name;

    editingFormTitle.textContent = 'Edit Client';
    editSubmitBtn.textContent = 'Save Client';
    editCancelBtn.style.display = 'inline-block';

    clientNameInput.classList.remove('invalid');
    hideStatusMessage();
    clientNameInput.focus();
}

function startEditTask(task) {
     if (!task || typeof task.id === 'undefined') {
        // console.error("[DEBUG] startEditTask called with invalid task object:", task);
        return;
    }
    // console.log('[DEBUG] Entering startEditTask for task:', task);
    isUserEditing = true;
    stopPolling();
    setupTaskForm('edit', task);
}

// --- Form Submission Handling ---
async function handleFormSubmit(event) {
    event.preventDefault();
    // console.log('[DEBUG] handleFormSubmit triggered.');
    const mode = editModeInput.value;
    // console.log(`[DEBUG] handleFormSubmit: Form mode detected: '${mode}'.`);
    // console.log(`[DEBUG] handleFormSubmit: Current input states: clientName=${clientNameInput.value}, taskDescription=${taskDescriptionInput.value}, taskDueDate=${taskDueDateInput.value}`);
    // console.log(`[DEBUG] handleFormSubmit: taskDescriptionInput state - required=${taskDescriptionInput.required}, disabled=${taskDescriptionInput.disabled}`);
    // console.log(`[DEBUG] handleFormSubmit: clientNameInput state - required=${clientNameInput.required}, disabled=${clientNameInput.disabled}`);

    // Frontend Validation
    let isValid = true;
    // console.log('[DEBUG] handleFormSubmit: Starting validation.');
    if (mode === 'client') {
        if (!clientNameInput.value.trim()) {
            clientNameInput.classList.add('invalid'); // Add style for invalid
            showStatusMessage('Client name is required.', 'error');
            isValid = false;
            // console.log('[DEBUG] handleFormSubmit: Validation FAILED - Client name missing.');
        } else {
            clientNameInput.classList.remove('invalid');
            // console.log('[DEBUG] handleFormSubmit: Client name validation PASSED.');
        }
    } else if (mode === 'task') {
        if (!taskDescriptionInput.value.trim()) {
            taskDescriptionInput.classList.add('invalid');
            showStatusMessage('Task description is required.', 'error');
            isValid = false;
            // console.log('[DEBUG] handleFormSubmit: Validation FAILED - Task description missing.');
        } else {
            taskDescriptionInput.classList.remove('invalid');
             // console.log('[DEBUG] handleFormSubmit: Task description validation PASSED.');
        }
    }

    if (!isValid) {
        // console.log('[DEBUG] handleFormSubmit: Validation failed. Aborting submission.');
        return;
    }

    // console.log('[DEBUG] handleFormSubmit: Validation passed. Disabling submit button.');
    // Disable button during submission
    editSubmitBtn.disabled = true;

    try {
        if (mode === 'client') {
            await handleClientSubmit();
        } else if (mode === 'task') {
            await handleTaskSubmit();
        } else {
            console.error("Unknown form mode:", mode);
            isUserEditing = false;
            startPolling();
            showStatusMessage('An unexpected error occurred.', 'error');
        }
    } finally {
        // Re-enable button regardless of outcome
        editSubmitBtn.disabled = false;
    }
}

async function handleClientSubmit() {
    const clientName = clientNameInput.value.trim();
    const clientId = editIdInput.value;
    // console.log(`[DEBUG] Entering handleClientSubmit. Mode: ${clientId ? 'Edit' : 'Add'}, Client ID: ${clientId || 'N/A'}, Name: '${clientName}'`);

    // Validation already done in handleFormSubmit

    let result;
    let updatedClientData = { name: clientName };
    stopPolling();
    // console.log('[DEBUG] handleClientSubmit: Polling stopped.');
    // showStatusMessage('Saving client...', 'loading', 0); // Handled by apiCall

    try {
        if (clientId) { // Editing
            // console.log(`[DEBUG] handleClientSubmit: Calling API to PUT /api/clients/${clientId}`);
            result = await apiCall(`/api/clients/${clientId}`, 'PUT', updatedClientData);
        } else { // Adding
            // console.log(`[DEBUG] handleClientSubmit: Calling API to POST /api/clients`);
            result = await apiCall('/api/clients', 'POST', updatedClientData);
        }

        if (result) {
            // console.log('[DEBUG] handleClientSubmit: API call successful.');
            isUserEditing = false;
            showStatusMessage(clientId ? 'Client updated.' : 'Client added.', 'success');
            // console.log('[DEBUG] handleClientSubmit: Fetching initial data after success.');
            await fetchInitialData(false); // Refresh without showing loading
        } else {
            // console.error('[DEBUG] handleClientSubmit: API call failed.');
            isUserEditing = false; // Still stop editing on failure
            startPolling(); // Restart polling on failure
            // console.log('[DEBUG] handleClientSubmit: Polling restarted after failure.');
            // Error message shown by apiCall
        }
    } catch (error) {
         // console.error("[DEBUG] handleClientSubmit: Error during submission:", error);
         isUserEditing = false;
         startPolling();
         // console.log('[DEBUG] handleClientSubmit: Polling restarted after catch block.');
         showStatusMessage('An unexpected error occurred saving the client.', 'error');
    }
}

async function handleTaskSubmit() {
    const description = taskDescriptionInput.value.trim();
    const dueDate = taskDueDateInput.value;
    const taskId = editIdInput.value;
    // console.log(`[DEBUG] Entering handleTaskSubmit. Mode: ${taskId ? 'Edit' : 'Add'}, Task ID: ${taskId || 'N/A'}, Desc: '${description}', Due: '${dueDate}', ClientID: ${selectedClientId}`);

    // Validation done in handleFormSubmit
    if (!selectedClientId) {
         showStatusMessage('Cannot save task: No client selected.', 'error');
         // console.error("[DEBUG] handleTaskSubmit: Aborted - No client selected.");
         isUserEditing = false;
         startPolling();
         return;
     }

    let result;
    const taskData = {
        client_id: selectedClientId,
        description: description,
        due_date: dueDate || null
    };
    stopPolling();
    // console.log('[DEBUG] handleTaskSubmit: Polling stopped.');
    // showStatusMessage('Saving task...', 'loading', 0); // Handled by apiCall

    try {
        if (taskId) { // Editing
            // console.log(`[DEBUG] handleTaskSubmit: Calling API to PUT /api/tasks/${taskId}`);
            result = await apiCall(`/api/tasks/${taskId}`, 'PUT', { description: taskData.description, due_date: taskData.due_date });
        } else { // Adding
            // console.log(`[DEBUG] handleTaskSubmit: Calling API to POST /api/tasks`);
            result = await apiCall('/api/tasks', 'POST', taskData);
        }

        if (result) {
            // console.log('[DEBUG] handleTaskSubmit: API call successful.');
            isUserEditing = false;
            showStatusMessage(taskId ? 'Task updated.' : 'Task added.', 'success');
            // console.log('[DEBUG] handleTaskSubmit: Fetching initial data after success.');
            await fetchInitialData(false); // Refresh without loading message
            // Keep form in add task mode (handled by fetchInitialData selection logic)
        } else {
            // console.error('[DEBUG] handleTaskSubmit: API call failed.');
            isUserEditing = false;
            startPolling();
            // console.log('[DEBUG] handleTaskSubmit: Polling restarted after failure.');
            // Error message shown by apiCall
        }
    } catch (error) {
         // console.error("[DEBUG] handleTaskSubmit: Error during submission:", error);
         isUserEditing = false;
         startPolling();
         // console.log('[DEBUG] handleTaskSubmit: Polling restarted after catch block.');
         showStatusMessage('An unexpected error occurred saving the task.', 'error');
    }
}

// --- Deletion Logic ---
async function deleteClient(clientId) {
    console.log(`Attempting to delete client: ${clientId}`);
    if (!confirm('Are you sure you want to delete this client and ALL associated tasks? This cannot be undone.')) {
        return;
    }
    stopPolling();
    // showStatusMessage('Deleting client...', 'loading', 0); // Handled by apiCall

    const result = await apiCall(`/api/clients/${clientId}`, 'DELETE');

    if (result) {
        console.log(`Client ${clientId} deleted successfully.`);
        isUserEditing = false; // Clear flag if we were editing the deleted client
        showStatusMessage('Client deleted.', 'success');
        await fetchInitialData(false); // Refresh without loading message
        // History refresh handled within fetchInitialData if visible
    } else {
        console.error(`Failed to delete client ${clientId}.`);
        startPolling();
        // Error message handled by apiCall
    }
}

async function deleteTask(taskId) {
     if (typeof taskId === 'undefined') {
        console.error("deleteTask called with undefined taskId");
        return;
    }
    console.log(`Attempting to delete task: ${taskId}`);
    if (!confirm('Are you sure you want to permanently delete this task?')) {
        return;
    }
    stopPolling();
    // showStatusMessage('Deleting task...', 'loading', 0); // Handled by apiCall

    const result = await apiCall(`/api/tasks/${taskId}`, 'DELETE');

    if (result) {
        console.log(`Task ${taskId} deleted successfully.`);
        showStatusMessage('Task deleted.', 'success');
        if (selectedTask && selectedTask.id === taskId) {
             isUserEditing = false;
             selectedTask = null;
        }
        await fetchInitialData(false); // Refresh without loading message
        // History refresh handled within fetchInitialData if visible
    } else {
        console.error(`Failed to delete task ${taskId}.`);
        startPolling();
        // Error message handled by apiCall
    }
}

// --- Event Listeners Setup ---
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM fully loaded and parsed');

    // Cache DOM elements
    clientListEl = document.getElementById('client-list');
    taskListEl = document.getElementById('task-list');
    editingForm = document.getElementById('editing-form');
    editIdInput = document.getElementById('edit-id-input');
    editModeInput = document.getElementById('edit-mode-input');
    clientFields = document.getElementById('client-fields');
    taskFields = document.getElementById('task-fields');
    clientNameInput = document.getElementById('client-name-input');
    taskDescriptionInput = document.getElementById('task-description-input');
    taskDueDateInput = document.getElementById('task-due-date-input');
    editSubmitBtn = document.getElementById('edit-submit-btn');
    editCancelBtn = document.getElementById('edit-cancel-btn');
    editingFormTitle = document.getElementById('editing-form-title');
    selectedClientNameSpan = document.getElementById('selected-client-name');
    completedTaskListEl = document.getElementById('completed-task-list');
    historyContainer = document.getElementById('completed-task-list-container');
    toggleHistoryBtn = document.getElementById('toggle-history-btn');
    statusMessageEl = document.getElementById('status-message'); // Cache status element

    // Add Form submit listener
    editingForm.addEventListener('submit', handleFormSubmit);

    // Add Cancel button listener
    editCancelBtn.addEventListener('click', () => {
        console.log('Cancel button clicked');
        const wasEditing = isUserEditing;
        isUserEditing = false;

        // Always reset the form to the default 'Add Client' state when cancelling.
        resetForm();

        if (wasEditing) {
             startPolling(); // Restart polling if we were editing
        }
        hideStatusMessage(); // Hide any status messages
    });

    // Add History toggle listener
    toggleHistoryBtn.addEventListener('click', async () => {
        console.log('Toggle history button clicked');
        const isVisible = historyContainer.style.display !== 'none';
        if (!isVisible) {
            // Fetch data when showing
            await fetchHistoryData();
            historyContainer.style.display = 'block';
            toggleHistoryBtn.textContent = 'Hide';
        } else {
            historyContainer.style.display = 'none';
            toggleHistoryBtn.textContent = 'Show';
        }
    });

    // Initial data load
    fetchInitialData().catch(error => {
        console.error("Error during initial data load:", error);
        showStatusMessage('Failed to load application data. Please try refreshing.', 'error');
    });

     // Optional: Add event listener to stop polling when window is hidden
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopPolling();
        } else {
            if (!isUserEditing) { // Only restart if not actively editing
                 // Optionally trigger an immediate poll on visibility regain
                 pollForUpdates().catch(err => console.error("Error polling on visibility regain:", err));
                 startPolling(); // Restart the interval
            }
        }
    });

}); 