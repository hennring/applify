-- Typical tech stacks (§5.9, D26), found by the Dagster asset skill_stacks.
select stack_id, skills, stack_name, stack_size, support
from {{ ref('stg_features__skill_stacks') }}
