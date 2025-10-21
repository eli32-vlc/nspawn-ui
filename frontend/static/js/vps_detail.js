// VPS Detail page functionality
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

// Get VPS ID from URL
const vpsId = window.location.pathname.split('/').pop();

// Load VPS details
async function loadVPSDetails() {
    try {
        const response = await fetch(`${API_BASE}/api/containers/${vpsId}`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const vps = await response.json();
            
            document.getElementById('vpsName').textContent = vps.name;
            document.getElementById('vpsStatus').textContent = vps.status;
            document.getElementById('vpsDistro').textContent = vps.distro;
            
            if (vps.ipv4_address) {
                document.getElementById('ipv4Address').value = vps.ipv4_address;
            }
            if (vps.ipv6_address) {
                document.getElementById('ipv6Address').value = vps.ipv6_address;
            }
            
            document.getElementById('cpuLimit').textContent = `${vps.cpu_quota}%`;
            document.getElementById('memoryLimit').textContent = `${vps.memory_mb} MB`;
            document.getElementById('diskLimit').textContent = `${vps.disk_gb} GB`;
        }
    } catch (error) {
        console.error('Error loading VPS details:', error);
    }
}

// Load VPS metrics
async function loadVPSMetrics() {
    try {
        const response = await fetch(`${API_BASE}/api/logs/containers/${vpsId}/metrics`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const metrics = await response.json();
            
            // Update progress bars
            const cpuPercent = Math.min(100, (metrics.cpu_percent || 0));
            const memoryPercent = Math.min(100, (metrics.memory_mb / parseInt(document.getElementById('memoryLimit').textContent) * 100 || 0));
            const diskPercent = Math.min(100, (metrics.disk_mb / (parseInt(document.getElementById('diskLimit').textContent) * 1024) * 100 || 0));
            
            document.getElementById('cpuProgress').style.width = `${cpuPercent}%`;
            document.getElementById('cpuProgress').textContent = `${Math.round(cpuPercent)}%`;
            
            document.getElementById('memoryProgress').style.width = `${memoryPercent}%`;
            document.getElementById('memoryProgress').textContent = `${Math.round(memoryPercent)}%`;
            
            document.getElementById('diskProgress').style.width = `${diskPercent}%`;
            document.getElementById('diskProgress').textContent = `${Math.round(diskPercent)}%`;
        }
    } catch (error) {
        console.error('Error loading metrics:', error);
    }
}

// Load VPS logs
async function loadVPSLogs() {
    try {
        const response = await fetch(`${API_BASE}/api/logs/containers/${vpsId}/logs?lines=100`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const data = await response.json();
            const logContainer = document.getElementById('logContainer');
            
            if (data.logs && data.logs.length > 0) {
                logContainer.innerHTML = data.logs.map(line => 
                    `<div>${escapeHtml(line)}</div>`
                ).join('');
            } else {
                logContainer.innerHTML = '<div class="text-muted">No logs available</div>';
            }
            
            if (autoScroll) {
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        }
    } catch (error) {
        console.error('Error loading logs:', error);
        document.getElementById('logContainer').innerHTML = '<div class="text-danger">Error loading logs</div>';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Copy to clipboard
document.getElementById('copyIpv4').addEventListener('click', () => {
    const ipv4 = document.getElementById('ipv4Address').value;
    navigator.clipboard.writeText(ipv4);
});

document.getElementById('copyIpv6').addEventListener('click', () => {
    const ipv6 = document.getElementById('ipv6Address').value;
    navigator.clipboard.writeText(ipv6);
});

// VPS control buttons
document.getElementById('startBtn').addEventListener('click', async () => {
    try {
        const response = await fetch(`${API_BASE}/api/containers/${vpsId}/start`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            alert('VPS started successfully');
            loadVPSDetails();
        } else {
            alert('Failed to start VPS');
        }
    } catch (error) {
        alert('Error starting VPS');
    }
});

document.getElementById('stopBtn').addEventListener('click', async () => {
    if (!confirm('Stop this VPS?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/containers/${vpsId}/stop`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            alert('VPS stopped successfully');
            loadVPSDetails();
        } else {
            alert('Failed to stop VPS');
        }
    } catch (error) {
        alert('Error stopping VPS');
    }
});

document.getElementById('restartBtn').addEventListener('click', async () => {
    if (!confirm('Restart this VPS?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/containers/${vpsId}/restart`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            alert('VPS restarted successfully');
            loadVPSDetails();
        } else {
            alert('Failed to restart VPS');
        }
    } catch (error) {
        alert('Error restarting VPS');
    }
});

document.getElementById('deleteBtn').addEventListener('click', async () => {
    if (!confirm('Delete this VPS? This action cannot be undone!')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/containers/${vpsId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            alert('VPS deleted successfully');
            window.location.href = '/';
        } else {
            alert('Failed to delete VPS');
        }
    } catch (error) {
        alert('Error deleting VPS');
    }
});

// Log controls
document.getElementById('refreshLogs').addEventListener('click', loadVPSLogs);

document.getElementById('downloadLogs').addEventListener('click', async () => {
    try {
        const response = await fetch(`${API_BASE}/api/logs/containers/${vpsId}/logs?lines=1000`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const data = await response.json();
            const logs = data.logs.join('\n');
            
            const blob = new Blob([logs], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${vpsId}-logs.txt`;
            a.click();
        }
    } catch (error) {
        alert('Error downloading logs');
    }
});

let autoScroll = true;
document.getElementById('toggleAutoScroll').addEventListener('click', () => {
    autoScroll = !autoScroll;
    const btn = document.getElementById('toggleAutoScroll');
    btn.classList.toggle('active', autoScroll);
});

// Initialize
checkAuth();
loadVPSDetails();
loadVPSMetrics();
loadVPSLogs();

// Auto-refresh
setInterval(() => {
    loadVPSMetrics();
    loadVPSLogs();
}, 5000);
