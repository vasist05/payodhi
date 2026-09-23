import os

# Read from backend/.env (which loads from payodhi/.env)
DB_URL = os.environ.get(
    "SIH_DB_URL",
    "postgresql://payodi:payodi_local_pass_2025@localhost:5432/payodi_db"
)

MOCK_MODE = False
MOCK_DB_DIR = "data/mock_db"


def get_connection():
    import psycopg2
    return psycopg2.connect(DB_URL)


def get_mock_path(table_name: str) -> str:
    return os.path.join(MOCK_DB_DIR, f"{table_name}.json")