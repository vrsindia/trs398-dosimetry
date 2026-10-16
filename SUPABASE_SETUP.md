# DOSE pro – Supabase Free Tier Setup

## 1. Create a free Supabase project

1. Go to https://supabase.com and sign up / log in  
2. **New project** → choose a name (e.g. `dosepro`)  
3. Set a database password (save it)  
4. Region: pick closest to you  
5. Wait until the project is ready  

## 2. Create tables

1. In Supabase: **SQL Editor** → **New query**  
2. Copy the full contents of `supabase/schema.sql` from this repo  
3. Paste and click **Run**  
4. Confirm tables appear under **Table Editor**  

## 3. Get API keys

1. **Project Settings** → **API**  
2. Copy:
   - **Project URL** → `SUPABASE_URL`  
   - **service_role** key (secret) → `SUPABASE_KEY`  

   Prefer **service_role** for this server-only app (bypasses RLS).  
   Never put service_role in browser code.  

## 4. Add keys on Render

1. Open your Render web service  
2. **Environment** → **Add Environment Variable**  

| Key | Value |
|-----|--------|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` |
| `SUPABASE_KEY` | `eyJ...` (service_role) |

3. **Save** → service will redeploy  

## 5. Verify

Open: `https://your-app.onrender.com/health`  

You should see something like:

```json
{
  "status": "ok",
  "app": "DOSE pro",
  "storage": {
    "mode": "supabase",
    "using_database": true
  }
}
```

If `mode` is still `in-memory`, check the env vars and Render logs.  

## 6. Behaviour

| Mode | When | Data survives restart? |
|------|------|-------------------------|
| **supabase** | URL + KEY set and connection works | **Yes** |
| **in-memory** | Keys missing or connection fails | **No** |

After Supabase is connected, detectors, machines, beams, tolerances, output history, reports, users, and department details are stored in PostgreSQL on the free tier.  

## Free tier limits (approximate)

- 500 MB database  
- 1 GB file storage  
- Enough for a single-clinic dosimetry app  

## Security note

This app uses server-side keys only. Do not expose `SUPABASE_KEY` in the frontend or a public repo secrets file. Set keys only in Render Environment.  
"}, {