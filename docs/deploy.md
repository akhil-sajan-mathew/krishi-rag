# Deploying Krishi RAG

The production stack is four containers on one Linux server, started with Docker Compose:

| Container | Role | Reachable from the internet? |
|---|---|---|
| `caddy` | HTTPS (automatic Let's Encrypt certificates), forwards requests to the API | Yes, ports 80 and 443 |
| `api` | FastAPI app, with both ML models baked into the image | No, only through Caddy |
| `db` | Postgres 16 with pgvector | No |
| `redis` | Answer cache and rate limit | No |

It runs on any Linux server with Docker. The steps below use AWS Lightsail; EC2 or any other VPS works the same way.

## 1. Server

- **Size:** at least **2 GB RAM** (the two models and PyTorch use about 1 GB). On Lightsail, the 2 GB Linux plan. Add swap if you use less.
- **OS:** Ubuntu 24.04 LTS.
- **Firewall:** open ports **22** (SSH), **80** and **443**. Nothing else.
- **Disk:** about 6 GB free for the image (~2.5 GB), database and PDFs.

Install Docker:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # then log out and back in
```

## 2. Domain

Caddy needs a domain name pointing at the server to get an HTTPS certificate. Create an **A record** for your domain (or a free subdomain, for example from DuckDNS) pointing at the server's public IP. Wait until `ping your.domain` shows that IP.

## 3. Configure

```bash
git clone https://github.com/akhil-sajan-mathew/krishi-rag.git
cd krishi-rag
cp .env.example .env
nano .env
```

Set at least:

| Setting | Value |
|---|---|
| `DOMAIN` | your domain, e.g. `krishi.example.com` |
| `POSTGRES_PASSWORD` | a long random password (`openssl rand -hex 24`). It is applied only when the database is first created. |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY` | your LLM provider (see the README) |
| `RATE_LIMIT_PER_HOUR` | questions per visitor per hour (default 20) |

`DATABASE_URL` and `REDIS_URL` in `.env` are ignored in production; the compose file points the API at the `db` and `redis` containers.

Keep `.env` private: `chmod 600 .env`. Also set a monthly spending limit at your LLM provider; that is the backstop if the rate limit is ever bypassed.

## 4. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The first build takes several minutes (PyTorch and the models). Check that all four containers are running:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

## 5. Load the documents (once)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm -v ./data:/app/data api \
  sh -c "python scripts/download.py && python -m app.ingest"
```

This downloads the PDFs listed in `data/sources.csv` into `data/raw/` on the server and loads about 1,300 chunks into Postgres. It takes a few minutes on a small server.

## 6. Check it

```bash
curl https://your.domain/health      # {"db":"ok","redis":"ok"}
```

Then open `https://your.domain` in a browser and ask a question.

## Updating

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Database contents and HTTPS certificates are kept in Docker volumes, so they survive updates and restarts. Re-run step 5 only if `data/sources.csv` changes.

## Logs and troubleshooting

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api caddy
```

- **Caddy can't get a certificate:** the domain doesn't point at this server yet, or ports 80/443 are closed.
- **`/health` says `"redis": "down"`:** the app keeps working without caching or rate limiting; restart the `redis` container.
- **503 "LLM unavailable":** check the `LLM_*` settings, the key, and the provider's limits.
- **Out of memory:** use a 2 GB server or add swap.

## Testing the production stack locally

With Docker Desktop, set `DOMAIN=localhost` in `.env` and run steps 4 and 6. Caddy then uses its own local certificate, so use `curl -k https://localhost/health`.
