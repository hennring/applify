-- The source groups a job was found through (ba, adzuna, careers, ...).
select
    job_id,
    array_agg(distinct source_group order by source_group) as source_groups
from {{ ref('stg_app__job_sources') }}
group by job_id
