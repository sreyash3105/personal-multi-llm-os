#!/usr/bin/env python3
"""
CI check to ensure requirements.txt is properly encoded as UTF-8
"""
import os
import sys

def check_requirements_encoding():
    """Check that requirements.txt is UTF-8 encoded and parseable"""
    req_file = "backend/requirements.txt"
    
    if not os.path.exists(req_file):
        print(f"ERROR: {req_file} not found")
        return False
    
    # Check file encoding
    with open(req_file, 'rb') as f:
        raw_bytes = f.read()
    
    # Try to decode as UTF-8
    try:
        content = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        print(f"ERROR: {req_file} is not valid UTF-8 encoded")
        return False
    
    # Check for BOM (Byte Order Mark) which indicates UTF-16/32
    if raw_bytes.startswith(b'\xff\xfe') or raw_bytes.startswith(b'\xfe\xff'):
        print(f"ERROR: {req_file} contains UTF-16 BOM")
        return False
    
    # Try to parse requirements
    try:
        import pkg_resources
        reqs = list(pkg_resources.parse_requirements(content))
        print(f"SUCCESS: Parsed {len(reqs)} requirements from UTF-8 encoded file")
    except Exception as e:
        print(f"ERROR: Failed to parse requirements: {e}")
        return False
    
    return True

if __name__ == "__main__":
    if check_requirements_encoding():
        sys.exit(0)
    else:
        sys.exit(1)