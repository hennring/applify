select
    job_id,
    stack_id
from {{ source('features', 'job_stacks') }}
