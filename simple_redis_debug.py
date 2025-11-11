#!/usr/bin/env python3
"""
Simple Redis Debug Script - No application imports
"""

import os
import socket
import subprocess

def print_header(title):
    print(f"\n🔍 {title}")
    print("-" * 50)

def check_environment():
    print_header("ENVIRONMENT VARIABLES")
    redis_vars = ['REDIS_HOST', 'REDIS_PORT', 'REDIS_URL', 'REDIS_DB']
    for var in redis_vars:
        value = os.getenv(var, 'NOT_SET')
        print(f"{var}: {value}")

def check_network():
    print_header("NETWORK CONNECTIVITY")
    endpoints = [
        ('localhost', 6379),
        ('redis', 6379), 
        ('backfin-redis', 6379)
    ]
    
    for host, port in endpoints:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print(f"✅ {host}:{port} - Connected")
            else:
                print(f"❌ {host}:{port} - Failed (error {result})")
        except Exception as e:
            print(f"❌ {host}:{port} - Exception: {e}")

def check_dns():
    print_header("DNS RESOLUTION")
    hostnames = ['redis', 'backfin-redis', 'localhost']
    
    for hostname in hostnames:
        try:
            ip = socket.gethostbyname(hostname)
            print(f"✅ {hostname} -> {ip}")
        except Exception as e:
            print(f"❌ {hostname} -> Failed: {e}")

def check_hosts_file():
    print_header("CONTAINER /etc/hosts")
    try:
        with open('/etc/hosts', 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                if 'redis' in line.lower() or 'backfin' in line.lower():
                    print(line)
    except Exception as e:
        print(f"Error reading /etc/hosts: {e}")

def test_direct_redis():
    print_header("DIRECT REDIS TEST")
    try:
        import redis
        
        # Test with environment variables
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', 6379))
        
        print(f"Testing Redis connection to {host}:{port}")
        
        client = redis.Redis(
            host=host,
            port=port,
            socket_connect_timeout=3,
            decode_responses=True
        )
        
        result = client.ping()
        print(f"✅ Redis PING successful: {result}")
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")

def main():
    print("🐳 SIMPLE REDIS DEBUG (No App Imports)")
    check_environment()
    check_dns() 
    check_hosts_file()
    check_network()
    test_direct_redis()

if __name__ == "__main__":
    main()