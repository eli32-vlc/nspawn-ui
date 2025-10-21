// Dashboard functionality
const API_BASE = window.location.origin;

// Check authentication
function checkAuth() {
    const token = localStorage.getItem('authToken');
    if (!token) {
        window.location.href = '/login';
        return null;
    }
    return token;
}

// Get auth headers
function getAuthHeaders() {
    const token = checkAuth();
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };
}

// Logout functionality
document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
    window.location.href = '/login';
});

// Set username
const username = localStorage.getItem('username');
if (username) {
    document.getElementById('username').textContent = username;
}

// Load VPS list
async function loadVPSList() {
    const token = checkAuth();
    if (!token) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/containers`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }
        
        const containers = await response.json();
        const tbody = document.getElementById('vpsTableBody');
        
        if (containers.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center py-5">
                        <i class="bi bi-inbox" style="font-size: 3rem; color: #ddd;"></i>
                        <p class="mt-2 text-muted">No VPS instances found</p>
                        <a href="/vps/create" class="btn btn-primary">Create Your First VPS</a>
                    </td>
                </tr>
            `;
        } else {
            tbody.innerHTML = containers.map(vps => {
                const statusClass = vps.status === 'running' ? 'success' : 
                                  vps.status === 'stopped' ? 'secondary' : 'danger';
                const statusIcon = vps.status === 'running' ? 'play-circle-fill' :
                                 vps.status === 'stopped' ? 'stop-circle-fill' : 'x-circle-fill';
                
                return `
                    <tr onclick="window.location.href='/vps/${vps.id}'" style="cursor: pointer;">
                        <td><strong>${vps.name}</strong></td>
                        <td><span class="badge bg-${statusClass}"><i class="bi bi-${statusIcon}"></i> ${vps.status}</span></td>
                        <td>${vps.distro}</td>
                        <td>${vps.ipv4_address || 'N/A'}</td>
                        <td>${vps.ipv6_address || 'N/A'}</td>
                        <td>
                            <small>CPU: ${vps.cpu_quota}%</small><br>
                            <small>RAM: ${vps.memory_mb}MB</small><br>
                            <small>Disk: ${vps.disk_gb}GB</small>
                        </td>
                        <td>${vps.uptime || 'N/A'}</td>
                        <td onclick="event.stopPropagation()">
                            <button class="btn btn-sm btn-success" onclick="startVPS('${vps.id}')">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-warning" onclick="stopVPS('${vps.id}')">
                                <i class="bi bi-stop-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="deleteVPS('${vps.id}')">
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
        }
        
        // Update stats
        const running = containers.filter(v => v.status === 'running').length;
        const stopped = containers.filter(v => v.status === 'stopped').length;
        
        document.getElementById('runningCount').textContent = running;
        document.getElementById('stoppedCount').textContent = stopped;
        
    } catch (error) {
        console.error('Error loading VPS list:', error);
        const tbody = document.getElementById('vpsTableBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-5 text-danger">
                    <i class="bi bi-exclamation-triangle" style="font-size: 3rem;"></i>
                    <p class="mt-2">Error loading VPS instances</p>
                </td>
            </tr>
        `;
    }
}

// Load system resources
async function loadSystemResources() {
    try {
        const response = await fetch(`${API_BASE}/api/system/resources`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const resources = await response.json();
            document.getElementById('cpuUsage').textContent = `${Math.round(resources.cpu_percent)}%`;
            document.getElementById('memoryUsage').textContent = `${Math.round(resources.memory_percent)}%`;
        }
    } catch (error) {
        console.error('Error loading system resources:', error);
    }
}

// VPS control functions
async function startVPS(id) {
    if (!confirm(`Start VPS ${id}?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/containers/${id}/start`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            loadVPSList();
        } else {
            alert('Failed to start VPS');
        }
    } catch (error) {
        alert('Error starting VPS');
    }
}

async function stopVPS(id) {
    if (!confirm(`Stop VPS ${id}?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/containers/${id}/stop`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            loadVPSList();
        } else {
            alert('Failed to stop VPS');
        }
    } catch (error) {
        alert('Error stopping VPS');
    }
}

async function deleteVPS(id) {
    if (!confirm(`Delete VPS ${id}? This action cannot be undone!`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/containers/${id}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            loadVPSList();
        } else {
            alert('Failed to delete VPS');
        }
    } catch (error) {
        alert('Error deleting VPS');
    }
}

// Refresh button
document.getElementById('refreshBtn').addEventListener('click', () => {
    loadVPSList();
    loadSystemResources();
});

// Search functionality
document.getElementById('searchInput').addEventListener('input', (e) => {
    const searchTerm = e.target.value.toLowerCase();
    const rows = document.querySelectorAll('#vpsTableBody tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(searchTerm) ? '' : 'none';
    });
});

// Initial load
loadVPSList();
loadSystemResources();

// Auto-refresh every 10 seconds
setInterval(() => {
    loadVPSList();
    loadSystemResources();
}, 10000);
