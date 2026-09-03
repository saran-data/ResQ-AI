"""Initial database schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-08-30

Creates all ResQAI tables within the 'resqai' schema.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the complete ResQAI database schema."""

    # --------------------------------------------------------
    # ENUMS (created before tables that use them)
    # --------------------------------------------------------
    op.execute("CREATE SCHEMA IF NOT EXISTS resqai")

    # User enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.user_role AS ENUM (
                'super_admin', 'admin', 'restaurant_owner', 'restaurant_staff',
                'ngo_manager', 'ngo_staff', 'volunteer', 'driver'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.user_status AS ENUM (
                'active', 'inactive', 'suspended', 'pending_verification', 'banned'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Restaurant enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.restaurant_type AS ENUM (
                'restaurant', 'hotel', 'marriage_hall', 'catering',
                'bakery', 'corporate_cafeteria', 'cloud_kitchen', 'food_court', 'other'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.restaurant_status AS ENUM (
                'pending_verification', 'active', 'suspended', 'inactive', 'blacklisted'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # NGO enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.ngo_type AS ENUM (
                'ngo', 'orphanage', 'old_age_home', 'shelter', 'community_kitchen',
                'food_bank', 'religious_institution', 'school', 'hospital', 'other'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.ngo_status AS ENUM (
                'pending_verification', 'active', 'suspended', 'inactive', 'blacklisted'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Volunteer enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.volunteer_status AS ENUM (
                'active', 'inactive', 'on_delivery', 'unavailable', 'suspended'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Vehicle enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.vehicle_type AS ENUM (
                'bicycle', 'motorcycle', 'auto_rickshaw', 'car', 'van',
                'tempo', 'truck', 'refrigerated_van', 'electric_bike', 'electric_car'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Donation enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.donation_status AS ENUM (
                'draft', 'pending_analysis', 'analyzed', 'safety_check', 'safety_failed',
                'matching', 'matched', 'pickup_scheduled', 'awaiting_pickup', 'picked_up',
                'in_transit', 'delivered', 'confirmed', 'cancelled', 'rejected', 'expired'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Food enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.food_category AS ENUM (
                'cooked_meal', 'raw_produce', 'bakery', 'dairy', 'beverages',
                'packaged', 'snacks', 'desserts', 'grains', 'pulses', 'condiments', 'other'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.food_safety_status AS ENUM (
                'pending', 'safe', 'conditionally_safe', 'unsafe', 'expired'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Delivery enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.delivery_status AS ENUM (
                'pending', 'assigned', 'heading_to_pickup', 'at_pickup', 'picked_up',
                'in_transit', 'near_destination', 'at_destination',
                'delivered', 'confirmed', 'failed', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Notification enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.notification_channel AS ENUM (
                'email', 'sms', 'whatsapp', 'push', 'in_app', 'webhook'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.notification_type AS ENUM (
                'donation_created', 'donation_analyzed', 'donation_matched',
                'pickup_scheduled', 'pickup_started', 'delivery_started',
                'delivery_completed', 'otp_generated', 'safety_rejected',
                'fraud_detected', 'ngo_accepted', 'ngo_rejected',
                'volunteer_assigned', 'system_alert', 'weekly_report',
                'verification_email', 'password_reset', 'welcome'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.notification_status AS ENUM (
                'pending', 'queued', 'sent', 'delivered', 'failed', 'read', 'bounced'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # AI enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.agent_type AS ENUM (
                'food_analysis', 'ngo_matching', 'route_optimization', 'food_safety',
                'demand_prediction', 'notification', 'volunteer', 'analytics',
                'fraud_detection', 'admin_assistant', 'orchestrator'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.agent_decision_status AS ENUM (
                'pending', 'running', 'success', 'failed', 'retrying', 'timeout', 'skipped'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Route / Report enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.route_algorithm AS ENUM (
                'astar', 'dijkstra', 'vrp', 'tsp', 'genetic', 'or_tools',
                'google_directions', 'openroute', 'dynamic'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.route_status AS ENUM (
                'computed', 'in_use', 'completed', 'rerouted', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.report_type AS ENUM (
                'donation_summary', 'impact_report', 'ngo_activity',
                'restaurant_contribution', 'volunteer_performance', 'food_safety_audit',
                'fraud_analysis', 'ai_performance', 'carbon_footprint',
                'financial_summary', 'weekly_digest', 'monthly_digest', 'custom'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.report_format AS ENUM ('pdf', 'csv', 'excel', 'json');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.report_status AS ENUM (
                'queued', 'processing', 'completed', 'failed', 'expired'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.snapshot_type AS ENUM (
                'daily', 'weekly', 'monthly', 'annual'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE resqai.document_type AS ENUM (
                'ngo_profile', 'restaurant_profile', 'food_safety_guideline',
                'fssai_regulation', 'who_guideline', 'government_notification',
                'donation_history', 'volunteer_report', 'weather_report',
                'traffic_report', 'demand_report', 'general'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("oauth_provider", sa.String(50), nullable=True),
        sa.Column("oauth_subject", sa.String(255), nullable=True),
        sa.Column("role", sa.Enum(name="user_role", schema="resqai"), nullable=False, server_default="volunteer"),
        sa.Column("permissions", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Enum(name="user_status", schema="resqai"), nullable=False, server_default="pending_verification"),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_phone_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_2fa_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("two_fa_secret", sa.String(64), nullable=True),
        sa.Column("email_verify_token", sa.String(128), nullable=True),
        sa.Column("password_reset_token", sa.String(128), nullable=True),
        sa.Column("refresh_token_hash", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=False, server_default="India"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("notification_preferences", postgresql.JSONB(), nullable=True),
        sa.Column("last_login_at", sa.String(50), nullable=True),
        sa.Column("last_login_ip", sa.String(45), nullable=True),
        sa.Column("login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="resqai",
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True, schema="resqai")
    op.create_index("idx_users_phone", "users", ["phone"], schema="resqai")
    op.create_index("idx_users_role", "users", ["role"], schema="resqai")
    op.create_index("idx_users_status", "users", ["status"], schema="resqai")

    # restaurants
    op.create_table(
        "restaurants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("type", sa.Enum(name="restaurant_type", schema="resqai"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=False),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("pincode", sa.String(10), nullable=False),
        sa.Column("country", sa.String(100), nullable=False, server_default="India"),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geohash", sa.String(12), nullable=True),
        sa.Column("fssai_license", sa.String(50), nullable=True),
        sa.Column("fssai_expiry", sa.String(20), nullable=True),
        sa.Column("gst_number", sa.String(20), nullable=True),
        sa.Column("registration_certificate", sa.String(1024), nullable=True),
        sa.Column("logo_url", sa.String(1024), nullable=True),
        sa.Column("cover_image_url", sa.String(1024), nullable=True),
        sa.Column("images", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("status", sa.Enum(name="restaurant_status", schema="resqai"), nullable=False, server_default="pending_verification"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.String(50), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("operating_hours", postgresql.JSONB(), nullable=True),
        sa.Column("avg_daily_surplus_kg", sa.Float(), nullable=True),
        sa.Column("cuisine_types", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("serves_veg", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("serves_nonveg", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("total_donations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_meals_saved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_weight_donated_kg", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("carbon_saved_kg", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("impact_rank", sa.Integer(), nullable=True),
        sa.Column("sustainability_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("notification_preferences", postgresql.JSONB(), nullable=True),
        sa.Column("ai_insights_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("auto_donate_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rag_embedding_id", sa.String(255), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["resqai.users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("fssai_license", name="uq_restaurant_fssai", deferrable=True),
        schema="resqai",
    )
    op.create_index("idx_restaurants_owner_id", "restaurants", ["owner_id"], schema="resqai")
    op.create_index("idx_restaurants_status", "restaurants", ["status"], schema="resqai")
    op.create_index("idx_restaurants_city", "restaurants", ["city"], schema="resqai")
    op.create_index("idx_restaurants_location", "restaurants", ["latitude", "longitude"], schema="resqai")

    # ---- updated_at triggers for all tables ----
    for table in ["users", "restaurants"]:
        op.execute(f"""
            CREATE OR REPLACE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON resqai.{table}
            FOR EACH ROW EXECUTE FUNCTION resqai.update_updated_at_column();
        """)

    # Create remaining tables via raw SQL for brevity (full DDL)
    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.ngos (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255) NOT NULL UNIQUE,
            type resqai.ngo_type NOT NULL DEFAULT 'ngo',
            description TEXT,
            mission_statement TEXT,
            phone VARCHAR(20) NOT NULL,
            email VARCHAR(255) NOT NULL,
            website VARCHAR(512),
            contact_person VARCHAR(255),
            address_line1 VARCHAR(255) NOT NULL,
            address_line2 VARCHAR(255),
            city VARCHAR(100) NOT NULL,
            state VARCHAR(100) NOT NULL,
            pincode VARCHAR(10) NOT NULL,
            country VARCHAR(100) NOT NULL DEFAULT 'India',
            latitude FLOAT NOT NULL,
            longitude FLOAT NOT NULL,
            geohash VARCHAR(12),
            registration_number VARCHAR(100),
            registration_type VARCHAR(50),
            pan_number VARCHAR(20),
            darpan_id VARCHAR(50),
            fcra_number VARCHAR(50),
            status resqai.ngo_status NOT NULL DEFAULT 'pending_verification',
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            verified_by UUID,
            verified_at VARCHAR(50),
            fraud_score FLOAT NOT NULL DEFAULT 0.0,
            fraud_flags TEXT[],
            beneficiaries_count INTEGER NOT NULL DEFAULT 0,
            capacity_per_day INTEGER NOT NULL DEFAULT 0,
            current_capacity INTEGER NOT NULL DEFAULT 0,
            storage_available BOOLEAN NOT NULL DEFAULT FALSE,
            refrigeration_available BOOLEAN NOT NULL DEFAULT FALSE,
            storage_capacity_kg FLOAT,
            cold_storage_capacity_kg FLOAT,
            food_preferences TEXT[],
            dietary_restrictions TEXT[],
            allergen_restrictions TEXT[],
            min_serving_size INTEGER,
            service_hours JSONB,
            pickup_available BOOLEAN NOT NULL DEFAULT TRUE,
            delivery_required BOOLEAN NOT NULL DEFAULT FALSE,
            advance_notice_hours INTEGER NOT NULL DEFAULT 2,
            acceptance_rate FLOAT NOT NULL DEFAULT 0.0,
            avg_response_time_minutes FLOAT NOT NULL DEFAULT 0.0,
            last_donation_at VARCHAR(50),
            total_received INTEGER NOT NULL DEFAULT 0,
            total_meals_distributed INTEGER NOT NULL DEFAULT 0,
            total_weight_received_kg FLOAT NOT NULL DEFAULT 0.0,
            logo_url VARCHAR(1024),
            cover_image_url VARCHAR(1024),
            rag_embedding_id VARCHAR(255),
            demand_forecast JSONB,
            manager_id UUID NOT NULL REFERENCES resqai.users(id) ON DELETE RESTRICT,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_ngos_manager_id ON resqai.ngos(manager_id);
        CREATE INDEX idx_ngos_status ON resqai.ngos(status);
        CREATE INDEX idx_ngos_city ON resqai.ngos(city);
        CREATE INDEX idx_ngos_type ON resqai.ngos(type);
        CREATE INDEX idx_ngos_location ON resqai.ngos(latitude, longitude);
        CREATE INDEX idx_ngos_geohash ON resqai.ngos(geohash);
        CREATE TRIGGER trg_ngos_updated_at BEFORE UPDATE ON resqai.ngos
            FOR EACH ROW EXECUTE FUNCTION resqai.update_updated_at_column();
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.volunteers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL UNIQUE REFERENCES resqai.users(id) ON DELETE CASCADE,
            badge_number VARCHAR(50) UNIQUE,
            bio TEXT,
            skills TEXT[],
            languages TEXT[],
            status resqai.volunteer_status NOT NULL DEFAULT 'inactive',
            is_available BOOLEAN NOT NULL DEFAULT FALSE,
            availability_schedule JSONB,
            max_concurrent_deliveries INTEGER NOT NULL DEFAULT 1,
            current_deliveries INTEGER NOT NULL DEFAULT 0,
            latitude FLOAT,
            longitude FLOAT,
            geohash VARCHAR(12),
            last_location_update VARCHAR(50),
            city VARCHAR(100),
            service_radius_km FLOAT NOT NULL DEFAULT 10.0,
            id_type VARCHAR(50),
            id_number VARCHAR(50),
            id_verified BOOLEAN NOT NULL DEFAULT FALSE,
            background_check_cleared BOOLEAN NOT NULL DEFAULT FALSE,
            rating FLOAT NOT NULL DEFAULT 0.0,
            rating_count INTEGER NOT NULL DEFAULT 0,
            total_deliveries INTEGER NOT NULL DEFAULT 0,
            successful_deliveries INTEGER NOT NULL DEFAULT 0,
            total_distance_km FLOAT NOT NULL DEFAULT 0.0,
            avg_delivery_time_minutes FLOAT NOT NULL DEFAULT 0.0,
            on_time_rate FLOAT NOT NULL DEFAULT 0.0,
            meals_delivered INTEGER NOT NULL DEFAULT 0,
            carbon_saved_kg FLOAT NOT NULL DEFAULT 0.0,
            rank INTEGER,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_volunteers_user_id ON resqai.volunteers(user_id);
        CREATE INDEX idx_volunteers_status ON resqai.volunteers(status);
        CREATE INDEX idx_volunteers_city ON resqai.volunteers(city);
        CREATE INDEX idx_volunteers_location ON resqai.volunteers(latitude, longitude);
        CREATE INDEX idx_volunteers_geohash ON resqai.volunteers(geohash);
        CREATE TRIGGER trg_volunteers_updated_at BEFORE UPDATE ON resqai.volunteers
            FOR EACH ROW EXECUTE FUNCTION resqai.update_updated_at_column();
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.vehicles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            volunteer_id UUID NOT NULL UNIQUE REFERENCES resqai.volunteers(id) ON DELETE CASCADE,
            type resqai.vehicle_type NOT NULL,
            registration_number VARCHAR(20) NOT NULL UNIQUE,
            make VARCHAR(100),
            model VARCHAR(100),
            year INTEGER,
            color VARCHAR(50),
            capacity_kg FLOAT NOT NULL DEFAULT 50.0,
            capacity_liters FLOAT,
            max_boxes INTEGER,
            has_refrigeration BOOLEAN NOT NULL DEFAULT FALSE,
            refrigeration_temp_min FLOAT,
            refrigeration_temp_max FLOAT,
            is_food_grade BOOLEAN NOT NULL DEFAULT TRUE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            insurance_number VARCHAR(100),
            insurance_expiry VARCHAR(20),
            pollution_cert_expiry VARCHAR(20),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_vehicles_volunteer_id ON resqai.vehicles(volunteer_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.donations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            restaurant_id UUID NOT NULL REFERENCES resqai.restaurants(id) ON DELETE RESTRICT,
            matched_ngo_id UUID REFERENCES resqai.ngos(id) ON DELETE SET NULL,
            volunteer_id UUID REFERENCES resqai.volunteers(id) ON DELETE SET NULL,
            status resqai.donation_status NOT NULL DEFAULT 'draft',
            status_history JSONB DEFAULT '[]',
            total_items INTEGER NOT NULL DEFAULT 0,
            total_servings INTEGER NOT NULL DEFAULT 0,
            total_weight_kg FLOAT NOT NULL DEFAULT 0.0,
            estimated_value_inr FLOAT,
            pickup_address VARCHAR(500) NOT NULL,
            pickup_latitude FLOAT NOT NULL,
            pickup_longitude FLOAT NOT NULL,
            pickup_geohash VARCHAR(12),
            pickup_window_start VARCHAR(50) NOT NULL,
            pickup_window_end VARCHAR(50) NOT NULL,
            special_instructions TEXT,
            contact_at_pickup VARCHAR(20),
            matched_at VARCHAR(50),
            scheduled_pickup_at VARCHAR(50),
            actual_pickup_at VARCHAR(50),
            delivered_at VARCHAR(50),
            confirmed_at VARCHAR(50),
            expires_at VARCHAR(50),
            otp VARCHAR(10),
            otp_expires_at VARCHAR(50),
            otp_verified BOOLEAN NOT NULL DEFAULT FALSE,
            qr_code_url VARCHAR(1024),
            ai_safety_score FLOAT,
            ai_confidence_score FLOAT,
            ai_rejection_reason TEXT,
            ai_processing_time_ms INTEGER,
            models_used JSONB,
            fraud_score FLOAT NOT NULL DEFAULT 0.0,
            fraud_flags JSONB,
            is_flagged BOOLEAN NOT NULL DEFAULT FALSE,
            carbon_saved_kg FLOAT,
            meals_equivalent INTEGER,
            ngo_rating INTEGER,
            ngo_feedback TEXT,
            volunteer_rating INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_donations_restaurant_id ON resqai.donations(restaurant_id);
        CREATE INDEX idx_donations_status ON resqai.donations(status);
        CREATE INDEX idx_donations_matched_ngo_id ON resqai.donations(matched_ngo_id);
        CREATE INDEX idx_donations_volunteer_id ON resqai.donations(volunteer_id);
        CREATE INDEX idx_donations_created_at ON resqai.donations(created_at);
        CREATE INDEX idx_donations_pickup_location ON resqai.donations(pickup_latitude, pickup_longitude);
        CREATE TRIGGER trg_donations_updated_at BEFORE UPDATE ON resqai.donations
            FOR EACH ROW EXECUTE FUNCTION resqai.update_updated_at_column();
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.food_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            donation_id UUID NOT NULL REFERENCES resqai.donations(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            category resqai.food_category NOT NULL DEFAULT 'cooked_meal',
            quantity FLOAT NOT NULL,
            unit VARCHAR(20) NOT NULL DEFAULT 'kg',
            weight_kg FLOAT,
            estimated_servings INTEGER,
            portions INTEGER,
            is_vegetarian BOOLEAN NOT NULL DEFAULT TRUE,
            is_vegan BOOLEAN NOT NULL DEFAULT FALSE,
            is_halal BOOLEAN NOT NULL DEFAULT FALSE,
            is_jain BOOLEAN NOT NULL DEFAULT FALSE,
            allergens TEXT[],
            ingredients TEXT[],
            preparation_time VARCHAR(50),
            best_before VARCHAR(50),
            expiry_time VARCHAR(50),
            storage_temperature_min FLOAT,
            storage_temperature_max FLOAT,
            requires_refrigeration BOOLEAN NOT NULL DEFAULT FALSE,
            requires_freezing BOOLEAN NOT NULL DEFAULT FALSE,
            image_urls TEXT[],
            primary_image_url VARCHAR(1024),
            cloudinary_public_ids TEXT[],
            safety_status resqai.food_safety_status NOT NULL DEFAULT 'pending',
            safety_notes TEXT,
            rejection_reason TEXT,
            ai_analysis JSONB,
            ai_analyzed_at VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_food_items_donation_id ON resqai.food_items(donation_id);
        CREATE INDEX idx_food_items_safety_status ON resqai.food_items(safety_status);
        CREATE INDEX idx_food_items_category ON resqai.food_items(category);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.deliveries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            donation_id UUID NOT NULL UNIQUE REFERENCES resqai.donations(id) ON DELETE RESTRICT,
            volunteer_id UUID NOT NULL REFERENCES resqai.volunteers(id) ON DELETE RESTRICT,
            ngo_id UUID NOT NULL REFERENCES resqai.ngos(id) ON DELETE RESTRICT,
            status resqai.delivery_status NOT NULL DEFAULT 'pending',
            status_history JSONB DEFAULT '[]',
            current_latitude FLOAT,
            current_longitude FLOAT,
            current_speed_kmh FLOAT,
            current_heading FLOAT,
            last_location_update VARCHAR(50),
            location_history JSONB DEFAULT '[]',
            estimated_pickup_at VARCHAR(50),
            actual_pickup_at VARCHAR(50),
            estimated_delivery_at VARCHAR(50),
            actual_delivery_at VARCHAR(50),
            distance_km FLOAT,
            duration_minutes INTEGER,
            pickup_duration_minutes INTEGER,
            otp_used VARCHAR(10),
            confirmed_by_ngo BOOLEAN NOT NULL DEFAULT FALSE,
            confirmed_by_volunteer BOOLEAN NOT NULL DEFAULT FALSE,
            proof_photo_url VARCHAR(1024),
            digital_signature VARCHAR(2048),
            notes TEXT,
            failure_reason TEXT,
            food_condition_on_delivery VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_deliveries_donation_id ON resqai.deliveries(donation_id);
        CREATE INDEX idx_deliveries_volunteer_id ON resqai.deliveries(volunteer_id);
        CREATE INDEX idx_deliveries_ngo_id ON resqai.deliveries(ngo_id);
        CREATE INDEX idx_deliveries_status ON resqai.deliveries(status);
        CREATE TRIGGER trg_deliveries_updated_at BEFORE UPDATE ON resqai.deliveries
            FOR EACH ROW EXECUTE FUNCTION resqai.update_updated_at_column();
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.routes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            delivery_id UUID NOT NULL UNIQUE REFERENCES resqai.deliveries(id) ON DELETE CASCADE,
            encoded_polyline TEXT,
            waypoints JSONB DEFAULT '[]',
            bounds JSONB,
            total_distance_km FLOAT NOT NULL DEFAULT 0.0,
            total_duration_minutes INTEGER NOT NULL DEFAULT 0,
            pickup_to_delivery_km FLOAT,
            algorithm resqai.route_algorithm NOT NULL DEFAULT 'or_tools',
            computation_time_ms INTEGER,
            alternative_routes JSONB,
            optimization_score FLOAT,
            traffic_condition VARCHAR(20),
            traffic_data JSONB,
            weather_condition VARCHAR(50),
            weather_data JSONB,
            is_traffic_aware BOOLEAN NOT NULL DEFAULT TRUE,
            is_weather_aware BOOLEAN NOT NULL DEFAULT FALSE,
            is_multi_stop BOOLEAN NOT NULL DEFAULT FALSE,
            status resqai.route_status NOT NULL DEFAULT 'computed',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_routes_delivery_id ON resqai.routes(delivery_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.notifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES resqai.users(id) ON DELETE SET NULL,
            donation_id UUID REFERENCES resqai.donations(id) ON DELETE SET NULL,
            type resqai.notification_type NOT NULL,
            channel resqai.notification_channel NOT NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            data JSONB,
            template_id VARCHAR(100),
            recipient_email VARCHAR(255),
            recipient_phone VARCHAR(20),
            recipient_device_token VARCHAR(512),
            status resqai.notification_status NOT NULL DEFAULT 'pending',
            sent_at VARCHAR(50),
            delivered_at VARCHAR(50),
            read_at VARCHAR(50),
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            last_error TEXT,
            external_message_id VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_notifications_user_id ON resqai.notifications(user_id);
        CREATE INDEX idx_notifications_donation_id ON resqai.notifications(donation_id);
        CREATE INDEX idx_notifications_status ON resqai.notifications(status);
        CREATE INDEX idx_notifications_type ON resqai.notifications(type);
        CREATE INDEX idx_notifications_created_at ON resqai.notifications(created_at);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.ai_decisions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            donation_id UUID REFERENCES resqai.donations(id) ON DELETE CASCADE,
            session_id VARCHAR(100),
            user_id UUID,
            agent_type resqai.agent_type NOT NULL,
            task_name VARCHAR(100),
            status resqai.agent_decision_status NOT NULL DEFAULT 'pending',
            model_used VARCHAR(100) NOT NULL,
            model_provider VARCHAR(50),
            model_version VARCHAR(50),
            input_data JSONB,
            output_data JSONB,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            cost_usd FLOAT,
            confidence_score FLOAT,
            reasoning TEXT,
            explanation TEXT,
            citations JSONB,
            latency_ms INTEGER,
            retry_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            error_type VARCHAR(100),
            was_overridden BOOLEAN NOT NULL DEFAULT FALSE,
            override_reason TEXT,
            overridden_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_ai_decisions_donation_id ON resqai.ai_decisions(donation_id);
        CREATE INDEX idx_ai_decisions_agent_type ON resqai.ai_decisions(agent_type);
        CREATE INDEX idx_ai_decisions_status ON resqai.ai_decisions(status);
        CREATE INDEX idx_ai_decisions_model_used ON resqai.ai_decisions(model_used);
        CREATE INDEX idx_ai_decisions_created_at ON resqai.ai_decisions(created_at);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES resqai.users(id) ON DELETE SET NULL,
            user_email VARCHAR(255),
            user_role VARCHAR(50),
            client_ip VARCHAR(45),
            user_agent VARCHAR(512),
            request_id VARCHAR(100),
            http_method VARCHAR(10),
            http_path VARCHAR(512),
            http_status INTEGER,
            duration_ms FLOAT,
            resource_type VARCHAR(100) NOT NULL,
            resource_id VARCHAR(100),
            action VARCHAR(100) NOT NULL,
            old_values JSONB,
            new_values JSONB,
            changed_fields JSONB,
            notes TEXT,
            tags JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_audit_logs_user_id ON resqai.audit_logs(user_id);
        CREATE INDEX idx_audit_logs_resource_type ON resqai.audit_logs(resource_type);
        CREATE INDEX idx_audit_logs_resource_id ON resqai.audit_logs(resource_id);
        CREATE INDEX idx_audit_logs_action ON resqai.audit_logs(action);
        CREATE INDEX idx_audit_logs_created_at ON resqai.audit_logs(created_at);
        CREATE INDEX idx_audit_logs_request_id ON resqai.audit_logs(request_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.knowledge_documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(500) NOT NULL,
            document_type resqai.document_type NOT NULL,
            source VARCHAR(255),
            source_url VARCHAR(1024),
            language VARCHAR(10) NOT NULL DEFAULT 'en',
            entity_type VARCHAR(50),
            entity_id UUID,
            raw_content TEXT,
            processed_content TEXT,
            summary TEXT,
            file_url VARCHAR(1024),
            file_type VARCHAR(50),
            file_size_bytes INTEGER,
            total_chunks INTEGER NOT NULL DEFAULT 0,
            embedding_model VARCHAR(100),
            embedding_dimensions INTEGER,
            qdrant_collection VARCHAR(100),
            is_embedded BOOLEAN NOT NULL DEFAULT FALSE,
            last_embedded_at VARCHAR(50),
            metadata JSONB,
            tags TEXT[],
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            version INTEGER NOT NULL DEFAULT 1,
            expires_at VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_knowledge_documents_type ON resqai.knowledge_documents(document_type);
        CREATE INDEX idx_knowledge_documents_entity_id ON resqai.knowledge_documents(entity_id);
        CREATE INDEX idx_knowledge_documents_is_active ON resqai.knowledge_documents(is_active);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.knowledge_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL,
            content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            token_count INTEGER,
            char_count INTEGER,
            section_title VARCHAR(500),
            page_number INTEGER,
            start_char INTEGER,
            end_char INTEGER,
            qdrant_point_id VARCHAR(100),
            qdrant_collection VARCHAR(100),
            embedding_model VARCHAR(100),
            retrieval_count INTEGER NOT NULL DEFAULT 0,
            avg_relevance_score FLOAT,
            metadata JSONB,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_knowledge_chunks_document_id ON resqai.knowledge_chunks(document_id);
        CREATE INDEX idx_knowledge_chunks_qdrant_id ON resqai.knowledge_chunks(qdrant_point_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.analytics_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_date VARCHAR(20) NOT NULL,
            snapshot_type resqai.snapshot_type NOT NULL DEFAULT 'daily',
            total_donations INTEGER NOT NULL DEFAULT 0,
            total_meals_saved INTEGER NOT NULL DEFAULT 0,
            total_weight_kg FLOAT NOT NULL DEFAULT 0.0,
            total_deliveries INTEGER NOT NULL DEFAULT 0,
            successful_deliveries INTEGER NOT NULL DEFAULT 0,
            failed_deliveries INTEGER NOT NULL DEFAULT 0,
            carbon_saved_kg FLOAT NOT NULL DEFAULT 0.0,
            water_saved_liters FLOAT,
            land_saved_sqm FLOAT,
            methane_prevented_kg FLOAT,
            avg_pickup_time_minutes FLOAT,
            avg_delivery_time_minutes FLOAT,
            avg_total_time_minutes FLOAT,
            success_rate FLOAT,
            on_time_rate FLOAT,
            active_restaurants INTEGER NOT NULL DEFAULT 0,
            active_ngos INTEGER NOT NULL DEFAULT 0,
            active_volunteers INTEGER NOT NULL DEFAULT 0,
            new_restaurants INTEGER NOT NULL DEFAULT 0,
            new_ngos INTEGER NOT NULL DEFAULT 0,
            ai_decisions_made INTEGER NOT NULL DEFAULT 0,
            ai_accuracy_rate FLOAT,
            avg_ai_confidence FLOAT,
            fraud_cases_detected INTEGER NOT NULL DEFAULT 0,
            by_city JSONB,
            by_food_category JSONB,
            by_ngo_type JSONB,
            by_restaurant_type JSONB,
            top_restaurants JSONB,
            top_ngos JSONB,
            top_volunteers JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_analytics_snapshots_date ON resqai.analytics_snapshots(snapshot_date);
        CREATE INDEX idx_analytics_snapshots_type ON resqai.analytics_snapshots(snapshot_type);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.daily_kpis (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kpi_date VARCHAR(20) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            entity_id UUID NOT NULL,
            donations INTEGER NOT NULL DEFAULT 0,
            meals_saved INTEGER NOT NULL DEFAULT 0,
            weight_kg FLOAT NOT NULL DEFAULT 0.0,
            carbon_saved_kg FLOAT NOT NULL DEFAULT 0.0,
            deliveries INTEGER NOT NULL DEFAULT 0,
            score FLOAT NOT NULL DEFAULT 0.0,
            rank INTEGER,
            extra JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_daily_kpis_date ON resqai.daily_kpis(kpi_date);
        CREATE INDEX idx_daily_kpis_entity ON resqai.daily_kpis(entity_type, entity_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS resqai.reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            requested_by UUID REFERENCES resqai.users(id) ON DELETE SET NULL,
            title VARCHAR(255) NOT NULL,
            type resqai.report_type NOT NULL,
            format resqai.report_format NOT NULL DEFAULT 'pdf',
            parameters JSONB,
            date_from VARCHAR(20),
            date_to VARCHAR(20),
            status resqai.report_status NOT NULL DEFAULT 'queued',
            progress_percent INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            file_url VARCHAR(1024),
            cloudinary_public_id VARCHAR(255),
            file_size_bytes INTEGER,
            row_count INTEGER,
            generation_time_ms INTEGER,
            completed_at VARCHAR(50),
            expires_at VARCHAR(50),
            is_public BOOLEAN NOT NULL DEFAULT FALSE,
            download_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_reports_requested_by ON resqai.reports(requested_by);
        CREATE INDEX idx_reports_type ON resqai.reports(type);
        CREATE INDEX idx_reports_status ON resqai.reports(status);
    """)

    # ---- Full-text search indexes using pg_trgm ----
    op.execute("""
        CREATE INDEX idx_restaurants_name_trgm ON resqai.restaurants
            USING gin (name gin_trgm_ops);
        CREATE INDEX idx_ngos_name_trgm ON resqai.ngos
            USING gin (name gin_trgm_ops);
        CREATE INDEX idx_food_items_name_trgm ON resqai.food_items
            USING gin (name gin_trgm_ops);
    """)


def downgrade() -> None:
    """Drop all ResQAI tables and schema."""
    tables = [
        "reports", "daily_kpis", "analytics_snapshots",
        "knowledge_chunks", "knowledge_documents",
        "audit_logs", "ai_decisions", "notifications",
        "routes", "deliveries", "food_items", "donations",
        "vehicles", "volunteers", "ngos", "restaurants", "users",
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS resqai.{table} CASCADE")

    enums = [
        "user_role", "user_status", "restaurant_type", "restaurant_status",
        "ngo_type", "ngo_status", "volunteer_status", "vehicle_type",
        "donation_status", "food_category", "food_safety_status",
        "delivery_status", "route_algorithm", "route_status",
        "notification_channel", "notification_type", "notification_status",
        "agent_type", "agent_decision_status", "report_type", "report_format",
        "report_status", "snapshot_type", "document_type",
    ]
    for enum in enums:
        op.execute(f"DROP TYPE IF EXISTS resqai.{enum} CASCADE")

    op.execute("DROP SCHEMA IF EXISTS resqai CASCADE")
