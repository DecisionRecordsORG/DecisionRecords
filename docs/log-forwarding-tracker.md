# Log Forwarding Features Tracker

This document tracks the implementation status of OpenTelemetry (OTLP) log forwarding features for the Architecture Decisions platform.

## Overview

The platform supports configurable log forwarding using OpenTelemetry Protocol (OTLP), enabling self-hosted users to send application logs to any OTLP-compatible backend:

- **Grafana Cloud (Loki)**: Cloud-hosted log aggregation
- **Datadog**: Full observability platform
- **New Relic**: Application performance monitoring
- **Elastic**: ELK stack integration
- **Self-hosted Collector**: OpenTelemetry Collector

## Feature Implementation Status

### Phase 1: Core Backend (Complete)

| Feature | Status | Backend | Frontend | Unit Tests | Integration Tests | E2E Tests |
|---------|--------|---------|----------|------------|-------------------|-----------|
| OpenTelemetry SDK integration | Complete | Done | N/A | Pending | Pending | - |
| OTLP log exporter | Complete | Done | N/A | Pending | Pending | - |
| BatchLogRecordProcessor (async) | Complete | Done | N/A | Pending | Pending | - |
| Configuration caching (5-min TTL) | Complete | Done | N/A | Pending | Pending | - |
| Graceful fallback on failure | Complete | Done | N/A | Pending | Pending | - |

### Phase 2: API & Configuration (Complete)

| Feature | Status | Backend | Frontend | Unit Tests | Integration Tests | E2E Tests |
|---------|--------|---------|----------|------------|-------------------|-----------|
| SystemConfig keys for log forwarding | Complete | Done | N/A | - | - | - |
| GET /api/admin/settings/log-forwarding | Complete | Done | N/A | Pending | Pending | - |
| POST /api/admin/settings/log-forwarding | Complete | Done | N/A | Pending | Pending | - |
| PUT /api/admin/settings/log-forwarding/api-key | Complete | Done | N/A | Pending | Pending | - |
| POST /api/admin/settings/log-forwarding/test | Complete | Done | N/A | Pending | Pending | - |
| Key Vault integration for API key | Complete | Done | N/A | - | - | - |

### Phase 3: Super Admin UI (Complete)

| Feature | Status | Backend | Frontend | Unit Tests | Integration Tests | E2E Tests |
|---------|--------|---------|----------|------------|-------------------|-----------|
| Enable/disable toggle | Complete | N/A | Done | N/A | N/A | Pending |
| OTLP endpoint URL input | Complete | N/A | Done | N/A | N/A | Pending |
| Auth type selector | Complete | N/A | Done | N/A | N/A | Pending |
| API key/token input | Complete | N/A | Done | N/A | N/A | Pending |
| Log level dropdown | Complete | N/A | Done | N/A | N/A | Pending |
| Service name/environment inputs | Complete | N/A | Done | N/A | N/A | Pending |
| Custom headers textarea | Complete | N/A | Done | N/A | N/A | Pending |
| Test Connection button | Complete | N/A | Done | N/A | N/A | Pending |

## Configuration Keys

System configuration keys used for log forwarding features:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `log_forwarding_enabled` | Boolean | false | Enable/disable log forwarding |
| `log_forwarding_endpoint_url` | String | - | OTLP endpoint URL |
| `log_forwarding_auth_type` | Enum | api_key | Authentication type (api_key, bearer, header, none) |
| `log_forwarding_auth_header_name` | String | Authorization | Custom auth header name |
| `log_forwarding_api_key` | String | - | API key/token (stored securely) |
| `log_forwarding_log_level` | Enum | INFO | Minimum log level to forward (DEBUG, INFO, WARNING, ERROR) |
| `log_forwarding_service_name` | String | architecture-decisions | Service identifier in logs |
| `log_forwarding_environment` | String | production | Environment tag in logs |
| `log_forwarding_custom_headers` | JSON | {} | Additional HTTP headers |

## API Endpoints

### Log Forwarding Settings (Super Admin)

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/admin/settings/log-forwarding` | GET | Get log forwarding settings | Not Started |
| `/api/admin/settings/log-forwarding` | POST | Update log forwarding settings | Not Started |
| `/api/admin/settings/log-forwarding/api-key` | PUT | Update API key separately | Not Started |
| `/api/admin/settings/log-forwarding/test` | POST | Test connection to endpoint | Not Started |

## Implementation Notes

### Authentication Types

The module supports multiple authentication methods for different OTLP backends:

1. **API Key** (`api_key`): Standard API key in Authorization header
   - Header: `Authorization: Api-Key <key>`

2. **Bearer Token** (`bearer`): OAuth-style bearer token
   - Header: `Authorization: Bearer <token>`

3. **Custom Header** (`header`): Custom header name for the key
   - Header: `<custom_name>: <key>`

4. **None** (`none`): No authentication (for internal collectors)

### Popular OTLP Endpoints

| Provider | Endpoint Format | Auth Type |
|----------|-----------------|-----------|
| Grafana Cloud | `https://otlp-gateway-<region>.grafana.net/otlp` | api_key |
| Datadog | `https://http-intake.logs.datadoghq.com/api/v2/logs` | api_key |
| New Relic | `https://otlp.nr-data.net:4317` | api_key |
| Elastic | `https://<deployment>.apm.us-central1.gcp.cloud.es.io:443` | bearer |
| Self-hosted | `http://otel-collector:4317` | none |

### Non-Blocking Design

Log forwarding uses OpenTelemetry's `BatchLogRecordProcessor` which:
- Batches log records before export (reduces network overhead)
- Exports asynchronously (doesn't block request handling)
- Handles failures gracefully (logs continue to stdout)
- Respects shutdown signals (flushes pending logs)

### Security Considerations

1. **API Key Storage**: API keys are stored in Azure Key Vault for cloud deployments, SystemConfig for self-hosted
2. **TLS**: All OTLP endpoints should use HTTPS in production
3. **Network Egress**: Ensure firewall/NSG allows outbound to OTLP endpoint

## Changelog

### 2025-12-13
- Created log forwarding features tracker
- Documented implementation plan for OpenTelemetry log forwarding
- Implemented log_forwarding.py module with OTLP integration
- Added SystemConfig keys for log forwarding settings
- Added Key Vault integration for API key storage
- Created API endpoints for settings management and testing
- Implemented super admin UI card for log forwarding configuration
- Added documentation files (log-forwarding.md, log-forwarding-tracker.md)
