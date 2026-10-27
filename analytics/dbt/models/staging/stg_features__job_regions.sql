select
    job_id,
    state_code
from {{ source('features', 'job_regions') }}
