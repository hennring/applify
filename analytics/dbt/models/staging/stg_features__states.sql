select
    state_code,
    name as state_name,
    population
from {{ source('features', 'states') }}
