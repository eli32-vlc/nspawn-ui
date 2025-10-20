// API base URL - in production this would be configured
const API_BASE_URL = 'http://localhost:8000';

// DOM Elements
const dashboardView = document.getElementById('dashboard-view');
const createContainerView = document.getElementById('create-container-view');
const networkConfigView = document.getElementById('network-config-view');
const containerDetailsView = document.getElementById('container-details-view');
const containersList = document.getElementById('containers-list');
const totalContainersEl = document.getElementById('total-containers');
const runningContainersEl = document.getElementById('running-containers');
const stoppedContainersEl = document.getElementById('stopped-containers');
const refreshBtn = document.getElementById('refresh-containers');
const createNewContainerBtn = document.getElementById('create-new-container');
const cancelCreateBtn = document.getElementById('cancel-create');
const cancelNetworkBtn = document.getElementById('cancel-network');
const backToDashboardBtn = document.getElementById('back-to-dashboard');
const createContainerForm = document.getElementById('create-container-form');
const networkConfigForm = document.getElementById('network-config-form');

// Navigation
document.getElementById('dashboard-link').addEventListener('click', showDashboard);
document.getElementById('create-container-link').addEventListener('click', showCreateContainer);
document.getElementById('network-config-link').addEventListener('click', showNetworkConfig);
document.getElementById('create-new-container').addEventListener('click', showCreateContainer);

// Buttons
refreshBtn.addEventListener('click', loadContainers);
cancelCreateBtn.addEventListener('click', showDashboard);
cancelNetworkBtn.addEventListener('click', showDashboard);
createContainerForm.addEventListener('submit', handleCreateContainer);
networkConfigForm.addEventListener('submit', handleNetworkConfig);

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    loadContainers();
});

// View management
function showDashboard() {
    dashboardView.classList.remove('d-none');
    createContainerView.classList.add('d-none');
    networkConfigView.classList.add('d-none');
    document.querySelector('.nav-link.active').classList.remove('active');
    document.getElementById('dashboard-link').classList.add('active');
}

function showCreateContainer() {
    dashboardView.classList.add('d-none');
    createContainerView.classList.remove('d-none');
    networkConfigView.classList.add('d-none');
    document.querySelector('.nav-link.active').classList.remove('active');
    document.getElementById('create-container-link').classList.add('active');
}

function showNetworkConfig() {
    dashboardView.classList.add('d-none');
    createContainerView.classList.add('d-none');
    networkConfigView.classList.remove('d-none');
    containerDetailsView.classList.add('d-none');
    document.querySelector('.nav-link.active').classList.remove('active');
    document.getElementById('network-config-link').classList.add('active');
}

function showContainerDetails(containerName) {
    dashboardView.classList.add('d-none');
    createContainerView.classList.add('d-none');
    networkConfigView.classList.add('d-none');
    containerDetailsView.classList.remove('d-none');
    document.querySelector('.nav-link.active').classList.remove('active');
    
    // Set the container name in the header
    document.getElementById('current-container-name').textContent = containerName;
    
    // Load container details
    loadContainerDetails(containerName);
    
    // Setup WebSocket for real-time logs
    setupRealtimeLogs(containerName);
}

function loadContainerDetails(containerName) {
    // This would fetch detailed container information from the API
    // For now, we'll just update the info section with placeholder data
    const containerInfo = document.getElementById('container-info');
    containerInfo.innerHTML = `
        <li class="list-group-item d-flex justify-content-between align-items-center">
            Name
            <span class="badge bg-primary rounded-pill">${containerName}</span>
        </li>
        <li class="list-group-item d-flex justify-content-between align-items-center">
            Status
            <span class="badge bg-secondary rounded-pill" id="container-status">Loading...</span>
        </li>
        <li class="list-group-item d-flex justify-content-between align-items-center">
            IP Address
            <span class="badge bg-info rounded-pill" id="container-ip">Loading...</span>
        </li>
        <li class="list-group-item d-flex justify-content-between align-items-center">
            Created
            <span class="badge bg-info rounded-pill" id="container-created">Loading...</span>
        </li>
    `;
    
    // Load actual status
    fetch(`${API_BASE_URL}/containers`)
        .then(response => response.json())
        .then(containers => {
            const container = containers.find(c => c.name === containerName);
            if (container) {
                document.getElementById('container-status').textContent = container.status;
                document.getElementById('container-ip').textContent = container.ip_address || 'N/A';
                document.getElementById('container-created').textContent = container.created_at ? new Date(container.created_at).toLocaleString() : 'N/A';
                
                // Update action buttons based on status
                updateActionButtons(container.status);
            }
        })
        .catch(error => {
            console.error('Error loading container details:', error);
        });
}

function updateActionButtons(status) {
    const startBtn = document.getElementById('start-container-btn');
    const stopBtn = document.getElementById('stop-container-btn');
    const restartBtn = document.getElementById('restart-container-btn');
    const removeBtn = document.getElementById('remove-container-btn');
    
    if (status === 'running') {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        restartBtn.disabled = false;
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        restartBtn.disabled = true;
    }
}

function setupRealtimeLogs(containerName) {
    // Clear previous logs
    const logsElement = document.getElementById('realtime-logs');
    logsElement.innerHTML = '';
    
    // Check if WebSocket is supported
    if (!window.WebSocket) {
        logsElement.innerHTML = 'WebSocket is not supported in your browser.';
        return;
    }
    
    // Create WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/logs/${containerName}`;
    
    try {
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = function(event) {
            logsElement.innerHTML += `[Connected to logs for ${containerName}]\n`;
        };
        
        ws.onmessage = function(event) {
            const logsElement = document.getElementById('realtime-logs');
            logsElement.innerHTML += event.data + '\n';
            
            // Auto-scroll to bottom
            logsElement.scrollTop = logsElement.scrollHeight;
        };
        
        ws.onclose = function(event) {
            logsElement.innerHTML += `[Disconnected from logs for ${containerName}]\n`;
        };
        
        ws.onerror = function(error) {
            logsElement.innerHTML += `[Error connecting to logs: ${error}]\n`;
        };
        
        // Store WebSocket reference for potential cleanup
        window.currentLogsWs = ws;
    } catch (e) {
        logsElement.innerHTML = `[Error establishing WebSocket connection: ${e.message}]\n`;
    }
}

// Add event listeners for container details view
document.getElementById('back-to-dashboard').addEventListener('click', showDashboard);
document.getElementById('start-container-btn').addEventListener('click', function() {
    const containerName = document.getElementById('current-container-name').textContent;
    startContainer(containerName);
});
document.getElementById('stop-container-btn').addEventListener('click', function() {
    const containerName = document.getElementById('current-container-name').textContent;
    stopContainer(containerName);
});
document.getElementById('restart-container-btn').addEventListener('click', function() {
    const containerName = document.getElementById('current-container-name').textContent;
    restartContainer(containerName);
});
document.getElementById('remove-container-btn').addEventListener('click', function() {
    const containerName = document.getElementById('current-container-name').textContent;
    removeContainer(containerName);
});
document.getElementById('clear-logs-btn').addEventListener('click', function() {
    document.getElementById('realtime-logs').innerHTML = '';
});

// Load containers from API
async function loadContainers() {
    try {
        const response = await fetch(`${API_BASE_URL}/containers`);
        const containers = await response.json();
        
        // Update statistics
        updateStats(containers);
        
        // Populate container list
        populateContainersList(containers);
    } catch (error) {
        console.error('Error loading containers:', error);
        showError('Failed to load containers');
    }
}

function updateStats(containers) {
    totalContainersEl.textContent = containers.length;
    
    const running = containers.filter(c => c.status === 'running').length;
    const stopped = containers.filter(c => c.status === 'stopped' || c.status === 'inactive').length;
    
    runningContainersEl.textContent = running;
    stoppedContainersEl.textContent = stopped;
}

function populateContainersList(containers) {
    containersList.innerHTML = '';
    
    if (containers.length === 0) {
        containersList.innerHTML = `
            <tr>
                <td colspan="9" class="text-center">No containers found</td>
            </tr>
        `;
        return;
    }
    
    containers.forEach(container => {
        const row = document.createElement('tr');
        
        row.innerHTML = `
            <td><a href="#" onclick="showContainerDetails('${container.name}')">${container.name}</a></td>
            <td>
                <span class="badge ${container.status === 'running' ? 'bg-success' : 'bg-secondary'}">
                    ${container.status}
                </span>
            </td>
            <td>${container.ip_address || 'N/A'}</td>
            <td>${container.ipv4 || 'N/A'}/${container.ipv6 || 'N/A'}</td>
            <td>${container.cpu_limit || 'Unlimited'}</td>
            <td>${container.memory_limit || 'Unlimited'}</td>
            <td>${container.storage_limit || 'Unlimited'}</td>
            <td>${container.created_at ? new Date(container.created_at).toLocaleDateString() : 'N/A'}</td>
            <td>
                <div class="btn-group" role="group">
                    <button class="btn btn-sm btn-info" onclick="showContainerDetails('${container.name}')">Details</button>
                    ${container.status === 'running' 
                        ? `<button class="btn btn-sm btn-warning" onclick="stopContainer('${container.name}')">Stop</button>`
                        : `<button class="btn btn-sm btn-success" onclick="startContainer('${container.name}')">Start</button>`
                    }
                    <button class="btn btn-sm btn-primary" onclick="setupSSH('${container.name}')">SSH</button>
                    <button class="btn btn-sm btn-danger" onclick="removeContainer('${container.name}')">Remove</button>
                </div>
            </td>
        `;
        
        containersList.appendChild(row);
    });
}

// Container actions
async function startContainer(name) {
    if (!confirm(`Are you sure you want to start container "${name}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/containers/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name: name })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`Container "${name}" started successfully`);
            loadContainers(); // Refresh the list
        } else {
            showError(`Failed to start container: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error starting container:', error);
        showError('Failed to start container');
    }
}

async function stopContainer(name) {
    if (!confirm(`Are you sure you want to stop container "${name}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/containers/stop`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name: name })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`Container "${name}" stopped successfully`);
            loadContainers(); // Refresh the list
        } else {
            showError(`Failed to stop container: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error stopping container:', error);
        showError('Failed to stop container');
    }
}

async function restartContainer(name) {
    if (!confirm(`Are you sure you want to restart container "${name}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/containers/restart`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name: name })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`Container "${name}" restarted successfully`);
            loadContainers(); // Refresh the list
        } else {
            showError(`Failed to restart container: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error restarting container:', error);
        showError('Failed to restart container');
    }
}

async function removeContainer(name) {
    if (!confirm(`Are you absolutely sure you want to remove container "${name}"? This cannot be undone!`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/containers/${name}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`Container "${name}" removed successfully`);
            loadContainers(); // Refresh the list
        } else {
            showError(`Failed to remove container: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error removing container:', error);
        showError('Failed to remove container');
    }
}

async function viewLogs(name) {
    try {
        const response = await fetch(`${API_BASE_URL}/containers/${name}/logs`);
        const result = await response.json();
        
        // Create modal to display logs
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'logsModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Logs for ${name}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <pre class="bg-light p-3" style="max-height: 400px; overflow-y: auto;">${result.logs}</pre>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Initialize and show the modal
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        // Clean up when modal is hidden
        modal.addEventListener('hidden.bs.modal', function() {
            document.body.removeChild(modal);
        });
        
        bsModal.show();
    } catch (error) {
        console.error('Error fetching logs:', error);
        showError('Failed to fetch logs');
    }
}

async function setupSSH(name) {
    // Create modal for SSH setup
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'sshModal';
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Setup SSH for ${name}</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="sshPublicKey" class="form-label">SSH Public Key</label>
                        <textarea class="form-control" id="sshPublicKey" rows="5" placeholder="Paste your public key here..."></textarea>
                        <div class="form-text">Enter your SSH public key to enable passwordless access</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="setupSSHBtn">Setup SSH</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Initialize modal
    const bsModal = new bootstrap.Modal(modal);
    
    // Setup SSH button event
    document.getElementById('setupSSHBtn').addEventListener('click', async function() {
        const publicKey = document.getElementById('sshPublicKey').value.trim();
        if (!publicKey) {
            alert('Please enter an SSH public key');
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE_URL}/containers/${name}/ssh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name: name, ssh_public_key: publicKey })
            });
            
            const result = await response.json();
            
            if (result.success) {
                showMessage(`SSH setup completed for container ${name}`);
                bsModal.hide();
            } else {
                showError(`Failed to setup SSH: ${result.message || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error setting up SSH:', error);
            showError('Failed to setup SSH');
        }
    });
    
    // Clean up when modal is hidden
    modal.addEventListener('hidden.bs.modal', function() {
        document.body.removeChild(modal);
    });
    
    bsModal.show();
}

// Create container
async function handleCreateContainer(event) {
    event.preventDefault();
    
    // Validate passwords match
    const password = document.getElementById('root-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    if (password !== confirmPassword) {
        showError('Passwords do not match');
        return;
    }
    
    const containerData = {
        name: document.getElementById('container-name').value,
        distro: document.getElementById('container-distro').value,
        root_password: password,
        cpu_limit: document.getElementById('cpu-limit').value || null,
        memory_limit: document.getElementById('memory-limit').value || null,
        storage_limit: document.getElementById('storage-limit').value ? `${document.getElementById('storage-limit').value}` : null,
        enable_docker: document.getElementById('enable-docker').checked,
        enable_nested: document.getElementById('enable-nested').checked
    };
    
    // Validate that storage limit is a number
    if (containerData.storage_limit && isNaN(containerData.storage_limit)) {
        showError('Storage limit must be a number');
        return;
    }
    
    // Add 'G' suffix to storage limit if it's provided
    if (containerData.storage_limit) {
        containerData.storage_limit = `${containerData.storage_limit}G`;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/containers`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(containerData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`Container "${containerData.name}" created successfully`);
            showDashboard(); // Go back to dashboard
            loadContainers(); // Refresh the list
            createContainerForm.reset(); // Clear the form
        } else {
            showError(`Failed to create container: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error creating container:', error);
        showError('Failed to create container');
    }
}

// Network configuration
async function handleNetworkConfig(event) {
    event.preventDefault();
    
    const networkData = {
        name: document.getElementById('network-container-name').value,
        ipv4: document.getElementById('network-ipv4').value || null,
        ipv6: document.getElementById('network-ipv6').value || null,
        enable_nat: document.getElementById('network-enable-nat').checked
    };
    
    if (!networkData.name) {
        showError('Container name is required');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/containers/${networkData.name}/network`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(networkData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`Network configuration updated for container ${networkData.name}`);
            showDashboard(); // Go back to dashboard
            networkConfigForm.reset(); // Clear the form
        } else {
            showError(`Failed to configure network: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error configuring network:', error);
        showError('Failed to configure network');
    }
}

// Utility functions
function showMessage(message) {
    // Create a temporary alert element
    const alert = document.createElement('div');
    alert.className = 'alert alert-success alert-dismissible fade show position-fixed';
    alert.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alert);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.parentNode.removeChild(alert);
        }
    }, 5000);
}

function showError(message) {
    // Create a temporary alert element
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show position-fixed';
    alert.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alert);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.parentNode.removeChild(alert);
        }
    }, 5000);
}