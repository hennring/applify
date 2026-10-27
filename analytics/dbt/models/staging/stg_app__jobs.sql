select
    id as job_id,
    company_id,
    title,
    company,
    -- Dedup keys: normalized company (legal form dropped), title and city.
    company_norm,
    title_norm,
    city_norm,
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
