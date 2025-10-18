#!/usr/bin/env python3
"""
Redis Debug Script - Run inside Docker containers to diagnose connection issues
"""

import os
import sys
import time
import socket
import subprocess
import redis

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"🔍 {title}")
    print("="*60)

def check_environment():
    """Check all Redis-related environment variables"""
    print_header("ENVIRONMENT VARIABLES")
    
    redis_vars = [
        'REDIS_HOST', 'REDIS_PORT', 'REDIS_URL', 'REDIS_DB', 
        'REDIS_PASSWORD', 'REDIS_MAX_CONNECTIONS', 'REDIS_CONNECT_TIMEOUT'
    ]
    
    for var in redis_vars:
        value = os.getenv(var, 'NOT_SET')
        print(f"  {var:<25}: {value}")
    
    print(f"\n  Current working dir     : {os.getcwd()}")
    print(f"  Python path             : {sys.path}")

def check_network_connectivity():
    """Test network connectivity to various Redis endpoints"""
    print_header("NETWORK CONNECTIVITY TESTS")
    
    endpoints = [
        ('localhost', 6379),
        ('redis', 6379),
        ('backfin-redis', 6379),
        ('127.0.0.1', 6379)
    ]
    
    for host, port in endpoints:
        try:
            # Test socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print(f"  ✅ {host}:{port} - Socket connection successful")
            else:
                print(f"  ❌ {host}:{port} - Socket connection failed (error {result})")
                
        except Exception as e:
            print(f"  ❌ {host}:{port} - Socket test failed: {e}")

def check_dns_resolution():
    """Test DNS resolution for Redis hostnames"""
    print_header("DNS RESOLUTION TESTS")
    
    hostnames = ['redis', 'backfin-redis', 'localhost']
    
    for hostname in hostnames:
        try:
            import socket
            ip = socket.gethostbyname(hostname)
            print(f"  ✅ {hostname:<15} -> {ip}")
        except Exception as e:
            print(f"  ❌ {hostname:<15} -> Failed: {e}")

def check_docker_network():
    """Check Docker network information"""
    print_header("DOCKER NETWORK INFO")
    
    try:
        # Get container's network info
        result = subprocess.run(['cat', '/etc/hosts'], capture_output=True, text=True)
        if result.returncode == 0:
            print("  Container /etc/hosts:")
            for line in result.stdout.strip().split('\n'):
                if 'redis' in line.lower() or 'backfin' in line.lower():
                    print(f"    {line}")
        
        # Check network interfaces
        print("\n  Network interfaces:")
        result = subprocess.run(['ip', 'addr'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'inet ' in line and ('172.' in line or '192.' in line or '10.' in line):
                    print(f"    {line.strip()}")
                    
    except Exception as e:
        print(f"  ❌ Error getting network info: {e}")

def test_redis_connections():
    """Test Redis connections with different configurations"""
    print_header("REDIS CONNECTION TESTS")
    
    # Test configurations
    configs = [
        {
            'name': 'Environment Variables',
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', 6379)),
            'url': os.getenv('REDIS_URL')
        },
        {
            'name': 'Direct redis:6379',
            'host': 'redis',
            'port': 6379,
            'url': None
        },
        {
            'name': 'Direct localhost:6379',
            'host': 'localhost',
            'port': 6379,
            'url': None
        },
        {
            'name': 'Container name',
            'host': 'backfin-redis',
            'port': 6379,
            'url': None
        }
    ]
    
    for config in configs:
        print(f"\n  🧪 Testing: {config['name']}")
        try:
            if config['url']:
                client = redis.from_url(config['url'], socket_connect_timeout=3, decode_responses=True)
                print(f"     URL: {config['url']}")
            else:
                client = redis.Redis(
                    host=config['host'],
                    port=config['port'],
                    socket_connect_timeout=3,
                    decode_responses=True
                )
                print(f"     Host: {config['host']}:{config['port']}")
            
            # Test ping
            result = client.ping()
            print(f"     ✅ PING successful: {result}")
            
            # Test basic operations
            client.set('test_key', 'test_value', ex=10)
            value = client.get('test_key')
            client.delete('test_key')
            print(f"     ✅ Basic operations work: {value}")
            
            # Get Redis info
            info = client.info('server')
            print(f"     ✅ Redis version: {info.get('redis_version', 'unknown')}")
            
        except Exception as e:
            print(f"     ❌ Failed: {e}")

def test_redis_config_class():
    """Test the RedisConfig class from the application"""
    print_header("APPLICATION REDIS CONFIG TEST")
    
    try:
        # Add app directory to Python path
        sys.path.insert(0, '/app')
        
        from src.queue.redis_client import RedisConfig, get_redis_client
        
        print("  🧪 Testing RedisConfig class:")
        config = RedisConfig()
        print(f"     Host: {config.redis_host}")
        print(f"     Port: {config.redis_port}")
        print(f"     URL: {config.redis_url}")
        print(f"     DB: {config.redis_db}")
        
        print("\n  🧪 Testing get_redis_client function:")
        client = get_redis_client()
        result = client.ping()
        print(f"     ✅ Application Redis client works: {result}")
        
    except Exception as e:
        print(f"     ❌ Application Redis config failed: {e}")
        import traceback
        print(f"     Traceback: {traceback.format_exc()}")

def check_redis_process():
    """Check if Redis processes are visible"""
    print_header("REDIS PROCESS CHECK")
    
    try:
        # Check if we can see Redis processes
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if result.returncode == 0:
            redis_processes = [line for line in result.stdout.split('\n') if 'redis' in line.lower()]
            if redis_processes:
                print("  Redis processes found:")
                for proc in redis_processes:
                    print(f"    {proc}")
            else:
                print("  No Redis processes visible from this container")
    except Exception as e:
        print(f"  ❌ Error checking processes: {e}")

def main():
    """Run all diagnostic tests"""
    print("🐳 REDIS CONNECTION DIAGNOSTIC TOOL")
    print("Running inside Docker container...")
    
    try:
        check_environment()
        check_dns_resolution()
        check_network_connectivity()
        check_docker_network()
        check_redis_process()
        test_redis_connections()
        test_redis_config_class()
        
        print_header("DIAGNOSTIC COMPLETE")
        print("📋 Summary:")
        print("   • Check environment variables for correct Redis host")
        print("   • Verify network connectivity to Redis container")
        print("   • Ensure Docker network configuration is correct")
        print("   • Review any failed connection tests above")
        
    except Exception as e:
        print(f"\n❌ Diagnostic script error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()