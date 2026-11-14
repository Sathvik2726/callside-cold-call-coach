# Callside

Callside is a small, quiet copilot for the first call a Meridian Growth Partners caller makes to a business leader. It guides the caller through the assignment's eight stages, shows likely prospect reactions, captures the prospect's words at the need stage, and saves an outcome and next action. It does not record audio. A Gemini 3.5 Flash powered follow-up question is optional; the core flow works without an LLM key.

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

## Decisions from the readings and calls

- The guide follows the required order exactly: Opening, Purpose, Permission, Their business, Their need (in their words), Objection, Next step, and Close.
- I reviewed the 100 supplied transcripts. Calls frequently turn on basic context: who is calling, why this company, what Meridian does, and how the caller found the number. People also correct outdated role or company information, ask for a later time, request an email or WhatsApp report, or decline. The examples and four quick outcome taps at each stage reflect those patterns and are paraphrased rather than copied from the transcripts.
- The calls have many distinct end states. The post-call selector keeps “agreed to receive a report,” “next step agreed,” “interested,” and “follow-up” separate from “not interested,” “do not call,” “wrong person,” “moved company,” “call again,” and “not logged.” This helps avoid recording politeness as buying intent.
- A caller can glance at one purpose line, likely reactions, and four stage-specific taps. Only the need stage has a free-text box, for the prospect's exact words. Stages save as the caller moves forward; ending early still leads to a closeout where they can record a true outcome and next action.
- The LLM makes one optional, bounded contribution: a short follow-up question based on the stage and any note typed at that stage. The key stays in Render, and the screen calls the backend. Core call guidance does not depend on Gemini. Google's current [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing/) lists Gemini 3.5 Flash on a free tier.
