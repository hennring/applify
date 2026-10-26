-- Maps each source posting to the job it belongs to now (dedup merges may move it).
select
    id as job_source_id,
    job_id,
    source,
    case
        when source like 'ats:%' or source = 'jsonld' then 'careers'
        else source
    end as source_group,
    external_id,
    url
from {{ source('app', 'job_sources') }}
