// Network page functionality
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
}

// Load bridge status
async function loadBridgeStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/network/bridge-status`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const bridge = await response.json();
            document.getElementById('bridgeStatus').innerHTML = `
                <table class="table table-sm">
                    <tr>
                        <th>Bridge Name:</th>
                        <td>${bridge.bridge_name}</td>
                    </tr>
                    <tr>
                        <th>IPv4 Subnet:</th>
                        <td>${bridge.ipv4_subnet}</td>
                    </tr>
                    <tr>
                        <th>IPv6 Prefix:</th>
                        <td>${bridge.ipv6_prefix || 'Not configured'}</td>
                    </tr>
                    <tr>
                        <th>Status:</th>
                        <td><span class="badge bg-success">${bridge.status}</span></td>
                    </tr>
                </table>
            `;
        } else {
            throw new Error('Failed to load bridge status');
        }
    } catch (error) {
        console.error('Error loading bridge status:', error);
        document.getElementById('bridgeStatus').innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> Failed to load bridge status
            </div>
        `;
    }
}

// Load NAT rules
async function loadNatRules() {
    try {
        const response = await fetch(`${API_BASE}/api/network/ipv4-nat-rules`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const data = await response.json();
            const rules = data.rules || [];
            
            const tbody = document.getElementById('natRulesTable');
            if (rules.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center py-3">
                            <i class="bi bi-inbox" style="font-size: 2rem; color: #ddd;"></i>
                            <p class="mt-2 text-muted">No port forwarding rules configured</p>
                        </td>
                    </tr>
                `;
            } else {
                tbody.innerHTML = rules.map(rule => `
                    <tr>
                        <td>${rule.host_port}</td>
                        <td>${rule.container_id}</td>
                        <td>${rule.container_port}</td>
                        <td><span class="badge bg-info">${rule.protocol.toUpperCase()}</span></td>
                        <td>
                            <button class="btn btn-sm btn-danger" onclick="deleteRule('${rule.id}')">
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Error loading NAT rules:', error);
    }
}

// Load containers for dropdown
async function loadContainers() {
    try {
        const response = await fetch(`${API_BASE}/api/containers`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const containers = await response.json();
            const select = document.getElementById('containerSelect');
            
            select.innerHTML = '<option value="">Select a container...</option>' +
                containers.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
        }
    } catch (error) {
        console.error('Error loading containers:', error);
    }
}

// Add port forwarding rule
document.getElementById('saveRuleBtn').addEventListener('click', async () => {
    const hostPort = document.getElementById('hostPort').value;
    const containerId = document.getElementById('containerSelect').value;
    const containerPort = document.getElementById('containerPort').value;
    const protocol = document.getElementById('protocol').value;
    
    if (!hostPort || !containerId || !containerPort) {
        alert('Please fill in all fields');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/network/port-forward`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                host_port: parseInt(hostPort),
                container_id: containerId,
                container_port: parseInt(containerPort),
                protocol: protocol
            })
        });
        
        if (response.ok) {
            alert('Port forwarding rule added');
            bootstrap.Modal.getInstance(document.getElementById('addRuleModal')).hide();
            document.getElementById('addRuleForm').reset();
            loadNatRules();
        } else {
            alert('Failed to add rule');
        }
    } catch (error) {
        alert('Error adding rule');
    }
});

// Delete port forwarding rule
async function deleteRule(ruleId) {
    if (!confirm('Delete this port forwarding rule?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/network/port-forward/${ruleId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            loadNatRules();
        } else {
            alert('Failed to delete rule');
        }
    } catch (error) {
        alert('Error deleting rule');
    }
}

// IPv6 mode change
document.getElementById('ipv6Mode').addEventListener('change', (e) => {
    const detailsDiv = document.getElementById('ipv6Details');
    if (e.target.value !== 'disabled') {
        detailsDiv.classList.remove('d-none');
    } else {
        detailsDiv.classList.add('d-none');
    }
});

// Initialize
checkAuth();
loadBridgeStatus();
loadNatRules();
loadContainers();
