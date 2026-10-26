-- One row per (merged) job with its features and history (§5.8).
with latest as (
    select max(seen_at) as seen_at from {{ ref('stg_raw__job_sightings') }}
)

select
    j.job_id,
    j.title,
    j.company,
    j.location_raw,
    j.remote_type,
    j.has_full_text,
    j.posted_at,
    s.scope,
    src.source_groups,
    coalesce(f.role_family, 'unknown') as role_family,
    coalesce(f.seniority, 'unknown') as seniority,
    f.years_min,
    f.years_max,
    f.salary_currency,
    f.salary_period,
    f.salary_min_eur,
    f.salary_max_eur,
    case
        when f.salary_min_eur is not null and f.salary_max_eur is not null
            then (f.salary_min_eur + f.salary_max_eur) / 2
        else coalesce(f.salary_min_eur, f.salary_max_eur)
    end as salary_mid_eur,
    f.role_family_origin,
    f.seniority_origin,
    f.salary_origin,
    coalesce(cardinality(f.skills), 0) as skill_count,
    l.first_seen_at,
    l.last_seen_at,
    l.runs_seen,
    date_trunc('week', l.first_seen_at)::date as first_seen_week,
    -- Still open: seen within a week of the latest sighting of any job.
    l.last_seen_at >= latest.seen_at - interval '7 days' as is_active
from {{ ref('stg_app__jobs') }} j
cross join latest
join {{ ref('int_job_lifespans') }} l using (job_id)
join {{ ref('int_job_scope') }} s using (job_id)
left join {{ ref('int_job_sources') }} src using (job_id)
left join {{ ref('stg_features__job_features') }} f using (job_id)
