# Log Forwarding

This document describes how to configure log forwarding in the Architecture Decisions platform using OpenTelemetry Protocol (OTLP).

## Overview

Log forwarding enables you to send application logs to external log aggregation services. The platform uses OpenTelemetry (OTLP), the industry-standard protocol for observability data, ensuring compatibility with most modern logging backends.

## Supported Backends

Any OTLP-compatible backend can receive logs from the platform:

| Provider | Type | Documentation |
|----------|------|---------------|
| Grafana Cloud (Loki) | Cloud | [OTLP Gateway](https://grafana.com/docs/grafana-cloud/send-data/otlp/) |
| Datadog | Cloud | [OTLP Ingest](https://docs.datadoghq.com/opentelemetry/) |
| New Relic | Cloud | [OTLP Endpoint](https://docs.newrelic.com/docs/more-integrations/open-source-telemetry-integrations/opentelemetry/opentelemetry-introduction/) |
| Elastic APM | Cloud/Self-hosted | [OTLP Support](https://www.elastic.co/guide/en/apm/guide/current/open-telemetry.html) |
| OpenTelemetry Collector | Self-hosted | [Collector Docs](https://opentelemetry.io/docs/collector/) |
| Jaeger | Self-hosted | [OTLP Receiver](https://www.jaegertracing.io/docs/latest/deployment/) |

## Configuration

### Via Super Admin UI

1. Log in as a super admin
2. Navigate to **Settings** > **Super Admin Settings**
3. Scroll to the **Log Forwarding** card
4. Configure the following settings:

| Setting | Description | Example |
|---------|-------------|---------|
| **Enable Log Forwarding** | Toggle to enable/disable | On |
| **OTLP Endpoint URL** | Your provider's OTLP endpoint | `https://otlp-gateway-prod-eu-west-2.grafana.net/otlp` |
| **Auth Type** | How to authenticate | API Key, Bearer, Custom Header, None |
| **Auth Header Name** | Header name for auth (if custom) | `Authorization` |
| **API Key / Token** | Your provider's API key | `glc_eyJ...` |
| **Log Level** | Minimum level to forward | INFO |
| **Service Name** | Identifier in logs | `architecture-decisions` |
| **Environment** | Environment tag | `production` |
| **Custom Headers** | Additional headers (JSON) | `{"X-Scope-OrgID": "my-org"}` |

5. Click **Test Connection** to verify the configuration
6. Click **Save** to apply the settings

### Via Environment Variables (Self-Hosted)

For Docker/container deployments, you can set these environment variables:

```bash
LOG_FORWARDING_ENABLED=true
LOG_FORWARDING_ENDPOINT_URL=https://otlp-gateway-prod-eu-west-2.grafana.net/otlp
LOG_FORWARDING_AUTH_TYPE=api_key
LOG_FORWARDING_API_KEY=your-api-key
LOG_FORWARDING_LOG_LEVEL=INFO
LOG_FORWARDING_SERVICE_NAME=architecture-decisions
LOG_FORWARDING_ENVIRONMENT=production
```

## Provider-Specific Configuration

### Grafana Cloud (Loki)

1. Get your OTLP endpoint from Grafana Cloud portal:
   - Navigate to **Connections** > **Add new connection** > **OpenTelemetry**
   - Copy the OTLP endpoint URL (format: `https://otlp-gateway-<region>.grafana.net/otlp`)

2. Create an API key:
   - Go to **Administration** > **API Keys**
   - Create a key with **MetricsPublisher** role

3. Configure in Architecture Decisions:
   - **OTLP Endpoint URL**: `https://otlp-gateway-prod-eu-west-2.grafana.net/otlp`
   - **Auth Type**: API Key
   - **API Key**: `<instance_id>:<api_key>` (format: `123456:glc_eyJ...`)
   - **Custom Headers**: `{"X-Scope-OrgID": "<instance_id>"}`

### Datadog

1. Get your API key from Datadog:
   - Navigate to **Organization Settings** > **API Keys**

2. Determine your OTLP endpoint based on region:
   - US1: `https://api.datadoghq.com`
   - EU1: `https://api.datadoghq.eu`

3. Configure in Architecture Decisions:
   - **OTLP Endpoint URL**: `https://api.datadoghq.eu/v1/logs`
   - **Auth Type**: API Key
   - **Auth Header Name**: `DD-API-KEY`
   - **API Key**: Your Datadog API key

### New Relic

1. Get your license key from New Relic:
   - Navigate to **API Keys** in your account settings

2. Configure in Architecture Decisions:
   - **OTLP Endpoint URL**: `https://otlp.eu01.nr-data.net:4317` (EU) or `https://otlp.nr-data.net:4317` (US)
   - **Auth Type**: API Key
   - **Auth Header Name**: `api-key`
   - **API Key**: Your New Relic license key

### Self-Hosted OpenTelemetry Collector

For self-hosted deployments, you can run an OpenTelemetry Collector:

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

exporters:
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

  file:
    path: /var/log/otel/logs.json

service:
  pipelines:
    logs:
      receivers: [otlp]
      exporters: [loki, file]
```

Run with Docker:
```bash
docker run -d \
  -p 4317:4317 \
  -p 4318:4318 \
  -v ./otel-collector-config.yaml:/etc/otel-collector-config.yaml \
  otel/opentelemetry-collector \
  --config=/etc/otel-collector-config.yaml
```

Configure in Architecture Decisions:
- **OTLP Endpoint URL**: `http://otel-collector:4317`
- **Auth Type**: None

## Log Levels

The **Log Level** setting controls the minimum severity of logs forwarded:

| Level | Description | Use Case |
|-------|-------------|----------|
| DEBUG | Detailed debugging information | Development, troubleshooting |
| INFO | General operational information | Production monitoring |
| WARNING | Potential issues or degraded state | Alert on anomalies |
| ERROR | Errors requiring attention | Critical issue alerting |

Setting a higher level (e.g., WARNING) means only WARNING and ERROR logs are forwarded. DEBUG and INFO logs will only go to stdout.

## Log Format

Logs are forwarded with the following attributes:

```json
{
  "timestamp": "2025-12-13T10:30:00.000Z",
  "severity": "INFO",
  "body": "User authenticated successfully",
  "resource": {
    "service.name": "architecture-decisions",
    "deployment.environment": "production"
  },
  "attributes": {
    "tenant": "example.com",
    "user_id": "abc123",
    "request_id": "req-xyz789"
  }
}
```

## Troubleshooting

### Connection Failures

If the **Test Connection** fails:

1. **Check endpoint URL**: Ensure the URL is correct and accessible from your server
2. **Verify authentication**: Confirm API key is correct and has required permissions
3. **Check network egress**: Ensure firewall/NSG allows outbound HTTPS to the endpoint
4. **Review custom headers**: Verify JSON syntax is valid

### Logs Not Appearing

If logs aren't showing in your provider:

1. **Check log level**: Ensure your app is generating logs at or above the configured level
2. **Wait for batch**: Logs are batched before export; wait 30-60 seconds
3. **Check provider filters**: Verify you're viewing the correct time range and service
4. **Review provider ingestion**: Some providers have ingestion delays

### High Memory Usage

If the application uses excessive memory with log forwarding:

1. **Increase batch timeout**: Logs are batched to reduce overhead
2. **Raise log level**: Forward fewer logs by setting a higher minimum level
3. **Check export failures**: Failed exports can cause log buffering

## Security Considerations

1. **API Key Storage**: API keys are stored securely in Azure Key Vault (cloud) or encrypted SystemConfig (self-hosted)
2. **TLS Required**: Always use HTTPS endpoints in production
3. **Sensitive Data**: Logs may contain sensitive information; ensure your logging backend has appropriate access controls
4. **Network Security**: Configure firewall rules to allow outbound traffic only to your specific OTLP endpoint

## Dependencies

The log forwarding feature requires these Python packages:

```
opentelemetry-sdk>=1.20.0
opentelemetry-exporter-otlp>=1.20.0
opentelemetry-instrumentation-logging>=0.41b0
```

These are included in the standard deployment and do not require additional installation.
