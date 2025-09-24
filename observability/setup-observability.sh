#!/bin/bash

# OpenWebUI Analytics Observability Setup Script
# Sets up the complete Grafana + Prometheus + Loki + OpenTelemetry stack

set -e

echo "🚀 Setting up OpenWebUI Analytics Observability Stack"

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p grafana-provisioning/datasources
mkdir -p grafana-provisioning/dashboards
mkdir -p grafana-dashboards

# Set up environment variables for OpenWebUI
echo "🔧 Setting up environment variables..."
cat > .env.observability << EOF
# OpenTelemetry Configuration for OpenWebUI
ENABLE_OTEL=true
ENABLE_OTEL_TRACES=true
ENABLE_OTEL_METRICS=true
ENABLE_OTEL_LOGS=true

# OTLP Endpoints (pointing to our collector)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_METRICS_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_LOGS_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# Service identification
OTEL_SERVICE_NAME=open-webui
OTEL_RESOURCE_ATTRIBUTES=service.version=1.0.0,environment=production

# Export format (use gRPC for better performance)
OTEL_OTLP_SPAN_EXPORTER=grpc
OTEL_METRICS_OTLP_SPAN_EXPORTER=grpc
OTEL_LOGS_OTLP_SPAN_EXPORTER=http
EOF

echo "📄 Environment configuration created at .env.observability"
echo "   Add this to your OpenWebUI environment or source it before starting OpenWebUI"

# Start the observability stack
echo "🐳 Starting observability stack..."
docker-compose -f docker-compose.observability.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Check service health
echo "🔍 Checking service health..."

# Check OpenTelemetry Collector
if curl -f http://localhost:13133 > /dev/null 2>&1; then
    echo "✅ OpenTelemetry Collector is healthy"
else
    echo "⚠️  OpenTelemetry Collector health check failed"
fi

# Check Prometheus
if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus is healthy"
else
    echo "⚠️  Prometheus health check failed"
fi

# Check Loki
if curl -f http://localhost:3100/ready > /dev/null 2>&1; then
    echo "✅ Loki is healthy"
else
    echo "⚠️  Loki health check failed"
fi

# Check Grafana
if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana is healthy"
else
    echo "⚠️  Grafana health check failed"
fi

echo ""
echo "🎉 Observability stack is ready!"
echo ""
echo "📊 Access your dashboards:"
echo "   • Grafana:    http://localhost:3000 (admin/admin)"
echo "   • Prometheus: http://localhost:9090"
echo "   • Jaeger:     http://localhost:16686"
echo ""
echo "🔧 OTLP Endpoints for OpenWebUI:"
echo "   • Traces/Metrics: grpc://localhost:4317"
echo "   • Logs:          http://localhost:4318"
echo ""
echo "📝 Next steps:"
echo "   1. Source the environment file:"
echo "      source .env.observability"
echo "   2. Start OpenWebUI with telemetry enabled"
echo "   3. Use the analytics API to generate metrics"
echo "   4. View dashboards in Grafana"
echo ""
echo "🔧 Configuration files created:"
echo "   • OpenTelemetry Collector: otel-collector-config.yml"
echo "   • Prometheus: prometheus.yml"
echo "   • Grafana: grafana-provisioning/"
echo "   • Docker Compose: docker-compose.observability.yml"