-- Distance of every job with a known place to each user's nearest place (§5.9, tab "Regionen").
select user_id, job_id, distance_km, within_radius
from {{ ref('int_job_profile_distance') }}
