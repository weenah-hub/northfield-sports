"""
Product catalogue seed
======================
Fills an empty products table with the starter catalogue.

Usage:
    cd backend
    python seed.py
"""

from database import Base, SessionLocal, engine
from models import Product

CATALOGUE = [
    {
        "name": "Matchday Home Jersey",
        "description": "Breathable performance knit with taped seams and a hem that stays put.",
        "price": 64.00,
        "category": "Jerseys",
        "stock": 24,
    },
    {
        "name": "Away Jersey",
        "description": "Reversible design for match and training. Machine washable.",
        "price": 64.00,
        "category": "Jerseys",
        "stock": 18,
    },
    {
        "name": "Training Shorts",
        "description": "Four-way stretch with a zip pocket for keys and a phone.",
        "price": 32.00,
        "category": "Shorts",
        "stock": 40,
    },
    {
        "name": "Pro Match Football",
        "description": "Size 5, thermally bonded seams, flight-tested over 200 matches.",
        "price": 38.00,
        "category": "Equipment",
        "stock": 15,
    },
    {
        "name": "Goalkeeper Gloves",
        "description": "4mm German latex palms with a cut-finger feel for grip control.",
        "price": 52.00,
        "category": "Equipment",
        "stock": 12,
    },
    {
        "name": "Everyday Crew Socks (3-pack)",
        "description": "Cushioned heel and toe, arch support that holds after washing.",
        "price": 18.00,
        "category": "Accessories",
        "stock": 60,
    },
    {
        "name": "Club Scarf",
        "description": "Brushed cotton, woven crest, generous 180cm length.",
        "price": 22.00,
        "category": "Accessories",
        "stock": 35,
    },
    {
        "name": "Water Bottle 1L",
        "description": "BPA-free, leak-proof, fits standard bottle holders.",
        "price": 14.00,
        "category": "Accessories",
        "stock": 0,
    },
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        existing = session.query(Product).count()
        if existing:
            print(f"Skipped: {existing} product(s) already in the catalogue.")
            return

        session.add_all(Product(**row) for row in CATALOGUE)
        session.commit()
        print(f"Seeded {len(CATALOGUE)} products.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
