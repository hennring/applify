-- German states with population, for jobs per inhabitant (§5.9).
select
    state_code,
    state_name,
    population
from {{ ref('stg_features__states') }}
