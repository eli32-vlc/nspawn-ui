// Login functionality
const API_BASE = window.location.origin;

document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorAlert = document.getElementById('errorAlert');
    const loginText = document.getElementById('loginText');
    const loginSpinner = document.getElementById('loginSpinner');
    
    // Show spinner
    loginText.classList.add('d-none');
    loginSpinner.classList.remove('d-none');
    errorAlert.classList.add('d-none');
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Store token
            localStorage.setItem('authToken', data.token);
            localStorage.setItem('username', data.username);
            
            // Redirect to dashboard
            window.location.href = '/';
        } else {
            errorAlert.textContent = data.detail || 'Login failed';
            errorAlert.classList.remove('d-none');
        }
    } catch (error) {
        errorAlert.textContent = 'Connection error. Please try again.';
        errorAlert.classList.remove('d-none');
    } finally {
        loginText.classList.remove('d-none');
        loginSpinner.classList.add('d-none');
    }
});
