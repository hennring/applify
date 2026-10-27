select
    stack_id,
    skills,
    array_to_string(skills, ' + ') as stack_name,
    cardinality(skills) as stack_size,
    support
from {{ source('features', 'skill_stacks') }}
