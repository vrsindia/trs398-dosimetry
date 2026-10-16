# DOSE pro – Supabase Free Tier Setup

## 1. Create a free Supabase project

1. Go to https://supabase.com and sign up / log in
2. **New project** → name e.g. `dosepro`
3. Set a database password (save it)
4. Pick a region near you
5. Wait until the project is ready

## 2. Create tables

1. Supabase → **SQL Editor** → **New query**
2. Open `supabase/schema.sql` from this GitHub repo
3. Copy all SQL → paste → **Run**
4. Check **Table Editor** for tables: machines, detectors, beams, etc.

## 3. Get API keys

1. **Project Settings** → **API**
2. Copy:
   - **Project URL** → use as `SUPABASE_URL`
   - **service_role** key (secret) → use as `SUPABASE_KEY`

Prefer **service_role** for this server-only app. Never put it in browser code.

## 4. Add keys on Render

Render → your web service → **Environment**:

| Key | Value |
|-----|--------|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` |
| `SUPABASE_KEY` | `eyJhbG...` (service_role) |

Save → wait for redeploy.

## 5. Verify

Open: `https://YOUR-APP.onrender.com/health`

Expect:

```json
{
  "status": "ok",
  "storage": { "mode": "supabase", "using_database": true }
}
```

If `mode` is `in-memory`, env vars are missing or wrong.

## Behaviour

| Mode | When | Survives restart? |
|------|------|-------------------|
| supabase | URL + KEY work | **Yes** |
| in-memory | keys missing / fail | **No** |

## Free tier

~500 MB DB — enough for single-clinic dosimetry data.
