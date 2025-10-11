#!/bin/bash

# Debug script to check port usage and clean up before deployment

echo "🔍 DEBUGGING PORT CONFLICTS"
echo "=========================="

# Check what's using port 8000
echo "🔍 Checking port 8000:"
sudo netstat -tulpn | grep :8000 || echo "   ✅ Port 8000 is free"

# Check what's using port 8080  
echo "🔍 Checking port 8080:"
sudo netstat -tulpn | grep :8080 || echo "   ✅ Port 8080 is free"

# Check what's using port 8081
echo "🔍 Checking port 8081:"
sudo netstat -tulpn | grep :8081 || echo "   ✅ Port 8081 is free"

# Check what's using port 6379 (Redis)
echo "🔍 Checking port 6379 (Redis):"
sudo netstat -tulpn | grep :6379 || echo "   ✅ Port 6379 is free"

echo ""
echo "🐳 DOCKER STATUS:"
echo "=================="

# Check running containers
echo "🔍 Running containers:"
docker ps

echo ""
echo "🔍 All containers (including stopped):"
docker ps -a

echo ""
echo "🔍 Docker networks:"
docker network ls | grep backfin || echo "   ✅ No backfin networks found"

echo ""
echo "🧹 CLEANUP OPTIONS:"
echo "==================="

# Check for conflicting containers
BACKFIN_CONTAINERS=$(docker ps -a --filter name=backfin --format "{{.Names}}" | wc -l)
if [[ $BACKFIN_CONTAINERS -gt 0 ]]; then
    echo "⚠️  Found $BACKFIN_CONTAINERS backfin containers:"
    docker ps -a --filter name=backfin --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "🧹 To clean up old containers:"
    echo "   docker stop \$(docker ps -a --filter name=backfin --format '{{.Names}}')"
    echo "   docker rm \$(docker ps -a --filter name=backfin --format '{{.Names}}')"
else
    echo "✅ No backfin containers found"
fi

# Check for conflicting networks
BACKFIN_NETWORKS=$(docker network ls --filter name=backfin --format "{{.Name}}" | wc -l)
if [[ $BACKFIN_NETWORKS -gt 0 ]]; then
    echo "⚠️  Found $BACKFIN_NETWORKS backfin networks:"
    docker network ls --filter name=backfin
    echo ""
    echo "🧹 To clean up networks:"
    echo "   docker network rm \$(docker network ls --filter name=backfin --format '{{.Name}}')"
else
    echo "✅ No backfin networks found"
fi

echo ""
echo "🚀 RECOMMENDED STEPS:"
echo "===================="
echo "1. Clean up any old containers:"
echo "   ./debug_ports.sh cleanup"
echo ""
echo "2. Try deployment again:"
echo "   ./deploy_containers.sh"

# If cleanup argument is provided
if [[ "$1" == "cleanup" ]]; then
    echo ""
    echo "🧹 PERFORMING CLEANUP..."
    echo "========================"
    
    # Stop and remove backfin containers
    echo "🛑 Stopping backfin containers..."
    docker stop $(docker ps -a --filter name=backfin --format '{{.Names}}') 2>/dev/null || echo "   No containers to stop"
    
    echo "🗑️  Removing backfin containers..."
    docker rm $(docker ps -a --filter name=backfin --format '{{.Names}}') 2>/dev/null || echo "   No containers to remove"
    
    # Remove backfin networks
    echo "🗑️  Removing backfin networks..."
    docker network rm $(docker network ls --filter name=backfin --format '{{.Name}}') 2>/dev/null || echo "   No networks to remove"
    
    # Remove any orphaned volumes
    echo "🗑️  Cleaning up volumes..."
    docker volume prune -f
    
    echo "✅ Cleanup complete!"
    echo ""
    echo "🚀 Now try deploying again:"
    echo "   ./deploy_containers.sh"
fi