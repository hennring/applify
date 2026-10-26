-- Demand per skill and week (by first sighting), with the share of that week's jobs.
with jobs as (
    select job_id, first_seen_week, scope from {{ ref('fct_job_postings') }}
    where has_full_text
),

weekly as (
    select first_seen_week, scope, count(*) as jobs from jobs group by 1, 2
)

select
    j.first_seen_week as week,
    j.scope,
    b.skill,
    b.category,
    count(*) as jobs,
    round(count(*)::numeric / w.jobs, 4) as share
from jobs j
join {{ ref('bridge_job_skills') }} b using (job_id)
join weekly w using (first_seen_week, scope)
group by j.first_seen_week, j.scope, b.skill, b.category, w.jobs
