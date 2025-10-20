// JavaScript for nspawn-ui
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the application
    loadContainers();
    loadDashboardData();
    
    // Set up form submissions
    document.getElementById('create-form').addEventListener('submit', createContainer);
    document.getElementById('network-setup-form').addEventListener('submit', setupNetworking);
    document.getElementById('refresh-logs').addEventListener('click', refreshLogs);
    
    // Set up network type change event
    document.getElementById('network-type').addEventListener('change', updateNetworkConfigFields);
    
    // Initialize network config fields
    updateNetworkConfigFields();
});

// Function to show specific page
function showPage(pageId) {
    // Hide all pages
    document.querySelectorAll('.page-content').forEach(page => {
        page.style.display = 'none';
    });
    
    // Show selected page
    document.getElementById(pageId + '-page').style.display = 'block';
    
    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Load page-specific data
    if (pageId === 'containers') {
        loadContainers();
    } else if (pageId === 'logs') {
        loadLogContainers();
    } else if (pageId === 'networking') {
        loadNetworkConfig();
    }
}

// Function to load containers
function loadContainers() {
    fetch('/api/containers')
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('containers-table');
            tbody.innerHTML = '';
            
            data.forEach(container => {
                const row = document.createElement('tr');
                
                // Determine status badge
                let statusClass = 'badge bg-secondary';
                if (container.state === 'running') statusClass = 'badge bg-success';
                else if (container.state === 'stopped') statusClass = 'badge bg-warning';
                
                row.innerHTML = `
                    <td>${container.name}</td>
                    <td><span class="${statusClass}">${container.state}</span></td>
                    <td>${container.ipv4 || 'N/A'}</td>
                    <td>${container.ipv6 || 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-success" onclick="startContainer('${container.name}')">Start</button>
                        <button class="btn btn-sm btn-warning" onclick="stopContainer('${container.name}')">Stop</button>
                        <button class="btn btn-sm btn-info" onclick="restartContainer('${container.name}')">Restart</button>
                        <button class="btn btn-sm btn-danger" onclick="removeContainer('${container.name}')">Remove</button>
                        <button class="btn btn-sm btn-primary" onclick="showLogs('${container.name}')">Logs</button>
                    </td>
                `;
                
                tbody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error loading containers:', error);
            alert('Error loading containers: ' + error.message);
        });
}

// Function to load dashboard data
function loadDashboardData() {
    fetch('/api/containers')
        .then(response => response.json())
        .then(data => {
            // Update dashboard counters
            document.getElementById('total-containers').textContent = data.length;
            
            const running = data.filter(c => c.state === 'running').length;
            const stopped = data.filter(c => c.state === 'stopped').length;
            
            document.getElementById('running-containers').textContent = running;
            document.getElementById('stopped-containers').textContent = stopped;
            
            // Update system status
            document.getElementById('system-status').textContent = 'Operational';
        })
        .catch(error => {
            console.error('Error loading dashboard data:', error);
        });
}

// Function to create a container
function createContainer(event) {
    event.preventDefault();
    
    const name = document.getElementById('container-name').value;
    const distribution = document.getElementById('distribution').value;
    const release = document.getElementById('release').value;
    const rootPassword = document.getElementById('root-password').value;
    const cpuLimit = parseInt(document.getElementById('cpu-limit').value) || null;
    const memoryLimit = parseInt(document.getElementById('memory-limit').value) || null;
    const storageLimit = parseInt(document.getElementById('storage-limit').value) || null;
    const ipv4 = document.getElementById('ipv4').value || null;
    const ipv6 = document.getElementById('ipv6').value || null;
    
    const requestData = {
        name: name,
        distribution: distribution,
        release: release,
        root_password: rootPassword,
        cpu_limit: cpuLimit,
        memory_limit: memoryLimit,
        storage_limit: storageLimit,
        ipv4: ipv4,
        ipv6: ipv6
    };
    
    fetch('/api/containers', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        alert('Container created successfully');
        document.getElementById('create-form').reset();
        loadContainers(); // Refresh the containers list
    })
    .catch(error => {
        console.error('Error creating container:', error);
        alert('Error creating container: ' + error.message);
    });
}

// Function to start a container
function startContainer(name) {
    fetch('/api/containers/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({name: name})
    })
    .then(response => response.json())
    .then(data => {
        alert(`Container ${name} started`);
        loadContainers(); // Refresh the containers list
    })
    .catch(error => {
        console.error('Error starting container:', error);
        alert('Error starting container: ' + error.message);
    });
}

// Function to stop a container
function stopContainer(name) {
    fetch('/api/containers/stop', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({name: name})
    })
    .then(response => response.json())
    .then(data => {
        alert(`Container ${name} stopped`);
        loadContainers(); // Refresh the containers list
    })
    .catch(error => {
        console.error('Error stopping container:', error);
        alert('Error stopping container: ' + error.message);
    });
}

// Function to restart a container
function restartContainer(name) {
    fetch('/api/containers/restart', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({name: name})
    })
    .then(response => response.json())
    .then(data => {
        alert(`Container ${name} restarted`);
        loadContainers(); // Refresh the containers list
    })
    .catch(error => {
        console.error('Error restarting container:', error);
        alert('Error restarting container: ' + error.message);
    });
}

// Function to remove a container
function removeContainer(name) {
    if (!confirm(`Are you sure you want to remove container ${name}?`)) {
        return;
    }
    
    fetch(`/api/containers/${name}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        alert(`Container ${name} removed`);
        loadContainers(); // Refresh the containers list
    })
    .catch(error => {
        console.error('Error removing container:', error);
        alert('Error removing container: ' + error.message);
    });
}

// Function to load available containers for logs
function loadLogContainers() {
    fetch('/api/containers')
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('log-container-select');
            select.innerHTML = '<option value="">Select a container</option>';
            
            data.forEach(container => {
                const option = document.createElement('option');
                option.value = container.name;
                option.textContent = container.name;
                select.appendChild(option);
            });
            
            select.addEventListener('change', function() {
                if (this.value) {
                    showLogs(this.value);
                }
            });
        })
        .catch(error => {
            console.error('Error loading log containers:', error);
        });
}

// Function to show logs for a container
function showLogs(name) {
    fetch(`/api/containers/${name}/logs`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('log-output').textContent = data.logs || 'No logs available';
            // Scroll to bottom
            const logOutput = document.getElementById('log-output');
            logOutput.scrollTop = logOutput.scrollHeight;
        })
        .catch(error => {
            console.error('Error loading logs:', error);
            document.getElementById('log-output').textContent = 'Error loading logs: ' + error.message;
        });
}

// Function to refresh logs
function refreshLogs() {
    const select = document.getElementById('log-container-select');
    if (select.value) {
        showLogs(select.value);
    } else {
        document.getElementById('log-output').textContent = 'Select a container to view logs';
    }
}

// Function to update network config fields based on selection
function updateNetworkConfigFields() {
    const networkType = document.getElementById('network-type').value;
    const container = document.getElementById('network-config-fields');
    
    container.innerHTML = '';
    
    switch(networkType) {
        case 'native':
            container.innerHTML = `
                <div class="mb-3">
                    <label for="ipv6-subnet" class="form-label">IPv6 Subnet</label>
                    <input type="text" class="form-control" id="ipv6-subnet" placeholder="2001:db8::/64">
                </div>
                <div class="mb-3">
                    <label for="gateway" class="form-label">Gateway</label>
                    <input type="text" class="form-control" id="gateway" placeholder="2001:db8::1">
                </div>
            `;
            break;
        case '6in4':
            container.innerHTML = `
                <div class="mb-3">
                    <label for="tunnel-server" class="form-label">Tunnel Server</label>
                    <input type="text" class="form-control" id="tunnel-server" placeholder="203.0.113.1">
                </div>
                <div class="mb-3">
                    <label for="tunnel-client" class="form-label">Tunnel Client</label>
                    <input type="text" class="form-control" id="tunnel-client" placeholder="198.51.100.1">
                </div>
                <div class="mb-3">
                    <label for="tunnel-ipv6" class="form-label">Tunnel IPv6</label>
                    <input type="text" class="form-control" id="tunnel-ipv6" placeholder="2001:db8::2/64">
                </div>
                <div class="mb-3">
                    <label for="authentication-key" class="form-label">Authentication Key (Optional)</label>
                    <input type="password" class="form-control" id="authentication-key">
                </div>
            `;
            break;
        case 'wireguard':
            container.innerHTML = `
                <div class="mb-3">
                    <label for="wg-private-key" class="form-label">Private Key</label>
                    <input type="text" class="form-control" id="wg-private-key" placeholder="yAnz5TF+lXXJte14tji3zlMNq+rfkK4QsV6x6KJdLao=">
                </div>
                <div class="mb-3">
                    <label for="wg-public-key" class="form-label">Public Key</label>
                    <input type="text" class="form-control" id="wg-public-key" placeholder="xTIBA5rboUvnH4htodjb6e697Qb0g5LSbIBB6XV8xng=">
                </div>
                <div class="mb-3">
                    <label for="wg-endpoint" class="form-label">Endpoint</label>
                    <input type="text" class="form-control" id="wg-endpoint" placeholder="192.0.2.1:51820">
                </div>
                <div class="mb-3">
                    <label for="wg-address" class="form-label">Address</label>
                    <input type="text" class="form-control" id="wg-address" placeholder="10.0.0.2/24, fd00::2/64">
                </div>
            `;
            break;
    }
}

// Function to load network configuration
function loadNetworkConfig() {
    fetch('/api/networking')
        .then(response => response.json())
        .then(data => {
            const configDiv = document.getElementById('network-config');
            if (data && Object.keys(data).length > 0) {
                let configHtml = '<ul class="list-unstyled">';
                for (const [key, value] of Object.entries(data)) {
                    configHtml += `<li><strong>${key}:</strong> ${value}</li>`;
                }
                configHtml += '</ul>';
                configDiv.innerHTML = configHtml;
            } else {
                configDiv.innerHTML = '<p>No network configuration found</p>';
            }
        })
        .catch(error => {
            console.error('Error loading network config:', error);
            document.getElementById('network-config').innerHTML = '<p>Error loading network configuration</p>';
        });
}

// Function to setup networking
function setupNetworking(event) {
    event.preventDefault();
    
    const networkType = document.getElementById('network-type').value;
    let config = {};
    
    switch(networkType) {
        case 'native':
            config = {
                ipv6_subnet: document.getElementById('ipv6-subnet')?.value,
                gateway: document.getElementById('gateway')?.value
            };
            break;
        case '6in4':
            config = {
                tunnel_server: document.getElementById('tunnel-server')?.value,
                tunnel_client: document.getElementById('tunnel-client')?.value,
                tunnel_ipv6: document.getElementById('tunnel-ipv6')?.value,
                auth_key: document.getElementById('authentication-key')?.value
            };
            break;
        case 'wireguard':
            config = {
                private_key: document.getElementById('wg-private-key')?.value,
                public_key: document.getElementById('wg-public-key')?.value,
                endpoint: document.getElementById('wg-endpoint')?.value,
                address: document.getElementById('wg-address')?.value
            };
            break;
    }
    
    fetch('/api/networking/setup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            type: networkType,
            config: config
        })
    })
    .then(response => response.json())
    .then(data => {
        alert('Networking configured successfully');
        loadNetworkConfig();
    })
    .catch(error => {
        console.error('Error setting up networking:', error);
        alert('Error setting up networking: ' + error.message);
    });
}

// Function to toggle theme (light/dark)
function toggleTheme() {
    // This is a placeholder - in a real implementation you'd toggle between light/dark themes
    alert('Theme toggle functionality would go here');
}