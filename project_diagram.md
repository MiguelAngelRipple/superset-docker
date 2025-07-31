# Diagrama de Arquitectura del Proyecto Superset-Docker

## 1. Arquitectura General del Sistema

```mermaid
graph TB
    subgraph "External Systems"
        ODK[ODK Central Server]
        S3[AWS S3 Storage]
    end
    
    subgraph "Docker Environment"
        subgraph "Services"
            SUPERSET[Apache Superset<br/>:8088]
            POSTGRES[PostgreSQL<br/>:5432]
            REDIS[Redis<br/>:6379]
            ODK_SYNC[ODK Sync Service<br/>Python]
        end
        
        subgraph "Data Flow"
            ODK -->|OData API| ODK_SYNC
            ODK_SYNC -->|Upsert Data| POSTGRES
            ODK_SYNC -->|Upload Images| S3
            POSTGRES -->|Query Data| SUPERSET
            REDIS -->|Cache| SUPERSET
        end
    end
    
    subgraph "User Interface"
        USER[User Browser]
        USER -->|Dashboard Access| SUPERSET
    end
```

## 2. Estructura de Base de Datos

```mermaid
erDiagram
    GRARentalDataCollection {
        string UUID PK
        string __id
        datetime survey_date
        datetime survey_start
        datetime survey_end
        string logo
        jsonb start_geopoint
        jsonb property_location
        jsonb property_description
        string generated_note_name_35
        string sum_owner
        string sum_landlord
        string sum_occupant
        string check_counts_1
        string check_counts_2
        jsonb End
        jsonb meta
        jsonb __system
        string person_details_link
        string building_image_url
    }
    
    GRARentalDataCollection_person_details {
        string UUID PK
        string __id
        string __Submissions_id FK
        string repeat_position
        jsonb person_type
        string shop_apt_unit_number
        string type
        string business_name
        string tax_registered
        string tin
        string individual_first_name
        string individual_middle_name
        string individual_last_name
        string individual_gender
        string individual_id_type
        string individual_nin
        string individual_drivers_licence
        string individual_passport_number
        string passport_country
        string individual_residence_permit_number
        string residence_permit_country
        string individual_dob
        string mobile_1
        string mobile_2
        string email
        jsonb occupancy
    }
    
    GRARentalDataCollection_unified {
        string UUID PK
        string __id
        datetime survey_date
        datetime survey_start
        datetime survey_end
        string logo
        jsonb start_geopoint
        jsonb property_location
        jsonb property_description
        string generated_note_name_35
        string sum_owner
        string sum_landlord
        string sum_occupant
        string check_counts_1
        string check_counts_2
        jsonb End
        jsonb meta
        jsonb __system
        string person_details_link
        string building_image_url
        jsonb person_details
        string building_image_url_html
    }
    
    GRARentalDataCollection ||--o{ GRARentalDataCollection_person_details : "has many"
    GRARentalDataCollection ||--|| GRARentalDataCollection_unified : "unified view"
```

## 3. Flujo de Sincronización de Datos

```mermaid
sequenceDiagram
    participant ODK as ODK Central
    participant Sync as ODK Sync Service
    participant DB as PostgreSQL
    participant S3 as AWS S3
    participant Superset as Apache Superset
    
    loop Every 60 seconds
        Sync->>Sync: Read last_sync.txt
        Sync->>ODK: Fetch new submissions (OData API)
        ODK-->>Sync: Return JSON data
        
        Sync->>Sync: Process main submissions
        Sync->>S3: Upload building images (parallel)
        S3-->>Sync: Return image URLs
        Sync->>DB: Upsert main records
        
        Sync->>ODK: Fetch person details
        ODK-->>Sync: Return person data
        Sync->>DB: Upsert person details
        
        Sync->>DB: Create unified view
        Sync->>Sync: Update last_sync.txt
        
        Superset->>DB: Query unified table
        DB-->>Superset: Return data for dashboards
    end
```

## 4. Estructura de Archivos del Proyecto

```mermaid
graph TD
    ROOT[superset-docker/]
    
    ROOT --> DOCKER[docker-compose.yml]
    ROOT --> DOCKERFILE[Dockerfile]
    ROOT --> BOOTSTRAP[docker-bootstrap.sh]
    ROOT --> CONFIG[superset_config_override.py]
    ROOT --> README[README.md]
    
    ROOT --> ODK_SYNC[okd_sync/]
    
    ODK_SYNC --> MAIN[main.py]
    ODK_SYNC --> CONFIG_PY[config.py]
    ODK_SYNC --> REQUIREMENTS[requirements.txt]
    ODK_SYNC --> DOCKERFILE_SYNC[Dockerfile]
    ODK_SYNC --> README_SYNC[README.md]
    
    ODK_SYNC --> DB[db/]
    DB --> CONNECTION[connection.py]
    DB --> MODELS[sqlalchemy_models.py]
    DB --> OPERATIONS[sqlalchemy_operations.py]
    
    ODK_SYNC --> ODK[odk/]
    ODK --> API[api.py]
    ODK --> PARSER[parser.py]
    
    ODK_SYNC --> STORAGE[storage/]
    STORAGE --> S3[s3.py]
    STORAGE --> DELETE[delete_s3_images.py]
    
    ODK_SYNC --> UTILS[utils/]
    UTILS --> HELPERS[helpers.py]
    UTILS --> LOGGER[logger.py]
```

## 5. Componentes del Servicio ODK Sync

```mermaid
graph LR
    subgraph "ODK Sync Service"
        MAIN[main.py<br/>Orchestrator]
        CONFIG[config.py<br/>Configuration]
        
        subgraph "Database Layer"
            CONNECTION[connection.py<br/>DB Connection]
            MODELS[models.py<br/>SQLAlchemy Models]
            OPERATIONS[operations.py<br/>CRUD Operations]
        end
        
        subgraph "ODK Integration"
            API[api.py<br/>ODK API Client]
            PARSER[parser.py<br/>Data Parser]
        end
        
        subgraph "Storage"
            S3[s3.py<br/>AWS S3 Upload]
        end
        
        subgraph "Utilities"
            HELPERS[helpers.py<br/>Helper Functions]
            LOGGER[logger.py<br/>Logging]
        end
    end
    
    MAIN --> CONFIG
    MAIN --> CONNECTION
    MAIN --> API
    MAIN --> S3
    MAIN --> HELPERS
    
    API --> PARSER
    CONNECTION --> MODELS
    MODELS --> OPERATIONS
```

## 6. Configuración de Variables de Entorno

```mermaid
graph TD
    subgraph ".env (Main)"
        SUPERSET_ADMIN[SUPERSET_ADMIN_USERNAME<br/>SUPERSET_ADMIN_PASSWORD<br/>SUPERSET_ADMIN_EMAIL]
        POSTGRES[POSTGRES_DB<br/>POSTGRES_USER<br/>POSTGRES_PASSWORD<br/>POSTGRES_HOST<br/>POSTGRES_PORT]
        REDIS_CONFIG[REDIS_HOST<br/>REDIS_PORT]
        SUPERSET_SECRET[SUPERSET_SECRET_KEY]
    end
    
    subgraph "okd_sync/.env"
        ODK_CONFIG[ODK_BASE_URL<br/>ODK_PROJECT_ID<br/>ODK_FORM_ID]
        ODK_CREDS[ODATA_USER<br/>ODATA_PASS]
        PG_CONFIG[PG_HOST<br/>PG_PORT<br/>PG_DB<br/>PG_USER<br/>PG_PASS]
        AWS_CONFIG[AWS_ACCESS_KEY<br/>AWS_SECRET_KEY<br/>AWS_BUCKET_NAME<br/>AWS_REGION]
        SYNC_CONFIG[SYNC_INTERVAL<br/>MAX_WORKERS<br/>PRIORITIZE_NEW]
    end
```

## 7. Proceso de Inicialización

```mermaid
flowchart TD
    START[Start Docker Compose] --> BUILD[Build Images]
    BUILD --> INIT_POSTGRES[Initialize PostgreSQL]
    INIT_POSTGRES --> INIT_REDIS[Initialize Redis]
    INIT_REDIS --> INIT_SUPERSET[Initialize Superset]
    INIT_SUPERSET --> CREATE_ADMIN[Create Admin User]
    CREATE_ADMIN --> START_SYNC[Start ODK Sync Service]
    START_SYNC --> READY[System Ready]
    
    START_SYNC --> SYNC_LOOP[Sync Loop]
    SYNC_LOOP --> FETCH_DATA[Fetch ODK Data]
    FETCH_DATA --> PROCESS[Process & Upload Images]
    PROCESS --> UPDATE_DB[Update Database]
    UPDATE_DB --> CREATE_VIEW[Create Unified View]
    CREATE_VIEW --> SYNC_LOOP
```

## 8. Puntos de Acceso y Puertos

```mermaid
graph LR
    subgraph "External Access"
        BROWSER[User Browser]
    end
    
    subgraph "Docker Services"
        SUPERSET[Superset<br/>:8088]
        POSTGRES[PostgreSQL<br/>:5432]
        REDIS[Redis<br/>:6379]
        ODK_SYNC[ODK Sync<br/>Internal]
    end
    
    BROWSER -->|HTTP| SUPERSET
    SUPERSET -->|SQL| POSTGRES
    SUPERSET -->|Cache| REDIS
    ODK_SYNC -->|OData| EXTERNAL[ODK Central]
    ODK_SYNC -->|Upload| S3[AWS S3]
```

## Resumen de la Arquitectura

### 🏗️ **Componentes Principales**
1. **Apache Superset** - Plataforma de visualización web
2. **PostgreSQL** - Base de datos principal
3. **Redis** - Cache y cola de tareas
4. **ODK Sync Service** - Servicio de sincronización Python

### 📊 **Estructura de Datos**
- **Tabla Principal**: `GRARentalDataCollection` - Datos de formularios
- **Tabla Detalles**: `GRARentalDataCollection_person_details` - Información de personas
- **Vista Unificada**: `GRARentalDataCollection_unified` - Vista combinada para Superset

### 🔄 **Flujo de Datos**
1. **ODK Central** → Datos de formularios móviles
2. **ODK Sync** → Sincronización cada 60 segundos
3. **PostgreSQL** → Almacenamiento estructurado
4. **Superset** → Dashboards y visualizaciones

### 🚀 **Características Clave**
- Sincronización automática cada 60 segundos
- Procesamiento paralelo de imágenes
- Upsert inteligente basado en UUID
- Vista unificada para consultas simples
- Subida automática de imágenes a S3 