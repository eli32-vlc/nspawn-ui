#!/bin/bash

# nspawn-ui build validation script
# This script validates the nspawn-ui build and configuration

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to validate Python dependencies
validate_python_deps() {
    print_status "Validating Python dependencies..."
    
    if ! command_exists python3; then
        print_error "Python3 is not installed"
        return 1
    fi
    
    # Check if required Python packages are available
    python3 -c "import fastapi, uvicorn, pydantic, typing" 2>/dev/null
    if [ $? -ne 0 ]; then
        print_error "Required Python packages are not installed (fastapi, uvicorn, pydantic)"
        return 1
    fi
    
    print_status "Python dependencies validated"
}

# Function to validate systemd-nspawn availability
validate_systemd_nspawn() {
    print_status "Validating systemd-nspawn availability..."
    
    if ! command_exists machinectl; then
        print_error "machinectl is not available - systemd-container package might not be installed"
        return 1
    fi
    
    if ! command_exists systemd-nspawn; then
        print_error "systemd-nspawn is not available - systemd-container package might not be installed"
        return 1
    fi
    
    print_status "systemd-nspawn tools validated"
}

# Function to validate debootstrap availability
validate_debootstrap() {
    print_status "Validating debootstrap availability..."
    
    if ! command_exists debootstrap; then
        print_error "debootstrap is not installed"
        return 1
    fi
    
    print_status "debootstrap validated"
}

# Function to validate iptables availability
validate_iptables() {
    print_status "Validating iptables availability..."
    
    if ! command_exists iptables; then
        print_error "iptables is not installed"
        return 1
    fi
    
    print_status "iptables validated"
}

# Function to validate network configuration
validate_networking() {
    print_status "Validating network configuration..."
    
    # Check if bridge interface exists
    if ip link show br0 >/dev/null 2>&1; then
        print_status "Bridge interface br0 exists"
    else
        print_warning "Bridge interface br0 does not exist - networking may not be properly configured"
    fi
    
    # Check IP forwarding
    if [ "$(cat /proc/sys/net/ipv4/ip_forward)" = "1" ]; then
        print_status "IPv4 forwarding is enabled"
    else
        print_warning "IPv4 forwarding is not enabled"
    fi
    
    # Check IPv6 forwarding if IPv6 is available
    if [ -f /proc/sys/net/ipv6/conf/all/forwarding ]; then
        if [ "$(cat /proc/sys/net/ipv6/conf/all/forwarding)" = "1" ]; then
            print_status "IPv6 forwarding is enabled"
        else
            print_warning "IPv6 forwarding is not enabled"
        fi
    fi
}

# Function to validate nspawn-ui service
validate_service() {
    print_status "Validating nspawn-ui service..."
    
    if systemctl is-active --quiet nspawn-ui; then
        print_status "nspawn-ui service is running"
        
        # Get the service status to show more details
        systemctl status nspawn-ui --no-pager -l
    else
        print_error "nspawn-ui service is not running"
        print_status "To start the service: sudo systemctl start nspawn-ui"
        return 1
    fi
}

# Function to validate API connectivity
validate_api() {
    print_status "Validating API connectivity..."
    
    # Check if the API is responding (using curl or wget)
    if command_exists curl; then
        response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null)
        if [ "$response" = "200" ]; then
            print_status "API is responding on port 8000"
        else
            print_warning "API is not responding on port 8000 (HTTP code: $response)"
        fi
    elif command_exists wget; then
        if wget --spider --quiet http://localhost:8000/ 2>/dev/null; then
            print_status "API is responding on port 8000"
        else
            print_warning "API is not responding on port 8000"
        fi
    else
        print_warning "Neither curl nor wget available to test API connectivity"
    fi
}

# Function to validate directory structure
validate_structure() {
    print_status "Validating directory structure..."
    
    # Check if installation directory exists
    if [ -d "/opt/nspawn-ui" ]; then
        print_status "Installation directory exists: /opt/nspawn-ui"
        
        # Check for required subdirectories
        for dir in "api" "webui" "config"; do
            if [ -d "/opt/nspawn-ui/$dir" ]; then
                print_status "Required directory exists: /opt/nspawn-ui/$dir"
            else
                print_warning "Required directory missing: /opt/nspawn-ui/$dir"
            fi
        done
        
        # Check for requirements file
        if [ -f "/opt/nspawn-ui/requirements.txt" ]; then
            print_status "Requirements file exists: /opt/nspawn-ui/requirements.txt"
        else
            print_warning "Requirements file missing: /opt/nspawn-ui/requirements.txt"
        fi
    else
        print_warning "Installation directory does not exist: /opt/nspawn-ui"
    fi
    
    # Check machines directory
    if [ -d "/var/lib/machines" ]; then
        print_status "Machines directory exists: /var/lib/machines"
    else
        print_warning "Machines directory does not exist: /var/lib/machines"
    fi
}

# Function to validate systemd unit file
validate_systemd_unit() {
    print_status "Validating systemd unit file..."
    
    if [ -f "/etc/systemd/system/nspawn-ui.service" ]; then
        print_status "Systemd unit file exists: /etc/systemd/system/nspawn-ui.service"
    else
        print_warning "Systemd unit file missing: /etc/systemd/system/nspawn-ui.service"
        return 1
    fi
}

# Main validation process
main() {
    print_status "Starting nspawn-ui build validation..."
    
    # Track results
    validation_results=()
    
    # Validate each component
    if validate_python_deps; then
        validation_results+=("Python dependencies: OK")
    else
        validation_results+=("Python dependencies: FAIL")
    fi
    
    if validate_systemd_nspawn; then
        validation_results+=("Systemd-nspawn tools: OK")
    else
        validation_results+=("Systemd-nspawn tools: FAIL")
    fi
    
    if validate_debootstrap; then
        validation_results+=("Debootstrap: OK")
    else
        validation_results+=("Debootstrap: FAIL")
    fi
    
    if validate_iptables; then
        validation_results+=("Iptables: OK")
    else
        validation_results+=("Iptables: FAIL")
    fi
    
    validate_networking
    validation_results+=("Networking: CHECKED")
    
    if validate_service; then
        validation_results+=("Service: OK")
    else
        validation_results+=("Service: FAIL")
    fi
    
    validate_api
    validation_results+=("API connectivity: CHECKED")
    
    validate_structure
    validation_results+=("Directory structure: CHECKED")
    
    if validate_systemd_unit; then
        validation_results+=("Systemd unit: OK")
    else
        validation_results+=("Systemd unit: FAIL")
    fi
    
    # Report results
    print_status "Validation results:"
    for result in "${validation_results[@]}"; do
        echo "  - $result"
    done
    
    # Count failures
    fail_count=0
    for result in "${validation_results[@]}"; do
        if [[ "$result" == *"FAIL"* ]]; then
            ((fail_count++))
        fi
    done
    
    if [ $fail_count -eq 0 ]; then
        print_status "Build validation completed successfully! All components are properly configured."
        return 0
    else
        print_warning "Build validation completed with $fail_count failure(s). Please check the warnings above."
        return 1
    fi
}

# Run main function
main "$@"