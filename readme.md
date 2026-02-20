# Cloud Logging Microservice

A multi-tenant, cloud-native logging microservice built for high-frequency event ingestion, analytics, and observability across multiple applications. Designed with a zero-latency philosophy — your application never waits for logs.


## Overview

LogStream is a centralized logging microservice designed to be integrated across multiple independent applications via lightweight SDKs. It abstracts the complexity of log collection, transmission, storage, and querying behind a simple, developer-friendly interface while ensuring no log is ever lost and no application is ever slowed down by the act of logging.

The service is built around four core pillars: a standardized SDK using OpenTelemetry conventions, API-key-based multi-tenancy, a ClickHouse OLAP database for analytical storage, and a Redis-backed caching and batching layer to minimize database write pressure.


## Prerequisites

1. Setup `ClickHouse`
2. Setup `Redis`
3. Install `OpenTelemetry`
3. Install `.\requirements.txt`


# Flow
Log sent -> stores internal cache (until maybe 10 object) -> writes redis mini batch of max 100 log objects -> writes to clickhouse every 5mins.


# Methodology (Why?)