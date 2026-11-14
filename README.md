# Callside

Callside is a small, quiet copilot for a live cold call. It gives a caller an eight stage structure, common prospect reactions, a place to capture the prospect's words, a next step, and a recent call list. It does not record audio. A Gemini 3.5 Flash powered follow-up idea is optional; the flow works without an LLM key.

## Run locally

```sh
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal:

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Without Supabase credentials, call history is stored in the running API process and mirrored in the browser for local preview. The API uses Supabase when configured.

## Deploy on free tiers

1. Create a Supabase project and run [`supabase/schema.sql`](supabase/schema.sql) in its SQL Editor.
2. Create a public GitHub repository for this folder and push the project.
3. In Render, create a Web Service from the repository, set its root directory to `backend`, and use `render.yaml`. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `CORS_ORIGINS` in the Render environment. `CORS_ORIGINS` should include the exact Vercel origin. Add `GEMINI_API_KEY` to enable AI coaching.
4. In Vercel, import the same repository with root directory `frontend`. Set `VITE_API_URL` to the Render service URL (for example `https://callside-api.onrender.com`) and deploy.
5. Add the final Vercel origin to Render's `CORS_ORIGINS`, then redeploy the backend. Confirm `https://<render-host>/health` returns `{"status":"ok","service":"callside-api"}`.

Never add the Supabase service role key or Gemini key to Vercel's `VITE_` variables or commit them. Render free services can sleep when idle; the first request after inactivity may take longer. API history is shared across callers in this starter and does not include authentication; add user accounts and per-user row policies before using it with real prospect data.

## Submission checklist

- [ ] Public GitHub repository with source, SQL schema, and this README
- [ ] Vercel URL live and in this README
- [ ] Render base URL and `/health` endpoint in this README
- [ ] Six minute screen and camera walkthrough uploaded to Drive with link access
- [ ] Paste GitHub URL into assignment form, and Vercel, health, and video links into the WhatsApp message

### Decisions from the brief

- The guide covers the eight stages shown in the assignment's required reading: opening, permission, context, discovery, impact, fit, objections, and next step. The attached screenshots did not include the linked stage guide, reference screen, or 100 fictionalized transcripts, so the prompts and response examples here are a starter synthesis from the brief and common call patterns. Replace them with findings from those supplied materials before presenting the work as transcript informed.
- The stage is always visible, with purpose, a flexible opening prompt, common prospect reactions, a gentle tip, outcome controls, and an optional place for verbatim prospect language. This keeps glanceable guidance ahead of dense notes.
- Calls are saved on each stage transition, and the final screen is the call history with outcome and reached stage. A missed call can be reopened and continued.
- Gemini 3.5 Flash is called only when the caller requests a follow-up idea. Core functionality never depends on the model. The model is on Google's free tier according to the current [Gemini API pricing page](https://ai.google.dev/gemini-api/docs/pricing/).
