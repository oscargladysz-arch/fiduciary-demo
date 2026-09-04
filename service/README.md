# Tark evaluation service

One endpoint. `POST /evaluate` with `{"cik": "...", "key": "..."}` runs
`src/ingest.py` for that fund synchronously and answers with what happened:
refused (reason plus the exact commands to run by hand), completed or
failed (exit code, output tail, report path), or timed out. No queue, no
job id, no progress state.

```
pip install -r requirements.txt
uvicorn service.app:app --port 8787
export TARK_SERVICE_URL=http://127.0.0.1:8787
python src/build_site.py        # the census entity card now posts to the service
```

Without `TARK_SERVICE_URL` at build time the site shows the command only.
The service needs what the ingest needs: the filings on disk, sec.gov
reachable, and an Anthropic credential in the environment.
