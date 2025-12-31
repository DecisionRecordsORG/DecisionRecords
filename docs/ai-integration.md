# AI/LLM Integration

This document describes the AI/LLM integration features in Architecture Decisions, enabling LLMs and AI agents to create, search, and read decision records.

## Overview

The AI integration allows:
- **Slack AI Bot**: Natural language queries via Slack commands
- **MCP Server**: Integration with developer tools (Claude Code, Cursor, VS Code)
- **External AI API**: Support for Custom GPTs and AI agents
- **AI-Assisted Creation**: Help users structure decisions from natural language (future)

All AI features are **opt-in** with hierarchical control.

## Configuration Hierarchy

AI features follow a three-level permission model:

```
Super Admin (System Level)
    │
    ├── Master switch for all AI features
    ├── LLM provider configuration
    └── Per-feature toggles
          │
          ▼
Tenant Admin (Organization Level)
    │
    ├── Enable AI for organization (if system allows)
    ├── Privacy settings (anonymization, logging)
    └── Per-feature toggles
          │
          ▼
User (Individual Level)
    │
    └── Opt-out preference
```

**Key principle**: A feature is only available if enabled at ALL levels above.

## Super Admin Configuration

Super admins control system-wide AI settings via `/api/admin/ai/config`:

| Setting | Description | Default |
|---------|-------------|---------|
| `ai_features_enabled` | Master switch for all AI | `false` |
| `ai_slack_bot_enabled` | Enable Slack AI queries | `false` |
| `ai_mcp_server_enabled` | Enable MCP server | `false` |
| `ai_external_api_enabled` | Enable external AI API | `false` |
| `ai_assisted_creation_enabled` | Enable AI-assisted creation | `false` |
| `llm_provider` | LLM provider (none/openai/anthropic/azure_openai/custom) | `none` |
| `llm_model` | Model identifier (e.g., gpt-4o, claude-3-sonnet) | `null` |
| `llm_endpoint` | Custom endpoint URL | `null` |

### API Endpoints

```
GET  /api/admin/ai/config    - Get system AI configuration
POST /api/admin/ai/config    - Update system AI configuration
GET  /api/admin/ai/stats     - Get system-wide AI usage statistics
```

### Example: Enable AI Features

```bash
curl -X POST /api/admin/ai/config \
  -H "Content-Type: application/json" \
  -d '{
    "ai_features_enabled": true,
    "ai_slack_bot_enabled": true,
    "ai_mcp_server_enabled": true,
    "ai_external_api_enabled": true,
    "llm_provider": "openai",
    "llm_model": "gpt-4o"
  }'
```

## Tenant Admin Configuration

Tenant admins control organization-level settings via `/api/tenant/ai/config`:

| Setting | Description | Default |
|---------|-------------|---------|
| `ai_features_enabled` | Enable AI for this org | `false` |
| `ai_slack_queries_enabled` | Allow Slack AI queries | `false` |
| `ai_assisted_creation_enabled` | Allow AI-assisted creation | `false` |
| `ai_external_access_enabled` | Allow external AI API access | `false` |
| `ai_require_anonymization` | Require PII anonymization | `true` |
| `ai_log_interactions` | Log all AI interactions | `true` |

### API Endpoints

```
GET  /api/tenant/ai/config   - Get tenant AI configuration
POST /api/tenant/ai/config   - Update tenant AI configuration
GET  /api/tenant/ai/stats    - Get tenant AI usage statistics
GET  /api/tenant/ai/logs     - Get AI interaction logs
```

### Example: Enable AI for Organization

```bash
curl -X POST /api/tenant/ai/config \
  -H "Content-Type: application/json" \
  -d '{
    "ai_features_enabled": true,
    "ai_slack_queries_enabled": true,
    "ai_external_access_enabled": true,
    "ai_require_anonymization": true
  }'
```

## User Preferences

Users can opt out of AI features for their account:

### API Endpoints

```
GET  /api/user/ai/preferences    - Get user AI preferences
POST /api/user/ai/preferences    - Update preferences (opt out)
```

### Example: Opt Out of AI

```bash
curl -X POST /api/user/ai/preferences \
  -H "Content-Type: application/json" \
  -d '{"ai_opt_out": true}'
```

## AI API Keys

Users can create API keys for external AI tools (Custom GPTs, agents):

### API Endpoints

```
GET    /api/user/ai/keys         - List user's API keys
POST   /api/user/ai/keys         - Create new API key
DELETE /api/user/ai/keys/{id}    - Revoke an API key
```

### Key Properties

- **Prefix**: All keys start with `adr_`
- **Scopes**: `read`, `search`, `write`
- **Expiration**: Optional, configurable in days
- **Security**: Keys are SHA256 hashed, shown only once on creation
- **Limit**: Maximum 5 keys per user per tenant

### Example: Create API Key

```bash
curl -X POST /api/user/ai/keys \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Custom GPT",
    "scopes": ["read", "search"],
    "expires_in_days": 90
  }'
```

Response:
```json
{
  "message": "API key created successfully. Save this key - it will not be shown again.",
  "key": "adr_abc123...",
  "id": "uuid",
  "name": "My Custom GPT",
  "key_prefix": "adr_abc1",
  "scopes": ["read", "search"],
  "expires_at": "2026-03-31T00:00:00"
}
```

## Slack AI Bot

When enabled, users can query decisions using natural language via Slack:

### Commands

```
/adr search <query>        - Search decisions with natural language
/adr summarize <id>        - Get AI summary of a decision
/adr explain <id>          - Explain decision consequences
```

### Examples

```
/adr search "What decisions did we make about authentication?"
/adr search "Recent accepted decisions about database"
/adr summarize ADR-042
```

### Configuration

1. Super Admin enables `ai_slack_bot_enabled`
2. Tenant Admin enables `ai_slack_queries_enabled`
3. User must not have opted out

## MCP Server

The MCP (Model Context Protocol) server enables integration with developer tools:

### Supported Tools

- **Claude Code**: Direct integration via MCP
- **Cursor**: MCP server configuration
- **VS Code**: Via MCP extension

### API Endpoint

The MCP server is exposed at:

```
POST /api/mcp
Authorization: Bearer adr_your_api_key_here
Content-Type: application/json
```

### Available MCP Tools

| Tool | Description | Scopes Required |
|------|-------------|-----------------|
| `search_decisions` | Search with filters | `search` |
| `get_decision` | Get by ID | `read` |
| `list_decisions` | List with pagination | `read` |
| `create_decision` | Create new decision | `write` |
| `get_decision_history` | View change history | `read` |

### Tool Schemas

#### search_decisions

```json
{
  "name": "search_decisions",
  "arguments": {
    "query": "authentication",
    "status": "accepted",
    "limit": 10
  }
}
```

#### get_decision

```json
{
  "name": "get_decision",
  "arguments": {
    "id": "ADR-42"
  }
}
```

#### list_decisions

```json
{
  "name": "list_decisions",
  "arguments": {
    "status": "accepted",
    "limit": 20,
    "offset": 0,
    "order_by": "created_at",
    "order": "desc"
  }
}
```

#### create_decision

```json
{
  "name": "create_decision",
  "arguments": {
    "title": "Use PostgreSQL for primary database",
    "context": "We need a reliable RDBMS for our data...",
    "decision": "We will use PostgreSQL 15...",
    "consequences": "Pros: ACID compliance, JSON support...",
    "status": "proposed"
  }
}
```

#### get_decision_history

```json
{
  "name": "get_decision_history",
  "arguments": {
    "id": "ADR-42",
    "limit": 20
  }
}
```

### MCP Protocol Examples

#### List Tools

```bash
curl -X POST https://decisionrecords.org/api/mcp \
  -H "Authorization: Bearer adr_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

#### Call a Tool

```bash
curl -X POST https://decisionrecords.org/api/mcp \
  -H "Authorization: Bearer adr_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_decisions",
      "arguments": {
        "query": "authentication"
      }
    }
  }'
```

### Configuration for Claude Code

Add to your Claude Code MCP configuration (`~/.config/claude-code/mcp.json`):

```json
{
  "mcpServers": {
    "architecture-decisions": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-remote-server"],
      "env": {
        "MCP_REMOTE_URL": "https://decisionrecords.org/api/mcp",
        "MCP_API_KEY": "adr_your_api_key_here"
      }
    }
  }
}
```

### Configuration for Cursor

Add to your Cursor settings:

```json
{
  "mcp.servers": {
    "architecture-decisions": {
      "url": "https://decisionrecords.org/api/mcp",
      "headers": {
        "Authorization": "Bearer adr_your_api_key_here"
      }
    }
  }
}
```

## External AI API

For Custom GPTs and external AI agents:

### Endpoints

| Method | Endpoint | Description | Scope Required |
|--------|----------|-------------|----------------|
| POST | `/api/ai/search` | Search decisions | `search` |
| GET | `/api/ai/decisions` | List decisions | `read` |
| GET | `/api/ai/decisions/{id}` | Get decision by ID | `read` |
| POST | `/api/ai/decisions` | Create decision | `write` |
| GET | `/api/ai/decisions/{id}/history` | Get change history | `read` |
| GET | `/api/ai/openapi.json` | OpenAPI schema | (no auth) |

### Authentication

Include API key in Authorization header:

```
Authorization: Bearer adr_your_api_key_here
```

### Search Decisions

```bash
curl -X POST https://decisionrecords.org/api/ai/search \
  -H "Authorization: Bearer adr_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication",
    "status": "accepted",
    "limit": 10
  }'
```

### List Decisions

```bash
curl "https://decisionrecords.org/api/ai/decisions?status=accepted&limit=20&offset=0&order_by=created_at&order=desc" \
  -H "Authorization: Bearer adr_your_api_key"
```

### Get Decision

```bash
curl "https://decisionrecords.org/api/ai/decisions/ADR-42" \
  -H "Authorization: Bearer adr_your_api_key"
```

### Create Decision

```bash
curl -X POST https://decisionrecords.org/api/ai/decisions \
  -H "Authorization: Bearer adr_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Use PostgreSQL for database",
    "context": "We need a reliable RDBMS...",
    "decision": "We will use PostgreSQL 15...",
    "consequences": "Positive: ACID compliance...",
    "status": "proposed"
  }'
```

### OpenAPI Schema

Available at `/api/ai/openapi.json` for Custom GPT configuration.

### Custom GPT Configuration

When creating a Custom GPT:

1. Go to ChatGPT → Create a GPT → Configure
2. Add an action with schema from `/api/ai/openapi.json`
3. Set authentication to "API Key" with "Bearer" type
4. Create an API key at Architecture Decisions → AI Settings → API Keys
5. Add the API key to the GPT configuration

## Audit Logging

All AI interactions are logged (when `ai_log_interactions` is enabled):

### Logged Information

- Channel (slack, mcp, api, web)
- Action (search, read, create, update, summarize)
- User ID
- Query text (anonymized if required)
- Decision IDs accessed
- LLM provider/model used
- Token usage
- Duration

### Viewing Logs

Tenant admins can view logs via `/api/tenant/ai/logs`:

```bash
curl "/api/tenant/ai/logs?limit=100&channel=slack&action=search"
```

## Privacy & Security

### Anonymization

When `ai_require_anonymization` is enabled:
- PII is detected using NER and regex patterns
- Entities are replaced with placeholders before LLM processing
- Original values are restored after processing
- Mapping is never persisted

### Data Flow

```
User Query → Anonymize → LLM Processing → De-anonymize → Response
```

### Security Measures

1. **API Key Security**
   - SHA256 hashing (keys never stored in plaintext)
   - Prefix-only display for identification
   - Automatic expiration option
   - Immediate revocation

2. **Access Control**
   - API keys inherit user's permissions
   - Tenant isolation at all layers
   - Scoped permissions (read/search/write)

3. **Rate Limiting**
   - Per-key rate limits
   - Per-tenant token budgets
   - Automatic throttling

## Troubleshooting

### AI Features Not Available

Check the configuration hierarchy:

1. Is `ai_features_enabled` true at system level?
2. Is the specific feature enabled at system level?
3. Is `ai_features_enabled` true at tenant level?
4. Is the specific feature enabled at tenant level?
5. Has the user opted out?

### API Key Not Working

1. Verify key hasn't expired (`expires_at`)
2. Verify key hasn't been revoked (`is_revoked`)
3. Check key has required scopes
4. Ensure external AI access is enabled for tenant

### Slack Commands Not Responding

1. Check Slack workspace is connected
2. Verify `ai_slack_queries_enabled` at both levels
3. Check user's Slack account is linked
4. Review rate limits

## Related Documentation

- [LLM Integration Plan](plans/llm-integration-plan.md) - Full implementation plan
- [Slack Integration](../README.md#slack-integration) - Basic Slack setup
- [API Documentation](api.md) - Full API reference
