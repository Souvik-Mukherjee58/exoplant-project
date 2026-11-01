# Documentation Assets & Visual Media Guide

This directory holds visual media, platform walkthroughs, and UI screenshots referenced across `README.md`, `docs/`, and project documentation.

---

## Required Visual Assets Checklist

| Asset File | Target Purpose & View | Recommended Specs | Referencing Documents | Status |
|:---|:---|:---|:---|:---:|
| `demo.gif` | 30-second animated platform walkthrough: navigating the candidate explorer, ranking leaderboard, and interactive Linear SHAP waterfall. | 1200×675 (16:9), 20–30 fps, < 5 MB, optimized GIF / WebM | `README.md:13` | Needs real recording |
| `screenshot_dashboard.png` | ExoSignal Home view: Hero section, 3D exoplanet visualizer, live telemetry HUD (DuckDB population, model quality AP/Recall), and visual analytics studio. | 1920×1080 (1080p), dark mode, PNG | `docs/`, Portfolio | Needs screenshot |
| `screenshot_waterfall.png` | Planet Detail view: Linear SHAP waterfall breakdown showing exact base value (bias logit), individual feature $\Delta$ log-odds attributions, and final logit conversion for an exemplary candidate (e.g. TRAPPIST-1 e or Kepler-452 b). | 1920×1080 (1080p), dark mode, PNG | `docs/`, `MODEL_CARD.md` | Needs screenshot |
| `screenshot_top_targets.png` | Top Targets view: Leaderboard showing percentile rankings, unobserved filter toggle, priority scores, and verified JWST out-of-fold benchmark targets. | 1920×1080 (1080p), dark mode, PNG | `docs/`, Portfolio | Optional / Recommended |
| `screenshot_model_registry.png` | Model Registry view: Active production artifact manifest, SHA-256 verification badge, hyperparameter configuration, and score diversity histogram. | 1920×1080 (1080p), dark mode, PNG | `docs/`, Portfolio | Optional / Recommended |

---

## Instructions for Capturing Assets

### 1. Start the Local Application
Run both backend and frontend services locally:

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1 on Windows
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

### 2. Configure Browser Window
- Navigate to `http://localhost:3000` (or your deployed Vercel demo URL).
- Set viewport resolution to **1920×1080** (or 1440×900) at 100% zoom.
- Ensure browser dark theme is active and developer console / scrollbars are hidden.

### 3. Recording `demo.gif`
1. Use an screen recorder such as **OBS Studio**, **Kap**, or **ScreenToGif**.
2. **Walkthrough Route (30s)**:
   - **00–08s**: Home page hero section and 3D globe interaction.
   - **08–16s**: Scroll to telemetry HUD and click into the "Top Candidates" leaderboard.
   - **16–24s**: Click a high-priority target (e.g., TRAPPIST-1 e) to open Planet Detail.
   - **24–30s**: Interact with the Linear SHAP Waterfall, hovering over features (Transmission SNR, Stellar Radius, K-Mag) to highlight log-odds attributions.
3. Compress and optimize using `gifsicle` or `ffmpeg`:
   ```bash
   ffmpeg -i raw_walkthrough.mp4 -vf "fps=20,scale=1200:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -loop 0 docs/assets/demo.gif
   ```

### 4. Capturing High-Res PNG Screenshots
- Capture clean screenshots of:
  - `docs/assets/screenshot_dashboard.png`: Full-screen capture of Home view.
  - `docs/assets/screenshot_waterfall.png`: Centered capture of the Linear SHAP card on Planet Detail.
- Save as uncompressed or PNGCRUSH-optimized PNGs.

