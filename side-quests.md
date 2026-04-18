## TODO: produce paths tagging in processor.py (recommended for production)

After the three S3 uploads succeed, retrieve the current job ARN (available via AWS_BATCH_JOB_ID env var + describe_jobs) and call `batch.tag_resource` to attach three deterministic tags:
- `OutputMarkdown=s3://.../stem.md`
- `OutputJson=s3://.../stem.json`
- `OutputOriginal=s3://.../original-basename`

This makes all artifact paths directly available in every `describe_jobs` result without any recomputation.

By also tagging input, we can support an easy trailing deletion of the input artifact while processing succeeded jobs.

