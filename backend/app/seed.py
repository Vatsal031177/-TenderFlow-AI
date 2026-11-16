from sqlalchemy.orm import Session
from app.db.models import CatalogItem
from app.ai.gateway import gateway
from app.ai.rag import rag_engine

SAMPLE_CATALOG = [
    {
        "sku": "SKU-DRYWALL-FR60",
        "name": "Fire-Rated Gypsum Board F90 / GKF 12.5mm",
        "category": "Drywall & Partitions",
        "unit": "m2",
        "cost_price": 14.50,
        "list_price": 21.80,
        "din_standard": "DIN 4102-4 / EN 520 Type DF",
        "description": "Fire-resistant plasterboard partition panel EI90 / F90 for commercial interior walls and shafts.",
    },
    {
        "sku": "SKU-SEALANT-FIRESTOP",
        "name": "Intumescent Firestop Acrylic Sealant 310ml",
        "category": "Fire Protection",
        "unit": "pcs",
        "cost_price": 9.20,
        "list_price": 14.90,
        "din_standard": "DIN 4102-1 / EN 1366-4",
        "description": "Intumescent firestop joint sealant for F90 drywall perimeter joints and penetrations.",
    },
    {
        "sku": "SKU-PROFILE-CW75",
        "name": "Galvanized Steel Stud Profile CW 75/50",
        "category": "Drywall Substructure",
        "unit": "m",
        "cost_price": 3.80,
        "list_price": 5.40,
        "din_standard": "DIN EN 14195",
        "description": "Metal framing stud profile CW75 for interior drywall partitions.",
    },
    {
        "sku": "SKU-INSUL-MINWOOL-100",
        "name": "Rockwool Acoustic & Thermal Insulation 100mm",
        "category": "Insulation",
        "unit": "m2",
        "cost_price": 11.00,
        "list_price": 15.20,
        "din_standard": "DIN 4108 / EN 13162 A1",
        "description": "Non-combustible mineral wool thermal and acoustic insulation slab 100mm WLG 035.",
    },
    {
        "sku": "SKU-VAPOR-BARRIER",
        "name": "Humidity-Variable Vapor Retarder Membrane",
        "category": "Insulation Accessories",
        "unit": "m2",
        "cost_price": 2.10,
        "list_price": 3.40,
        "din_standard": "DIN 4108-3",
        "description": "Vapor control barrier foil sd-value adaptive for interior insulation.",
    },
    {
        "sku": "SKU-CONCRETE-C30",
        "name": "Ready-Mix Structural Concrete C30/37 XC4",
        "category": "Concrete & Structural",
        "unit": "m3",
        "cost_price": 128.00,
        "list_price": 152.00,
        "din_standard": "DIN EN 206 / DIN 1045-2",
        "description": "High-durability ready-mix concrete C30/37 exposure class XC4 XF1 for foundations and slabs.",
    },
]


def seed_catalog(db: Session):
    existing = {c.sku for c in db.query(CatalogItem.sku).all()}
    for item_data in SAMPLE_CATALOG:
        if item_data["sku"] not in existing:
            text_for_embedding = (
                f"{item_data['name']} {item_data['din_standard']} {item_data['description']}"
            )
            item = CatalogItem(
                **item_data,
                embedding=gateway.embed(text_for_embedding),
            )
            db.add(item)
            db.flush()
            try:
                rag_engine.index_catalog_item(item)
            except Exception:
                pass
    db.commit()
