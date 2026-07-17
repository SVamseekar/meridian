with source as (

    select * from {{ source('app', 'raw_events') }}

),

renamed as (

    select
        id,
        tenant_id,
        anonymous_id,
        user_id,
        event_name,
        properties ->> 'firm_type' as firm_type,
        properties,
        client_timestamp,
        received_at

    from source

)

select * from renamed
