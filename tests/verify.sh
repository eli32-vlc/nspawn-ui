#!/bin/bash

# nspawn-vps - Test and Verification Script

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

# Test systemd-nspawn availability
test_nspawn() {
    log_info "Testing systemd-nspawn availability..."
    
    if ! command -v machinectl &>/dev/null; then
        log_error "machinectl command not found. systemd-nspawn is not properly installed."
        return 1
    fi
    
    if ! command -v systemd-nspawn &>/dev/null; then
        log_error "systemd-nspawn command not found."
        return 1
    fi
    
    # Test basic functionality
    machinectl list > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        log_error "machinectl list failed. systemd-nspawn may not be properly configured."
        return 1
    fi
    
    log_info "systemd-nspawn is properly installed and accessible."
    return 0
}

# Test WebUI service
test_webui() {
    log_info "Testing WebUI service..."
    
    # Check if service is running
    if ! systemctl is-active --quiet nspawn-manager; then
        log_error "nspawn-manager service is not running."
        return 1
    fi
    
    # Check if service is enabled
    if ! systemctl is-enabled --quiet nspawn-manager; then
        log_warn "nspawn-manager service is not enabled at boot."
    else
        log_info "nspawn-manager service is running and enabled at boot."
    fi
    
    # Test API access locally
    if curl -s --max-time 10 127.0.0.1:8080 > /dev/null 2>&1; then
        log_info "WebUI API is accessible at 127.0.0.1:8080"
    else
        log_warn "WebUI API is not accessible at 127.0.0.1:8080, but service is running"
    fi
    
    return 0
}

# Test bridge networking
test_networking() {
    log_info "Testing network bridge..."
    
    # Check if bridge exists
    if ip link show br0 &>/dev/null; then
        log_info "Bridge br0 exists"
        
        # Check if bridge is up
        if ip link show br0 up &>/dev/null; then
            log_info "Bridge br0 is up"
        else
            log_warn "Bridge br0 exists but is not up"
        fi
    else
        log_error "Bridge br0 does not exist"
        return 1
    fi
    
    # Check IP forwarding
    ipv4_forward=$(cat /proc/sys/net/ipv4/ip_forward)
    ipv6_forward=$(cat /proc/sys/net/ipv6/conf/all/forwarding)
    
    if [ "$ipv4_forward" -eq 1 ]; then
        log_info "IPv4 forwarding is enabled"
    else
        log_error "IPv4 forwarding is not enabled"
        return 1
    fi
    
    if [ "$ipv6_forward" -eq 1 ]; then
        log_info "IPv6 forwarding is enabled"
    else
        log_warn "IPv6 forwarding is not enabled (this may be expected)"
    fi
    
    # Check iptables NAT rules
    if iptables -t nat -L POSTROUTING -v -n | grep -q br0; then
        log_info "NAT rules for br0 found in iptables"
    else
        log_warn "No NAT rules for br0 found in iptables"
    fi
    
    return 0
}

# Test debootstrap availability
test_debootstrap() {
    log_info "Testing debootstrap availability..."
    
    if command -v debootstrap &>/dev/null; then
        log_info "debootstrap is available"
    else
        log_error "debootstrap is not available. Container creation will not work."
        return 1
    fi
    
    return 0
}

# Test database functionality
test_database() {
    log_info "Testing database functionality..."
    
    if [ -f "/etc/nspawn-manager/containers.db" ]; then
        log_info "Database file exists"
        
        # Test database access
        if sqlite3 /etc/nspawn-manager/containers.db "SELECT name FROM sqlite_master WHERE type='table';" > /dev/null 2>&1; then
            log_info "Database is accessible"
        else
            log_error "Database is not accessible"
            return 1
        fi
    else
        log_warn "Database file does not exist yet (this is normal on first run)"
    fi
    
    return 0
}

# Test Python dependencies
test_python_deps() {
    log_info "Testing Python dependencies..."
    
    PYTHON_PATH="/opt/nspawn-manager/venv/bin/python3"
    
    if [ ! -f "$PYTHON_PATH" ]; then
        log_error "Python virtual environment not found at $PYTHON_PATH"
        return 1
    fi
    
    # Test key dependencies
    DEPS=("fastapi" "uvicorn" "pydantic" "bcrypt" "jose" "sqlite3")
    
    for dep in "${DEPS[@]}"; do
        if "$PYTHON_PATH" -c "import $dep" 2>/dev/null; then
            log_info "Python dependency '$dep' is available"
        else
            log_error "Python dependency '$dep' is not available"
            return 1
        fi
    done
    
    return 0
}

# Run all tests
run_tests() {
    log_info "Starting comprehensive tests..."
    
    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    
    # Array of test functions
    local tests=("test_nspawn" "test_webui" "test_networking" "test_debootstrap" "test_database" "test_python_deps")
    
    for test in "${tests[@]}"; do
        ((total_tests++))
        
        log "Running test: $test"
        if "$test"; then
            ((passed_tests++))
            log_info "✓ Test $test PASSED"
        else
            ((failed_tests++))
            log_error "✗ Test $test FAILED"
        fi
        
        echo
    done
    
    log_info "Test Summary:"
    log_info "Total tests: $total_tests"
    log_info "Passed: $passed_tests"
    log_info "Failed: $failed_tests"
    
    if [ $failed_tests -eq 0 ]; then
        log_info "🎉 All tests passed! nspawn-vps is ready for use."
        return 0
    else
        log_error "❌ Some tests failed. Please check the errors above."
        return 1
    fi
}

# Main function
main() {
    log_info "Starting nspawn-vps verification..."
    run_tests
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi