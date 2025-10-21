// Settings page functionality
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

function getAuthHeaders() {
    const token = checkAuth();
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };
}

// Logout
document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
    window.location.href = '/login';
});

// Set username
const username = localStorage.getItem('username');
if (username) {
    document.getElementById('username').textContent = username;
    document.getElementById('currentUsername').value = username;
}

// Load system information
async function loadSystemInfo() {
    try {
        const response = await fetch(`${API_BASE}/api/system/info`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const info = await response.json();
            document.getElementById('systemInfo').innerHTML = `
                <table class="table table-sm">
                    <tr>
                        <th>Version:</th>
                        <td>${info.version}</td>
                    </tr>
                    <tr>
                        <th>Architecture:</th>
                        <td>${info.architecture}</td>
                    </tr>
                    <tr>
                        <th>Hostname:</th>
                        <td>${info.hostname}</td>
                    </tr>
                    <tr>
                        <th>CPU Cores:</th>
                        <td>${info.cpu_count}</td>
                    </tr>
                    <tr>
                        <th>Total Memory:</th>
                        <td>${(info.total_memory_mb / 1024).toFixed(2)} GB</td>
                    </tr>
                    <tr>
                        <th>Available Memory:</th>
                        <td>${(info.available_memory_mb / 1024).toFixed(2)} GB</td>
                    </tr>
                    <tr>
                        <th>Uptime:</th>
                        <td>${info.uptime}</td>
                    </tr>
                </table>
            `;
            
            // Update storage info
            document.getElementById('storageInfo').innerHTML = `
                <table class="table table-sm">
                    <tr>
                        <th>Total Disk Space:</th>
                        <td>${info.disk_total_gb.toFixed(2)} GB</td>
                    </tr>
                    <tr>
                        <th>Available Space:</th>
                        <td>${info.disk_available_gb.toFixed(2)} GB</td>
                    </tr>
                    <tr>
                        <th>Used Space:</th>
                        <td>${(info.disk_total_gb - info.disk_available_gb).toFixed(2)} GB</td>
                    </tr>
                    <tr>
                        <th>Usage:</th>
                        <td>
                            <div class="progress">
                                <div class="progress-bar" role="progressbar" 
                                     style="width: ${((info.disk_total_gb - info.disk_available_gb) / info.disk_total_gb * 100).toFixed(1)}%">
                                    ${((info.disk_total_gb - info.disk_available_gb) / info.disk_total_gb * 100).toFixed(1)}%
                                </div>
                            </div>
                        </td>
                    </tr>
                </table>
            `;
        } else {
            throw new Error('Failed to load system info');
        }
    } catch (error) {
        console.error('Error loading system info:', error);
        document.getElementById('systemInfo').innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> Failed to load system information
            </div>
        `;
        document.getElementById('storageInfo').innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> Failed to load storage information
            </div>
        `;
    }
}

// Update password
document.getElementById('userSettingsForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (!currentPassword || !newPassword || !confirmPassword) {
        alert('Please fill in all password fields');
        return;
    }
    
    if (newPassword !== confirmPassword) {
        alert('New passwords do not match');
        return;
    }
    
    if (newPassword.length < 8) {
        alert('Password must be at least 8 characters long');
        return;
    }
    
    // TODO: Implement password change API
    alert('Password update functionality will be implemented');
});

// Save preferences
document.getElementById('savePreferencesBtn').addEventListener('click', () => {
    const defaultCpuQuota = document.getElementById('defaultCpuQuota').value;
    const defaultMemory = document.getElementById('defaultMemory').value;
    const defaultDisk = document.getElementById('defaultDisk').value;
    const autoStart = document.getElementById('autoStartContainers').checked;
    
    // Save to localStorage for now
    localStorage.setItem('defaultCpuQuota', defaultCpuQuota);
    localStorage.setItem('defaultMemory', defaultMemory);
    localStorage.setItem('defaultDisk', defaultDisk);
    localStorage.setItem('autoStartContainers', autoStart);
    
    alert('Preferences saved successfully');
});

// Refresh distributions
document.getElementById('refreshDistrosBtn').addEventListener('click', async () => {
    if (!confirm('Refresh distribution templates? This may take a few minutes.')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/system/distros/refresh`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            alert('Distribution templates refreshed successfully');
        } else {
            alert('Failed to refresh distribution templates');
        }
    } catch (error) {
        alert('Error refreshing distribution templates');
    }
});

// Clear logs
document.getElementById('clearLogsBtn').addEventListener('click', () => {
    if (!confirm('Clear all system logs? This action cannot be undone.')) return;
    
    alert('Log clearing functionality will be implemented');
});

// Load saved preferences
function loadPreferences() {
    const defaultCpuQuota = localStorage.getItem('defaultCpuQuota');
    const defaultMemory = localStorage.getItem('defaultMemory');
    const defaultDisk = localStorage.getItem('defaultDisk');
    const autoStart = localStorage.getItem('autoStartContainers');
    
    if (defaultCpuQuota) document.getElementById('defaultCpuQuota').value = defaultCpuQuota;
    if (defaultMemory) document.getElementById('defaultMemory').value = defaultMemory;
    if (defaultDisk) document.getElementById('defaultDisk').value = defaultDisk;
    if (autoStart !== null) document.getElementById('autoStartContainers').checked = autoStart === 'true';
}

// Initialize
checkAuth();
loadSystemInfo();
loadPreferences();
