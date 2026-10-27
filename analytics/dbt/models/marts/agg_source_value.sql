-- What each source contributes (§5.9, tab "Daten"): jobs, jobs found only there, full text.
with job_source as (
    select distinct job_id, source, source_group
    from {{ ref('stg_app__job_sources') }}
),

source_count as (
    select job_id, count(*) as sources
    from job_source
    group by job_id
)

select
    s.source,
    s.source_group,
    count(*) as jobs,
    count(*) filter (where c.sources = 1) as only_here,
    count(*) filter (where f.has_full_text) as full_text,
    count(*) filter (where f.is_active) as active
from job_source s
join source_count c using (job_id)
join {{ ref('fct_job_postings') }} f using (job_id)
group by s.source, s.source_group
