select
    content_hash,
    source,
    external_id,
    title,
    company,
    location_raw,
    remote_type,
    salary_min,
    salary_max,
    description,
    has_full_text,
    posted_at,
    payload,
    first_seen_at
from {{ source('raw', 'job_versions') }}
