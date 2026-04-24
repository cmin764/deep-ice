# Deployment Guide

This document maps the deployment journey from a quick E2E check to a production-grade setup,
aligned with the roadmap in [TODO.md](TODO.md). Each stage builds on the previous one, so you
can stop at any point that fits the current development phase. See the [README](../README.md) for
the system architecture diagram.

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

### Option B: AWS free tier (EC2 + RDS, 12 months)

The AWS free tier covers everything except managed Redis. The strategy is to run the app,
worker, and Redis together on a single EC2 instance (exactly like `docker-compose.yml` does
locally), and point Postgres at a free RDS instance so the database is managed separately.

**What's free (12-month free tier on a new AWS account):**

| Service | Free allowance |
|---|---|
| EC2 t2.micro | 750 hrs/month (enough for one always-on instance) |
| RDS Postgres t2.micro | 750 hrs/month + 20 GB storage + 20 GB backups |
| ECR | 500 MB/month storage |
| Data transfer out | 1 GB/month |

**ElastiCache has no free tier.** Run Redis as a container on the EC2 instance instead -- the
existing `docker-compose.yml` already does this, so no changes needed. For higher reliability,
[Upstash](https://upstash.com) offers a permanent free tier (10,000 commands/day, 256 MB) as a
drop-in replacement -- just swap `REDIS_HOST` for the Upstash endpoint.

**Setup (roughly 3 hours):**

1. Launch an EC2 t2.micro (Ubuntu, 1 vCPU, 1 GB RAM). Assign an Elastic IP (free while attached).
2. Launch an RDS Postgres t2.micro in the same VPC. Set the security group to allow the EC2
   instance on port 5432 only.
3. SSH into EC2, install Docker + Compose, clone the repo.
4. `cp .env.template .env` -- set `POSTGRES_SERVER` to the RDS endpoint, leave `REDIS_HOST`
   pointing at `localhost` (Redis runs in a container on the same instance).
5. Remove the `db` service from `docker-compose.yml` (RDS replaces it). Keep `redis`, `app`,
   `worker`, and `alembic`.
6. `docker compose up -d`. Open port 80 (and 443 if adding TLS) in the EC2 security group.

**Cost:**

| Resource | Free tier (months 1-12) | After free tier |
|---|---|---|
| EC2 t2.micro | $0 | ~$8/month |
| RDS Postgres t2.micro | $0 | ~$15/month |
| Redis (in container) | $0 | $0 |
| Elastic IP | $0 while attached | $0 while attached |
| **Total** | **$0** | **~$23/month** |

**Tradeoffs:**
- Pro: fully on AWS, zero cost for 12 months -- ideal for learning the platform.
- Pro: RDS gives managed backups and minor version upgrades without touching the instance.
- Pro: after 12 months, upgrade to Lightsail ($5/month) or ECS without changing the app.
- Con: Redis and the app share 1 GB RAM on t2.micro -- monitor memory usage; add a swap file as
  a safety net (`fallocate -l 1G /swapfile`).
- Con: single EC2 instance is still a single point of failure; `restart: always` in compose
  handles crashes but not instance failure.
- Con: manual OS patching on the EC2 instance.

---

### Option C: AWS Lightsail (cheap VPS, post-free-tier fallback)

Once the 12-month free tier expires, Lightsail is the cheapest way to stay on AWS without moving
to managed services. A single `$5/month` instance runs the full `docker-compose.yml` as-is.

**Cost:**

| Resource | Price |
|---|---|
| Lightsail instance ($5 tier, 1 vCPU / 1 GB RAM) | $5/month |
| Static IP | free while attached |
| **Total** | **$5/month** |

**Tradeoffs:**
- Pro: one monthly line item, no IAM complexity.
- Pro: identical to local `docker compose` -- zero config delta.
- Con: all services share 1 GB RAM (same constraint as the free-tier EC2 path above).
- Con: no managed DB -- Postgres runs in a container, so backups are your responsibility.

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

## Continuous deployment

CI already runs on every PR and push to `main` via `.github/workflows/ci.yml`. The steps below
extend it with a deploy job that fires only on pushes to `main` (i.e. after a PR merges).

### Stage 1: Railway

Railway auto-deploys on every push to the connected branch by default -- no extra workflow
needed. To trigger it explicitly from CI (e.g. to enforce deploy only after all checks pass):

```yaml
deploy:
  needs: checks
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Trigger Railway deploy
      run: |
        curl -X POST "${{ secrets.RAILWAY_DEPLOY_WEBHOOK }}"
```

Set `RAILWAY_DEPLOY_WEBHOOK` in GitHub repo secrets (available in the Railway service settings).

### Stage 1b: AWS EC2 (SSH + docker compose pull)

The simplest CD for an EC2 instance: SSH in, pull the new image, restart compose. This assumes
the image is pushed to a registry (ECR or Docker Hub) as part of the workflow.

```yaml
deploy:
  needs: checks
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ secrets.AWS_REGION }}

    - name: Login to ECR
      id: ecr-login
      uses: aws-actions/amazon-ecr-login@v2

    - name: Build and push image
      env:
        ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
        IMAGE_TAG: ${{ github.sha }}
      run: |
        docker build -t $ECR_REGISTRY/deep-ice:$IMAGE_TAG .
        docker push $ECR_REGISTRY/deep-ice:$IMAGE_TAG
        echo "IMAGE=$ECR_REGISTRY/deep-ice:$IMAGE_TAG" >> $GITHUB_ENV

    - name: Deploy to EC2
      uses: appleboy/ssh-action@v1
      with:
        host: ${{ secrets.EC2_HOST }}
        username: ubuntu
        key: ${{ secrets.EC2_SSH_KEY }}
        script: |
          cd ~/deep-ice
          IMAGE=${{ env.IMAGE }} docker compose pull app worker
          docker compose up -d --no-deps app worker
          docker compose run --rm alembic
```

Required GitHub secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`,
`EC2_HOST`, `EC2_SSH_KEY`.

The `alembic` service runs migrations after each deploy. If a migration fails, the old
containers are already replaced -- add a health check or blue/green swap if zero-downtime
migrations matter at this stage.

### Stage 3: AWS ECS Fargate

ECS deployments replace the SSH step with a service update. After pushing to ECR:

```yaml
    - name: Deploy to ECS
      run: |
        aws ecs update-service \
          --cluster deep-ice \
          --service web \
          --force-new-deployment
        aws ecs update-service \
          --cluster deep-ice \
          --service worker \
          --force-new-deployment
```

ECS pulls the new image tag, drains the old tasks, and starts the new ones. Migrations are best
run as a separate ECS task (one-off run) before the service update, using the same image.

---

## Recommended journey

```
Stage 1a: Railway (today, ~$0)
  → Fastest E2E smoke test, no AWS account needed
  → Vercel for Next.js frontend (free, permanent)

Stage 1b: AWS free tier -- EC2 t2.micro + RDS Postgres ($0 for 12 months)
  → Best option if the goal is learning AWS
  → Redis runs in a container on EC2; Upstash as a free managed alternative
  → Same docker-compose.yml with the db service swapped for RDS

Stage 1c: AWS Lightsail ($5/month, post-free-tier)
  → Cheapest way to stay on AWS after the 12-month free tier expires
  → Full docker-compose.yml, no config changes

Stage 2: Add SaaS observability (~$0)
  → Sentry.io free tier: error tracking, 5k errors/month
  → Grafana Cloud free tier: metrics (Prometheus) + logs (Loki, replaces ELK)
  → Both are permanent free tiers, not 12-month limited

Stage 3: AWS ECS Fargate (~$60/month)
  → When uptime, auto-scaling, or compliance matter
  → CI pushes image to ECR, ECS rolls out automatically
  → CloudWatch can replace Grafana Cloud if already deep in AWS
```

None of these stages requires rewriting the app. The `docker-compose.yml` and `Dockerfile` work
as-is through Stages 1 and 2. Stage 3 is purely infrastructure configuration.
