-- Skills asked for in a user's target role families, and whether the profile has them.
with targets as (
    select distinct user_id, role_family
    from {{ ref('stg_features__profile_role_families') }}
    where role_family is not null
),

target_jobs as (
    select t.user_id, j.job_id
    from targets t
    join {{ ref('fct_job_postings') }} j using (role_family)
    where j.has_full_text
),

demand as (
    select tj.user_id, b.skill, b.category, count(*) as jobs
    from target_jobs tj
    join {{ ref('bridge_job_skills') }} b using (job_id)
    group by tj.user_id, b.skill, b.category
),

totals as (
    select user_id, count(*) as jobs from target_jobs group by user_id
)

select
    d.user_id,
    d.skill,
    d.category,
    d.jobs,
    round(d.jobs::numeric / t.jobs, 4) as share,
    p.weight as profile_weight,
    p.skill is not null and p.weight <> 'avoid' as in_profile
from demand d
join totals t using (user_id)
left join {{ ref('stg_app__profile_skills') }} p
    on p.user_id = d.user_id and lower(p.skill) = lower(d.skill)
