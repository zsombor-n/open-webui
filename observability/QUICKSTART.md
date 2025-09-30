# 🚀 OpenWebUI Analytics Observability Quick Start

## What's Running

Your observability stack is now ready with:

- **✅ Grafana** (cf-grafana): http://localhost:3000 (admin/admin)
- **✅ Prometheus** (cf-prometheus): http://localhost:9090
- **✅ OpenTelemetry Collector** (cf-otel-collector): http://localhost:13133
- **✅ Jaeger** (cf-jaeger): http://localhost:16686
- **✅ Loki** (cf-loki): http://localhost:3100

All containers use `cf-` prefixes to avoid conflicts with your existing containers.

## 📋 Next Steps

### 1. Enable OpenWebUI Telemetry

Add these environment variables when starting OpenWebUI:

```bash
# Enable OpenTelemetry in OpenWebUI
export ENABLE_OTEL=true
export ENABLE_OTEL_TRACES=true
export ENABLE_OTEL_METRICS=true
export ENABLE_OTEL_LOGS=true

# Point to our collector
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=open-webui

# Start OpenWebUI
uv run open-webui serve
```

### 2. Generate Analytics Traffic

Use the analytics endpoints to generate metrics:

```bash
# Get analytics summary (creates metrics)
curl http://localhost:8080/api/v1/analytics/summary

# Get user activity data
curl http://localhost:8080/api/v1/analytics/users/activity

# Get model usage stats
curl http://localhost:8080/api/v1/analytics/models/usage
```

### 3. View Metrics in Grafana

1. Open http://localhost:3000 (admin/admin)
2. Go to **Dashboards** → **OpenWebUI** → **OpenWebUI Analytics Dashboard**
3. You should see:
   - Analytics API request rates
   - Response times
   - Cache hit rates (if analytics caching is enabled)
   - Error rates
   - Active/total users

### 4. Check Prometheus Targets

Visit http://localhost:9090/targets to verify the OpenTelemetry Collector target is healthy.

## 🔧 Troubleshooting

### Check Service Health
```bash
# OTEL Collector
curl http://localhost:13133

# Prometheus
curl http://localhost:9090/-/healthy

# Grafana
curl http://localhost:3000/api/health
```

### View Container Logs
```bash
cd observability

# All services
docker-compose -f docker-compose.observability.yml logs

# Specific service
docker-compose -f docker-compose.observability.yml logs cf-otel-collector
```

### Verify Telemetry Flow
```bash
# Check if metrics are being received by Prometheus
curl "http://localhost:9090/api/v1/query?query=openwebui_analytics_requests_total"

# Check OTEL Collector logs for incoming telemetry
docker-compose -f docker-compose.observability.yml logs cf-otel-collector | grep "otlp"
```

## ⚡ Quick Test Script

```bash
#!/bin/bash
echo "🧪 Testing observability stack..."

# Start OpenWebUI with telemetry
ENABLE_OTEL=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
uv run open-webui serve &

# Wait for startup
sleep 10

# Generate test traffic
curl -s http://localhost:8080/api/v1/analytics/summary > /dev/null
curl -s http://localhost:8080/api/v1/analytics/users/activity > /dev/null

# Check metrics appeared in Prometheus
sleep 5
METRICS=$(curl -s "http://localhost:9090/api/v1/query?query=openwebui_analytics_requests_total" | grep -o '"value"')

if [ -n "$METRICS" ]; then
    echo "✅ Observability pipeline working! Metrics are flowing."
    echo "🎯 Visit http://localhost:3000 to see your dashboards"
else
    echo "⚠️ No metrics found yet. Check the troubleshooting guide."
fi
```

## 🎯 What You'll Monitor

- **Request Volume**: How many analytics API calls per second
- **Response Times**: How fast your analytics queries respond
- **Cache Performance**: Hit rates if caching is enabled
- **Error Rates**: Failed requests and database errors
- **User Activity**: Active users and registration trends
- **Database Performance**: Query execution times

Your **enterprise-grade observability** is ready! 🎉