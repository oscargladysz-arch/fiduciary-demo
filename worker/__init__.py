"""The job runner (R3-P4-6): one library entry, run_job(job_id, model_client),
two callers, the GitHub Actions workflow in the private repository
(runner actions) and the laptop command line (runner laptop). The pipeline
runs in a child process inside the public checkout pinned by the job."""
