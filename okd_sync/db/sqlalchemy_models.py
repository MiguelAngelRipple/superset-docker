"""
SQLAlchemy models for the database tables
"""
import logging
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, create_engine, Table, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS

# Logging configuration
logger = logging.getLogger(__name__)

# Create the database connection URL
DB_URL = f'postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}'

# Create the SQLAlchemy engine
engine = create_engine(DB_URL)

# Create the base class for models
Base = declarative_base()

# Create the session
Session = sessionmaker(bind=engine)

# Table names
MAIN_TABLE = "GRARentalDataCollection"
PERSON_DETAILS_TABLE = "GRARentalDataCollection_person_details"
UNIFIED_TABLE = "GRARentalDataCollection_unified"

class MainSubmission(Base):
    """Model for the main table"""
    __tablename__ = MAIN_TABLE
    
    UUID = Column(String, primary_key=True)
    id = Column(String, name="__id")
    survey_date = Column(DateTime)
    survey_start = Column(DateTime)
    survey_end = Column(DateTime)
    logo = Column(String)
    start_geopoint = Column(JSONB)
    property_location = Column(JSONB)
    property_description = Column(JSONB)
    generated_note_name_35 = Column(String)
    sum_owner = Column(String)
    sum_landlord = Column(String)
    sum_occupant = Column(String)
    check_counts_1 = Column(String)
    check_counts_2 = Column(String)
    End = Column(JSONB)
    meta = Column(JSONB)
    system = Column(JSONB, name="__system")
    person_details_link = Column(String, name="person_details@odata.navigationLink")
    building_image_url = Column(String)
    # New field for address plus code image from property_location
    address_plus_code_url = Column(String)
    # Submitted date for sync tracking
    SubmittedDate = Column(DateTime)

class PersonDetail(Base):
    """Model for the person details table"""
    __tablename__ = PERSON_DETAILS_TABLE
    
    UUID = Column(String, primary_key=True)
    id = Column(String, name="__id")
    submissions_id = Column(String, name="__Submissions-id")
    repeat_position = Column(String)
    person_type = Column(JSONB)
    shop_apt_unit_number = Column(String)
    type = Column(String)
    business_name = Column(String)
    tax_registered = Column(String)
    tin = Column(String)
    individual_first_name = Column(String)
    individual_middle_name = Column(String)
    individual_last_name = Column(String)
    individual_gender = Column(String)
    individual_id_type = Column(String)
    individual_nin = Column(String)
    individual_drivers_licence = Column(String)
    individual_passport_number = Column(String)
    passport_country = Column(String)
    individual_residence_permit_number = Column(String)
    residence_permit_country = Column(String)
    individual_dob = Column(String)
    mobile_1 = Column(String)
    mobile_2 = Column(String)
    email = Column(String)
    occupancy = Column(JSONB)
    
    # Propiedades para acceder a los campos con nombres especiales
    @property
    def __id(self):
        return self.id
        
    @property
    def __Submissions_id(self):
        return self.submissions_id
        
    # Propiedad con guión para compatibilidad
    @property
    def __Submissions_dash_id(self):
        return self.submissions_id

class UnifiedView(Base):
    """Model for the unified table"""
    __tablename__ = UNIFIED_TABLE
    
    UUID = Column(String, primary_key=True)
    __id = Column(String)
    survey_date = Column(DateTime)
    survey_start = Column(DateTime)
    survey_end = Column(DateTime)
    logo = Column(String)
    start_geopoint = Column(JSONB)
    property_location = Column(JSONB)
    property_description = Column(JSONB)
    generated_note_name_35 = Column(String)
    sum_owner = Column(String)
    sum_landlord = Column(String)
    sum_occupant = Column(String)
    check_counts_1 = Column(String)
    check_counts_2 = Column(String)
    End = Column(JSONB)
    meta = Column(JSONB)
    __system = Column(JSONB)
    person_details_link = Column(String, name="person_details@odata.navigationLink")
    building_image_url = Column(String)
    # New field for address plus code image from property_location
    address_plus_code_url = Column(String)
    person_details = Column(JSONB)
    building_image_url_html = Column(String)
    # HTML version of address plus code image for display
    address_plus_code_url_html = Column(String)

def create_tables():
    """Create tables in the database if they don't exist"""
    try:
        logger.info("Creating tables in the database if they don't exist")
        Base.metadata.create_all(engine)
        logger.info("Tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False

def drop_tables():
    """Drop tables from the database"""
    try:
        logger.info("Dropping tables from the database")
        Base.metadata.drop_all(engine)
        logger.info("Tables dropped successfully")
        return True
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")
        return False
