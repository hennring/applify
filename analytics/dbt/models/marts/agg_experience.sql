-- Required years of experience per role family and seniority.
select
    role_family,
    seniority,
    count(*) as jobs,
    count(years_min) as jobs_with_years,
    percentile_cont(0.5) within group (order by years_min) as median_years_min,
    round(avg(years_min), 1) as avg_years_min
from {{ ref('fct_job_postings') }}
where has_full_text
group by role_family, seniority
