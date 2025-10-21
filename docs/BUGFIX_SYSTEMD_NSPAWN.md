# Bug Fix: systemd-nspawn Execution Errors

## Problem Statement

The container service was experiencing failures when executing scripts inside containers using `systemd-nspawn`, with the error:

```
Error: Command '['systemd-nspawn', '-D', '/var/lib/machines/vps', '/tmp/set_password.sh']' returned non-zero exit status 1.
```

## Root Causes Identified

### 1. Missing systemd-nspawn Flags (Primary Issue)

The original code executed systemd-nspawn without proper flags for non-interactive execution:

```python
# Before (INCORRECT)
subprocess.run(
    ["systemd-nspawn", "-D", str(container_dir), "/tmp/set_password.sh"],
    capture_output=True,
    check=True
)
```

**Issues:**
- Without `--quiet`, systemd-nspawn produces interactive prompts
- Without `--register=no`, it tries to register with systemd-machined, which fails in non-interactive contexts
- The `check=True` raises exception without capturing useful error information

### 2. Missing /tmp Directory

Fresh debootstrap installations may not have a `/tmp` directory created yet, causing script creation to fail:

```python
# Before (INCORRECT)
script_path = container_dir / "tmp" / "set_password.sh"
script_path.parent.mkdir(exist_ok=True)  # Creates host path, not guaranteed in container
```

### 3. Poor Error Handling

The original code used `check=True` which raises `CalledProcessError` without capturing stderr:

```python
# Before (INCORRECT)
subprocess.run(..., check=True)  # Raises exception with minimal info
```

### 4. Missing Script Error Handling

Scripts didn't exit immediately on errors, potentially masking failures:

```bash
#!/bin/bash
echo 'root:password' | chpasswd  # No error checking
```

### 5. Resolv.conf Symlink Issue

Many modern distributions use systemd-resolved, which creates `/etc/resolv.conf` as a symlink. Writing to a symlink can fail:

```python
# Before (INCORRECT)
resolv_conf = container_dir / "etc" / "resolv.conf"
resolv_conf.write_text(...)  # Fails if resolv_conf is a symlink
```

### 6. Duplicate SSH Configuration

Repeated calls could append duplicate SSH configuration lines to `sshd_config`.

## Solutions Implemented

### 1. Fixed systemd-nspawn Execution

**Added proper flags:**

```python
# After (CORRECT)
result = subprocess.run(
    ["systemd-nspawn", "--quiet", "--register=no", "-D", str(container_dir), "/tmp/set_password.sh"],
    capture_output=True,
    text=True,
    timeout=30
)

if result.returncode != 0:
    logger.error(f"Failed to set root password. Return code: {result.returncode}")
    logger.error(f"Stdout: {result.stdout}")
    logger.error(f"Stderr: {result.stderr}")
    raise Exception(f"Failed to set root password: {result.stderr}")
```

**Flags explanation:**
- `--quiet`: Suppresses interactive prompts and unnecessary output
- `--register=no`: Skips registration with systemd-machined (not needed for script execution)
- `text=True`: Returns output as strings for easier logging
- `timeout=30`: Prevents hanging processes

### 2. Ensured /tmp Directory Exists

**Explicit directory creation with proper permissions:**

```python
# After (CORRECT)
tmp_dir = container_dir / "tmp"
tmp_dir.mkdir(exist_ok=True, mode=0o1777)  # Sticky bit for /tmp
```

The mode `0o1777` sets the sticky bit, which is standard for `/tmp` directories.

### 3. Enhanced Error Handling

**Implemented try-finally with detailed logging:**

```python
# After (CORRECT)
try:
    result = subprocess.run(...)
    
    if result.returncode != 0:
        logger.error(f"Failed. Return code: {result.returncode}")
        logger.error(f"Stdout: {result.stdout}")
        logger.error(f"Stderr: {result.stderr}")
        raise Exception(...)
        
finally:
    # Always cleanup
    if script_path.exists():
        script_path.unlink()
```

### 4. Added Script Error Handling

**All scripts now include proper error handling:**

```bash
#!/bin/bash
set -e  # Exit on any error
echo 'root:password' | chpasswd
exit 0  # Explicit success
```

**Benefits:**
- `set -e`: Bash exits immediately if any command fails
- `exit 0`: Explicit success signal to systemd-nspawn

### 5. Fixed Resolv.conf Handling

**Check and remove symlinks before writing:**

```python
# After (CORRECT)
resolv_conf = container_dir / "etc" / "resolv.conf"
# Remove if it's a symlink to avoid issues
if resolv_conf.is_symlink():
    resolv_conf.unlink()
resolv_conf.write_text("nameserver 8.8.8.8\nnameserver 1.1.1.1\n")
```

### 6. Prevented Duplicate SSH Configuration

**Check before appending:**

```python
# After (CORRECT)
if sshd_config.exists():
    config_text = sshd_config.read_text()
    # Only add if not already present
    if "PermitRootLogin yes" not in config_text:
        config_text += "\nPermitRootLogin yes\n"
    if "PasswordAuthentication yes" not in config_text:
        config_text += "PasswordAuthentication yes\n"
    sshd_config.write_text(config_text)
```

## Methods Fixed

The following methods were updated in `backend/services/container_service.py`:

1. **`_set_root_password()`** (lines 216-250)
   - Added `--quiet` and `--register=no` flags
   - Ensured /tmp directory exists
   - Enhanced error logging
   - Added try-finally for cleanup

2. **`_install_ssh()`** (lines 292-352)
   - Same systemd-nspawn fixes
   - Added script error handling
   - Prevented duplicate SSH config entries

3. **`_configure_wireguard()`** (lines 354-401)
   - Same systemd-nspawn fixes
   - Better error handling

4. **`_configure_network()`** (lines 252-293)
   - Fixed resolv.conf symlink handling

## Testing

All fixes have been validated with:

1. **Import validation**: Module loads without errors
2. **Syntax validation**: Python compilation successful
3. **Logic validation**: Script generation works correctly
4. **Command structure**: systemd-nspawn flags are correct

**Note:** Full end-to-end testing requires root privileges and a proper systemd environment, which are not available in the CI/CD sandbox.

## Expected Behavior After Fix

1. **Container creation succeeds** without the "exit status 1" error
2. **Root password is set correctly** in the container
3. **SSH server installs successfully** (if enabled)
4. **WireGuard configures properly** (if enabled)
5. **Network configuration works** including DNS resolution
6. **Error messages are descriptive** when failures occur

## Migration Guide

No migration is needed. The changes are backward compatible and only fix execution bugs. Users should simply pull the latest code and restart the service:

```bash
cd /opt/zenithstack
git pull
sudo systemctl restart zenithstack
```

## Additional Notes

- The fixes maintain the same API and behavior
- All changes follow the existing code style
- Error handling is more robust and informative
- The changes are minimal and surgical, affecting only the buggy areas
- No new dependencies were added

## References

- systemd-nspawn documentation: `man systemd-nspawn`
- Bash error handling: `help set` (see `-e` option)
- File permissions: `man chmod` (see sticky bit for /tmp)
