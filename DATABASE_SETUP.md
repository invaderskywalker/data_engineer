# Database Setup Guide

Step-by-step to get a local PostgreSQL database running with all tables created.

---

## 1. Install PostgreSQL locally

**Mac (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Or use Docker (easiest):**
```bash
docker run -d \
  --name ai-data-engineer-db \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=admin \
  -e POSTGRES_DB=ai_data_engineer \
  -p 5432:5432 \
  postgres:15
```

---

## 2. Create your `.env`

```bash
cp .env.example .env
```

Edit `.env` with your local values:

```env
DB_NAME=ai_data_engineer
DB_USER=admin
DB_PASSWORD=admin
DB_HOST=localhost
DB_PORT=5432

OPENAI_KEY=sk-...

# Leave these blank for local dev — they are optional
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
MONGO_USER=
MONGO_PASSWORD=
MONGO_DATABASE=

ENVIRONMENT=dev
VECTORSTORE_ENDPOINT=http://localhost:8001
DJANGO_BACKEND_URL=http://localhost:8000/
```

---

## 3. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements/base.txt
pip install -r requirements/dev.txt
```

---

## 4. Run migrations

```bash
# Make sure you're in the project root (where alembic.ini lives)
cd ai_data_engineer

# Check alembic can connect and see pending migrations
alembic current

# Apply all migrations (creates all tables)
alembic upgrade head
```

You should see:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Initial tables for AI data engineer
```

---

## 5. Verify tables were created

```bash
# Connect to your local DB
psql -U admin -d ai_data_engineer

# List tables
\dt

# Should show:
#  agent_run_steps
#  agent_run_events
#  tango_states
#  tango_tangoconversations
#  tango_chattitles
#  tango_stats
#  tango_activitylog

\q
```

---

## Alembic cheat sheet

| Command | What it does |
|---------|-------------|
| `alembic upgrade head` | Apply all pending migrations |
| `alembic current` | Show which migration is currently applied |
| `alembic history` | List all migrations |
| `alembic downgrade -1` | Roll back the last migration |
| `alembic downgrade base` | Roll back everything |
| `alembic upgrade head --sql` | Preview SQL without applying |
| `alembic revision -m "add xyz table"` | Create a new blank migration |

---

## Adding a new table (workflow)

1. Create a new migration:
   ```bash
   alembic revision -m "add_my_new_table"
   ```

2. Edit the generated file in `alembic/versions/` — fill in `upgrade()` and `downgrade()`.

3. Apply it:
   ```bash
   alembic upgrade head
   ```

---

## Troubleshooting

**`connection refused` on port 5432**
→ PostgreSQL isn't running. Start it with `brew services start postgresql@15` or `docker start ai-data-engineer-db`.

**`role "admin" does not exist`**
→ Create the user first:
```bash
psql postgres -c "CREATE USER admin WITH PASSWORD 'admin';"
psql postgres -c "CREATE DATABASE ai_data_engineer OWNER admin;"
```

**`alembic: command not found`**
→ Your venv isn't activated. Run `source venv/bin/activate` first.

**`Missing required DB env vars`**
→ Your `.env` file is missing or `DB_NAME`/`DB_USER`/`DB_PASSWORD` are empty.
