# Kubernetes Deployment Guide for Backfin

This guide explains how to deploy the Backfin Redis Queue Architecture to Kubernetes.

## 🚀 Quick Start

### Prerequisites

1. **Docker** - For building container images
2. **kubectl** - Kubernetes command-line tool
3. **Kubernetes cluster** - Either local (kind/minikube) or cloud-based

### Local Testing

```bash
# Quick local setup with kind/minikube
./scripts/test-k8s-local.sh setup

# Access services via port forwarding
./scripts/test-k8s-local.sh forward
```

### Production Deployment

```bash
# Deploy to production cluster
./scripts/deploy-k8s.sh

# With specific version and registry
./scripts/deploy-k8s.sh v1.0.0 production-context deploy
```

## 📁 Kubernetes Resources

### Core Infrastructure

- **Namespace**: `backfin` - Isolated environment for all resources
- **Redis**: Persistent storage with 10GB volume and optimized configuration
- **ConfigMaps**: Environment variables and Redis configuration
- **Secrets**: Encrypted storage for API keys and credentials

### Application Components

#### Scrapers
- **BSE Scraper**: Monitors BSE announcements (CronJob every 15 minutes)
- **NSE Scraper**: Monitors NSE announcements (CronJob every 10 minutes)

#### Workers
- **AI Worker**: Processes announcements with Gemini AI (2 replicas, auto-scaling)
- **Supabase Worker**: Uploads processed data to Supabase (2 replicas)
- **Investor Worker**: Analyzes investor data and notifications (1 replica)

#### Services
- **API Server**: REST API for external access (2 replicas, LoadBalancer)
- **Queue Manager**: Web interface for queue monitoring (1 replica)

### Scaling & Reliability

- **Horizontal Pod Autoscaler**: Auto-scales workers based on CPU/memory
- **Pod Disruption Budgets**: Ensures minimum availability during updates
- **Resource Limits**: Prevents resource starvation
- **Health Checks**: Liveness and readiness probes for all services

## 🔧 Configuration

### Environment Variables

Set these in `k8s/secrets.yaml` (base64 encoded):

```yaml
SUPABASE_URL: <base64-encoded-url>
SUPABASE_KEY: <base64-encoded-key>
GEMINI_API_KEY: <base64-encoded-key>
REDIS_PASSWORD: <base64-encoded-password>
```

### Service Configuration

Modify `k8s/namespace.yaml` ConfigMap:

```yaml
data:
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
  LOG_LEVEL: "INFO"
  WORKER_CONCURRENCY: "4"
  JOB_TIMEOUT: "300"
```

## 🐳 Docker Images

### Base Image

All services build from `Dockerfile.base`:
- Python 3.11 slim
- Common dependencies
- Non-root user
- Health check support

### Service Images

Each service has its own Dockerfile in `docker/`:
- `Dockerfile.bse-scraper` - BSE scraping service
- `Dockerfile.nse-scraper` - NSE scraping service
- `Dockerfile.ai-worker` - AI processing worker
- `Dockerfile.supabase-worker` - Database upload worker
- `Dockerfile.investor-worker` - Investor analysis worker
- `Dockerfile.api-server` - FastAPI REST server
- `Dockerfile.queue-manager` - Queue monitoring service

## 📊 Monitoring & Observability

### Health Checks

Each service exposes standard endpoints:
- `/health` - Liveness probe (is the service running?)
- `/ready` - Readiness probe (is the service ready to serve traffic?)
- `/metrics` - Basic metrics for monitoring

### Logs

View logs for any service:

```bash
# View API server logs
kubectl logs -f deployment/api-server -n backfin

# View worker logs
kubectl logs -f deployment/ai-worker -n backfin

# View scraper logs
kubectl logs -f job/bse-scraper-job-xxx -n backfin
```

### Queue Monitoring

Access queue manager at `http://localhost:8080` (with port forwarding):

```bash
kubectl port-forward service/queue-manager-service 8080:8080 -n backfin
```

## 🔄 Scaling

### Manual Scaling

```bash
# Scale AI workers
kubectl scale deployment ai-worker --replicas=5 -n backfin

# Scale API servers
kubectl scale deployment api-server --replicas=3 -n backfin
```

### Auto Scaling

Workers automatically scale based on resource usage:
- **AI Worker**: 2-10 replicas (70% CPU threshold)
- **API Server**: 2-5 replicas (70% CPU threshold)

## 🔐 Security

### Network Policies

- Services can only communicate within the `backfin` namespace
- External access only through LoadBalancer services
- Redis is internal-only

### RBAC

Create service account with minimal permissions:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: backfin-worker
  namespace: backfin
```

### Secrets Management

- All secrets are base64 encoded in Kubernetes
- Use external secret management (Vault, AWS Secrets Manager) for production
- Rotate secrets regularly

## 🚀 Deployment Strategies

### Rolling Updates

Default deployment strategy for zero-downtime updates:

```bash
# Update image version
kubectl set image deployment/api-server api-server=backfin/api-server:v1.1.0 -n backfin

# Check rollout status
kubectl rollout status deployment/api-server -n backfin

# Rollback if needed
kubectl rollout undo deployment/api-server -n backfin
```

### Blue-Green Deployment

For critical updates, deploy to separate namespace:

```bash
# Deploy to staging namespace
kubectl apply -f k8s/ --namespace=backfin-staging

# Test thoroughly
# Switch traffic
# Cleanup old deployment
```

## 🔧 Troubleshooting

### Common Issues

1. **Image Pull Errors**
   ```bash
   # Check if images exist
   docker images | grep backfin
   
   # Load images into kind cluster
   kind load docker-image backfin/api-server:latest --name backfin
   ```

2. **Redis Connection Issues**
   ```bash
   # Check Redis pod status
   kubectl get pods -l app=redis -n backfin
   
   # Test Redis connectivity
   kubectl exec -it deployment/redis -n backfin -- redis-cli ping
   ```

3. **Worker Not Processing Jobs**
   ```bash
   # Check worker logs
   kubectl logs -f deployment/ai-worker -n backfin
   
   # Check queue status
   kubectl port-forward service/queue-manager-service 8080:8080 -n backfin
   ```

### Debug Commands

```bash
# Get all resources
kubectl get all -n backfin

# Describe problematic pod
kubectl describe pod <pod-name> -n backfin

# Get events
kubectl get events -n backfin --sort-by='.lastTimestamp'

# Shell into container
kubectl exec -it deployment/api-server -n backfin -- /bin/bash
```

## 📈 Performance Tuning

### Resource Requests/Limits

Adjust based on your workload:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

### Redis Optimization

Modify Redis configuration in `k8s/redis.yaml`:

```yaml
data:
  redis.conf: |
    maxmemory 4gb                    # Increase for larger datasets
    maxmemory-policy allkeys-lru     # Memory eviction policy
    save 900 1                       # Persistence settings
    appendonly yes                   # Enable AOF
```

### Queue Optimization

Tune worker concurrency in ConfigMap:

```yaml
data:
  WORKER_CONCURRENCY: "8"          # Increase for more parallel processing
  QUEUE_BATCH_SIZE: "20"           # Process more jobs per batch
  JOB_TIMEOUT: "600"               # Increase timeout for complex jobs
```

## 🌐 Production Considerations

### High Availability

1. **Multi-zone deployment**: Spread pods across availability zones
2. **Backup strategy**: Regular Redis snapshots and data backups
3. **Monitoring**: Prometheus + Grafana for comprehensive monitoring
4. **Alerting**: PagerDuty/Slack integration for critical issues

### Security Hardening

1. **Network segmentation**: Use Istio service mesh
2. **Pod security**: Enable Pod Security Standards
3. **Image scanning**: Scan for vulnerabilities before deployment
4. **Secret rotation**: Automated secret rotation

### Cost Optimization

1. **Right-sizing**: Monitor and adjust resource requests
2. **Spot instances**: Use for non-critical workers
3. **Cluster autoscaling**: Scale nodes based on demand
4. **Resource quotas**: Prevent resource abuse

## 📋 Scripts Reference

### `scripts/deploy-k8s.sh`

Main deployment script with commands:
- `deploy` - Full deployment
- `build` - Build images only
- `push` - Push to registry
- `apply` - Apply manifests only
- `status` - Check deployment status
- `cleanup` - Delete all resources

### `scripts/test-k8s-local.sh`

Local testing script with commands:
- `setup` - Complete local setup
- `deploy` - Deploy to local cluster
- `test` - Run deployment tests
- `forward` - Port forward services
- `logs` - View service logs
- `cleanup` - Delete local cluster

## 🎯 Next Steps

1. **Set up monitoring**: Deploy Prometheus and Grafana
2. **Configure CI/CD**: Automate deployments with GitHub Actions
3. **Add ingress**: Expose services with proper DNS
4. **Implement service mesh**: Add Istio for advanced traffic management
5. **Database migration**: Move to managed Redis (AWS ElastiCache, etc.)

## 🤝 Contributing

When adding new services:

1. Create Dockerfile in `docker/`
2. Add Kubernetes manifests in `k8s/`
3. Update deployment scripts
4. Add health check endpoints
5. Document configuration options