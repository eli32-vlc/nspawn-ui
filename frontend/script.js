document.addEventListener('DOMContentLoaded', () => {
    const containerList = document.getElementById('container-list');
    const createContainerForm = document.getElementById('create-container-form');
    const logView = document.getElementById('log-view');
    const sshModal = new bootstrap.Modal(document.getElementById('sshModal'));
    const sshForm = document.getElementById('ssh-form');
    const sshContainerNameInput = document.getElementById('ssh-container-name');
    const logoutButton = document.getElementById('logout-button');

    const API_URL = 'http://localhost:8000';
    const token = localStorage.getItem('accessToken');

    if (!token) {
        window.location.href = 'login.html';
        return;
    }

    const authHeader = { 'Authorization': `Bearer ${token}` };

    const getContainers = async () => {
        try {
            const response = await fetch(`${API_URL}/containers`, { headers: authHeader });
            if (response.status === 401) {
                window.location.href = 'login.html';
                return;
            }
            const containers = await response.json();

            containerList.innerHTML = '';

            containers.forEach(container => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${container.name}</td>
                    <td>${container.status}</td>
                    <td>${container.ip || 'N/A'}</td>
                    <td>${container.image}</td>
                    <td>
                        <button class="btn btn-success btn-sm" onclick="startContainer('${container.name}')">Start</button>
                        <button class="btn btn-warning btn-sm" onclick="stopContainer('${container.name}')">Stop</button>
                        <button class="btn btn-info btn-sm" onclick="restartContainer('${container.name}')">Restart</button>
                        <button class="btn btn-danger btn-sm" onclick="removeContainer('${container.name}')">Remove</button>
                        <button class="btn btn-secondary btn-sm" onclick="getLogs('${container.name}')">Logs</button>
                        <button class="btn btn-primary btn-sm" onclick="openSshModal('${container.name}')">Setup SSH</button>
                    </td>
                `;
                containerList.appendChild(row);
            });
        } catch (error) {
            console.error('Error fetching containers:', error);
        }
    };

    createContainerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const distro = document.getElementById('distro').value;
        const root_password = document.getElementById('root-password').value;
        const cpu_max = document.getElementById('cpu-max').value;
        const memory_max = document.getElementById('memory-max').value;
        const storage_max = document.getElementById('storage-max').value;

        const containerData = {
            distro,
            root_password,
            cpu_max: cpu_max ? parseInt(cpu_max) : null,
            memory_max_mb: memory_max ? parseInt(memory_max) : null,
            storage_max_gb: storage_max ? parseInt(storage_max) : null,
        };

        try {
            const response = await fetch(`${API_URL}/containers`, {
                method: 'POST',
                headers: { ...authHeader, 'Content-Type': 'application/json' },
                body: JSON.stringify(containerData),
            });

            if (response.ok) {
                getContainers();
                createContainerForm.reset();
            } else {
                console.error('Error creating container');
            }
        } catch (error) {
            console.error('Error creating container:', error);
        }
    });

    window.startContainer = async (name) => {
        await fetch(`${API_URL}/containers/${name}/start`, { method: 'POST', headers: authHeader });
        getContainers();
    };

    window.stopContainer = async (name) => {
        await fetch(`${API_URL}/containers/${name}/stop`, { method: 'POST', headers: authHeader });
        getContainers();
    };

    window.restartContainer = async (name) => {
        await fetch(`${API_URL}/containers/${name}/restart`, { method: 'POST', headers: authHeader });
        getContainers();
    };

    window.removeContainer = async (name) => {
        await fetch(`${API_URL}/containers/${name}`, { method: 'DELETE', headers: authHeader });
        getContainers();
    };

    window.getLogs = async (name) => {
        try {
            const response = await fetch(`${API_URL}/containers/${name}/logs`, { headers: authHeader });
            const data = await response.json();
            logView.textContent = data.logs;
        } catch (error) {
            console.error('Error fetching logs:', error);
            logView.textContent = 'Error fetching logs.';
        }
    };

    window.openSshModal = (name) => {
        sshContainerNameInput.value = name;
        sshModal.show();
    };

    const sshKeyModal = new bootstrap.Modal(document.getElementById('sshKeyModal'));
    const sshPrivateKey = document.getElementById('ssh-private-key');

    sshForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const containerName = sshContainerNameInput.value;
        const username = document.getElementById('ssh-username').value;

        const sshData = { username };

        try {
            const response = await fetch(`${API_URL}/containers/${containerName}/ssh`, {
                method: 'POST',
                headers: { ...authHeader, 'Content-Type': 'application/json' },
                body: JSON.stringify(sshData),
            });

            if (response.ok) {
                const data = await response.json();
                sshPrivateKey.textContent = data.private_key;
                sshForm.reset();
                sshModal.hide();
                sshKeyModal.show();
            } else {
                console.error('Error setting up SSH');
            }
        } catch (error) {
            console.error('Error setting up SSH:', error);
        }
    });

    logoutButton.addEventListener('click', () => {
        localStorage.removeItem('accessToken');
        window.location.href = 'login.html';
    });

    getContainers();
});
