-- Where a job is: Germany, abroad or unknown. The offline gazetteer only knows German
-- places, so coordinates mean Germany; a named place without them lies abroad.
select
    job_id,
    case
        when lat is not null then 'germany'
        when location_raw ~* '(deutschland|germany)' then 'germany'
        when location_raw ~* '^\s*(remote|home\s?office|anywhere|ortsunabhängig)?\s*$' then 'unknown'
        else 'abroad'
    end as scope
from {{ ref('stg_app__jobs') }}
