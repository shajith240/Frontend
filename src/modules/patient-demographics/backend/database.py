"""MongoDB Atlas connection management for the patient demographics module."""

import time
import os
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

load_dotenv()

DB_NAME = "patient_demographics_db"
MONGO_URI_KEY = "MONGODB_URI"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


class DatabaseConnection:
    """Manages a singleton connection to MongoDB Atlas with retry logic."""

    def __init__(self) -> None:
        """Initialise the DatabaseConnection with no active client."""
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None

    def connect(self) -> None:
        """Connect to MongoDB Atlas, retrying up to 3 times on failure.

        Raises:
            ConnectionError: If all retry attempts are exhausted.
            ValueError: If MONGODB_URI is not set in the environment.
        """
        uri = os.getenv(MONGO_URI_KEY)
        if not uri:
            raise ValueError(
                f"'{MONGO_URI_KEY}' is not set. Add it to your .env file."
            )

        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                client: MongoClient = MongoClient(uri, serverSelectionTimeoutMS=5000)
                # Force an actual network round-trip to verify the connection.
                client.admin.command("ping")
                self._client = client
                self._db = client.get_database(DB_NAME)
                print(f"Connected to MongoDB Atlas — {DB_NAME}")
                self._create_indexes()
                return
            except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    print(
                        f"Connection attempt {attempt}/{MAX_RETRIES} failed: {exc}. "
                        f"Retrying in {RETRY_DELAY_SECONDS}s…"
                    )
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    print(f"Connection attempt {attempt}/{MAX_RETRIES} failed: {exc}.")

        if isinstance(last_error, BaseException):
            raise ConnectionError(
                f"Could not connect to MongoDB Atlas after {MAX_RETRIES} attempts."
            ) from last_error
        
        raise ConnectionError(
            f"Could not connect to MongoDB Atlas after {MAX_RETRIES} attempts."
        )

    def disconnect(self) -> None:
        """Close the MongoDB client connection if it is open."""
        client = self._client
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                print(f"Error while closing MongoDB connection: {exc}")
            finally:
                self._client = None
                self._db = None

    def get_collection(self, name: str) -> Collection:
        """Return a MongoDB collection by name.

        Args:
            name: The collection name (e.g. 'patients', 'visits').

        Returns:
            A PyMongo Collection object.

        Raises:
            RuntimeError: If called before a successful connect().
        """
        db = self._db
        if db is None:
            raise RuntimeError(
                "No active database connection. Call connect() first."
            )
        return db.get_collection(name)

    def _create_indexes(self) -> None:
        """Create indexes on the patients collection after connecting."""
        try:
            patients = self.get_collection("patients")
            patients.create_index([("patient_id", ASCENDING)], unique=True)
            patients.create_index([("name", ASCENDING)])
            patients.create_index([("date_of_birth", ASCENDING)])
        except Exception as exc:
            print(f"Warning: could not create indexes on patients collection: {exc}")


def ping_database() -> bool:
    """Ping MongoDB Atlas to check connectivity.

    Returns:
        True if the server responds to a ping, False otherwise.
    """
    uri = os.getenv(MONGO_URI_KEY)
    if not uri:
        return False

    try:
        client: MongoClient = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False
