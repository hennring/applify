select
    id as job_id,
    company_id,
    title,
    company,
    location_raw,
    lat,
    lon,
    remote_type,
    salary_min,
    salary_max,
    description,
    has_full_text,
    posted_at,
    skills,
    first_seen_at
from {{ source('app', 'jobs') }}
