# Deployment Guide

This document maps the deployment journey from a quick E2E check to a production-grade setup,
aligned with the roadmap in [TODO.md](TODO.md). Each stage builds on the previous one, so you
can stop at any point that fits the current development phase.

## Stack recap

The full stack requires five concerns to be served:

| Concern | Component |
|---|---|
| API server | FastAPI (Uvicorn) |
| Background worker | ARQ |
| Relational DB | PostgreSQL |
| Cache / queue broker | Redis |
| Migrations | Alembic (run-once job) |

All five are already wired in `docker-compose.yml`, which is the unit of deployment across every
stage below.

---

## Stage 1: Light deployment (E2E smoke testing)

**Goal:** get the whole stack online quickly to verify the payment flow, async worker, and
stats endpoint work end-to-end. No production hardening needed yet.

### Option A: Railway (recommended starting point)

Railway provides first-class Postgres and Redis plugins and deploys straight from GitHub.

**Setup (roughly 1 hour):**

1. Create a Railway project and add a **Postgres** plugin and a **Redis** plugin.
2. Add two services from the repo:
   - `web`: start command `uv run uvicorn deep_ice:app --host 0.0.0.0 --port 80`
   - `worker`: start command `uv run arq deep_ice.TaskQueue`
3. Copy env vars from `.env.template`; Railway injects `DATABASE_URL` and `REDIS_URL`
   automatically from the plugins -- map them to your `POSTGRES_*` / `REDIS_HOST` vars in the
   service config.
4. Add a one-off migration deploy command (`alembic upgrade head`) as a pre-deploy hook or a
   third service that exits after running.

**Cost:**

| Resource | Free tier | Paid |
|---|---|---|
| Web service | $5/month credit (covers light usage) | ~$5-10/month |
| Worker service | included in credit | ~$5/month |
| Postgres plugin | included in credit | ~$5/month |
| Redis plugin | included in credit | ~$5/month |
| **Total (light)** | **~$0 under credit** | **~$20/month** |

**Tradeoffs:**
- Pro: minimal config, no new files needed, HTTPS out of the box.
- Pro: same Docker image used locally; no portability risk.
- Con: free tier sleeps idle services (~10-30 s cold start).
- Con: not AWS/GCP -- no path to enterprise infra from here.

---

### Option B: AWS Lightsail (cheap VPS, stepping stone to AWS)

A single `$5/month` Lightsail instance runs the full `docker-compose.yml` stack as-is. No
managed services, no IAM complexity.

**Setup (roughly 2 hours):**

1. Launch a Lightsail instance (Ubuntu, $5/month tier: 1 vCPU, 1 GB RAM).
2. SSH in, install Docker + Compose, clone the repo.
3. `cp .env.template .env`, fill in secrets, `docker compose up -d`.
4. Open port 80 in the Lightsail firewall rules.

**Cost:**

| Resource | Price |
|---|---|
| Lightsail instance ($5 tier) | $5/month |
| Static IP | free while attached |
| **Total** | **$5/month** |

**Tradeoffs:**
- Pro: cheapest AWS option; one monthly line item.
- Pro: identical to local `docker compose` -- zero config delta.
- Con: single point of failure; no auto-restart on crash (add a systemd unit or `restart: always` in compose).
- Con: all services share 1 GB RAM -- tight once Sentry/Grafana sidecars are added.
- Con: manual OS patching.

---

## Stage 2: Observability layer (Sentry + Grafana)

Add these once the app is stable on Stage 1. Both can run as extra services in the same compose
file or as external SaaS.

### Sentry (error tracking)

**SaaS (recommended for small teams):**

- Sentry.io free tier: 5,000 errors/month, 10,000 performance events.
- Add `sentry-sdk[fastapi]` to deps, configure `SENTRY_DSN` env var, call `sentry_sdk.init()` in
  `deep_ice/__init__.py`.
- Cost: **$0** on free tier, **$26/month** (Team) when you outgrow it.

**Self-hosted (Lightsail/Railway sidecar):**

- Official Sentry Docker compose needs ~4 GB RAM minimum -- not viable on a $5 Lightsail instance.
- Requires a separate $20-40/month instance.
- Only worth it at scale where SaaS pricing becomes significant. Avoid for now.

### Grafana (metrics + dashboards)

The TODO calls out Prometheus + Grafana for system and app metrics.

**Option 1: Grafana Cloud (SaaS)**

- Free tier: 10,000 metrics series, 50 GB logs, 14-day retention.
- Add `prometheus-fastapi-instrumentator` to expose `/metrics`; point a Grafana Cloud agent
  (runs as a sidecar) at it.
- Cost: **$0** on free tier, **$29/month** (Pro) for higher retention/volume.

**Option 2: Self-hosted Prometheus + Grafana in compose**

- Add two more services to `docker-compose.yml`: `prometheus` and `grafana`.
- Works fine on a $10/month Lightsail instance (2 GB RAM).
- Cost: **$0 software** + instance cost delta (~$5/month upgrade from $5 to $10 tier).

**Tradeoffs (SaaS vs self-hosted):**

| | SaaS | Self-hosted |
|---|---|---|
| Setup time | 30 min | 2-4 hours |
| Maintenance | none | you manage upgrades |
| Data locality | vendor servers | your instance |
| Cost at low volume | free | instance cost only |
| Cost at high volume | $29-100+/month | flat instance cost |

For Stage 2 the pragmatic path is: **Sentry SaaS (free tier) + Grafana Cloud (free tier)**. Zero
infra overhead, covers the roadmap items, revisit self-hosting if volume justifies it.

### Logstash + Elasticsearch + Kibana (ELK)

The TODO lists Logstash/Elasticsearch/Kibana for log aggregation. These are expensive to
self-host (ELK needs 4-8 GB RAM minimum across three services).

**Recommended alternative: Elastic Cloud or Grafana Loki**

- **Elastic Cloud** free trial (14 days), then $95+/month -- only viable at production scale.
- **Grafana Loki** (via Grafana Cloud free tier): drop-in log aggregation, works with the same
  Grafana instance above. Send structured logs from FastAPI via `python-logging-loki` or a
  Promtail sidecar.
- Cost: **$0** on Grafana Cloud free tier, same paid tier as Grafana above.

For the roadmap intent (store logs, query them), **Loki covers it at no extra cost** if Grafana
Cloud is already in use. Defer full ELK unless there's a specific Elasticsearch query use case.

---

## Stage 3: Production on AWS (ECS Fargate)

When you need reliability, auto-scaling, and a path to enterprise infra.

**Architecture:**

- **ECR**: store Docker images built by CI.
- **ECS Fargate**: two task definitions -- `web` (FastAPI) and `worker` (ARQ). No EC2 to manage.
- **RDS Postgres** (t3.micro, free tier for 12 months, then ~$15/month).
- **ElastiCache Redis** (cache.t3.micro, ~$12/month, no free tier).
- **ALB**: HTTPS termination + routing (~$16/month).
- **Secrets Manager**: env vars / DB credentials.

**Rough cost (post-free-tier, minimal sizing):**

| Service | Monthly |
|---|---|
| ECS Fargate (web + worker, ~0.25 vCPU / 0.5 GB each) | ~$15 |
| RDS Postgres (t3.micro, single-AZ) | ~$15 |
| ElastiCache Redis (t3.micro) | ~$12 |
| ALB | ~$16 |
| ECR storage | ~$1 |
| **Total** | **~$60/month** |

**Tradeoffs vs Lightsail:**
- Pro: auto-scaling, rolling deploys, no single point of failure.
- Pro: native integration with CloudWatch (logs/metrics) -- can replace Grafana Cloud if already
  on AWS.
- Con: ~1 day of setup (VPC, IAM roles, task definitions, target groups).
- Con: ~$60/month baseline vs $5 on Lightsail.
- Con: ELK/Sentry still external SaaS unless you add more AWS services.

**CI/CD bridge:** extend `.github/workflows/ci.yml` with a deploy step that builds the image,
pushes to ECR, and triggers a new ECS deployment via `aws ecs update-service`.

---

## Recommended journey

```
Stage 1a: Railway (today)
  → E2E smoke test, zero config overhead, ~$0

Stage 1b: AWS Lightsail ($5/month)
  → If you want everything on AWS from the start
  → Same docker-compose.yml, SSH + deploy

Stage 2: Add SaaS observability (Sentry free + Grafana Cloud free)
  → Covers Sentry, Grafana, and Loki (replaces ELK) from the TODO
  → ~$0 until volume forces an upgrade

Stage 3: AWS ECS Fargate (~$60/month)
  → When uptime, auto-scaling, or compliance matter
  → CI pushes to ECR, ECS rolls out
```

None of these stages requires rewriting the app. The `docker-compose.yml` and the `Dockerfile`
work as-is through Stage 1 and Stage 2. Stage 3 is purely infrastructure configuration.
