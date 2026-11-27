# Deploying ExoSignal

One backend platform (Fly.io, Docker) and one frontend platform (Vercel, static build).
Nothing here has been deployed yet; follow the steps in order and record the URLs you get.

## 0. Before you start

- Install `flyctl` and run `fly auth login`. Fly bills machine time; check current pricing on fly.io before
  deploying. `backend/fly.toml` sets `min_machines_running = 0` (no cost while idle, but a cold start on the
  first request). While you are job-hunting, consider `1` so the first click is fast.
- A Vercel account connected to your GitHub repository.
- The artifact `backend/artifacts/<active_version>/planets.parquet` is stored with Git LFS. Run
  `git lfs pull` locally and check `ls -l backend/artifacts/*/planets.parquet` shows megabytes, not a
  ~130-byte pointer: `fly deploy` uploads your local files as the build context.

## 1. Backend on Fly.io

```bash
cd backend
# fly.toml says app = "exosignal-backend"; app names are global, so pick your own and edit fly.toml
fly apps create <your-backend-app>
fly deploy
curl -s https://<your-backend-app>.fly.dev/ready
```

The image needs only `PORT` (set), `CORS_ORIGINS` (step 3) and an artifact (baked into the image from
`backend/artifacts/active_version.txt`). Until step 3, CORS defaults to `["*"]` (the Dockerfile default).

## 2. Frontend on Vercel

1. Vercel dashboard: Add New Project, import the GitHub repository. Keep the root directory as the
   repository root (`vercel.json` builds `frontend/` and serves `frontend/dist`).
2. Environment variable (Production): `VITE_API_URL = https://<your-backend-app>.fly.dev/api/v1`.
   The build fails on purpose if it is missing (see `frontend/vite.config.js`).
3. Deploy, and note the production URL, e.g. `https://<your-frontend>.vercel.app`.

## 3. Lock CORS to the frontend

```bash
cd backend
fly secrets set CORS_ORIGINS='["https://<your-frontend>.vercel.app"]'   # triggers a redeploy
```

Exact origins only: the API refuses to start on patterns like `https://*.vercel.app`, because Starlette
matches origins literally and such a pattern would silently block the real site.

## 4. Smoke test (must pass)

```bash
bash scripts/smoke_test.sh https://<your-backend-app>.fly.dev https://<your-frontend>.vercel.app
```

It checks every core endpoint returns 200, that the live `n_positives` equals the committed
`evaluation.json` of the active artifact, that the frontend serves `index.html`, and that CORS allows the
frontend origin. Then click through the site on a laptop and a phone.

## 5. Operating it

| task                   | command                                                                                                           |
| :--------------------- | :---------------------------------------------------------------------------------------------------------------- |
| logs                   | `cd backend && fly logs`                                                                                          |
| status / machines      | `fly status`                                                                                                      |
| list releases          | `fly releases`                                                                                                    |
| roll back the API      | `fly deploy --image <image-of-previous-release>` (find image refs with `fly releases`; see `fly releases --help`) |
| roll back the frontend | Vercel dashboard: Deployments, select a previous deployment, "Promote to Production"                              |
| ship a new model       | build a new artifact version, update `active_version.txt`, run the tests, `fly deploy`                            |

The API has no endpoint that changes the live model: a model goes live only through a reviewed commit and a
deploy (the API runs several worker processes, which load the active version at start).
`GET /api/v1/models/registry/active` reports both the version in `active_version.txt` and the version the
process serves (`served_version`, `serving_matches_pointer`).

## Configuration reference

| variable                | where      | value                                                            |
| :---------------------- | :--------- | :--------------------------------------------------------------- |
| `CORS_ORIGINS`          | Fly secret | `["https://<your-frontend>.vercel.app"]`                         |
| `TRUSTED_PROXY_HOPS`    | `fly.toml` | `1` (Fly's proxy appends the client IP to `X-Forwarded-For`)     |
| `RATE_LIMIT_PER_MINUTE` | `fly.toml` | `120` per client per process (per-process: N machines allow N x) |
| `VITE_API_URL`          | Vercel env | `https://<your-backend-app>.fly.dev/api/v1`                      |
