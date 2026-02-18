# LogStream — Logging Microservice

A multi-tenant, cloud-native logging microservice built for high-frequency event ingestion, analytics, and observability across multiple applications. Designed with a zero-latency philosophy — your application never waits for logs.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
  - [1. OpenTelemetry SDK Wrapper](#1-opentelemetry-sdk-wrapper)
  - [2. Multi-Tenant API Key Management](#2-multi-tenant-api-key-management)
  - [3. ClickHouse OLAP Database](#3-clickhouse-olap-database)
  - [4. Caching & Batching Layer](#4-caching--batching-layer)
- [Cold Start & Latency Handling](#cold-start--latency-handling)
- [Data Flow](#data-flow)
- [Storage & Retention](#storage--retention)
- [Security](#security)
- [Deployment](#deployment)

---

## Overview

LogStream is a centralized logging microservice designed to be integrated across multiple independent applications via lightweight SDKs. It abstracts the complexity of log collection, transmission, storage, and querying behind a simple, developer-friendly interface — while ensuring no log is ever lost and no application is ever slowed down by the act of logging.

The service is built around four core pillars: a standardized SDK using OpenTelemetry conventions, API-key-based multi-tenancy, a ClickHouse OLAP database for analytical storage, and a Redis-backed caching and batching layer to minimize database write pressure.

---

## Features

### 1. OpenTelemetry SDK Wrapper

The SDK is the primary integration point for client applications. Rather than building a proprietary protocol from scratch, LogStream wraps the OpenTelemetry (OTel) specification — the industry-standard observability framework — giving teams a familiar interface with production-grade semantics built in.

#### What It Does

The SDK wraps OTel's `Tracer`, `Meter`, and `Logger` primitives and exposes a simplified, opinionated API tailored for application-level event logging. Under the hood it maps log calls to OTel's semantic conventions so that data is always structured, queryable, and consistent across tenants.

#### Python SDK (Backend)

The Python SDK is designed for server-side applications including FastAPI, Django, Flask, and standalone scripts. It operates in two modes: synchronous and asynchronous. In both modes, the call to `logger.info()` or `logger.error()` returns immediately — actual transmission happens in a background thread managed by the SDK.

Key behaviors include automatic context propagation (attaching trace IDs, span IDs, and service names to every log), structured attribute capture (arbitrary key-value pairs appended to any log entry), local in-memory buffering with configurable flush intervals, graceful shutdown handling to flush remaining logs on `SIGTERM`, and built-in retry logic with exponential backoff on transient network failures.

#### TypeScript / React SDK (Frontend)

The TypeScript SDK targets both browser and Node.js environments. In the browser, it uses `navigator.sendBeacon()` for page unload events to guarantee a final delivery attempt, and a Service Worker for background batched transmission during normal usage. It also integrates with React via a custom hook (`useLogger`) that scopes logging to a component's lifecycle and automatically captures route changes, user interactions, and page visibility events.

Custom attributes like `time_spent_on_page`, `component_render_ms`, or `ab_test_variant` are passed as plain objects and forwarded to ClickHouse's dynamic `Map` column without requiring any schema changes.

#### SDK Design Principles

The SDK enforces a strict fire-and-forget contract. Application code calls a logging method and continues executing in the same tick. The SDK maintains an internal priority queue where `ERROR` and `FATAL` logs are flushed immediately, while `DEBUG` and `INFO` logs are batched over a configurable time window (default: 5 seconds or 100 entries, whichever comes first). This ensures critical events are captured with minimal delay while routine telemetry does not saturate the network.

---

### 2. Multi-Tenant API Key Management

Every application that integrates with LogStream is issued API keys to authenticate its log streams. The control plane for key management is backed by PostgreSQL, chosen for its ACID guarantees, mature ecosystem, and suitability for transactional metadata storage — a different concern from the high-frequency analytical writes handled by ClickHouse.

#### Key Structure

API keys follow a structured format that encodes environment and application identity directly in the key string:

```
app_{app_id}_{env}_{random_32_chars}
Example: app_ecommerce_live_a7f3k9...
```

This makes it immediately clear during debugging which application and environment a key belongs to, without needing a database lookup.

#### What PostgreSQL Stores

The PostgreSQL schema holds the full lifecycle of every API key: the key hash (bcrypt, never the raw key), the associated `app_id`, creation and expiry timestamps, per-key rate limits, permission scopes (e.g., write-only vs. read-write), and revocation status. It also stores the application registry — a record of every tenant, their assigned ClickHouse partition prefix, and their retention configuration.

#### Multi-Tenancy Isolation

Each API key is bound to exactly one `app_id`. At the ingestion API, every incoming log payload is tagged with the `app_id` derived from the authenticated key before it is forwarded to the queue. ClickHouse enforces tenant isolation at the storage layer via the `app_id` column in the primary key sort order, meaning all queries are partitioned by tenant at the physical data level. One tenant can never accidentally read or affect another's data.

#### App Monitoring

The control plane exposes a lightweight dashboard that surfaces per-app ingestion rates, error rates, key usage, and quota consumption. Rate limiting is enforced at the API layer using a Redis sliding window counter keyed on `app_id`. If an application exceeds its configured requests-per-minute, the API returns `429 Too Many Requests` and the SDK queues the rejected batch for retry.

---

### 3. ClickHouse OLAP Database

ClickHouse is the analytical backbone of LogStream. It is a columnar, append-only OLAP database purpose-built for the exact workload logging generates: extremely high write throughput, time-series queries over large datasets, and aggregations across millions of rows in milliseconds.

#### Why ClickHouse

Traditional relational databases like PostgreSQL struggle under the write pressure of production logging. ClickHouse's columnar storage engine compresses repetitive log data (level strings, app IDs, status codes) aggressively — typically 10–20x compression ratios — and its `MergeTree` engine is optimized for ordered, append-only time-series data. Query performance on analytical operations (e.g., "count all errors for app X in the last 24 hours grouped by endpoint") is orders of magnitude faster than row-oriented databases.

#### Schema Design

The core logs table uses a `MergeTree` engine partitioned by month (`toYYYYMM(timestamp)`) and ordered by `(app_id, timestamp)`. This ordering means ClickHouse reads only the relevant tenant's data for any query. An `INDEX` on `(app_id, timestamp)` using `minmax` granularity further prunes unnecessary data blocks during scans.

Log attributes — custom key-value pairs like `page_duration_ms`, `feature_flag`, or any future field — are stored in a `Map(String, String)` column. This is the auto-scaling attribute mechanism: no schema migrations, no ALTER TABLE statements, no downtime. Any new attribute key sent by the SDK appears automatically in queries the next time it is logged.

#### TTL and Data Lifecycle

ClickHouse's native TTL feature handles the 2–3 month retention window automatically. A TTL expression on the `timestamp` column deletes rows older than 90 days during background merge operations. For cold archival beyond 90 days, ClickHouse's `TTL ... TO DISK` feature can offload older partitions to S3-compatible object storage (MinIO or AWS S3) transparently, keeping query interfaces unchanged while moving cold data off expensive SSD storage.

#### Storage Tiers

| Tier | Age | Storage Medium | Purpose |
|---|---|---|---|
| Hot | 0 – 7 days | SSD | Fast queries, dashboards |
| Warm | 7 – 60 days | HDD | Historical queries |
| Cold | 60 – 90 days | ClickHouse + S3 | Retention compliance |
| Archive | 90+ days | S3 / MinIO | Long-term audit |

---

### 4. Caching & Batching Layer

Sending every individual log event directly to ClickHouse as it arrives is inefficient and unnecessary. ClickHouse performs best with large, ordered batch inserts rather than thousands of tiny single-row writes. The caching and batching layer, built on Redis, acts as a shock absorber between the ingestion API and the database.

#### Redis Streams as the Buffer

Every log event accepted by the ingestion API is written to a Redis Stream rather than directly to ClickHouse. Redis Streams are an append-only, persistent data structure with consumer group semantics — similar to a lightweight Kafka topic. They offer microsecond write latency, at-least-once delivery guarantees, and native replay capability for handling consumer failures.

The stream is configured with persistence (`appendonly yes`) so that a Redis restart does not lose buffered logs. Messages are retained in the stream for a configurable window (default: 30 minutes) after acknowledgement, enabling replay if the ClickHouse consumer encounters errors.

#### Batch Aggregation Worker

A pool of background workers (Consumer Group) reads from the Redis Stream and aggregates incoming log events into batches. A batch is flushed to ClickHouse when either of two conditions is met: a configurable batch size threshold is reached (default: 500 events) or a time window elapses (default: 3 seconds). This dual-trigger ensures that both high-traffic applications (flush by volume) and low-traffic applications (flush by time) are handled gracefully.

Workers use ClickHouse's native batch insert API (`INSERT INTO logs VALUES (...)` with multiple rows per statement), which is significantly more efficient than individual inserts and aligns with ClickHouse's internal merge scheduling.

#### API-Level Caching

For read operations — such as querying recent logs or fetching aggregated metrics for a dashboard — the API layer uses Redis as a short-lived result cache. ClickHouse query results for common dashboard queries (e.g., error counts per app per hour) are cached for 60 seconds, preventing repeated full scans under dashboard polling. Cache keys are namespaced by `app_id` to ensure tenant isolation.

#### Benefits of This Approach

The batching layer decouples ingestion rate from write rate. During traffic spikes, the Redis buffer absorbs the load while workers drain it at a steady, optimal pace for ClickHouse. During low-traffic periods, the time-based flush ensures logs still arrive in ClickHouse within seconds. The result is consistently low write amplification on ClickHouse and a database that operates near its optimal throughput regardless of inbound traffic patterns.

---

## Cold Start & Latency Handling

Since the ingestion API may run on serverless infrastructure, two failure modes must be addressed: cold start delays causing data loss, and async logging adding latency to the calling application.

### Fire-and-Forget Contract

The SDK enforces a strict contract: `logger.info()` returns in under 1 millisecond. The application never awaits network confirmation of log delivery. All transmission happens in a background worker thread or browser Service Worker, completely outside the application's critical path.

### Client-Side Durability

The SDK maintains a local buffer (in-memory for servers, IndexedDB for browsers) that persists undelivered logs across network failures and cold start delays. If the ingestion API is cold and takes 2–5 seconds to respond, those logs are not lost — they are held in the buffer and retried with exponential backoff once the instance is warm.

### Edge Warm Buffer

A lightweight always-on edge layer (Cloudflare Workers or a minimal Fly.io instance) sits in front of the serverless function. This layer accepts log payloads in under 10ms globally, writes them immediately to an Upstash Redis queue, and acknowledges the SDK. The serverless consumer then drains the queue at its own pace, cold starts notwithstanding. This architecture means cold starts are invisible to log producers.

### Priority-Based Flushing

The SDK's internal queue assigns priority to log levels. `ERROR` and `FATAL` events bypass batching and are transmitted immediately. `WARN` events are flushed within 1 second. `INFO` and `DEBUG` events are batched over the standard 5-second window. This ensures critical events reach storage quickly while routine telemetry is handled efficiently.

---

## Data Flow

```
1. App calls logger.error("Payment failed", {user_id: "123", amount: 99.99})
2. SDK returns immediately (<1ms)
3. Background worker picks up the log from local buffer
4. Worker encrypts sensitive fields with AES-256
5. Worker batches with other pending logs (up to 100 or 5 seconds)
6. Batch is sent via HTTPS to the Edge Buffer
7. Edge Buffer acknowledges and writes to Redis Stream
8. ClickHouse Consumer Worker reads from Redis Stream
9. Consumer aggregates into a 500-event batch
10. Batch is inserted into ClickHouse in a single statement
11. ClickHouse merges, compresses, and indexes the data
12. Data is queryable within ~3–5 seconds of original log call
```

---

## Storage & Retention

Retention is configured per application at the tenant level. The default policy retains logs for 90 days in ClickHouse with monthly partitioning. Dropping a partition (e.g., all logs from 3 months ago) is a near-instant metadata operation in ClickHouse — no expensive DELETE scans required.

For compliance use cases requiring longer retention, partitions older than 90 days are offloaded to S3/MinIO in ClickHouse's native binary format. These archived partitions can be reattached to ClickHouse on-demand for historical queries without requiring a separate ETL pipeline.

---

## Security

All log payloads in transit are encrypted via TLS. Sensitive fields within log payloads (e.g., email addresses, tokens, PII flagged by the SDK) are additionally encrypted with AES-256-GCM before leaving the client, using a per-tenant encryption key stored in the server's secret manager. The ClickHouse `encrypted_payload` column stores these pre-encrypted blobs. Decryption happens at query time, server-side, only for authorized API key holders.

API keys are stored as bcrypt hashes in PostgreSQL. The raw key is shown only once at creation time and is never recoverable from the database. Key rotation is a first-class operation: new keys can be issued and old keys revoked without any downtime or reconfiguration of the ClickHouse schema.

---

## Deployment

The entire stack is designed to run on zero-cost or minimal-cost infrastructure for early-stage usage:

| Component | Free Option | Paid Upgrade Path |
|---|---|---|
| Ingestion API | Railway / Render free tier | Dedicated VPS |
| Redis Streams | Upstash free tier | Upstash Pro / self-hosted |
| ClickHouse | Oracle Cloud Free Tier (24GB RAM) | ClickHouse Cloud |
| PostgreSQL | Supabase free tier | Railway managed Postgres |
| Cold Storage | Backblaze B2 / Cloudflare R2 (10GB free) | AWS S3 |
| Edge Buffer | Cloudflare Workers (100K req/day free) | Cloudflare Workers Paid |

As volume grows, each layer scales independently. ClickHouse can be sharded horizontally. Redis can be clustered. The ingestion API can run behind a load balancer with multiple instances. None of these scaling steps require changes to the SDK or the tenant's integration code.

---

*LogStream is designed to be invisible to the applications it observes — fast to integrate, zero overhead to run, and always there when you need to understand what your systems are doing.*