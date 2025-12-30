# LLM Integration Plan for Decision Records

**Created:** 2025-12-30
**Status:** Planning
**Author:** Claude (AI Assistant)

---

## Executive Summary

Enable LLMs and AI agents to create, search, and read decision records through multiple channels (Slack, MCP, Custom GPTs, API). All AI features are opt-in with hierarchical control: Super Admin enables globally, Tenant Admins enable per-tenant.

---

## Design Principles

1. **Opt-in by default** - AI features disabled until explicitly enabled
2. **Hierarchical control** - Super Admin → Tenant Admin → User preferences
3. **Privacy-first** - Data anonymization options, no data sent without consent
4. **Open source friendly** - Self-hosted instances can disable AI entirely
5. **Audit trail** - All AI-initiated actions logged

---

## Configuration Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SUPER ADMIN (System Level)                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ AI Features Master Switch: [OFF] / ON                           ││
│  │                                                                  ││
│  │ If ON, enable which integrations:                               ││
│  │   ☐ Slack AI Bot (natural language queries)                     ││
│  │   ☐ MCP Server (developer tools)                                ││
│  │   ☐ API for External AI (Custom GPTs, agents)                   ││
│  │   ☐ LLM-assisted decision creation (anonymization)              ││
│  │                                                                  ││
│  │ LLM Provider Configuration:                                     ││
│  │   Provider: [None] / OpenAI / Anthropic / Azure OpenAI / Custom ││
│  │   API Key: ******* (stored in Key Vault)                        ││
│  │   Model: gpt-4o / claude-3-sonnet / etc.                        ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ If enabled by Super Admin
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TENANT ADMIN (Organization Level)                 │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ AI Features for this Tenant: [OFF] / ON                         ││
│  │                                                                  ││
│  │ If ON, allow which features:                                    ││
│  │   ☐ Slack AI queries (search/read decisions via bot)            ││
│  │   ☐ AI-assisted decision creation                               ││
│  │   ☐ External AI access (API keys for agents)                    ││
│  │                                                                  ││
│  │ Privacy Settings:                                               ││
│  │   ☑ Require anonymization before LLM processing                 ││
│  │   ☑ Log all AI interactions                                     ││
│  │   ☐ Allow full-text processing (faster, less private)           ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ If enabled by Tenant Admin
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         USER (Individual Level)                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Personal AI Preferences:                                        ││
│  │   ☑ Enable AI features for my account                           ││
│  │   ☐ Opt out of AI features                                      ││
│  │                                                                  ││
│  │ API Keys (if external AI access enabled):                       ││
│  │   [Generate Personal API Key]                                   ││
│  │   Active Keys: key_abc...xyz (created 2025-01-15)               ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (Database & Configuration)
**Goal:** Build the configuration infrastructure

- [ ] **1.1** Add `system_config` fields for AI master settings
  - `ai_features_enabled` (boolean)
  - `ai_slack_bot_enabled` (boolean)
  - `ai_mcp_server_enabled` (boolean)
  - `ai_external_api_enabled` (boolean)
  - `ai_assisted_creation_enabled` (boolean)
  - `ai_llm_provider` (enum: none, openai, anthropic, azure, custom)
  - `ai_llm_model` (string)
  - `ai_llm_api_key_secret` (Key Vault reference)

- [ ] **1.2** Add `tenant` fields for tenant-level AI settings
  - `ai_features_enabled` (boolean, default false)
  - `ai_slack_queries_enabled` (boolean)
  - `ai_assisted_creation_enabled` (boolean)
  - `ai_external_access_enabled` (boolean)
  - `ai_require_anonymization` (boolean, default true)
  - `ai_log_interactions` (boolean, default true)

- [ ] **1.3** Add `user_preferences` or extend `tenant_membership`
  - `ai_opt_out` (boolean, default false)

- [ ] **1.4** Create `ai_api_keys` table
  - `id`, `user_id`, `tenant_id`, `key_hash`, `key_prefix`, `name`
  - `created_at`, `last_used_at`, `expires_at`, `revoked_at`
  - `scopes` (JSON: read, write, search)

- [ ] **1.5** Create `ai_interaction_log` table
  - `id`, `user_id`, `tenant_id`, `channel` (slack, mcp, api, web)
  - `action` (search, read, create, update)
  - `query_anonymized` (text), `decision_ids` (array)
  - `llm_provider`, `tokens_used`, `created_at`

- [ ] **1.6** Super Admin UI for AI configuration
- [ ] **1.7** Tenant Admin UI for AI settings
- [ ] **1.8** User settings UI for AI preferences and API keys

---

### Phase 2: Slack AI Bot Enhancement
**Goal:** Add natural language queries to existing Slack bot

- [ ] **2.1** Add feature flag check to Slack bot
  - Check system-level `ai_slack_bot_enabled`
  - Check tenant-level `ai_slack_queries_enabled`
  - Return graceful message if disabled

- [ ] **2.2** Implement natural language query parsing
  - Intent detection: search, get, list, summarize
  - Entity extraction: keywords, date ranges, status filters

- [ ] **2.3** Search integration
  - `/adr search <natural language query>`
  - "What decisions did we make about authentication?"
  - "Show me recent accepted decisions"

- [ ] **2.4** Read/summarize integration
  - `/adr summarize ADR-042`
  - "Explain the consequences of ADR-042"

- [ ] **2.5** Privacy controls
  - If anonymization required, process query through anonymizer
  - Log all AI interactions to `ai_interaction_log`

- [ ] **2.6** Rate limiting for AI queries
  - Per-user, per-tenant limits
  - Token budget tracking

---

### Phase 3: MCP Server (Developer Tools)
**Goal:** Enable Claude Code, Cursor, and VS Code integration

- [ ] **3.1** Create MCP server module (`mcp_server/`)
  - Standalone process or integrated endpoint
  - WebSocket or stdio transport

- [ ] **3.2** Implement MCP tools
  - `search_decisions` - Search with filters
  - `get_decision` - Get by ID or display_id
  - `list_decisions` - List with pagination
  - `create_decision` - Create new (if write enabled)
  - `get_decision_history` - View change history

- [ ] **3.3** Authentication for MCP
  - API key validation
  - Scope checking (read-only vs read-write)
  - Tenant context from API key

- [ ] **3.4** MCP configuration guide
  - Documentation for Claude Code setup
  - Documentation for Cursor setup
  - Example configurations

- [ ] **3.5** Feature flag integration
  - Check `ai_mcp_server_enabled` at system level
  - Check tenant settings for connected API key

---

### Phase 4: External AI API (Custom GPTs, Agents)
**Goal:** Enable any AI tool to integrate via API

- [ ] **4.1** Create `/api/ai/` namespace
  - Separate from regular API for clarity
  - Different rate limits and logging

- [ ] **4.2** Implement AI-optimized endpoints
  ```
  POST /api/ai/search
  GET  /api/ai/decisions/{id}
  GET  /api/ai/decisions (list)
  POST /api/ai/decisions (create)
  ```

- [ ] **4.3** OpenAPI/Swagger schema for AI tools
  - Function calling compatible schema
  - Clear descriptions for LLM understanding

- [ ] **4.4** OAuth2 flow for Custom GPTs
  - Authorization endpoint
  - Token exchange
  - Refresh tokens

- [ ] **4.5** Simple "Connect Code" flow for non-OAuth tools
  - Generate short-lived connect code in UI
  - AI exchanges code for API key via endpoint

- [ ] **4.6** Custom GPT template/instructions
  - Publish pre-built GPT configuration
  - Documentation for creating custom GPT

---

### Phase 5: LLM-Assisted Decision Creation
**Goal:** Help users structure decisions from natural language

- [ ] **5.1** Entity detection module
  - spaCy NER for names, organizations, dates
  - Regex patterns for emails, URLs, numbers
  - Tenant-specific dictionary support

- [ ] **5.2** Anonymization service
  - Replace entities with placeholders
  - Maintain mapping table (in-memory, never persisted)
  - Restore values after LLM response

- [ ] **5.3** LLM integration service
  - Abstract provider interface
  - OpenAI implementation
  - Anthropic implementation
  - Azure OpenAI implementation

- [ ] **5.4** Structured extraction prompt
  - Extract: title, context, decision, consequences, status
  - Return JSON schema

- [ ] **5.5** Integration points
  - Slack `/adr create` with natural language
  - Web UI "Create from description" option
  - API endpoint for programmatic use

- [ ] **5.6** Review flow
  - Never auto-create, always show preview
  - User confirms/edits before saving

---

## Database Schema Changes

```sql
-- System-level AI configuration (extends system_config)
ALTER TABLE system_config ADD COLUMN ai_features_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE system_config ADD COLUMN ai_slack_bot_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE system_config ADD COLUMN ai_mcp_server_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE system_config ADD COLUMN ai_external_api_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE system_config ADD COLUMN ai_assisted_creation_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE system_config ADD COLUMN ai_llm_provider VARCHAR(50) DEFAULT 'none';
ALTER TABLE system_config ADD COLUMN ai_llm_model VARCHAR(100);
ALTER TABLE system_config ADD COLUMN ai_llm_api_key_secret VARCHAR(255);

-- Tenant-level AI settings (extends tenant)
ALTER TABLE tenant ADD COLUMN ai_features_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE tenant ADD COLUMN ai_slack_queries_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE tenant ADD COLUMN ai_assisted_creation_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE tenant ADD COLUMN ai_external_access_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE tenant ADD COLUMN ai_require_anonymization BOOLEAN DEFAULT TRUE;
ALTER TABLE tenant ADD COLUMN ai_log_interactions BOOLEAN DEFAULT TRUE;

-- User AI opt-out (extends tenant_membership)
ALTER TABLE tenant_membership ADD COLUMN ai_opt_out BOOLEAN DEFAULT FALSE;

-- AI API Keys
CREATE TABLE ai_api_key (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    key_hash VARCHAR(64) NOT NULL,  -- SHA256 of the key
    key_prefix VARCHAR(8) NOT NULL,  -- First 8 chars for identification
    name VARCHAR(100) NOT NULL,
    scopes JSONB DEFAULT '["read", "search"]',
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    revoked_at TIMESTAMP,
    UNIQUE(key_hash)
);

-- AI Interaction Log
CREATE TABLE ai_interaction_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES "user"(id),
    tenant_id INTEGER REFERENCES tenant(id),
    channel VARCHAR(20) NOT NULL,  -- slack, mcp, api, web
    action VARCHAR(20) NOT NULL,   -- search, read, create, summarize
    query_text TEXT,               -- Anonymized query (if applicable)
    decision_ids INTEGER[],        -- Decisions accessed
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    tokens_input INTEGER,
    tokens_output INTEGER,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ai_interaction_log_tenant ON ai_interaction_log(tenant_id, created_at);
CREATE INDEX idx_ai_interaction_log_user ON ai_interaction_log(user_id, created_at);
CREATE INDEX idx_ai_api_key_user ON ai_api_key(user_id);
CREATE INDEX idx_ai_api_key_tenant ON ai_api_key(tenant_id);
```

---

## Security Considerations

1. **API Key Security**
   - Keys hashed with SHA256, only prefix stored readable
   - Keys shown once on creation, never retrievable
   - Automatic expiration option
   - Revocation with immediate effect

2. **Data Privacy**
   - Anonymization enabled by default
   - LLM providers never receive raw PII
   - Interaction logs store anonymized queries only

3. **Access Control**
   - API keys inherit user's permissions
   - Cannot access decisions user doesn't have access to
   - Tenant isolation enforced at all layers

4. **Rate Limiting**
   - Per-key rate limits
   - Per-tenant token budgets
   - Automatic throttling when limits approached

5. **Audit Trail**
   - All AI interactions logged
   - Exportable for compliance
   - Retention policy configurable

---

## File Structure (Proposed)

```
/ai/
  __init__.py
  config.py           # AI configuration management
  api_keys.py         # API key generation/validation
  interaction_log.py  # Logging service

  /anonymization/
    __init__.py
    detector.py       # Entity detection (NER + patterns)
    anonymizer.py     # Replace entities with placeholders
    restorer.py       # Restore original values

  /llm/
    __init__.py
    base.py           # Abstract LLM provider interface
    openai.py         # OpenAI implementation
    anthropic.py      # Anthropic implementation
    azure.py          # Azure OpenAI implementation

  /mcp/
    __init__.py
    server.py         # MCP server implementation
    tools.py          # Tool definitions

  /slack/
    __init__.py
    nl_query.py       # Natural language query processing
    handlers.py       # AI-specific Slack handlers
```

---

## Success Metrics

1. **Adoption**
   - % of tenants enabling AI features
   - # of AI queries per day/week
   - # of API keys created

2. **Quality**
   - Search relevance (user feedback)
   - Decision creation accuracy (edit rate after AI assist)

3. **Performance**
   - Query latency (p50, p95)
   - Token usage efficiency

4. **Security**
   - Zero PII leaks to LLM providers
   - Audit log completeness

---

## Open Questions

1. Should MCP server be a separate process or integrated into main app?
2. Token budget model: per-tenant flat rate or pay-per-use?
3. Support for self-hosted LLMs (Ollama, vLLM)?
4. Should AI-created decisions be marked as such?

---

## Next Steps

1. Review and approve this plan
2. Create GitHub issues for each phase
3. Start with Phase 1 (Foundation) to unblock all other phases
4. Parallel work possible on Phase 2 (Slack) and Phase 3 (MCP) after Phase 1

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-30 | Initial plan created | Claude |
