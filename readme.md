# *Cloud Logging — Distributed Logging Microservice* 

> A multi-tenant, serverless-resilient, encrypted logging infrastructure designed to be embedded into any application with zero latency impact.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
  - [Standard SDK](#1-standard-sdk)
  - [Client & Server Wrapper Objects](#2-client--server-wrapper-objects)
  - [API Key Management & Multi-Tenancy](#3-api-key-management--multi-tenancy)
  - [OLAP Database Layer](#4-olap-database-layer)
  - [Auto-Scaling Attributes](#5-auto-scaling-attributes)
  - [Storage Window & Data Lifecycle](#6-storage-window--data-lifecycle)
  - [Encryption](#7-encryption)
- [Cold Start & Latency Resilience](#cold-start--latency-resilience)
- [Deployment](#deployment)
- [Technology Stack](#technology-stack)
- [Cost Model](#cost-model)
- [Scaling Path](#scaling-path)

---

## Overview

LogStream is a self-hostable, multi-tenant logging microservice designed to be reused across multiple applications with minimal integration overhead. It solves three problems simultaneously: **high-frequency write throughput**, **zero application-side latency**, and **reliable delivery in serverless environments**. It exposes a unified SDK for Python backends and React/TypeScript frontends, manages tenants via API keys, and stores all data in a columnar OLAP database purpose-built for time-series log workloads.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                         CLIENT APPLICATION                             │
│                                                                        │
│   SDK.log() → Local Buffer → Background Worker → Compressed Batch      │
└────────────────────────────────────────┬───────────────────────────────┘
                                         │ Fire-and-forget (async)
                                         ▼
                             ┌───────────────────────┐
                             │    Edge Buffer Layer  │
                             │  (Cloudflare Workers /│
                             │   Fly.io always-on)   │
                             │  No cold start. < 10ms│
                             └───────────┬───────────┘
                                         │ Batched relay
                                         ▼
                             ┌───────────────────────┐
                             │    Message Queue      │
                             │  (Upstash Redis       │
                             │   Streams / SQS)      │
                             │  Durability buffer    │
                             └───────────┬───────────┘
                                         │ Consumer group pull
                                         ▼
                             ┌───────────────────────┐
                             │   Serverless Ingestor │
                             │   (FastAPI / Lambda)  │
                             │  Auth · Validate ·    │
                             │  Decrypt · Enrich     │
                             └───────────┬───────────┘
                                         │ Bulk insert
                                         ▼
              ┌──────────────────────────────────────────────┐
              │                  ClickHouse                  │
              │    Hot (0–7d) │ Warm (7–60d) │ Cold (60–90d) │
              │    SSD        │ HDD          │ S3 offload    │
              └──────────────────────────────────────────────┘
                                         │ TTL auto-purge at 90 days
                                         ▼
                             ┌───────────────────────┐
                             │   Archive Storage     │
                             │  (Backblaze B2 / S3)  │
                             └───────────────────────┘
```

---

## Features

### 1. Standard SDK

A unified SDK is published in two flavors that share the same design contract: one for Python (backend services) and one for TypeScript (React frontends and Node.js).

**Core SDK Capabilities (both flavors)**

- Single initialization with `api_key` and `endpoint`
- Named log levels: `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL`
- Structured logging with arbitrary key-value pairs as attributes
- Built-in local buffer that absorbs spikes and network failures
- Automatic batching: flushes every 5 seconds or when 100 logs accumulate, whichever comes first
- Retry logic with exponential backoff and jitter on delivery failure
- Circuit breaker: pauses retries after 5 consecutive failures for 2 minutes to avoid draining resources on mobile or bandwidth-constrained environments
- Graceful shutdown hook: flushes remaining buffer on process exit
- Optional sampling rate per log level (e.g., sample `DEBUG` at 10% in production)
- AES-256 payload encryption before any log leaves the device

**Python SDK specifics**

- Supports both `asyncio` and synchronous usage patterns
- Thread pool executor for non-blocking delivery in sync code
- File-based persistence fallback when memory buffer exceeds threshold
- Context manager support for structured scoped logging (e.g., log all events within a request block with a shared `request_id`)

**TypeScript/React SDK specifics**

- Works in both browser and Node.js environments
- `useLogger()` React hook for ergonomic component-level usage
- IndexedDB persistence in the browser for queue durability across page reloads
- `navigator.sendBeacon()` used automatically on `visibilitychange`/page unload to guarantee a final flush attempt
- Service Worker integration (optional) for background queue processing
- Web Crypto API used for AES-256 encryption natively in the browser with no additional dependencies

---

### 2. Client & Server Wrapper Objects

The SDK exposes a `Logger` wrapper object as its primary interface. This object is the only point of contact between your application and the logging infrastructure.

**Wrapper Object Responsibilities**

- Holds the API key and resolved tenant context for the lifetime of the application session
- Exposes a consistent method signature across Python and TypeScript so integrations feel identical regardless of language
- Automatically attaches environment metadata to every log entry: SDK version, runtime environment (browser/server/lambda), hostname or user agent, and a monotonic sequence number for ordering
- Provides a `setContext()` method that attaches persistent key-value pairs to all subsequent logs in a session (e.g., `user_id`, `tenant_id`, `session_id`, `app_version`)
- Supports scoped child loggers: call `logger.child({ request_id: "abc" })` to create a derived logger that inherits all parent context and appends its own

**Server-side usage pattern (Python)**

Instantiated once at application startup (e.g., in a FastAPI lifespan handler or Django AppConfig) and injected via dependency injection or a module-level singleton. Each request handler calls `logger.info(...)` and returns immediately. The SDK handles everything else in the background.

**Client-side usage pattern (React/TypeScript)**

Instantiated in a root-level provider component and exposed via a React context. Child components consume the `useLogger()` hook and call log methods. No component ever awaits a log call.

---

### 3. API Key Management & Multi-Tenancy

Each application that integrates LogStream is treated as a separate tenant identified by an `app_id`. Access is gated by API keys.

**API Key Format**

Keys follow a structured format for easy identification and environment separation:

```
app_{app_id}_{env}_{random_32_chars}
```

Example: `app_dashboard_live_a7f3b2c1d9e4f8a2b3c4d5e6f7a8b9c0`

**Key Storage**

Raw keys are never stored. On creation, the key is hashed with bcrypt and only the hash is persisted. The raw key is shown once at creation time.

**Per-key Metadata**

Each key carries: `app_id`, `app_name`, `environment` (live/test), `rate_limit_per_minute`, `allowed_log_levels`, `created_at`, `last_used_at`, `revoked` flag. This enables per-app monitoring, revocation without downtime, and granular permission scoping.

**Multi-Tenant Data Isolation**

Every log row stored in ClickHouse carries `app_id` as a leading partition and sort key component. All queries from the API layer enforce an `app_id = ?` predicate, making cross-tenant data leakage structurally impossible at the query level. Encryption keys are also scoped per `app_id`.

**App Monitoring Dashboard**

A lightweight read API exposes per-app metrics queryable in Grafana: log volume over time, error rate, top attributes, and active sessions. Alerts can be wired to Discord or Slack webhooks.

**Rate Limiting**

The ingestor enforces per-key rate limits at the edge buffer layer using a sliding window counter in Redis. Requests exceeding the limit receive a `429` response. The SDK handles this gracefully by holding excess logs in the local buffer and retrying after the window resets.

---

### 4. OLAP Database Layer

**ClickHouse** is chosen as the primary storage engine because it is purpose-built for the exact workload logging produces: append-only, high-cardinality, time-series data with infrequent point reads and frequent analytical aggregations.

**Why ClickHouse over alternatives**

| Concern | ClickHouse | PostgreSQL | Elasticsearch |
|---|---|---|---|
| Write throughput | Millions/sec | Thousands/sec | Hundreds of thousands/sec |
| Compression ratio | 10–50x (columnar) | 3–5x | 3–5x |
| Analytical query speed | Sub-second on billions | Slow at scale | Moderate |
| Self-host cost | Free, open source | Free | Resource-heavy |
| TTL / partitioning | Native | Manual | ILM policies |

**Table Design**

The primary `logs` table uses a `MergeTree` engine with the following design decisions:

- Partitioned by `toYYYYMM(timestamp)` so each month's data is a discrete partition that can be dropped atomically for retention enforcement
- Ordered by `(app_id, timestamp)` to co-locate all logs for a tenant and enable fast time-range scans
- `attributes Map(String, String)` column stores all dynamic custom attributes without requiring schema migrations
- `encrypted_payload String` column stores AES-256 encrypted sensitive fields separately from plaintext metadata
- Secondary indices on `log_level` and `session_id` for common filter patterns
- Native TTL expression deletes rows older than 90 days automatically during background merges

**Write Path**

Logs arrive from the message queue in batches. The consumer worker uses ClickHouse's native HTTP bulk insert endpoint to write thousands of rows per request, which is optimal for ClickHouse's columnar merge engine. Individual row inserts are never used.

---

### 5. Auto-Scaling Attributes

LogStream is designed so that adding a new tracking dimension to your application requires **zero backend changes**.

**How It Works**

The `attributes Map(String, String)` column in ClickHouse accepts any arbitrary key-value pair. When your SDK sends a new attribute name for the first time, it simply flows through the pipeline and lands in that column without any migration, schema update, or deployment.

**Example Progression**

At launch, you log:
```
{ "page": "dashboard" }
```

Three weeks later, you decide to track:
```
{ "page": "dashboard", "time_spent_ms": "3200", "scroll_depth_pct": "78", "ab_variant": "B" }
```

No infrastructure change is required. ClickHouse stores the new keys immediately, and they are queryable the moment the first row lands.

**Querying Dynamic Attributes**

ClickHouse exposes map access syntax (`attributes['time_spent_ms']`) and map functions (`mapKeys`, `mapValues`) so you can aggregate, filter, and group on any attribute you've ever logged.

**SDK-Level Attribute Typing**

While storage is loosely typed (all values are strings in the map), the SDK enforces value serialization consistently. Numbers, booleans, and objects are serialized to string before transmission and can be cast at query time using ClickHouse's `toInt64`, `toFloat64`, and `JSONExtract` functions.

---

### 6. Storage Window & Data Lifecycle

Data moves through three tiers automatically based on age.

**Tier 1 — Hot (0 to 7 days)**

Stored on SSD-backed ClickHouse storage. All recent log data is immediately queryable with sub-second response times. This is the tier used for live dashboards, real-time alerting, and active debugging sessions.

**Tier 2 — Warm (7 to 60 days)**

Automatically migrated to HDD-backed ClickHouse volumes by a tiered storage policy. Queries still work transparently but may take slightly longer for large time ranges. Suitable for weekly trend analysis and retrospective debugging.

**Tier 3 — Cold / Archive (60 to 90 days)**

ClickHouse's `s3` disk integration offloads older partitions to object storage (Backblaze B2 or S3-compatible). Data remains queryable through ClickHouse without any application-level change; the engine fetches from S3 transparently. Storage cost drops to object storage pricing (~$0.006/GB/month on Backblaze B2).

**Automatic Expiry**

ClickHouse's native TTL expression permanently deletes rows older than 90 days during background merge operations. No cron jobs, no manual partition drops, no operational burden. The retention window is configurable per deployment via a single TTL value change.

---

### 7. Encryption

All sensitive log data is encrypted before it leaves the originating application and remains encrypted at rest in the database.

**Encryption Standard**

AES-256-GCM is used for all payload encryption. GCM mode provides both confidentiality and authentication (tamper detection) in a single pass, making it suitable for network transmission and storage.

**Key Architecture**

- One encryption key per `app_id` — a compromised key for one tenant exposes no other tenant's data
- Keys are stored in environment variables on the ingestor service and never written to the database
- Key rotation is supported: the ingestor stores a `key_version` field alongside each encrypted payload, enabling background re-encryption jobs to rotate keys without downtime or data loss

**What Is Encrypted**

Structured metadata (`timestamp`, `app_id`, `log_level`) is stored in plaintext to enable indexing and partitioning. The `message` field and all `attributes` values for logs marked sensitive are stored only in the `encrypted_payload` column as an AES-256-GCM ciphertext blob. Decryption happens at query time on the ingestor's read API, never inside ClickHouse itself.

**Transport Security**

All communication between SDK and edge buffer uses TLS 1.3. AES payload encryption is additive — it protects data even if TLS termination is compromised at an intermediate layer (e.g., a misconfigured CDN).

**Browser Encryption**

The TypeScript SDK uses the Web Crypto API (`SubtleCrypto.encrypt`) natively in the browser. No third-party crypto library is required, reducing bundle size and eliminating supply-chain risk in the encryption path.

---

## Cold Start & Latency Resilience

This is a first-class design concern. LogStream is engineered so that serverless cold starts and network latency are **invisible to the calling application**.

### Principle: Fire-and-Forget at Every Layer

The SDK's public interface is synchronous from the caller's perspective. `logger.info(...)` returns in under 1 millisecond regardless of network conditions. Internally, every log call is placed into an in-process queue and a background worker handles all batching, compression, encryption, and transmission.

### SDK-Level Resilience

The local buffer persists across retries. If the network is unavailable, logs accumulate in memory (or IndexedDB in the browser / a local file in Python) and are replayed automatically when connectivity is restored. A circuit breaker halts retry attempts during extended outages to conserve resources, and reopens the circuit automatically after a cool-down period.

### Edge Buffer Layer (Cold Start Shield)

The most critical architectural decision for serverless deployments is the insertion of an always-on edge buffer between the SDK and the serverless ingestor. This layer (deployed on Cloudflare Workers or a small Fly.io VM) accepts log batches in under 10ms globally, writes them to a Redis Stream for durability, and returns a `202 Accepted` immediately. The serverless ingestor then reads from the stream at its own pace. A cold-starting ingestor introduces queue lag, not data loss.

### Delivery Guarantee Tiers

Applications choose a delivery guarantee level per log level at SDK initialization time:

| Level | Mechanism | Survives |
|---|---|---|
| Best Effort | In-memory buffer only | Network blips |
| Persistent | In-memory + IndexedDB/file | App crash |
| Guaranteed | Persistent + Edge buffer + Redis Stream | Edge outage |

`ERROR` and `FATAL` logs default to Guaranteed. `DEBUG` logs default to Best Effort.

### Keeping Serverless Instances Warm

The SDK's background health-check pings a lightweight `/ping` endpoint on the ingestor every 30–60 seconds. This keeps at least one serverless instance warm for low-latency delivery during active application sessions. Provisioned concurrency can be added as a cost trade-off for high-traffic applications.

---

## Deployment

The full stack is deployable via Docker Compose on a single VM for development and small-scale production.

**Services**

- `api` — FastAPI ingestor service (Python 3.11, Uvicorn)
- `worker` — Redis Stream consumer that bulk-writes to ClickHouse
- `redis` — Redis 7 with `appendonly yes` for stream durability
- `clickhouse` — ClickHouse server with mounted data volume
- `edge` — Optional: Cloudflare Worker or lightweight Fly.io app for always-on buffering

**Recommended Hosting (Zero Cost Start)**

| Component | Provider | Cost |
|---|---|---|
| API + Worker | Oracle Cloud Free Tier (ARM VM) | $0 |
| ClickHouse | Self-hosted on same VM | $0 |
| Redis | Upstash free tier | $0 |
| Edge Buffer | Cloudflare Workers free tier | $0 |
| Archive Storage | Backblaze B2 (10GB free) | $0 |
| Monitoring | Grafana Cloud free tier | $0 |

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Ingestor API | FastAPI (Python) | Async, fast, auto-docs, easy deployment |
| Edge Buffer | Cloudflare Workers | No cold start, global, generous free tier |
| Message Queue | Redis Streams (Upstash) | Durable, ordered, consumer groups, cheap |
| OLAP Database | ClickHouse | Purpose-built for logs, columnar, TTL native |
| Archive Storage | Backblaze B2 / S3 | Cheapest object storage available |
| Monitoring | Grafana + ClickHouse datasource | Free, powerful, ClickHouse plugin available |
| Python SDK | Pure Python + `httpx` | Async-native HTTP, minimal dependencies |
| TypeScript SDK | Fetch API + Web Crypto | Zero dependencies in browser, tree-shakeable |
| Encryption | AES-256-GCM | Authenticated encryption, native in all envs |
| Key Hashing | bcrypt | Industry standard for secret hashing |

---

## Cost Model

| Scale | Monthly Cost |
|---|---|
| 0 – 500K logs/day | $0 (all free tiers) |
| 500K – 5M logs/day | ~$5–15 (Upstash + storage) |
| 5M – 50M logs/day | ~$30–80 (dedicated Redis + more VM) |
| 50M+ logs/day | ~$150+ (ClickHouse cluster, dedicated infra) |

---

## Scaling Path

LogStream scales in discrete steps, each requiring minimal operational change:

**Stage 1 — Single VM (0 to 1M logs/day)**
Everything runs on one Oracle Cloud VM via Docker Compose. ClickHouse handles this load comfortably on a single node.

**Stage 2 — Separate Services (1M to 10M logs/day)**
Split ingestor API and ClickHouse onto separate VMs. Add a second Redis replica. Deploy edge buffer to Cloudflare Workers if not already done.

**Stage 3 — Horizontal Ingestors (10M to 100M logs/day)**
Scale ingestor API horizontally behind a load balancer. ClickHouse remains single-node. Add ClickHouse replication for read replicas to offload dashboard queries from the write path.

**Stage 4 — ClickHouse Cluster (100M+ logs/day)**
Introduce ClickHouse sharding with `Distributed` table engine. Add Zookeeper or ClickHouse Keeper for replication coordination. This stage handles internet-scale log volumes.

At every stage, the SDK interface, the API contract, and the data schema remain unchanged. Applications require no modification as the infrastructure beneath them scales.

*This is an AI-generated readme*