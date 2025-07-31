# Diagrama Unificado del Proyecto Superset-Docker

## Vista Completa del Sistema

```mermaid
graph TB
    %% External Systems
    subgraph "External Systems"
        ODK[ODK Central Server<br/>📱 Mobile Forms]
        S3[AWS S3 Storage<br/>🖼️ Image Storage]
    end
    
    %% User Interface
    subgraph "User Interface"
        USER[👤 User Browser<br/>Dashboard Access]
    end
    
    %% Docker Environment - Main Services
    subgraph "Docker Environment"
        subgraph "Core Services"
            SUPERSET[Apache Superset<br/>📊 :8088<br/>Data Visualization]
            POSTGRES[PostgreSQL<br/>🗄️ :5432<br/>Main Database]
            REDIS[Redis<br/>⚡ :6379<br/>Cache & Queue]
            ODK_SYNC[ODK Sync Service<br/>🔄 Python<br/>Data Sync]
        end
        
        %% Database Structure
        subgraph "Database Tables"
            MAIN_TABLE[📋 GRARentalDataCollection<br/>Main Form Data]
            PERSON_TABLE[👥 GRARentalDataCollection_person_details<br/>Person Details]
            UNIFIED_TABLE[🔗 GRARentalDataCollection_unified<br/>Unified View]
        end
        
        %% ODK Sync Components
        subgraph "ODK Sync Service Components"
            MAIN_PY[main.py<br/>Orchestrator]
            CONFIG_PY[config.py<br/>Configuration]
            API_PY[api.py<br/>ODK API Client]
            PARSER_PY[parser.py<br/>Data Parser]
            S3_PY[s3.py<br/>Image Upload]
            MODELS_PY[models.py<br/>SQLAlchemy Models]
            OPS_PY[operations.py<br/>CRUD Operations]
        end
    end
    
    %% Data Flow Connections
    ODK -->|OData API<br/>JSON Data| ODK_SYNC
    ODK_SYNC -->|Upsert Data<br/>UUID-based| POSTGRES
    ODK_SYNC -->|Upload Images<br/>Parallel Processing| S3
    POSTGRES -->|Query Data<br/>SQL| SUPERSET
    REDIS -->|Cache<br/>Session Data| SUPERSET
    USER -->|HTTP Access<br/>Dashboard| SUPERSET
    
    %% Internal Service Connections
    ODK_SYNC --> MAIN_PY
    MAIN_PY --> CONFIG_PY
    MAIN_PY --> API_PY
    MAIN_PY --> PARSER_PY
    MAIN_PY --> S3_PY
    MAIN_PY --> MODELS_PY
    MAIN_PY --> OPS_PY
    
    %% Database Table Relationships
    POSTGRES --> MAIN_TABLE
    POSTGRES --> PERSON_TABLE
    POSTGRES --> UNIFIED_TABLE
    MAIN_TABLE -->|1:N Relationship| PERSON_TABLE
    MAIN_TABLE -->|Unified View| UNIFIED_TABLE
    PERSON_TABLE -->|JSONB Field| UNIFIED_TABLE
    
    %% Database Operations
    MODELS_PY -->|Create Tables| POSTGRES
    OPS_PY -->|Upsert Operations| POSTGRES
    
    %% API Operations
    API_PY -->|Fetch Data| ODK
    PARSER_PY -->|Process Data| MAIN_PY
    S3_PY -->|Upload Images| S3
    
    %% Styling
    classDef external fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef service fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef database fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef component fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef user fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    
    class ODK,S3 external
    class SUPERSET,POSTGRES,REDIS,ODK_SYNC service
    class MAIN_TABLE,PERSON_TABLE,UNIFIED_TABLE database
    class MAIN_PY,CONFIG_PY,API_PY,PARSER_PY,S3_PY,MODELS_PY,OPS_PY component
    class USER user
```

## Flujo de Datos Detallado

```mermaid
sequenceDiagram
    participant User as 👤 User
    participant Superset as 📊 Superset
    participant ODKSync as 🔄 ODK Sync
    participant ODK as 📱 ODK Central
    participant Postgres as 🗄️ PostgreSQL
    participant S3 as 🖼️ AWS S3
    participant Redis as ⚡ Redis
    
    %% Initialization
    Note over User,Redis: System Startup
    ODKSync->>Postgres: Initialize Database Tables
    ODKSync->>Superset: Wait for Superset Ready
    
    %% Continuous Sync Loop
    loop Every 60 seconds
        ODKSync->>ODKSync: Read last_sync.txt
        ODKSync->>ODK: Fetch new submissions (OData API)
        ODK-->>ODKSync: Return JSON data
        
        %% Process Main Submissions
        ODKSync->>ODKSync: Process main submissions
        ODKSync->>S3: Upload building images (parallel)
        S3-->>ODKSync: Return image URLs
        ODKSync->>Postgres: Upsert main records
        
        %% Process Person Details
        ODKSync->>ODK: Fetch person details
        ODK-->>ODKSync: Return person data
        ODKSync->>Postgres: Upsert person details
        
        %% Create Unified View
        ODKSync->>Postgres: Create unified view
        ODKSync->>ODKSync: Update last_sync.txt
        
        %% User Access
        User->>Superset: Access Dashboard
        Superset->>Redis: Check Cache
        Superset->>Postgres: Query unified table
        Postgres-->>Superset: Return data
        Superset-->>User: Display Dashboard
    end
```

## Estructura de Archivos Integrada

```mermaid
graph TD
    ROOT[📁 superset-docker/]
    
    %% Main Project Files
    ROOT --> DOCKER[docker-compose.yml<br/>🐳 Services Config]
    ROOT --> DOCKERFILE[Dockerfile<br/>🐳 Superset Image]
    ROOT --> BOOTSTRAP[docker-bootstrap.sh<br/>🚀 Init Script]
    ROOT --> CONFIG[superset_config_override.py<br/>⚙️ Superset Config]
    ROOT --> README[README.md<br/>📖 Documentation]
    
    %% ODK Sync Service
    ROOT --> ODK_SYNC[📁 okd_sync/]
    
    ODK_SYNC --> MAIN[main.py<br/>🎯 Main Orchestrator]
    ODK_SYNC --> CONFIG_PY[config.py<br/>⚙️ Configuration]
    ODK_SYNC --> REQUIREMENTS[requirements.txt<br/>📦 Dependencies]
    ODK_SYNC --> DOCKERFILE_SYNC[Dockerfile<br/>🐳 Sync Image]
    ODK_SYNC --> README_SYNC[README.md<br/>📖 Sync Docs]
    
    %% Database Layer
    ODK_SYNC --> DB[📁 db/]
    DB --> CONNECTION[connection.py<br/>🔌 DB Connection]
    DB --> MODELS[sqlalchemy_models.py<br/>🗄️ Data Models]
    DB --> OPERATIONS[sqlalchemy_operations.py<br/>🔄 CRUD Operations]
    
    %% ODK Integration
    ODK_SYNC --> ODK[📁 odk/]
    ODK --> API[api.py<br/>🌐 ODK API Client]
    ODK --> PARSER[parser.py<br/>🔍 Data Parser]
    
    %% Storage Layer
    ODK_SYNC --> STORAGE[📁 storage/]
    STORAGE --> S3[s3.py<br/>☁️ AWS S3 Upload]
    STORAGE --> DELETE[delete_s3_images.py<br/>🗑️ S3 Cleanup]
    
    %% Utilities
    ODK_SYNC --> UTILS[📁 utils/]
    UTILS --> HELPERS[helpers.py<br/>🛠️ Helper Functions]
    UTILS --> LOGGER[logger.py<br/>📝 Logging]
    
    %% Environment Files
    ROOT --> ENV_MAIN[.env<br/>🔐 Main Config]
    ODK_SYNC --> ENV_SYNC[okd_sync/.env<br/>🔐 Sync Config]
    
    %% Styling
    classDef root fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef file fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef folder fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef config fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    
    class ROOT root
    class DOCKER,DOCKERFILE,BOOTSTRAP,CONFIG,README,MAIN,CONFIG_PY,REQUIREMENTS,DOCKERFILE_SYNC,README_SYNC,CONNECTION,MODELS,OPERATIONS,API,PARSER,S3,DELETE,HELPERS,LOGGER file
    class ODK_SYNC,DB,ODK,STORAGE,UTILS folder
    class ENV_MAIN,ENV_SYNC config
```

## Configuración de Variables de Entorno

```mermaid
graph LR
    subgraph "🔐 Main .env"
        SUPERSET_ADMIN[👤 SUPERSET_ADMIN_USERNAME<br/>🔑 SUPERSET_ADMIN_PASSWORD<br/>📧 SUPERSET_ADMIN_EMAIL]
        POSTGRES[🗄️ POSTGRES_DB<br/>👤 POSTGRES_USER<br/>🔑 POSTGRES_PASSWORD<br/>🌐 POSTGRES_HOST<br/>🔌 POSTGRES_PORT]
        REDIS_CONFIG[⚡ REDIS_HOST<br/>🔌 REDIS_PORT]
        SUPERSET_SECRET[🔐 SUPERSET_SECRET_KEY]
    end
    
    subgraph "🔐 okd_sync/.env"
        ODK_CONFIG[🌐 ODK_BASE_URL<br/>📋 ODK_PROJECT_ID<br/>📝 ODK_FORM_ID]
        ODK_CREDS[👤 ODATA_USER<br/>🔑 ODATA_PASS]
        PG_CONFIG[🗄️ PG_HOST<br/>🔌 PG_PORT<br/>📊 PG_DB<br/>👤 PG_USER<br/>🔑 PG_PASS]
        AWS_CONFIG[☁️ AWS_ACCESS_KEY<br/>🔑 AWS_SECRET_KEY<br/>🪣 AWS_BUCKET_NAME<br/>🌍 AWS_REGION]
        SYNC_CONFIG[⏱️ SYNC_INTERVAL<br/>👥 MAX_WORKERS<br/>⚡ PRIORITIZE_NEW]
    end
    
    %% Connections
    POSTGRES -.->|Database Connection| PG_CONFIG
    REDIS_CONFIG -.->|Cache Connection| SUPERSET_ADMIN
    ODK_CONFIG -.->|API Connection| ODK_CREDS
    AWS_CONFIG -.->|Storage Connection| S3_PY
```

## Resumen Visual del Sistema

```mermaid
mindmap
  root((Superset-Docker<br/>Project))
    🐳 Docker Environment
      📊 Apache Superset
        🌐 Web Interface :8088
        📈 Data Visualization
        🎨 Dashboard Creation
      🗄️ PostgreSQL
        📋 Main Tables
        🔗 Relationships
        🔄 Upsert Operations
      ⚡ Redis
        💾 Cache Storage
        🚀 Performance Boost
        📝 Session Data
      🔄 ODK Sync Service
        🌐 API Integration
        📱 Mobile Data Sync
        ☁️ S3 Upload
    📁 Project Structure
      🐳 Docker Files
        docker-compose.yml
        Dockerfile
        docker-bootstrap.sh
      📁 okd_sync/
        🎯 main.py
        ⚙️ config.py
        🌐 api.py
        🗄️ models.py
        ☁️ s3.py
    🔄 Data Flow
      📱 ODK Central
        📝 Form Submissions
        📍 GPS Data
        🖼️ Images
      🔄 Sync Process
        ⏱️ Every 60s
        🔄 Upsert Logic
        📊 Unified View
      📊 Superset
        📈 Charts
        📊 Dashboards
        🔍 Data Exploration
    🛠️ Features
      🔄 Auto Sync
      ⚡ Parallel Processing
      🔐 UUID-based Upsert
      📊 Unified Views
      ☁️ S3 Integration
```

## Características Técnicas Destacadas

### 🔄 **Sincronización Automática**
- **Intervalo**: Cada 60 segundos
- **Método**: OData API de ODK Central
- **Estrategia**: Upsert basado en UUID
- **Procesamiento**: Paralelo para imágenes

### 🗄️ **Estructura de Base de Datos**
- **Tabla Principal**: `GRARentalDataCollection` (datos de formularios)
- **Tabla Detalles**: `GRARentalDataCollection_person_details` (información de personas)
- **Vista Unificada**: `GRARentalDataCollection_unified` (vista combinada)

### 🐳 **Arquitectura Docker**
- **4 Servicios**: Superset, PostgreSQL, Redis, ODK Sync
- **Red Interna**: Comunicación entre contenedores
- **Persistencia**: Volúmenes para datos
- **Health Checks**: Monitoreo de servicios

### 🚀 **Optimizaciones**
- **Cache Redis**: Mejora rendimiento de Superset
- **Procesamiento Paralelo**: Subida de imágenes a S3
- **Upsert Inteligente**: Evita duplicados
- **Vista Unificada**: Consultas simples en Superset

### 📊 **Casos de Uso**
- **Recopilación de Datos**: Formularios móviles con ODK
- **Visualización**: Dashboards en tiempo real
- **Análisis**: Exploración de datos con Superset
- **Almacenamiento**: Imágenes en AWS S3 