-- Distance of each job with coordinates to the nearest of a user's places (haversine, km),
-- and whether it lies within that place's radius.
with distances as (
    select
        l.user_id,
        j.job_id,
        2 * 6371 * asin(least(1, sqrt(
            power(sin(radians(j.lat - l.lat) / 2), 2)
            + cos(radians(l.lat)) * cos(radians(j.lat)) * power(sin(radians(j.lon - l.lon) / 2), 2)
        ))) as distance_km,
        l.radius_km
    from {{ ref('stg_app__jobs') }} j
    cross join {{ ref('stg_app__profile_locations') }} l
    where j.lat is not null
)

select
    user_id,
    job_id,
    min(distance_km) as distance_km,
    bool_or(distance_km <= radius_km) as within_radius
from distances
group by user_id, job_id
