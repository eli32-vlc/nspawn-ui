#!/bin/bash

# nspawn-vps - Integration Test

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
    log "[INFO] $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    log "[WARNING] $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    log "[ERROR] $1"
}

# Test container creation and management
test_container_lifecycle() {
    log_info "Testing container lifecycle..."
    
    # Define test container parameters
    local test_container="test-container-$(date +%s)"
    local test_password="test123"
    local api_url="http://127.0.0.1:8080"
    
    log_info "Creating test container: $test_container"
    
    # Get auth token (login with default admin credentials)
    local token_response=$(curl -s -X POST "$api_url/api/login" \
        -H "Content-Type: application/json" \
        -d '{"username": "admin", "password": "admin123"}')
    
    local token=$(echo "$token_response" | jq -r '.access_token' 2>/dev/null)
    
    if [ -z "$token" ] || [ "$token" = "null" ]; then
        log_error "Failed to get authentication token"
        return 1
    fi
    
    log_info "Successfully obtained authentication token"
    
    # Create a test container
    local create_response=$(curl -s -X POST "$api_url/api/containers/create" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "{
            \"name\": \"$test_container\",
            \"distro\": \"debian\",
            \"architecture\": \"x86_64\",
            \"root_password\": \"$test_password\",
            \"enable_ssh\": true
        }")
    
    if echo "$create_response" | grep -q "created successfully"; then
        log_info "Container $test_container created successfully"
    else
        log_error "Failed to create container: $create_response"
        return 1
    fi
    
    # Wait for container to be created
    sleep 5
    
    # Test starting the container
    local start_response=$(curl -s -X POST "$api_url/api/containers/$test_container/start" \
        -H "Authorization: Bearer $token")
    
    if echo "$start_response" | grep -q "started successfully"; then
        log_info "Container $test_container started successfully"
    else
        log_error "Failed to start container: $start_response"
        return 1
    fi
    
    # Wait for container to start
    sleep 10
    
    # Check container status
    local containers_response=$(curl -s -X GET "$api_url/api/containers" \
        -H "Authorization: Bearer $token")
    
    if echo "$containers_response" | grep -q "$test_container" && \
       echo "$containers_response" | grep -q "running"; then
        log_info "Container status is running as expected"
    else
        log_warn "Container status may not be running: $containers_response"
    fi
    
    # Test stopping the container
    local stop_response=$(curl -s -X POST "$api_url/api/containers/$test_container/stop" \
        -H "Authorization: Bearer $token")
    
    if echo "$stop_response" | grep -q "stopped successfully"; then
        log_info "Container $test_container stopped successfully"
    else
        log_error "Failed to stop container: $stop_response"
        return 1
    fi
    
    # Wait for container to stop
    sleep 5
    
    # Remove the test container
    local delete_response=$(curl -s -X DELETE "$api_url/api/containers/$test_container" \
        -H "Authorization: Bearer $token")
    
    if echo "$delete_response" | grep -q "removed successfully"; then
        log_info "Container $test_container removed successfully"
    else
        log_error "Failed to remove container: $delete_response"
        return 1
    fi
    
    log_info "Container lifecycle test completed successfully"
    return 0
}

# Test API endpoints
test_api_endpoints() {
    log_info "Testing API endpoints..."
    
    local api_url="http://127.0.0.1:8080"
    
    # Get auth token
    local token_response=$(curl -s -X POST "$api_url/api/login" \
        -H "Content-Type: application/json" \
        -d '{"username": "admin", "password": "admin123"}')
    
    local token=$(echo "$token_response" | jq -r '.access_token' 2>/dev/null)
    
    if [ -z "$token" ] || [ "$token" = "null" ]; then
        log_error "Failed to get authentication token"
        return 1
    fi
    
    # Test system info endpoint
    local system_response=$(curl -s -X GET "$api_url/api/system/info" \
        -H "Authorization: Bearer $token")
    
    if [ -n "$system_response" ] && [ "$system_response" != "null" ]; then
        log_info "System info endpoint is working"
    else
        log_error "System info endpoint failed: $system_response"
        return 1
    fi
    
    # Test containers endpoint
    local containers_response=$(curl -s -X GET "$api_url/api/containers" \
        -H "Authorization: Bearer $token")
    
    if [ -n "$containers_response" ]; then
        log_info "Containers endpoint is working"
    else
        log_error "Containers endpoint failed"
        return 1
    fi
    
    # Test distros endpoint
    local distros_response=$(curl -s -X GET "$api_url/api/distros/available" \
        -H "Authorization: Bearer $token")
    
    if [ -n "$distros_response" ] && echo "$distros_response" | grep -q "distros"; then
        log_info "Distros endpoint is working"
    else
        log_error "Distros endpoint failed: $distros_response"
        return 1
    fi
    
    log_info "API endpoints test completed successfully"
    return 0
}

# Run integration tests
run_integration_tests() {
    log_info "Starting integration tests..."
    
    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    
    # Array of test functions
    local tests=("test_api_endpoints" "test_container_lifecycle")
    
    for test in "${tests[@]}"; do
        ((total_tests++))
        
        log "Running integration test: $test"
        if "$test"; then
            ((passed_tests++))
            log_info "✓ Integration test $test PASSED"
        else
            ((failed_tests++))
            log_error "✗ Integration test $test FAILED"
        fi
        
        echo
    done
    
    log_info "Integration Test Summary:"
    log_info "Total tests: $total_tests"
    log_info "Passed: $passed_tests"
    log_info "Failed: $failed_tests"
    
    if [ $failed_tests -eq 0 ]; then
        log_info "🎉 All integration tests passed!"
        return 0
    else
        log_error "❌ Some integration tests failed."
        return 1
    fi
}

# Main function
main() {
    log_info "Starting nspawn-vps integration tests..."
    
    # Check for required tools
    if ! command -v curl &>/dev/null; then
        log_error "curl is required for integration tests"
        exit 1
    fi
    
    if ! command -v jq &>/dev/null; then
        log_warn "jq is not installed, some tests may fail"
    fi
    
    run_integration_tests
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi