// Create VPS functionality
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

// Distribution version mapping
const distroVersions = {
    'debian': ['bookworm', 'bullseye', 'sid'],
    'ubuntu': ['24.04', '22.04', '20.04'],
    'arch': ['latest']
};

// Update version dropdown when distribution changes
document.getElementById('distribution').addEventListener('change', (e) => {
    const distro = e.target.value;
    const versionSelect = document.getElementById('version');
    
    if (distro && distroVersions[distro]) {
        versionSelect.innerHTML = '<option value="">Select version...</option>' +
            distroVersions[distro].map(v => `<option value="${v}">${v}</option>`).join('');
        versionSelect.disabled = false;
    } else {
        versionSelect.innerHTML = '<option value="">Select distribution first...</option>';
        versionSelect.disabled = true;
    }
});

// Password strength indicator
document.getElementById('rootPassword').addEventListener('input', (e) => {
    const password = e.target.value;
    const strengthDiv = document.getElementById('passwordStrength');
    
    if (password.length === 0) {
        strengthDiv.textContent = '';
        return;
    }
    
    let strength = 0;
    if (password.length >= 8) strength++;
    if (password.length >= 12) strength++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
    if (/\d/.test(password)) strength++;
    if (/[^a-zA-Z0-9]/.test(password)) strength++;
    
    const levels = ['Very Weak', 'Weak', 'Fair', 'Good', 'Strong'];
    const colors = ['danger', 'warning', 'info', 'primary', 'success'];
    
    strengthDiv.innerHTML = `<span class="badge bg-${colors[strength-1]}">${levels[strength-1]}</span>`;
});

// Resource sliders
document.getElementById('cpuQuota').addEventListener('input', (e) => {
    document.getElementById('cpuQuotaValue').textContent = `${e.target.value}%`;
});

document.getElementById('memoryMb').addEventListener('input', (e) => {
    const value = parseInt(e.target.value);
    if (value >= 1024) {
        document.getElementById('memoryMbValue').textContent = `${(value/1024).toFixed(1)} GB`;
    } else {
        document.getElementById('memoryMbValue').textContent = `${value} MB`;
    }
});

document.getElementById('diskGb').addEventListener('input', (e) => {
    document.getElementById('diskGbValue').textContent = `${e.target.value} GB`;
});

// IPv6 configuration handlers
document.getElementById('enableIpv6').addEventListener('change', (e) => {
    const ipv6ModeGroup = document.getElementById('ipv6ModeGroup');
    if (e.target.checked) {
        ipv6ModeGroup.style.display = 'block';
    } else {
        ipv6ModeGroup.style.display = 'none';
        document.getElementById('wireguardConfigGroup').style.display = 'none';
    }
});

document.getElementById('ipv6Mode').addEventListener('change', (e) => {
    const wireguardGroup = document.getElementById('wireguardConfigGroup');
    if (e.target.value === 'wireguard') {
        wireguardGroup.style.display = 'block';
    } else {
        wireguardGroup.style.display = 'none';
    }
});

// Step navigation
let currentStep = 1;

function showStep(step) {
    // Hide all steps
    document.querySelectorAll('.step').forEach(s => s.classList.add('d-none'));
    
    // Show current step
    document.getElementById(`step${step}`).classList.remove('d-none');
    
    // Update progress bar
    const progress = (step / 3) * 100;
    document.getElementById('progressBar').style.width = `${progress}%`;
    
    // Update step indicators
    document.querySelectorAll('.step-indicator').forEach((indicator, index) => {
        if (index < step) {
            indicator.classList.add('active');
        } else {
            indicator.classList.remove('active');
        }
    });
}

// Step 1 validation
document.getElementById('nextStep1').addEventListener('click', () => {
    const name = document.getElementById('vpsName').value;
    const distro = document.getElementById('distribution').value;
    const version = document.getElementById('version').value;
    const password = document.getElementById('rootPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (!name || !distro || !version) {
        alert('Please fill in all required fields');
        return;
    }
    
    if (!/^[a-z0-9-]+$/.test(name)) {
        alert('VPS name must contain only lowercase letters, numbers, and hyphens');
        return;
    }
    
    if (password.length < 8) {
        alert('Password must be at least 8 characters long');
        return;
    }
    
    if (password !== confirmPassword) {
        alert('Passwords do not match');
        return;
    }
    
    currentStep = 2;
    showStep(currentStep);
});

// Step navigation buttons
document.getElementById('prevStep2').addEventListener('click', () => {
    currentStep = 1;
    showStep(currentStep);
});

document.getElementById('nextStep2').addEventListener('click', () => {
    currentStep = 3;
    showStep(currentStep);
});

document.getElementById('prevStep3').addEventListener('click', () => {
    currentStep = 2;
    showStep(currentStep);
});

// Form submission
document.getElementById('createVpsForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const createBtn = document.getElementById('createBtn');
    createBtn.disabled = true;
    createBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Creating...';
    
    // Show status display
    const statusDiv = document.getElementById('creationStatus');
    statusDiv.style.display = 'block';
    
    const data = {
        name: document.getElementById('vpsName').value,
        distro: document.getElementById('distribution').value + ':' + document.getElementById('version').value,
        root_password: document.getElementById('rootPassword').value,
        cpu_quota: parseInt(document.getElementById('cpuQuota').value),
        memory_mb: parseInt(document.getElementById('memoryMb').value),
        disk_gb: parseInt(document.getElementById('diskGb').value),
        enable_ssh: document.getElementById('enableSsh').checked,
        enable_ipv6: document.getElementById('enableIpv6').checked
    };
    
    // Add IPv6 configuration if enabled
    if (data.enable_ipv6) {
        data.ipv6_mode = document.getElementById('ipv6Mode').value;
        
        // Add WireGuard config if selected
        if (data.ipv6_mode === 'wireguard') {
            const wgConfig = document.getElementById('wireguardConfig').value;
            if (!wgConfig.trim()) {
                alert('Please enter WireGuard configuration');
                createBtn.disabled = false;
                createBtn.innerHTML = '<i class="bi bi-plus-circle"></i> Create VPS';
                statusDiv.style.display = 'none';
                return;
            }
            data.wireguard_config = wgConfig;
        }
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/containers/create`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // Start polling for status
            const containerId = result.container_id;
            pollCreationStatus(containerId);
        } else {
            alert(`Failed to create VPS: ${result.detail || 'Unknown error'}`);
            createBtn.disabled = false;
            createBtn.innerHTML = '<i class="bi bi-plus-circle"></i> Create VPS';
            statusDiv.style.display = 'none';
        }
    } catch (error) {
        alert(`Error creating VPS: ${error.message}`);
        createBtn.disabled = false;
        createBtn.innerHTML = '<i class="bi bi-plus-circle"></i> Create VPS';
        statusDiv.style.display = 'none';
    }
});

// Poll creation status
async function pollCreationStatus(containerId) {
    const statusMessageDiv = document.getElementById('creationStatusMessage');
    const progressBar = document.getElementById('creationProgressBar');
    
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/containers/create-status/${containerId}`, {
                headers: getAuthHeaders()
            });
            
            if (response.ok) {
                const status = await response.json();
                
                // Update progress bar
                progressBar.style.width = `${status.progress}%`;
                progressBar.textContent = `${status.progress}%`;
                
                // Update status message
                statusMessageDiv.textContent = status.message;
                
                // Check if completed or failed
                if (status.status === 'completed') {
                    clearInterval(pollInterval);
                    progressBar.classList.remove('progress-bar-animated');
                    progressBar.classList.add('bg-success');
                    setTimeout(() => {
                        alert('VPS created successfully!');
                        window.location.href = '/';
                    }, 1000);
                } else if (status.status === 'failed') {
                    clearInterval(pollInterval);
                    progressBar.classList.remove('progress-bar-animated');
                    progressBar.classList.add('bg-danger');
                    statusMessageDiv.innerHTML = `<span class="text-danger">Error: ${status.error || status.message}</span>`;
                    
                    const createBtn = document.getElementById('createBtn');
                    createBtn.disabled = false;
                    createBtn.innerHTML = '<i class="bi bi-plus-circle"></i> Create VPS';
                }
            } else {
                // Status not found, might have completed
                clearInterval(pollInterval);
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    }, 2000); // Poll every 2 seconds
}

// Initialize
checkAuth();
showStep(1);
