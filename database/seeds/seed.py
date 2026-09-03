"""
ResQAI - Database Seed Script
Populates the database with realistic demo data for development and testing.
Run with: python database/seeds/seed.py
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

# Add backend to path
import sys
sys.path.insert(0, "backend")

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole, UserStatus
from app.models.restaurant import Restaurant, RestaurantType, RestaurantStatus
from app.models.ngo import NGO, NGOType, NGOStatus
from app.models.volunteer import Volunteer, VolunteerStatus
from app.models.vehicle import Vehicle, VehicleType
from loguru import logger


# -------------------------------------------------------
# Seed Data
# -------------------------------------------------------
CITIES = [
    {"city": "Mumbai", "state": "Maharashtra", "lat": 19.0760, "lng": 72.8777},
    {"city": "Delhi", "state": "Delhi", "lat": 28.6139, "lng": 77.2090},
    {"city": "Bengaluru", "state": "Karnataka", "lat": 12.9716, "lng": 77.5946},
    {"city": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lng": 80.2707},
    {"city": "Hyderabad", "state": "Telangana", "lat": 17.3850, "lng": 78.4867},
]

RESTAURANTS = [
    {"name": "The Grand Palace Hotel", "type": RestaurantType.HOTEL, "city_idx": 0},
    {"name": "Annapurna Restaurant", "type": RestaurantType.RESTAURANT, "city_idx": 0},
    {"name": "Royal Banquet Hall", "type": RestaurantType.MARRIAGE_HALL, "city_idx": 1},
    {"name": "Sunrise Bakery", "type": RestaurantType.BAKERY, "city_idx": 1},
    {"name": "Tech Park Cafeteria", "type": RestaurantType.CORPORATE_CAFETERIA, "city_idx": 2},
    {"name": "Spice Garden Catering", "type": RestaurantType.CATERING, "city_idx": 2},
    {"name": "Mumbai Street Kitchen", "type": RestaurantType.CLOUD_KITCHEN, "city_idx": 0},
    {"name": "Heritage Grand Hotel", "type": RestaurantType.HOTEL, "city_idx": 3},
]

NGOS = [
    {"name": "Helping Hands Foundation", "type": NGOType.NGO, "city_idx": 0, "capacity": 500},
    {"name": "Little Stars Orphanage", "type": NGOType.ORPHANAGE, "city_idx": 0, "capacity": 150},
    {"name": "Sunset Old Age Home", "type": NGOType.OLD_AGE_HOME, "city_idx": 1, "capacity": 80},
    {"name": "Hope Shelter", "type": NGOType.SHELTER, "city_idx": 1, "capacity": 200},
    {"name": "Community Kitchen Delhi", "type": NGOType.COMMUNITY_KITCHEN, "city_idx": 1, "capacity": 1000},
    {"name": "Rainbow Children's Home", "type": NGOType.ORPHANAGE, "city_idx": 2, "capacity": 120},
    {"name": "Asha Food Bank", "type": NGOType.FOOD_BANK, "city_idx": 2, "capacity": 300},
    {"name": "Seva Community Kitchen", "type": NGOType.COMMUNITY_KITCHEN, "city_idx": 3, "capacity": 400},
]


async def seed_database() -> None:
    """Main seed function — creates all demo entities."""
    async with AsyncSessionLocal() as db:
        logger.info("Starting database seed...")

        # ---- Admin User ----
        admin = User(
            email="admin@resqai.org",
            name="ResQAI Admin",
            hashed_password=hash_password("Admin@123456"),
            role=UserRole.SUPER_ADMIN,
            status=UserStatus.ACTIVE,
            is_email_verified=True,
            city="Mumbai",
            state="Maharashtra",
        )
        db.add(admin)
        await db.flush()
        logger.info(f"Created admin user: {admin.email}")

        # ---- Restaurant Owners ----
        restaurant_owners = []
        for i, r_data in enumerate(RESTAURANTS):
            owner = User(
                email=f"restaurant{i+1}@resqai.org",
                name=f"{r_data['name']} Owner",
                hashed_password=hash_password("Password@123"),
                role=UserRole.RESTAURANT_OWNER,
                status=UserStatus.ACTIVE,
                is_email_verified=True,
                phone=f"+9198765{str(i+1).zfill(5)}",
                city=CITIES[r_data["city_idx"]]["city"],
                state=CITIES[r_data["city_idx"]]["state"],
            )
            db.add(owner)
            restaurant_owners.append(owner)
        await db.flush()
        logger.info(f"Created {len(restaurant_owners)} restaurant owners")

        # ---- Restaurants ----
        restaurants = []
        for i, r_data in enumerate(RESTAURANTS):
            city_info = CITIES[r_data["city_idx"]]
            restaurant = Restaurant(
                name=r_data["name"],
                slug=r_data["name"].lower().replace(" ", "-"),
                type=r_data["type"],
                phone=f"+9122{str(i+1).zfill(8)}",
                email=f"contact@{r_data['name'].lower().replace(' ', '')}.com",
                address_line1=f"{i+1}00, Main Road",
                city=city_info["city"],
                state=city_info["state"],
                pincode="400001",
                latitude=city_info["lat"] + (i * 0.001),
                longitude=city_info["lng"] + (i * 0.001),
                geohash="te7u",
                fssai_license=f"10016011{str(i+1).zfill(6)}",
                status=RestaurantStatus.ACTIVE,
                is_verified=True,
                owner_id=restaurant_owners[i].id,
                serves_veg=True,
                serves_nonveg=i % 2 == 0,
                total_donations=i * 15,
                total_meals_saved=i * 150,
                carbon_saved_kg=i * 75.5,
                sustainability_score=7.5 + (i * 0.1),
            )
            db.add(restaurant)
            restaurants.append(restaurant)
        await db.flush()
        logger.info(f"Created {len(restaurants)} restaurants")

        # ---- NGO Managers ----
        ngo_managers = []
        for i, n_data in enumerate(NGOS):
            manager = User(
                email=f"ngo{i+1}@resqai.org",
                name=f"{n_data['name']} Manager",
                hashed_password=hash_password("Password@123"),
                role=UserRole.NGO_MANAGER,
                status=UserStatus.ACTIVE,
                is_email_verified=True,
                phone=f"+9197654{str(i+1).zfill(5)}",
                city=CITIES[n_data["city_idx"]]["city"],
                state=CITIES[n_data["city_idx"]]["state"],
            )
            db.add(manager)
            ngo_managers.append(manager)
        await db.flush()
        logger.info(f"Created {len(ngo_managers)} NGO managers")

        # ---- NGOs ----
        ngos = []
        for i, n_data in enumerate(NGOS):
            city_info = CITIES[n_data["city_idx"]]
            ngo = NGO(
                name=n_data["name"],
                slug=n_data["name"].lower().replace(" ", "-"),
                type=n_data["type"],
                phone=f"+9111{str(i+1).zfill(8)}",
                email=f"contact@{n_data['name'].lower().replace(' ', '')}.org",
                address_line1=f"{i+1}5, Service Road",
                city=city_info["city"],
                state=city_info["state"],
                pincode="400002",
                latitude=city_info["lat"] - (i * 0.001),
                longitude=city_info["lng"] - (i * 0.001),
                geohash="te7u",
                registration_number=f"MH/NGO/{str(i+1).zfill(6)}",
                status=NGOStatus.ACTIVE,
                is_verified=True,
                beneficiaries_count=n_data["capacity"] // 2,
                capacity_per_day=n_data["capacity"],
                current_capacity=n_data["capacity"] - (i * 20),
                storage_available=i % 2 == 0,
                refrigeration_available=i % 3 == 0,
                food_preferences=["cooked_meal", "raw_produce"],
                dietary_restrictions=["no_beef"] if i % 2 == 0 else [],
                acceptance_rate=0.85 + (i * 0.01),
                avg_response_time_minutes=15 + i,
                total_received=i * 20,
                total_meals_distributed=i * 200,
                manager_id=ngo_managers[i].id,
            )
            db.add(ngo)
            ngos.append(ngo)
        await db.flush()
        logger.info(f"Created {len(ngos)} NGOs")

        # ---- Volunteers ----
        volunteer_users = []
        volunteers = []
        for i in range(10):
            city_info = CITIES[i % len(CITIES)]
            user = User(
                email=f"volunteer{i+1}@resqai.org",
                name=f"Volunteer {i+1}",
                hashed_password=hash_password("Password@123"),
                role=UserRole.VOLUNTEER,
                status=UserStatus.ACTIVE,
                is_email_verified=True,
                phone=f"+9196543{str(i+1).zfill(5)}",
                city=city_info["city"],
                state=city_info["state"],
            )
            db.add(user)
            volunteer_users.append(user)

        await db.flush()

        for i, user in enumerate(volunteer_users):
            city_info = CITIES[i % len(CITIES)]
            vol = Volunteer(
                user_id=user.id,
                badge_number=f"VOL-{str(i+1).zfill(4)}",
                status=VolunteerStatus.ACTIVE,
                is_available=True,
                latitude=city_info["lat"] + (i * 0.002),
                longitude=city_info["lng"] + (i * 0.002),
                geohash="te7u",
                city=city_info["city"],
                service_radius_km=15.0,
                id_verified=True,
                background_check_cleared=True,
                rating=4.2 + (i * 0.05),
                rating_count=i * 5,
                total_deliveries=i * 8,
                successful_deliveries=i * 7,
                meals_delivered=i * 80,
                carbon_saved_kg=i * 25.0,
            )
            db.add(vol)
            volunteers.append(vol)

        await db.flush()

        # Add vehicles for volunteers
        vehicle_types = [VehicleType.MOTORCYCLE, VehicleType.CAR, VehicleType.BICYCLE]
        for i, vol in enumerate(volunteers[:5]):
            vehicle = Vehicle(
                volunteer_id=vol.id,
                type=vehicle_types[i % len(vehicle_types)],
                registration_number=f"MH{str(i+1).zfill(2)}AB{str(i+1000)}",
                make="Honda" if i % 2 == 0 else "Maruti",
                capacity_kg=50.0 if vehicle_types[i % 3] != VehicleType.BICYCLE else 10.0,
                has_refrigeration=i == 0,
                is_food_grade=True,
            )
            db.add(vehicle)

        await db.commit()
        logger.info(f"Created {len(volunteers)} volunteers with vehicles")
        logger.info("Database seeded successfully!")

        print("\n=== Seed Credentials ===")
        print("Admin:      admin@resqai.org / Admin@123456")
        print("Restaurant: restaurant1@resqai.org / Password@123")
        print("NGO:        ngo1@resqai.org / Password@123")
        print("Volunteer:  volunteer1@resqai.org / Password@123")
        print("========================\n")


if __name__ == "__main__":
    asyncio.run(seed_database())
