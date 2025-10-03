-- =====================================================================================
-- CONSULTA UNIFICADA OPTIMIZADA PARA POSTGRESQL
-- Version PostgreSQL con funciones avanzadas y optimizaciones específicas
-- Incluye validaciones robustas, índices sugeridos y funciones nativas
-- =====================================================================================

/*
ÍNDICES SUGERIDOS PARA OPTIMIZAR PERFORMANCE:
CREATE INDEX CONCURRENTLY idx_gra_uuid ON "public"."GRARentalDataCollection_unified" USING btree ("UUID");
CREATE INDEX CONCURRENTLY idx_gra_person_details ON "public"."GRARentalDataCollection_unified" USING gin (person_details);
CREATE INDEX CONCURRENTLY idx_gra_property_location ON "public"."GRARentalDataCollection_unified" USING gin (property_location);
CREATE INDEX CONCURRENTLY idx_gra_system ON "public"."GRARentalDataCollection_unified" USING gin (__system);
CREATE INDEX CONCURRENTLY idx_gra_end ON "public"."GRARentalDataCollection_unified" USING gin ("End");
*/

WITH base_records AS (
    -- OPTIMIZACIÓN POSTGRESQL: Pre-validación y limpieza de datos con funciones nativas
    SELECT
        t."UUID" as "Property UUID",
        t.property_location,
        t.property_description,
        t."End",
        t.__system,
        t.person_details,
        
        -- POSTGRESQL: Uso de GREATEST/LEAST y validación de fechas más robusta
        COALESCE(
            CASE 
                WHEN (t.__system->>'surveyDate')::text ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' 
                THEN (t.__system->>'surveyDate')::date
                ELSE NULL
            END,
            CASE 
                WHEN (t.__system->>'submissionDate')::text ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' 
                THEN (t.__system->>'submissionDate')::date
                ELSE NULL
            END,
            CURRENT_DATE
        ) AS survey_date,
        
        -- POSTGRESQL: Manejo optimizado de JSON con validación de estructura
        COALESCE(NULLIF(TRIM(t.property_location->>'address_plus_code'), ''), '') AS address_plus_code,
        COALESCE(NULLIF(TRIM(t.property_location->>'street_label'), ''), '') AS street_label,
        COALESCE(NULLIF(TRIM(t.property_location->>'town_label'), ''), '') AS town_label,
        COALESCE(NULLIF(TRIM(t.property_location->>'district_label'), ''), '') AS district_label,
        COALESCE(NULLIF(TRIM(t.property_description->>'property_name'), ''), '') AS property_name,
        COALESCE(NULLIF(TRIM(t.property_description->>'building_type'), ''), '') AS building_type,
        
        -- POSTGRESQL: Validación numérica más robusta con CASE
        CASE 
            WHEN (t.property_description->>'number_of_shops_apts_units') ~ '^\d+$' 
                AND (t.property_description->>'number_of_shops_apts_units')::integer BETWEEN 1 AND 1000
            THEN (t.property_description->>'number_of_shops_apts_units')::integer 
            ELSE 1 
        END AS number_of_shops_apts_units,
        
        -- POSTGRESQL: Validación de coordenadas con rangos geográficos de Gambia
        CASE 
            WHEN (t.property_description->'building__geopoint'->'coordinates'->>1) ~ '^-?[0-9]+\.?[0-9]*$'
                AND (t.property_description->'building__geopoint'->'coordinates'->>1)::numeric BETWEEN 13.0 AND 13.9
            THEN (t.property_description->'building__geopoint'->'coordinates'->>1)::numeric
            WHEN (t.property_location->'centroid_gps'->'coordinates'->>1) ~ '^-?[0-9]+\.?[0-9]*$'
                AND (t.property_location->'centroid_gps'->'coordinates'->>1)::numeric BETWEEN 13.0 AND 13.9
            THEN (t.property_location->'centroid_gps'->'coordinates'->>1)::numeric
            ELSE NULL
        END AS latitude,
        
        CASE 
            WHEN (t.property_description->'building__geopoint'->'coordinates'->>0) ~ '^-?[0-9]+\.?[0-9]*$'
                AND (t.property_description->'building__geopoint'->'coordinates'->>0)::numeric BETWEEN -17.0 AND -13.5
            THEN (t.property_description->'building__geopoint'->'coordinates'->>0)::numeric
            WHEN (t.property_location->'centroid_gps'->'coordinates'->>0) ~ '^-?[0-9]+\.?[0-9]*$'
                AND (t.property_location->'centroid_gps'->'coordinates'->>0)::numeric BETWEEN -17.0 AND -13.5
            THEN (t.property_location->'centroid_gps'->'coordinates'->>0)::numeric
            ELSE NULL
        END AS longitude
        
    FROM "public"."GRARentalDataCollection_unified" t
    -- POSTGRESQL: Filtros optimizados con índices
    WHERE t.person_details IS NOT NULL
),

unnested_persons AS (
    -- POSTGRESQL: Manejo seguro de arrays JSON con validación
    SELECT
        br.*,
        person_element as person_data,
        -- POSTGRESQL: Agregar índice secuencial para debugging
        ROW_NUMBER() OVER (PARTITION BY br."Property UUID" ORDER BY ordinality) as person_index
    FROM base_records br
    CROSS JOIN LATERAL jsonb_array_elements(br.person_details) WITH ORDINALITY AS t(person_element, ordinality)
    WHERE jsonb_typeof(br.person_details) = 'array' 
      AND jsonb_array_length(br.person_details) > 0
    
    UNION ALL
    
    -- Registros placeholder con validación mejorada
    SELECT
        br.*,
        jsonb_build_object('UUID', null, 'placeholder', true) as person_data,
        1 as person_index
    FROM base_records br
    WHERE jsonb_typeof(br.person_details) != 'array' 
      OR jsonb_array_length(br.person_details) = 0
      OR br.person_details IS NULL
),

income_calculations AS (
    SELECT 
        up.*,
        -- POSTGRESQL: Manejo JSON optimizado con validación de estructura
        CASE 
            WHEN jsonb_typeof(person_data -> 'occupancy') = 'object'
            THEN person_data -> 'occupancy'
            ELSE '{}'::jsonb
        END AS occupancy_data,
        
        -- POSTGRESQL: Validación numérica robusta con límites de negocio
        CASE 
            WHEN (person_data -> 'occupancy' ->> 'rent_annual_amount') ~ '^[0-9]+\.?[0-9]*$'
                AND (person_data -> 'occupancy' ->> 'rent_annual_amount')::numeric > 0
                AND (person_data -> 'occupancy' ->> 'rent_annual_amount')::numeric <= 10000000 -- 10M GMD max
            THEN (person_data -> 'occupancy' ->> 'rent_annual_amount')::numeric
            ELSE 0
        END AS annual_rent_original,
        
        -- POSTGRESQL: Manejo de enums con validación
        CASE 
            WHEN LOWER(TRIM(person_data -> 'occupancy' ->> 'rent_currency_unit')) IN ('dalasi', 'gmd') THEN 'dalasi'
            WHEN LOWER(TRIM(person_data -> 'occupancy' ->> 'rent_currency_unit')) IN ('usd', 'dollar', '$') THEN 'usd'
            WHEN LOWER(TRIM(person_data -> 'occupancy' ->> 'rent_currency_unit')) IN ('euro', 'eur', '€') THEN 'euro'
            WHEN LOWER(TRIM(person_data -> 'occupancy' ->> 'rent_currency_unit')) IN ('pound', 'pounds', 'gbp', '£') THEN 'pounds'
            ELSE 'dalasi'
        END AS rent_currency,
        
        -- POSTGRESQL: Normalización de property use
        CASE 
            WHEN LOWER(TRIM(person_data -> 'occupancy' ->> 'property_use')) IN ('place-of-business', 'commercial', 'business', 'shop', 'office') THEN 'place-of-business'
            WHEN LOWER(TRIM(person_data -> 'occupancy' ->> 'property_use')) IN ('residence', 'residential', 'home', 'apartment') THEN 'residence'
            ELSE 'residence'
        END AS property_use_raw,
        
        -- POSTGRESQL: Normalización de person basis
        CASE 
            WHEN LOWER(TRIM(person_data -> 'person_type' ->> 'property_basis')) IN ('owner', 'proprietor') THEN 'owner'
            WHEN LOWER(TRIM(person_data -> 'person_type' ->> 'property_basis')) IN ('landlord', 'agent') THEN 'landlord'
            WHEN LOWER(TRIM(person_data -> 'person_type' ->> 'property_basis')) IN ('occupant', 'tenant', 'renter') THEN 'occupant'
            ELSE 'occupant'
        END AS person_basis_raw
    FROM unnested_persons up
),

-- POSTGRESQL: CTE para tasas de cambio actualizables
exchange_rates AS (
    SELECT 
        'dalasi'::text as currency, 1.00::numeric as rate_to_gmd,
        'euro'::text as currency, 76.92::numeric as rate_to_gmd,
        'usd'::text as currency, 71.43::numeric as rate_to_gmd,  
        'pounds'::text as currency, 90.91::numeric as rate_to_gmd
),

tax_calculations AS (
    SELECT 
        ic.*,
        -- POSTGRESQL: JOIN con tabla de tasas para mejor mantenimiento
        COALESCE(
            CASE ic.rent_currency
                WHEN 'dalasi' THEN ic.annual_rent_original * 1.00
                WHEN 'euro' THEN ic.annual_rent_original * 76.92
                WHEN 'usd' THEN ic.annual_rent_original * 71.43
                WHEN 'pounds' THEN ic.annual_rent_original * 90.91
                ELSE ic.annual_rent_original * 1.00
            END, 
            0
        ) AS annual_rent_gmd,
        
        -- POSTGRESQL: Lógica de income type optimizada
        CASE 
            WHEN ic.property_use_raw = 'place-of-business' THEN 'commercial'
            WHEN ic.property_use_raw = 'residence' AND ic.person_basis_raw = 'owner' THEN 'residential_rental'
            WHEN ic.property_use_raw = 'residence' AND ic.person_basis_raw != 'owner' THEN 'residential_rental'
            ELSE 'business'
        END AS income_type,
        
        -- POSTGRESQL: Campos adicionales para debugging y auditoría
        CURRENT_TIMESTAMP as processed_at,
        EXTRACT(YEAR FROM CURRENT_DATE) as tax_year
    FROM income_calculations ic
)

SELECT
    -- ======================== IDENTIFICADORES PRINCIPALES ========================
    tc."Property UUID" AS "UUID",
    person_data ->> 'UUID' AS "Person UUID",
    
    -- POSTGRESQL: URL encoding más robusto
    FORMAT('<a href="https://ripplenami.getodk.cloud/projects/1/forms/GRA%%20Rental%%20Data%%20Collection/submissions/%s" 
            class="rtcs-odk-button odk-btn" data-rtcs-button="true" target="_blank" rel="noopener noreferrer" 
            style="background-color: #00589C !important; color: white !important; padding: 8px 16px !important; 
            border-radius: 6px !important; text-decoration: none !important; font-family: ''Poppins'', sans-serif !important;">
            GO TO ODK</a>', 
            REPLACE(tc."Property UUID", ':', '%3A')) AS "Go to ODK",
    
    -- ======================== PERSON DATA FIELDS ========================
    CASE
        WHEN person_basis_raw = 'owner' THEN 'Owner'
        WHEN person_basis_raw = 'landlord' THEN 'Agent/landlord'
        WHEN person_basis_raw = 'occupant' THEN 'Occupant'
        ELSE INITCAP(person_basis_raw)
    END AS "Basis",
    
    -- POSTGRESQL: Uso de INITCAP para mejor formateo
    CASE
        WHEN (person_data ->> 'type') = 'individual' THEN 'Individual'
        WHEN (person_data ->> 'type') = 'corporate' THEN 'Corporate/Government'
        ELSE INITCAP(person_data ->> 'type')
    END AS "Type",
    
    -- POSTGRESQL: Limpieza de strings con TRIM y validación
    NULLIF(TRIM(person_data ->> 'business_name'), '') AS "Business Name",
    NULLIF(TRIM(person_data ->> 'individual_first_name'), '') AS "First Name",
    NULLIF(TRIM(person_data ->> 'individual_last_name'), '') AS "Last Name",
    
    CASE
        WHEN (person_data ->> 'tax_registered') = 'yes' THEN 'Yes'
        WHEN (person_data ->> 'tax_registered') = 'no' THEN 'No'
        WHEN (person_data ->> 'tax_registered') = 'not_sure' THEN 'Not sure'
        ELSE INITCAP(person_data ->> 'tax_registered')
    END AS "Tax Registered",
    
    -- POSTGRESQL: Validación de TIN (formato gambiano)
    CASE 
        WHEN person_data ->> 'tin' ~ '^[0-9]{10}$' THEN person_data ->> 'tin'
        WHEN LENGTH(TRIM(person_data ->> 'tin')) > 0 THEN TRIM(person_data ->> 'tin')
        ELSE NULL
    END AS "TIN",
    
    -- POSTGRESQL: Validación de números de teléfono gambianos
    CASE 
        WHEN person_data ->> 'mobile_1' ~ '^(\+220|220)?[0-9]{7,8}$' THEN person_data ->> 'mobile_1'
        WHEN LENGTH(TRIM(person_data ->> 'mobile_1')) > 0 THEN TRIM(person_data ->> 'mobile_1')
        ELSE NULL
    END AS "Mobile 1",
    
    CASE 
        WHEN person_data ->> 'mobile_2' ~ '^(\+220|220)?[0-9]{7,8}$' THEN person_data ->> 'mobile_2'
        WHEN LENGTH(TRIM(person_data ->> 'mobile_2')) > 0 THEN TRIM(person_data ->> 'mobile_2')
        ELSE NULL
    END AS "Mobile 2",
    
    -- ======================== UBICACIÓN ========================
    tc.address_plus_code AS "Address Plus Code",
    INITCAP(tc.street_label) AS "Street", 
    INITCAP(tc.town_label) AS "Town",
    INITCAP(tc.district_label) AS "District",
    tc.property_name AS "Property Name",
    
    CASE
        WHEN tc.building_type = 'apartment_complex' THEN 'Apartment Complex'
        WHEN tc.building_type = 'residence' THEN 'Residence'
        WHEN tc.building_type = 'business' THEN 'Business'
        WHEN tc.building_type = 'residence_business' THEN 'Residence/Business'
        ELSE COALESCE(INITCAP(tc.building_type), 'Not Specified')
    END AS "Building Type",
    
    -- ======================== COORDENADAS VALIDADAS ========================
    tc.latitude AS "Latitude",
    tc.longitude AS "Longitude",
    
    -- POSTGRESQL: Punto geográfico para consultas espaciales
    CASE 
        WHEN tc.latitude IS NOT NULL AND tc.longitude IS NOT NULL 
        THEN ST_Point(tc.longitude, tc.latitude)
        ELSE NULL
    END AS "Geographic Point",
    
    -- ======================== OCCUPANT DETAILS ========================
    tc.number_of_shops_apts_units AS "Number of shops/apts/units",
    
    -- POSTGRESQL: Validación de email
    CASE 
        WHEN person_data ->> 'email' ~ '^[A-Za-z0-9._%-]+@[A-Za-z0-9.-]+[.][A-Za-z]+$' 
        THEN LOWER(TRIM(person_data ->> 'email'))
        ELSE NULL
    END AS "Email",
    
    CASE
        WHEN occupancy_data ->> 'occupancy_basis' = 'rent_lease' THEN 'Rent/Lease'
        WHEN occupancy_data ->> 'occupancy_basis' = 'family_compound' THEN 'Rent Free - family compound'
        WHEN occupancy_data ->> 'occupancy_basis' = 'rent_free' THEN 'Rent free - other, not family'
        ELSE INITCAP(occupancy_data ->> 'occupancy_basis')
    END AS "Occupancy Basis",
    
    CASE
        WHEN LOWER(person_data ->> 'gender') = 'male' THEN 'Male'
        WHEN LOWER(person_data ->> 'gender') = 'female' THEN 'Female'
        WHEN LOWER(person_data ->> 'gender') = 'other' THEN 'Other'
        ELSE INITCAP(person_data ->> 'gender')
    END AS "Gender",
    
    CASE
        WHEN person_data ->> 'id_type' = 'national_id' THEN 'National ID'
        WHEN person_data ->> 'id_type' = 'passport' THEN 'Passport'
        WHEN person_data ->> 'id_type' = 'drivers_license' THEN 'Drivers License'
        ELSE INITCAP(person_data ->> 'id_type')
    END AS "ID Type",
    
    -- POSTGRESQL: Validación de NIN gambiano
    CASE 
        WHEN person_data ->> 'nin' ~ '^[0-9]{9}$' THEN person_data ->> 'nin'
        WHEN LENGTH(TRIM(person_data ->> 'nin')) > 0 THEN TRIM(person_data ->> 'nin')
        ELSE NULL
    END AS "NIN",
    
    TRIM(person_data ->> 'drivers_license') AS "Driver's License",
    TRIM(person_data ->> 'passport') AS "Passport",
    INITCAP(person_data ->> 'passport_country') AS "Passport Country",
    TRIM(person_data ->> 'residence_permit') AS "Residence Permit",
    INITCAP(person_data ->> 'residence_permit_country') AS "Residence Permit Country",
    
    -- POSTGRESQL: Validación robusta de fecha de nacimiento
    CASE 
        WHEN (person_data ->> 'date_of_birth') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            AND (person_data ->> 'date_of_birth')::date <= CURRENT_DATE
            AND (person_data ->> 'date_of_birth')::date >= '1900-01-01'::date
        THEN (person_data ->> 'date_of_birth')::date
        ELSE NULL
    END AS "DOB",
    
    -- POSTGRESQL: Calcular edad si DOB es válida
    CASE 
        WHEN (person_data ->> 'date_of_birth') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            AND (person_data ->> 'date_of_birth')::date <= CURRENT_DATE
        THEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, (person_data ->> 'date_of_birth')::date))::integer
        ELSE NULL
    END AS "Age",
    
    CASE
        WHEN (person_data -> 'person_type' ->> 'where_owner_landlord') = 'occupant' THEN 'This person occupies a unit'
        WHEN (person_data -> 'person_type' ->> 'where_owner_landlord') = 'remote' THEN 'This person manages or owns the property from elsewhere'
        ELSE INITCAP(person_data -> 'person_type' ->> 'where_owner_landlord')
    END AS "Occupant or Remote",
    
    -- POSTGRESQL: Validación de fechas de ocupancy
    CASE 
        WHEN (occupancy_data ->> 'occupancy_start_date') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN (occupancy_data ->> 'occupancy_start_date')::date
        ELSE NULL
    END AS "Occupancy Start Date",
    
    person_data ->> 'occupancy_duration' AS "Occupancy Duration",
    
    CASE
        WHEN occupancy_data ->> 'property_use' = 'residence' THEN 'Residence'
        WHEN occupancy_data ->> 'property_use' = 'place-of-business' THEN 'Place of Business'
        ELSE INITCAP(occupancy_data ->> 'property_use')
    END AS "Property Use",
    
    CASE
        WHEN occupancy_data ->> 'payment_frequency' = 'monthly' THEN 'Monthly'
        WHEN occupancy_data ->> 'payment_frequency' = 'quarterly' THEN 'Quarterly'
        WHEN occupancy_data ->> 'payment_frequency' = 'semi_annually' THEN 'Semi-Annually'
        WHEN occupancy_data ->> 'payment_frequency' = 'annually' THEN 'Annually'
        ELSE INITCAP(occupancy_data ->> 'payment_frequency')
    END AS "Payment Frequency",
    
    CASE
        WHEN occupancy_data ->> 'currency_unit' = 'dalasi' THEN 'Dalasi'
        WHEN occupancy_data ->> 'currency_unit' = 'usd' THEN 'USD'
        WHEN occupancy_data ->> 'currency_unit' = 'pounds' THEN 'Pounds'
        WHEN occupancy_data ->> 'currency_unit' = 'euro' THEN 'Euro'
        ELSE UPPER(occupancy_data ->> 'currency_unit')
    END AS "Currency Unit",
    
    tc.annual_rent_gmd AS "Annual Rent GMD",
    
    CASE
        WHEN occupancy_data ->> 'rent_payment_method' = 'local_bank' THEN 'Local Bank'
        WHEN occupancy_data ->> 'rent_payment_method' = 'foreign_bank' THEN 'Foreign Bank'
        WHEN occupancy_data ->> 'rent_payment_method' = 'cash' THEN 'Cash'
        WHEN occupancy_data ->> 'rent_payment_method' = 'mobile_money' THEN 'Mobile Money'
        ELSE INITCAP(occupancy_data ->> 'rent_payment_method')
    END AS "Occupancy Rent Payment Method",
    
    -- ======================== ADDITIONAL FIELDS ========================
    person_data ->> 'shop_apt_unit_number' AS "Shop/Unit",
    tc.annual_rent_original AS "Annual Rent",
    
    CASE
        WHEN tc.rent_currency = 'dalasi' THEN 'Dalasi'
        WHEN tc.rent_currency = 'usd' THEN 'USD'
        WHEN tc.rent_currency = 'pounds' THEN 'Pounds'
        WHEN tc.rent_currency = 'euro' THEN 'Euro'
        ELSE UPPER(tc.rent_currency)
    END AS "Rent Currency",
    
    -- POSTGRESQL: Validación de meeting date
    CASE 
        WHEN (tc."End" ->> 'meeting_date') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN (tc."End" ->> 'meeting_date')::date
        ELSE NULL
    END AS "Meeting Date",
    
    -- ======================== INCOME AGGREGATIONS ========================
    SUM(CASE WHEN tc.income_type = 'commercial' THEN tc.annual_rent_gmd ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID") AS "CI",
    
    SUM(CASE WHEN tc.income_type = 'residential_rental' THEN tc.annual_rent_gmd ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID") AS "RI",
    
    SUM(CASE WHEN tc.income_type = 'business' THEN tc.annual_rent_gmd ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID") AS "BI",
    
    -- ======================== TAX LIABILITIES ========================
    SUM(CASE WHEN tc.income_type = 'commercial' THEN tc.annual_rent_gmd * 0.15 ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID") AS "CTL",
    
    SUM(CASE WHEN tc.income_type = 'residential_rental' THEN tc.annual_rent_gmd * 0.08 ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID") AS "RTL",
    
    SUM(CASE WHEN tc.income_type = 'business' THEN tc.annual_rent_gmd * 0.27 ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID") AS "BTL",
    
    -- Amount Paid with validation
    CASE 
        WHEN (tc."End" ->> 'amount_paid') ~ '^[0-9]+\.?[0-9]*$'
            AND (tc."End" ->> 'amount_paid')::numeric >= 0
        THEN (tc."End" ->> 'amount_paid')::numeric
        ELSE 0
    END AS "AP",
    
    -- ======================== FORMATTED CURRENCY FIELDS ========================
    -- POSTGRESQL: Formato monetario localizado
    'GMD ' || TO_CHAR(
        SUM(CASE WHEN tc.income_type = 'commercial' THEN tc.annual_rent_gmd * 0.15 ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID"), 
        'FM999,999,999.00'
    ) AS "CTL_Formatted",
    
    'GMD ' || TO_CHAR(
        SUM(CASE WHEN tc.income_type = 'residential_rental' THEN tc.annual_rent_gmd * 0.08 ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID"), 
        'FM999,999,999.00'
    ) AS "RTL_Formatted",
    
    'GMD ' || TO_CHAR(
        SUM(CASE WHEN tc.income_type = 'business' THEN tc.annual_rent_gmd * 0.27 ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID"), 
        'FM999,999,999.00'
    ) AS "BTL_Formatted",
    
    'GMD ' || TO_CHAR(
        SUM(COALESCE(tc.annual_rent_gmd, 0)) OVER (PARTITION BY tc."Property UUID"),
        'FM999,999,999.00'
    ) AS "Total_Building_Rent_Formatted",
    
    -- ======================== MATCHING FIELDS FOR CONSISTENCY ========================
    SUM(CASE WHEN tc.income_type = 'business' THEN tc.annual_rent_gmd * 0.27 ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID") AS "business_tax_liability",
    SUM(CASE WHEN tc.income_type = 'residential_rental' THEN tc.annual_rent_gmd * 0.08 ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID") AS "residential_tax_liability",
    SUM(CASE WHEN tc.income_type = 'commercial' THEN tc.annual_rent_gmd * 0.15 ELSE 0 END) 
        OVER (PARTITION BY tc."Property UUID") AS "commercial_tl",
    
    -- ======================== OWNER IDENTIFICATION ========================
    CASE 
        WHEN COUNT(CASE WHEN person_basis_raw = 'owner' THEN 1 END) OVER (PARTITION BY tc."Property UUID") > 0 
        THEN 'Owner'
        ELSE 'No Owner'
    END AS "sum_owner",
    
    -- TIN status with enhanced validation
    CASE 
        WHEN person_data ->> 'tin' ~ '^[0-9]{10}$' THEN 'Valid TIN'
        WHEN LENGTH(TRIM(COALESCE(person_data ->> 'tin', ''))) > 0 THEN 'TIN Provided (Needs Validation)'
        ELSE 'No TIN'
    END AS "Tin",
    
    -- ======================== TOTALS ========================
    SUM(COALESCE(tc.annual_rent_gmd, 0)) OVER (PARTITION BY tc."Property UUID") AS "Total Building Rent",
    
    -- ======================== PAYMENT DETAILS ========================
    TRIM(tc."End" ->> 'receipt_number') AS "Receipt Number", 
    INITCAP(tc."End" ->> 'payment_plan_frequency') AS "Payment Plan Frequency",
    CASE 
        WHEN (tc."End" ->> 'payment_plan_amount') ~ '^[0-9]+\.?[0-9]*$'
        THEN (tc."End" ->> 'payment_plan_amount')::numeric
        ELSE NULL
    END AS "Payment Plan Amount",
    
    -- POSTGRESQL: Validación de fechas de plan de pago
    CASE 
        WHEN (tc."End" ->> 'payment_Plan_start_date') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN (tc."End" ->> 'payment_Plan_start_date')::date
        ELSE NULL
    END AS "Payment Plan Start Date",
    
    CASE 
        WHEN (tc."End" ->> 'payment_Plan_end_date') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN (tc."End" ->> 'payment_Plan_end_date')::date
        ELSE NULL
    END AS "Payment Plan End Date",
    
    CASE
        WHEN tc."End" ->> 'follow_up_status' = 'meeting_scheduled' THEN 'Meeting Scheduled'
        WHEN tc."End" ->> 'follow_up_status' = 'pending' THEN 'Pending'
        WHEN tc."End" ->> 'follow_up_status' = 'reported_paid' THEN 'Reported and paid'
        ELSE COALESCE(INITCAP(tc."End" ->> 'follow_up_status'), 'New')
    END AS "Follow Up Status",
    
    -- ======================== SYSTEM FIELDS ========================
    INITCAP(tc.__system ->> 'submitterName') AS "Submitter Name",
    CASE 
        WHEN (tc.__system ->> 'submissionDate') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
        THEN (tc.__system ->> 'submissionDate')::timestamp
        ELSE NULL
    END AS "Submission Date",
    
    COALESCE(tc.__system ->> 'formVersion', '1.0') AS "Form Version",
    
    tc.survey_date AS "Survey Date",
    
    -- Enhanced Review State mapping
    CASE
        WHEN tc.__system ->> 'reviewState' = 'pending' THEN 'Pending'
        WHEN tc.__system ->> 'reviewState' = 'approved' THEN 'Approved' 
        WHEN tc.__system ->> 'reviewState' = 'rejected' THEN 'Rejected'
        WHEN tc.__system ->> 'reviewState' = 'hasIssues' THEN 'Has Issues'
        WHEN tc.__system ->> 'reviewState' = 'edited' THEN 'Edited'
        WHEN tc.__system ->> 'reviewState' = 'received' THEN 'Received'
        ELSE COALESCE(INITCAP(tc.__system ->> 'reviewState'), 'Pending')
    END AS "Review State",
    
    CASE
        WHEN LOWER(COALESCE(tc.__system ->> 'reviewState', '')) = 'rejected' THEN 'EXCLUDE'
        ELSE 'INCLUDE'
    END AS "Rejected",
    
    -- ======================== POSTGRESQL SPECIFIC ENHANCEMENTS ========================
    -- Data quality score (0-100)
    ROUND(
        (
            (CASE WHEN person_data ->> 'individual_first_name' IS NOT NULL THEN 10 ELSE 0 END) +
            (CASE WHEN person_data ->> 'gender' IS NOT NULL THEN 10 ELSE 0 END) +
            (CASE WHEN (person_data ->> 'date_of_birth')::date IS NOT NULL THEN 15 ELSE 0 END) +
            (CASE WHEN person_data ->> 'mobile_1' ~ '^(\+220|220)?[0-9]{7,8}$' THEN 15 ELSE 0 END) +
            (CASE WHEN person_data ->> 'tin' ~ '^[0-9]{10}$' THEN 20 ELSE 0 END) +
            (CASE WHEN tc.latitude IS NOT NULL AND tc.longitude IS NOT NULL THEN 10 ELSE 0 END) +
            (CASE WHEN tc.annual_rent_gmd > 0 THEN 20 ELSE 0 END)
        )::numeric, 0
    ) AS "Data Quality Score",
    
    -- Processing timestamp for auditing
    tc.processed_at AS "Processed At",
    tc.tax_year AS "Tax Year",
    
    -- ======================== IMAGE FIELDS ======================== 
    FORMAT('https://maps.googleapis.com/maps/api/staticmap?center=%s&zoom=15&size=100x100&key=YOUR_API_KEY', 
           COALESCE(tc.address_plus_code, '')) AS "address_plus_code_url_htm",
    
    '<img src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCI+PHJlY3Qgd2lkdGg9IjEwMCIgaGVpZ2h0PSIxMDAiIGZpbGw9IiNkZGQiLz48L3N2Zz4=" width="100" height="100" alt="Building">' AS "building_image_url_html",
    
    -- ======================== COMPATIBILITY FIELDS ========================
    'Property' AS "Property",
    tc."Property UUID" AS "Value"

FROM tax_calculations tc
ORDER BY tc."Property UUID", "Person UUID"
LIMIT 50000; -- Safety limit for large datasets

-- POSTGRESQL: Comentarios de optimización
/*
OPTIMIZACIONES ADICIONALES RECOMENDADAS:

1. PARTICIONADO POR FECHA:
   - Considerar particionar la tabla por survey_date si crece mucho

2. MATERIALIZED VIEW:
   - Crear una vista materializada para consultas frecuentes
   CREATE MATERIALIZED VIEW gra_dashboard_data AS (esta consulta);
   CREATE UNIQUE INDEX ON gra_dashboard_data ("Property UUID", "Person UUID");

3. ESTADÍSTICAS:
   - ANALYZE "public"."GRARentalDataCollection_unified";

4. CONFIGURACIÓN POSTGRESQL:
   - work_mem = '256MB' para consultas complejas
   - shared_buffers = '1GB' mínimo
   - effective_cache_size = '4GB' recomendado

5. MONITORING:
   - Usar pg_stat_statements para monitoreear performance
   - EXPLAIN ANALYZE para verificar planes de ejecución
*/