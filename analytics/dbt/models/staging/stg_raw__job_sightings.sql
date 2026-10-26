select
    id as sighting_id,
    run_id,
    seen_at,
    source,
    external_id,
    job_id as job_id_at_sighting,
    content_hash
from {{ source('raw', 'job_sightings') }}
