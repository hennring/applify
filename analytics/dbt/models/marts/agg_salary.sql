-- Yearly gross salary in EUR per role family and seniority, with the share of jobs that
-- state one at all (n and coverage are part of every salary figure, §5.8).
with jobs as (
    select role_family, seniority, salary_mid_eur
    from {{ ref('fct_job_postings') }}
    where has_full_text
)

select
    role_family,
    seniority,
    count(*) as jobs,
    count(salary_mid_eur) as jobs_with_salary,
    round(count(salary_mid_eur)::numeric / count(*), 4) as salary_coverage,
    percentile_cont(0.25) within group (order by salary_mid_eur) as p25_eur,
    percentile_cont(0.5) within group (order by salary_mid_eur) as median_eur,
    percentile_cont(0.75) within group (order by salary_mid_eur) as p75_eur
from jobs
group by role_family, seniority
