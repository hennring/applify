{# The read-only login role for BI tools; its password comes from APPLIFY_READER_PASSWORD.
   Table grants are set by the marts' `grants` config on every build. #}
{% macro create_reader_role() %}
    {# Same name as in the marts' grants in dbt_project.yml. #}
    {% set role = 'applify_reader' %}
    {% set password = env_var('APPLIFY_READER_PASSWORD', 'applify_reader') %}
    do $$
    begin
        if not exists (select from pg_roles where rolname = '{{ role }}') then
            create role {{ role }} login password '{{ password }}';
        end if;
    end
    $$;
    create schema if not exists marts;
    grant usage on schema marts to {{ role }};
    revoke all on schema public from {{ role }};
{% endmacro %}
