-- The stack each IT job belongs to (grain: job).
select s.job_id, s.stack_id
from {{ ref('stg_features__job_stacks') }} s
join {{ ref('fct_job_postings') }} using (job_id)
