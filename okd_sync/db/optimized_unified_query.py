"""
Optimized Unified Table Query Implementation
PostgreSQL optimized query for creating enhanced unified dataset with advanced validations and calculations.
This implementation ONLY uses the source tables:
- GRARentalDataCollection (main submissions)
- GRARentalDataCollection_person_details (person details)
"""

# Updated query from query_superset_working (1).sql - working version for remote environment  
OPTIMIZED_UNIFIED_QUERY = """
WITH base_records AS (
    SELECT
        m."UUID" as "Property UUID",
        m."__system",
        m."End",
        m.property_location,
        m.property_description,
        COALESCE(
            CASE
                WHEN (m."__system"::jsonb->>'surveyDate') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                THEN (m."__system"::jsonb->>'surveyDate')::date
                ELSE CURRENT_DATE
            END
        ) AS survey_date,
        COALESCE(NULLIF(TRIM(m.property_location::jsonb->>'address_plus_code'), ''), '') AS address_plus_code,
        COALESCE(NULLIF(TRIM(m.property_location::jsonb->>'street_label'), ''), '') AS street_label,
        COALESCE(NULLIF(TRIM(m.property_location::jsonb->>'town_label'), ''), '') AS town_label,
        COALESCE(NULLIF(TRIM(m.property_location::jsonb->>'district_label'), ''), '') AS district_label,
        COALESCE(NULLIF(TRIM(m.property_description::jsonb->>'property_name'), ''), '') AS property_name,
        COALESCE(NULLIF(TRIM(m.property_description::jsonb->>'building_type'), ''), '') AS building_type,
        CASE
            WHEN (m.property_description::jsonb->>'number_of_shops_apts_units') ~ '^\d+$'
                AND (m.property_description::jsonb->>'number_of_shops_apts_units')::integer BETWEEN 1 AND 1000
            THEN (m.property_description::jsonb->>'number_of_shops_apts_units')::integer
            ELSE 1
        END AS number_of_shops_apts_units,
        CASE
            WHEN (m.property_description::jsonb->'building__geopoint'->'coordinates'->>1) ~ '^-?[0-9]+\.?[0-9]*$'
                AND (m.property_description::jsonb->'building__geopoint'->'coordinates'->>1)::numeric BETWEEN 13.0 AND 13.9
            THEN (m.property_description::jsonb->'building__geopoint'->'coordinates'->>1)::numeric
            WHEN (m.property_location::jsonb->'centroid_gps'->'coordinates'->>1) ~ '^-?[0-9]+\.?[0-9]*$'
                AND (m.property_location::jsonb->'centroid_gps'->'coordinates'->>1)::numeric BETWEEN 13.0 AND 13.9
            THEN (m.property_location::jsonb->'centroid_gps'->'coordinates'->>1)::numeric
            ELSE NULL
        END AS latitude,
        CASE
            WHEN (m.property_description::jsonb->'building__geopoint'->'coordinates'->>0) ~ '^-?[0-9]+\.?[0-9]*$'
                AND (m.property_description::jsonb->'building__geopoint'->'coordinates'->>0)::numeric BETWEEN -17.0 AND -13.5
            THEN (m.property_description::jsonb->'building__geopoint'->'coordinates'->>0)::numeric
            WHEN (m.property_location::jsonb->'centroid_gps'->'coordinates'->>0) ~ '^-?[0-9]+\.?[0-9]*$'
                AND (m.property_location::jsonb->'centroid_gps'->'coordinates'->>0)::numeric BETWEEN -17.0 AND -13.5
            THEN (m.property_location::jsonb->'centroid_gps'->'coordinates'->>0)::numeric
            ELSE NULL
        END AS longitude,
        m."__id", m.survey_date as orig_survey_date, m.survey_start, m.survey_end, m.logo,
        m.start_geopoint, m.generated_note_name_35, m.sum_owner, m.sum_landlord,
        m.sum_occupant, m.check_counts_1, m.check_counts_2, m.meta,
        m."person_details@odata.navigationLink" as person_details_link,
        m.building_image_url, m.address_plus_code_url, m."SubmittedDate",
        COALESCE(pd_agg.person_details, '[]'::jsonb) as person_details
    FROM "public"."GRARentalDataCollection" m
    LEFT JOIN (
        SELECT
            SPLIT_PART(p."UUID", '_', 1) as main_uuid,
            jsonb_agg(
                jsonb_build_object(
                    'UUID', p."UUID",
                    'person_type', p."person_type",
                    'shop_apt_unit_number', p."shop_apt_unit_number",
                    'type', p."type",
                    'business_name', p."business_name",
                    'tax_registered', p."tax_registered",
                    'tin', p."tin",
                    'individual_first_name', p."individual_first_name",
                    'individual_middle_name', p."individual_middle_name",
                    'individual_last_name', p."individual_last_name",
                    'individual_gender', p."individual_gender",
                    'individual_id_type', p."individual_id_type",
                    'individual_nin', p."individual_nin",
                    'individual_drivers_licence', p."individual_drivers_licence",
                    'individual_passport_number', p."individual_passport_number",
                    'passport_country', p."passport_country",
                    'individual_residence_permit_number', p."individual_residence_permit_number",
                    'residence_permit_country', p."residence_permit_country",
                    'individual_dob', p."individual_dob",
                    'mobile_1', p."mobile_1",
                    'mobile_2', p."mobile_2",
                    'email', p."email",
                    'occupancy', p."occupancy"
                )
            ) as person_details
        FROM "public"."GRARentalDataCollection_person_details" p
        WHERE p."UUID" IS NOT NULL AND p."UUID" != ''
        GROUP BY SPLIT_PART(p."UUID", '_', 1)
    ) pd_agg ON m."UUID" = pd_agg.main_uuid
    WHERE pd_agg.person_details IS NOT NULL AND jsonb_array_length(pd_agg.person_details) > 0
),
unnested_persons AS (
    SELECT
        br.*,
        person_element as person_data,
        ROW_NUMBER() OVER (PARTITION BY br."Property UUID" ORDER BY ordinality) as person_index
    FROM base_records br
    CROSS JOIN LATERAL jsonb_array_elements(br.person_details) WITH ORDINALITY AS t(person_element, ordinality)
    WHERE jsonb_typeof(br.person_details) = 'array'
      AND jsonb_array_length(br.person_details) > 0
    UNION ALL
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
        CASE
            WHEN up.person_data::jsonb ->> 'occupancy' IS NOT NULL 
                AND up.person_data::jsonb ->> 'occupancy' != ''
                AND up.person_data::jsonb ->> 'occupancy' != 'null'
            THEN (up.person_data::jsonb ->> 'occupancy')::jsonb
            ELSE '{}'::jsonb
        END AS occupancy_data,
        CASE 
            WHEN ((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'rent_annual_amount') ~ '^\d+\.?\d*$'
                AND ((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'rent_annual_amount')::numeric > 0
                AND ((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'rent_annual_amount')::numeric <= 10000000
            THEN ((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'rent_annual_amount')::numeric
            ELSE 0
        END AS annual_rent_original,
        CASE
            WHEN LOWER(TRIM((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'rent_currency_unit')) IN ('dalasi', 'gmd') THEN 'dalasi'
            WHEN LOWER(TRIM((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'rent_currency_unit')) IN ('usd', 'dollar', '$') THEN 'usd'
            WHEN LOWER(TRIM((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'rent_currency_unit')) IN ('euro', 'eur', '€') THEN 'euro'
            WHEN LOWER(TRIM((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'rent_currency_unit')) IN ('pound', 'pounds', 'gbp', '£') THEN 'pounds'
            ELSE 'dalasi'
        END AS rent_currency,
        CASE
            WHEN LOWER(TRIM((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'property_use')) IN ('place-of-business', 'commercial', 'business', 'shop', 'office') THEN 'place-of-business'
            WHEN LOWER(TRIM((up.person_data::jsonb ->> 'occupancy')::jsonb ->> 'property_use')) IN ('residence', 'residential', 'home', 'apartment') THEN 'residence'
            ELSE 'residence'
        END AS property_use_raw,
        CASE
            WHEN LOWER(TRIM((up.person_data::jsonb ->> 'person_type')::jsonb ->> 'property_basis')) IN ('owner', 'proprietor') THEN 'owner'
            WHEN LOWER(TRIM((up.person_data::jsonb ->> 'person_type')::jsonb ->> 'property_basis')) IN ('landlord', 'agent') THEN 'landlord'
            WHEN LOWER(TRIM((up.person_data::jsonb ->> 'person_type')::jsonb ->> 'property_basis')) IN ('occupant', 'tenant', 'renter') THEN 'occupant'
            ELSE 'occupant'
        END AS person_basis_raw
    FROM unnested_persons up
),
tax_calculations AS (
    SELECT
        ic.*,
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
        CASE
            WHEN ic.property_use_raw = 'place-of-business' THEN 'commercial'
            WHEN ic.property_use_raw = 'residence' AND ic.person_basis_raw = 'owner' THEN 'residential_rental'
            WHEN ic.property_use_raw = 'residence' AND ic.person_basis_raw != 'owner' THEN 'residential_rental'
            ELSE 'business'
        END AS income_type,
        CURRENT_TIMESTAMP as processed_at,
        EXTRACT(YEAR FROM CURRENT_DATE) as tax_year
    FROM income_calculations ic
)
SELECT
    tc."Property UUID" AS "UUID",
    (tc.person_data::jsonb ->> 'UUID') AS "Person UUID",
    FORMAT('<a href="https://ripplenami.getodk.cloud/projects/1/forms/GRA%%20Rental%%20Data%%20Collection/submissions/%s" class="rtcs-odk-button odk-btn" data-rtcs-button="true" target="_blank" rel="noopener noreferrer" style="background-color: #00589C !important; color: white !important; padding: 8px 16px !important; border-radius: 6px !important; text-decoration: none !important; font-family: ''Poppins'', sans-serif !important;">GO TO ODK</a>', REPLACE(tc."Property UUID", ':', '%3A')) AS "Go to ODK",
    CASE
        WHEN tc.person_basis_raw = 'owner' THEN 'Owner'
        WHEN tc.person_basis_raw = 'landlord' THEN 'Agent/landlord'
        WHEN tc.person_basis_raw = 'occupant' THEN 'Occupant'
        ELSE INITCAP(tc.person_basis_raw)
    END AS "Basis",
    CASE
        WHEN ((tc.person_data::jsonb ->> 'type')) = 'individual' THEN 'Individual'
        WHEN ((tc.person_data::jsonb ->> 'type')) = 'corporate' THEN 'Corporate/Government'
        ELSE INITCAP((tc.person_data::jsonb ->> 'type'))
    END AS "Type",
    NULLIF(TRIM((tc.person_data::jsonb ->> 'business_name')), '') AS "Business Name",
    NULLIF(TRIM((tc.person_data::jsonb ->> 'individual_first_name')), '') AS "First Name",
    NULLIF(TRIM((tc.person_data::jsonb ->> 'individual_last_name')), '') AS "Last Name",
    CASE
        WHEN ((tc.person_data::jsonb ->> 'tax_registered')) = 'yes' THEN 'Yes'
        WHEN ((tc.person_data::jsonb ->> 'tax_registered')) = 'no' THEN 'No'
        WHEN ((tc.person_data::jsonb ->> 'tax_registered')) = 'not_sure' THEN 'Not sure'
        ELSE INITCAP((tc.person_data::jsonb ->> 'tax_registered'))
    END AS "Tax Registered",
    CASE
        WHEN (tc.person_data::jsonb ->> 'tin') ~ '^[0-9]{10}$' THEN (tc.person_data::jsonb ->> 'tin')
        WHEN LENGTH(TRIM((tc.person_data::jsonb ->> 'tin'))) > 0 THEN TRIM((tc.person_data::jsonb ->> 'tin'))
        ELSE NULL
    END AS "TIN",
    CASE
        WHEN (tc.person_data::jsonb ->> 'mobile_1') ~ '^(\+220|220)?[0-9]{7,8}$' THEN (tc.person_data::jsonb ->> 'mobile_1')
        WHEN LENGTH(TRIM((tc.person_data::jsonb ->> 'mobile_1'))) > 0 THEN TRIM((tc.person_data::jsonb ->> 'mobile_1'))
        ELSE NULL
    END AS "Mobile 1",
    CASE
        WHEN (tc.person_data::jsonb ->> 'mobile_2') ~ '^(\+220|220)?[0-9]{7,8}$' THEN (tc.person_data::jsonb ->> 'mobile_2')
        WHEN LENGTH(TRIM((tc.person_data::jsonb ->> 'mobile_2'))) > 0 THEN TRIM((tc.person_data::jsonb ->> 'mobile_2'))
        ELSE NULL
    END AS "Mobile 2",
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
    tc.latitude AS "Latitude",
    tc.longitude AS "Longitude",
    CASE
        WHEN tc.latitude IS NOT NULL AND tc.longitude IS NOT NULL
        THEN CONCAT('POINT(', tc.longitude, ' ', tc.latitude, ')')::text
        ELSE NULL
    END AS "Geographic Point",
    tc.number_of_shops_apts_units AS "Number of shops/apts/units",
    CASE
        WHEN (tc.person_data::jsonb ->> 'email') ~ '^[A-Za-z0-9._%-]+@[A-Za-z0-9.-]+[.][A-Za-z]+$'
        THEN LOWER(TRIM((tc.person_data::jsonb ->> 'email')))
        ELSE NULL
    END AS "Email",
    CASE
        WHEN tc.occupancy_data ->> 'occupancy_basis' = 'rent_lease' THEN 'Rent/Lease'
        WHEN tc.occupancy_data ->> 'occupancy_basis' = 'family_compound' THEN 'Rent Free - family compound'
        WHEN tc.occupancy_data ->> 'occupancy_basis' = 'rent_free' THEN 'Rent free - other, not family'
        ELSE INITCAP(tc.occupancy_data ->> 'occupancy_basis')
    END AS "Occupancy Basis",
    CASE
        WHEN LOWER((tc.person_data::jsonb ->> 'individual_gender')) = 'male' THEN 'Male'
        WHEN LOWER((tc.person_data::jsonb ->> 'individual_gender')) = 'female' THEN 'Female'
        WHEN LOWER((tc.person_data::jsonb ->> 'individual_gender')) = 'other' THEN 'Other'
        ELSE INITCAP((tc.person_data::jsonb ->> 'individual_gender'))
    END AS "Gender",
    CASE
        WHEN (tc.person_data::jsonb ->> 'individual_id_type') = 'national_id' THEN 'National ID'
        WHEN (tc.person_data::jsonb ->> 'individual_id_type') = 'passport' THEN 'Passport'
        WHEN (tc.person_data::jsonb ->> 'individual_id_type') = 'drivers_license' THEN 'Drivers License'
        ELSE INITCAP((tc.person_data::jsonb ->> 'individual_id_type'))
    END AS "ID Type",
    CASE
        WHEN (tc.person_data::jsonb ->> 'individual_nin') ~ '^[0-9]{9}$' THEN (tc.person_data::jsonb ->> 'individual_nin')
        WHEN LENGTH(TRIM((tc.person_data::jsonb ->> 'individual_nin'))) > 0 THEN TRIM((tc.person_data::jsonb ->> 'individual_nin'))
        ELSE NULL
    END AS "NIN",
    TRIM((tc.person_data::jsonb ->> 'individual_drivers_licence')) AS "Driver's License",
    TRIM((tc.person_data::jsonb ->> 'individual_passport_number')) AS "Passport",
    INITCAP((tc.person_data::jsonb ->> 'passport_country')) AS "Passport Country",
    TRIM((tc.person_data::jsonb ->> 'individual_residence_permit_number')) AS "Residence Permit",
    INITCAP((tc.person_data::jsonb ->> 'residence_permit_country')) AS "Residence Permit Country",
    CASE
        WHEN ((tc.person_data::jsonb ->> 'individual_dob')) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            AND ((tc.person_data::jsonb ->> 'individual_dob'))::date <= CURRENT_DATE
            AND ((tc.person_data::jsonb ->> 'individual_dob'))::date >= '1900-01-01'::date
        THEN ((tc.person_data::jsonb ->> 'individual_dob'))::date
        ELSE NULL
    END AS "DOB",
    CASE
        WHEN ((tc.person_data::jsonb ->> 'individual_dob')) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            AND ((tc.person_data::jsonb ->> 'individual_dob'))::date <= CURRENT_DATE
        THEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, ((tc.person_data::jsonb ->> 'individual_dob'))::date))::integer
        ELSE NULL
    END AS "Age",
    CASE
        WHEN (((tc.person_data::jsonb ->> 'person_type')::jsonb ->> 'where_owner_landlord')) = 'occupant' THEN 'This person occupies a unit'
        WHEN (((tc.person_data::jsonb ->> 'person_type')::jsonb ->> 'where_owner_landlord')) = 'remote' THEN 'This person manages or owns the property from elsewhere'
        ELSE INITCAP(((tc.person_data::jsonb ->> 'person_type')::jsonb ->> 'where_owner_landlord'))
    END AS "Occupant or Remote",
    CASE
        WHEN (tc.occupancy_data ->> 'occupancy_start_date') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN (tc.occupancy_data ->> 'occupancy_start_date')::date
        ELSE NULL
    END AS "Occupancy Start Date",
    (tc.person_data::jsonb ->> 'occupancy_duration') AS "Occupancy Duration",
    CASE
        WHEN tc.occupancy_data ->> 'property_use' = 'residence' THEN 'Residence'
        WHEN tc.occupancy_data ->> 'property_use' = 'place-of-business' THEN 'Place of Business'
        ELSE INITCAP(tc.occupancy_data ->> 'property_use')
    END AS "Property Use",
    CASE
        WHEN tc.occupancy_data ->> 'payment_frequency' = 'monthly' THEN 'Monthly'
        WHEN tc.occupancy_data ->> 'payment_frequency' = 'quarterly' THEN 'Quarterly'
        WHEN tc.occupancy_data ->> 'payment_frequency' = 'semi_annually' THEN 'Semi-Annually'
        WHEN tc.occupancy_data ->> 'payment_frequency' = 'annually' THEN 'Annually'
        ELSE INITCAP(tc.occupancy_data ->> 'payment_frequency')
    END AS "Payment Frequency",
    CASE
        WHEN tc.occupancy_data ->> 'currency_unit' = 'dalasi' THEN 'Dalasi'
        WHEN tc.occupancy_data ->> 'currency_unit' = 'usd' THEN 'USD'
        WHEN tc.occupancy_data ->> 'currency_unit' = 'pounds' THEN 'Pounds'
        WHEN tc.occupancy_data ->> 'currency_unit' = 'euro' THEN 'Euro'
        ELSE UPPER(tc.occupancy_data ->> 'currency_unit')
    END AS "Currency Unit",
    tc.annual_rent_gmd AS "Annual Rent GMD",
    CASE
        WHEN tc.occupancy_data ->> 'rent_payment_method' = 'local_bank' THEN 'Local Bank'
        WHEN tc.occupancy_data ->> 'rent_payment_method' = 'foreign_bank' THEN 'Foreign Bank'
        WHEN tc.occupancy_data ->> 'rent_payment_method' = 'cash' THEN 'Cash'
        WHEN tc.occupancy_data ->> 'rent_payment_method' = 'mobile_money' THEN 'Mobile Money'
        ELSE INITCAP(tc.occupancy_data ->> 'rent_payment_method')
    END AS "Occupancy Rent Payment Method",
    (tc.person_data::jsonb ->> 'shop_apt_unit_number') AS "Shop/Unit",
    tc.annual_rent_original AS "Annual Rent",
    CASE
        WHEN tc.rent_currency = 'dalasi' THEN 'Dalasi'
        WHEN tc.rent_currency = 'usd' THEN 'USD'
        WHEN tc.rent_currency = 'pounds' THEN 'Pounds'
        WHEN tc.rent_currency = 'euro' THEN 'Euro'
        ELSE UPPER(tc.rent_currency)
    END AS "Rent Currency",
    CASE
        WHEN (tc."End"::jsonb ->> 'meeting_date') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN (tc."End"::jsonb ->> 'meeting_date')::date
        ELSE NULL
    END AS "Meeting Date",
    SUM(CASE WHEN tc.income_type = 'commercial' THEN tc.annual_rent_gmd ELSE 0 END) OVER (PARTITION BY tc."Property UUID") AS "CI",
    SUM(CASE WHEN tc.income_type = 'residential_rental' THEN tc.annual_rent_gmd ELSE 0 END) OVER (PARTITION BY tc."Property UUID") AS "RI",
    SUM(CASE WHEN tc.income_type = 'business' THEN tc.annual_rent_gmd ELSE 0 END) OVER (PARTITION BY tc."Property UUID") AS "BI",
    SUM(CASE WHEN tc.income_type = 'commercial' THEN tc.annual_rent_gmd * 0.15 ELSE 0 END) OVER (PARTITION BY tc."Property UUID") AS "CTL",
    SUM(CASE WHEN tc.income_type = 'residential_rental' THEN tc.annual_rent_gmd * 0.08 ELSE 0 END) OVER (PARTITION BY tc."Property UUID") AS "RTL",
    SUM(CASE WHEN tc.income_type = 'business' THEN tc.annual_rent_gmd * 0.27 ELSE 0 END) OVER (PARTITION BY tc."Property UUID") AS "BTL",
    CASE
        WHEN (tc."End"::jsonb ->> 'amount_paid') ~ '^[0-9]+\.?[0-9]*$'
            AND (tc."End"::jsonb ->> 'amount_paid')::numeric >= 0
        THEN (tc."End"::jsonb ->> 'amount_paid')::numeric
        ELSE 0
    END AS "AP",
    'GMD ' || TO_CHAR(SUM(CASE WHEN tc.income_type = 'commercial' THEN tc.annual_rent_gmd * 0.15 ELSE 0 END) OVER (PARTITION BY tc."Property UUID"), 'FM999,999,999.00') AS "CTL_Formatted",
    'GMD ' || TO_CHAR(SUM(CASE WHEN tc.income_type = 'residential_rental' THEN tc.annual_rent_gmd * 0.08 ELSE 0 END) OVER (PARTITION BY tc."Property UUID"), 'FM999,999,999.00') AS "RTL_Formatted",
    'GMD ' || TO_CHAR(SUM(CASE WHEN tc.income_type = 'business' THEN tc.annual_rent_gmd * 0.27 ELSE 0 END) OVER (PARTITION BY tc."Property UUID"), 'FM999,999,999.00') AS "BTL_Formatted",
    'GMD ' || TO_CHAR(SUM(COALESCE(tc.annual_rent_gmd, 0)) OVER (PARTITION BY tc."Property UUID"), 'FM999,999,999.00') AS "Total_Building_Rent_Formatted",
    SUM(CASE WHEN tc.income_type = 'business' THEN tc.annual_rent_gmd * 0.27 ELSE 0 END) OVER (PARTITION BY tc."Property UUID") AS "business_tax_liability",
    SUM(CASE WHEN tc.income_type = 'residential_rental' THEN tc.annual_rent_gmd * 0.08 ELSE 0 END) OVER (PARTITION BY tc."Property UUID") AS "residential_tax_liability",
    SUM(CASE WHEN tc.income_type = 'commercial' THEN tc.annual_rent_gmd * 0.15 ELSE 0 END) OVER (PARTITION BY tc."Property UUID") AS "commercial_tl",
    CASE
        WHEN COUNT(CASE WHEN tc.person_basis_raw = 'owner' THEN 1 END) OVER (PARTITION BY tc."Property UUID") > 0
        THEN 'Owner'
        ELSE 'No Owner'
    END AS "sum_owner",
    CASE
        WHEN (tc.person_data::jsonb ->> 'tin') ~ '^[0-9]{10}$' THEN 'Valid TIN'
        WHEN LENGTH(TRIM(COALESCE((tc.person_data::jsonb ->> 'tin'), ''))) > 0 THEN 'TIN Provided (Needs Validation)'
        ELSE 'No TIN'
    END AS "Tin",
    SUM(COALESCE(tc.annual_rent_gmd, 0)) OVER (PARTITION BY tc."Property UUID") AS "Total Building Rent",
    TRIM(tc."End"::jsonb ->> 'receipt_number') AS "Receipt Number",
    INITCAP(tc."End"::jsonb ->> 'payment_plan_frequency') AS "Payment Plan Frequency",
    CASE
        WHEN (tc."End"::jsonb ->> 'payment_plan_amount') ~ '^[0-9]+\.?[0-9]*$'
        THEN (tc."End"::jsonb ->> 'payment_plan_amount')::numeric
        ELSE NULL
    END AS "Payment Plan Amount",
    CASE
        WHEN (tc."End"::jsonb ->> 'payment_Plan_start_date') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN (tc."End"::jsonb ->> 'payment_Plan_start_date')::date
        ELSE NULL
    END AS "Payment Plan Start Date",
    CASE
        WHEN (tc."End"::jsonb ->> 'payment_Plan_end_date') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN (tc."End"::jsonb ->> 'payment_Plan_end_date')::date
        ELSE NULL
    END AS "Payment Plan End Date",
    CASE
        WHEN tc."End"::jsonb ->> 'follow_up_status' = 'meeting_scheduled' THEN 'Meeting Scheduled'
        WHEN tc."End"::jsonb ->> 'follow_up_status' = 'pending' THEN 'Pending'
        WHEN tc."End"::jsonb ->> 'follow_up_status' = 'reported_paid' THEN 'Reported and paid'
        ELSE COALESCE(INITCAP(tc."End"::jsonb ->> 'follow_up_status'), 'New')
    END AS "Follow Up Status",
    INITCAP(tc."__system"::jsonb ->> 'submitterName') AS "Submitter Name",
    CASE
        WHEN (tc."__system"::jsonb ->> 'submissionDate') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
        THEN (tc."__system"::jsonb ->> 'submissionDate')::timestamp
        ELSE NULL
    END AS "Submission Date",
    COALESCE(tc."__system"::jsonb ->> 'formVersion', '1.0') AS "Form Version",
    tc.survey_date AS "Survey Date",
    CASE
        WHEN tc."__system"::jsonb ->> 'reviewState' = 'pending' THEN 'Pending'
        WHEN tc."__system"::jsonb ->> 'reviewState' = 'approved' THEN 'Approved'
        WHEN tc."__system"::jsonb ->> 'reviewState' = 'rejected' THEN 'Rejected'
        WHEN tc."__system"::jsonb ->> 'reviewState' = 'hasIssues' THEN 'Has Issues'
        WHEN tc."__system"::jsonb ->> 'reviewState' = 'edited' THEN 'Edited'
        WHEN tc."__system"::jsonb ->> 'reviewState' = 'received' THEN 'Received'
        ELSE COALESCE(INITCAP(tc."__system"::jsonb ->> 'reviewState'), 'Pending')
    END AS "Review State",
    CASE
        WHEN LOWER(COALESCE(tc."__system"::jsonb ->> 'reviewState', '')) = 'rejected' THEN 'EXCLUDE'
        ELSE 'INCLUDE'
    END AS "Rejected",
    ROUND(
        (
            (CASE WHEN ((tc.person_data::jsonb ->> 'individual_first_name')) IS NOT NULL THEN 10 ELSE 0 END) +
            (CASE WHEN ((tc.person_data::jsonb ->> 'individual_gender')) IS NOT NULL THEN 10 ELSE 0 END) +
            (CASE WHEN (((tc.person_data::jsonb ->> 'individual_dob'))::date) IS NOT NULL THEN 15 ELSE 0 END) +
            (CASE WHEN ((tc.person_data::jsonb ->> 'mobile_1')) ~ '^(\+220|220)?[0-9]{7,8}$' THEN 15 ELSE 0 END) +
            (CASE WHEN ((tc.person_data::jsonb ->> 'tin')) ~ '^[0-9]{10}$' THEN 20 ELSE 0 END) +
            (CASE WHEN tc.latitude IS NOT NULL AND tc.longitude IS NOT NULL THEN 10 ELSE 0 END) +
            (CASE WHEN tc.annual_rent_gmd > 0 THEN 20 ELSE 0 END)
        )::numeric, 0
    ) AS "Data Quality Score",
    tc.processed_at AS "Processed At",
    tc.tax_year AS "Tax Year",
    FORMAT('https://maps.googleapis.com/maps/api/staticmap?center=%s&zoom=15&size=100x100&key=YOUR_API_KEY', COALESCE(tc.address_plus_code, '')) AS "address_plus_code_url_htm",
    'Property' AS "Property",
    tc."Property UUID" AS "Value",
    CASE
        WHEN tc.building_image_url IS NOT NULL
        THEN '<img src=' || CHR(34) || tc.building_image_url || CHR(34) || ' width=' || CHR(34) || '100%' || CHR(34) || ' height=' || CHR(34) || '100%' || CHR(34) || ' />'
        ELSE NULL
    END as building_image_url_html,
    CASE
        WHEN tc.address_plus_code_url IS NOT NULL
        THEN '<img src=' || CHR(34) || tc.address_plus_code_url || CHR(34) || ' width=' || CHR(34) || '100%' || CHR(34) || ' height=' || CHR(34) || '100%' || CHR(34) || ' />'
        ELSE NULL
    END as address_plus_code_url_html
FROM "tax_calculations" tc
ORDER BY tc."Property UUID", (tc.person_data::jsonb ->> 'UUID')
LIMIT 50000;
"""

# Index creation queries for performance optimization (only on columns that exist)
PERFORMANCE_INDEXES = [
    # Composite primary key is already created, add supporting indexes
    "CREATE INDEX IF NOT EXISTS idx_gra_uuid_only ON \"public\".\"GRARentalDataCollection_unified\" USING btree (\"UUID\");",
    "CREATE INDEX IF NOT EXISTS idx_gra_person_uuid ON \"public\".\"GRARentalDataCollection_unified\" USING btree (\"Person UUID\");",
    "CREATE INDEX IF NOT EXISTS idx_gra_composite ON \"public\".\"GRARentalDataCollection_unified\" USING btree (\"UUID\", \"Person UUID\");",
    # Note: person_details, property_location, __system, End columns may not exist in final output
    # Only create indexes for columns that are actually selected in the final query
]

def get_optimized_unified_query():
    """Return the optimized unified table creation query"""
    return OPTIMIZED_UNIFIED_QUERY

def get_performance_indexes():
    """Return the list of performance indexes to create"""
    return PERFORMANCE_INDEXES