# API Documentation

## Authentication

All API endpoints (except login) require authentication using JWT tokens.

### Login

**Endpoint:** `POST /api/auth/login`

**Request:**
```json
{
  "username": "admin",
  "password": "your_password"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "username": "admin",
  "message": "Login successful"
}
```

**Usage:**
```bash
# Get token
TOKEN=$(curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r '.token')

# Use token in requests
curl http://localhost:8080/api/containers \
  -H "Authorization: Bearer $TOKEN"
```

## Container Management

### Create Container

**Endpoint:** `POST /api/containers/create`

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "name": "my-vps",
  "distro": "debian",
  "architecture": "x86_64",
  "root_password": "SecurePassword123!",
  "cpu_quota": 100,
  "memory_mb": 512,
  "disk_gb": 10,
  "enable_ssh": true,
  "enable_ipv6": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "VPS my-vps created successfully",
  "container_id": "vps-my-vps",
  "data": {
    "name": "my-vps",
    "distro": "debian",
    "status": "creating"
  }
}
```

### List Containers

**Endpoint:** `GET /api/containers`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
[
  {
    "id": "vps-my-vps",
    "name": "my-vps",
    "status": "running",
    "distro": "debian",
    "ipv4_address": "10.0.0.10",
    "ipv6_address": "2001:db8::1",
    "cpu_quota": 100,
    "memory_mb": 512,
    "disk_gb": 10,
    "created_at": "2025-10-21T07:00:00Z",
    "uptime": "2 days, 5 hours"
  }
]
```

### Get Container Details

**Endpoint:** `GET /api/containers/{container_id}`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "id": "vps-my-vps",
  "name": "my-vps",
  "status": "running",
  "distro": "debian",
  "ipv4_address": "10.0.0.10",
  "ipv6_address": "2001:db8::1",
  "cpu_quota": 100,
  "memory_mb": 512,
  "disk_gb": 10,
  "created_at": "2025-10-21T07:00:00Z",
  "uptime": "2 days, 5 hours"
}
```

### Start Container

**Endpoint:** `POST /api/containers/{container_id}/start`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "VPS vps-my-vps started successfully"
}
```

### Stop Container

**Endpoint:** `POST /api/containers/{container_id}/stop`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "VPS vps-my-vps stopped successfully"
}
```

### Restart Container

**Endpoint:** `POST /api/containers/{container_id}/restart`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "VPS vps-my-vps restarted successfully"
}
```

### Delete Container

**Endpoint:** `DELETE /api/containers/{container_id}`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "VPS vps-my-vps deleted successfully"
}
```

### Force Stop Container

**Endpoint:** `POST /api/containers/{container_id}/force-stop`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "VPS vps-my-vps force stopped successfully"
}
```

## Network Management

### Get Bridge Status

**Endpoint:** `GET /api/network/bridge-status`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "bridge_name": "br0",
  "ipv4_subnet": "10.0.0.0/24",
  "ipv6_prefix": "2001:db8::/64",
  "status": "active"
}
```

### Create Port Forward

**Endpoint:** `POST /api/network/port-forward`

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "host_port": 8080,
  "container_id": "vps-my-vps",
  "container_port": 80,
  "protocol": "tcp"
}
```

**Response:**
```json
{
  "message": "Port forwarding created",
  "rule": {
    "host_port": 8080,
    "container_id": "vps-my-vps",
    "container_port": 80,
    "protocol": "tcp"
  }
}
```

## System Information

### Get System Info

**Endpoint:** `GET /api/system/info`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "version": "1.0.0",
  "uptime": "5 days, 3:24:15",
  "architecture": "x86_64",
  "hostname": "zenithstack-server",
  "cpu_count": 4,
  "total_memory_mb": 8192,
  "available_memory_mb": 4096,
  "disk_total_gb": 500.0,
  "disk_available_gb": 250.0
}
```

### Get Available Distributions

**Endpoint:** `GET /api/system/distros/available`

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
[
  {
    "name": "debian",
    "versions": ["bookworm", "bullseye", "sid"],
    "architectures": ["x86_64"]
  },
  {
    "name": "ubuntu",
    "versions": ["24.04", "22.04", "20.04"],
    "architectures": ["x86_64"]
  },
  {
    "name": "arch",
    "versions": ["latest"],
    "architectures": ["x86_64"]
  }
]
```

## Logging

### Get Container Logs

**Endpoint:** `GET /api/logs/containers/{container_id}/logs`

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `lines`: Number of log lines to retrieve (default: 100)
- `level`: Log level filter (optional)

**Response:**
```json
{
  "logs": [
    "Oct 21 07:00:00 my-vps systemd[1]: Started System Logging Service.",
    "Oct 21 07:00:01 my-vps sshd[123]: Server listening on 0.0.0.0 port 22."
  ],
  "container_id": "vps-my-vps",
  "lines": 100
}
```

### WebSocket Log Stream

**Endpoint:** `WS /api/logs/ws/containers/{container_id}/logs`

**Usage:**
```javascript
const ws = new WebSocket('ws://localhost:8080/api/logs/ws/containers/vps-my-vps/logs');

ws.onmessage = (event) => {
  console.log('Log:', event.data);
};
```

## Error Responses

All endpoints may return error responses:

**401 Unauthorized:**
```json
{
  "detail": "Invalid token"
}
```

**404 Not Found:**
```json
{
  "detail": "Container not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Internal server error message"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. This will be added in future versions.

## Pagination

Currently, no pagination is implemented for list endpoints. All results are returned. This will be improved in future versions.
