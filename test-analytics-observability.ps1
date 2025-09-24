# PowerShell script to test OpenWebUI Analytics Observability
# This script verifies the telemetry pipeline is working

Write-Host "🚀 Testing OpenWebUI Analytics Observability Pipeline" -ForegroundColor Green

# Check if all observability services are running
Write-Host "`n🔍 Checking observability services..." -ForegroundColor Yellow

$services = @(
    @{Name="OTEL Collector"; Url="http://localhost:13133"; Port=13133},
    @{Name="Prometheus"; Url="http://localhost:9090/-/healthy"; Port=9090},
    @{Name="Grafana"; Url="http://localhost:3000/api/health"; Port=3000},
    @{Name="Jaeger"; Url="http://localhost:16686"; Port=16686},
    @{Name="Alertmanager"; Url="http://localhost:9093/-/healthy"; Port=9093}
)

$healthyServices = 0
foreach ($service in $services) {
    try {
        $response = Invoke-WebRequest -Uri $service.Url -Method GET -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ $($service.Name): http://localhost:$($service.Port)" -ForegroundColor Green
            $healthyServices++
        }
    }
    catch {
        Write-Host "❌ $($service.Name): Not responding" -ForegroundColor Red
    }
}

Write-Host "`n📊 Service Status: $healthyServices/5 services healthy" -ForegroundColor Cyan

if ($healthyServices -ge 4) {
    Write-Host "`n🎯 Core observability stack is ready!" -ForegroundColor Green
    Write-Host "📝 Next steps:" -ForegroundColor Yellow
    Write-Host "1. Source the environment file:"
    Write-Host "   Get-Content .env.analytics | ForEach-Object { [System.Environment]::SetEnvironmentVariable(`$_.Split('=')[0], `$_.Split('=')[1]) }" -ForegroundColor White
    Write-Host "2. Start OpenWebUI with telemetry:"
    Write-Host "   `$env:ENABLE_OTEL='true'; `$env:OTEL_EXPORTER_OTLP_ENDPOINT='http://localhost:4317'; uv run open-webui serve" -ForegroundColor White
    Write-Host "3. Generate analytics traffic and check dashboards at http://localhost:3000" -ForegroundColor White

    # Check if we can access Prometheus metrics endpoint
    try {
        $metricsCheck = Invoke-WebRequest -Uri "http://localhost:8889/metrics" -Method GET -TimeoutSec 3 -UseBasicParsing
        if ($metricsCheck.StatusCode -eq 200) {
            Write-Host "`n✅ OTEL Collector metrics endpoint ready at http://localhost:8889/metrics" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "`n⚠️ OTEL Collector metrics endpoint not yet available" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n⚠️ Some services are not ready. Check the observability stack." -ForegroundColor Red
    Write-Host "Run: docker ps | findstr cf-" -ForegroundColor White
}

Write-Host "`n🎉 Observability test complete!" -ForegroundColor Green