#!/usr/bin/env python3
"""
Initialize Superset with IoTDB database connection and PLC dashboard.
This script is run after Superset starts to configure the IoTDB connection
and import the dashboard configuration.
"""
import os
import time
import json
import requests
from pathlib import Path

# Configuration
SUPERSET_URL = "http://localhost:8088"
SUPERSET_USERNAME = os.getenv("SUPERSET_ADMIN_USERNAME", "admin")
SUPERSET_PASSWORD = os.getenv("SUPERSET_ADMIN_PASSWORD", "admin")

# IoTDB connection details
IOTDB_URI = "iotdb://root:root@iotdb:6667"
IOTDB_DATABASE_NAME = "IoTDB"

# Paths
SCRIPTS_DIR = Path(__file__).parent
DASHBOARD_FILE = SCRIPTS_DIR / "superset" / "dashboards" / "plc_iot_dashboard.json"
DATABASE_YAML = SCRIPTS_DIR / "superset" / "databases" / "iotdb.yaml"


def wait_for_superset(timeout=300, interval=5):
    """Wait for Superset to become available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{SUPERSET_URL}/api/v1/security/health", timeout=5)
            if response.status_code == 200:
                print("Superset is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(interval)
    raise Exception("Superset did not become ready within timeout")


def login():
    """Login to Superset and return session cookies."""
    login_url = f"{SUPERSET_URL}/api/v1/security/login"
    payload = {
        "username": SUPERSET_USERNAME,
        "password": SUPERSET_PASSWORD,
        "provider": "db"
    }
    response = requests.post(login_url, json=payload)
    response.raise_for_status()
    
    # Get session cookie
    session_cookie = None
    for cookie in response.cookies:
        if cookie.name == "session":
            session_cookie = cookie.value
            break
    
    if not session_cookie:
        raise Exception("Failed to get session cookie")
    
    return {"session": session_cookie}


def create_iotdb_database(cookies):
    """Create IoTDB database connection in Superset."""
    url = f"{SUPERSET_URL}/api/v1/database/"
    
    # Check if database already exists
    response = requests.get(url, cookies=cookies)
    response.raise_for_status()
    databases = response.json().get("result", [])
    
    for db in databases:
        if db.get("database_name") == IOTDB_DATABASE_NAME:
            print(f"Database '{IOTDB_DATABASE_NAME}' already exists")
            return db["id"]
    
    # Create new database
    payload = {
        "database_name": IOTDB_DATABASE_NAME,
        "sqlalchemy_uri": IOTDB_URI,
        "expose_in_sqla": True,
        "is_managed_externally": False
    }
    
    response = requests.post(url, json=payload, cookies=cookies)
    response.raise_for_status()
    result = response.json()
    db_id = result.get("result", {}).get("id")
    
    if not db_id:
        raise Exception(f"Failed to create database: {result}")
    
    print(f"Created IoTDB database with ID: {db_id}")
    return db_id


def get_datasource_id(database_id, cookies):
    """Get or create datasource (table) for IoTDB."""
    # For IoTDB, we use the device path as the table
    url = f"{SUPERSET_URL}/api/v1/dataset/"
    
    # List existing datasets
    response = requests.get(url, cookies=cookies)
    response.raise_for_status()
    datasets = response.json().get("result", [])
    
    # Look for our dataset
    for ds in datasets:
        if ds.get("table_name") == "root.sg.line_1":
            print(f"Dataset 'root.sg.line_1' already exists with ID: {ds['id']}")
            return ds["id"]
    
    # Create new dataset
    payload = {
        "database_id": database_id,
        "table_name": "root.sg.line_1",
        "main_dttm_col": "time",
        "schema": "root.sg"
    }
    
    response = requests.post(url, json=payload, cookies=cookies)
    response.raise_for_status()
    result = response.json()
    ds_id = result.get("result", {}).get("id")
    
    if not ds_id:
        raise Exception(f"Failed to create dataset: {result}")
    
    print(f"Created dataset with ID: {ds_id}")
    return ds_id


def import_dashboard(database_id, datasource_id, cookies):
    """Import the PLC IoT dashboard."""
    if not DASHBOARD_FILE.exists():
        print(f"Dashboard file not found: {DASHBOARD_FILE}")
        return
    
    # Load dashboard JSON
    with open(DASHBOARD_FILE) as f:
        dashboard_data = json.load(f)
    
    # Update slice datasource IDs
    # This is a simplified approach - in production you'd want to properly map slices
    
    # Create dashboard
    url = f"{SUPERSET_URL}/api/v1/dashboard/"
    payload = {
        "dashboard_title": dashboard_data.get("dashboard_title", "PLC IoT Dashboard"),
        "position": json.dumps(dashboard_data.get("position", {})),
        "properties": json.dumps(dashboard_data.get("properties", {})),
        "css": dashboard_data.get("css", "")
    }
    
    response = requests.post(url, json=payload, cookies=cookies)
    response.raise_for_status()
    result = response.json()
    dashboard_id = result.get("result", {}).get("id")
    
    if not dashboard_id:
        raise Exception(f"Failed to create dashboard: {result}")
    
    print(f"Created dashboard with ID: {dashboard_id}")
    return dashboard_id


def main():
    """Main initialization function."""
    print("Starting Superset initialization...")
    
    # Wait for Superset to be ready
    wait_for_superset()
    
    # Login
    cookies = login()
    print("Logged in to Superset")
    
    # Create IoTDB database connection
    database_id = create_iotdb_database(cookies)
    
    # Get or create datasource
    datasource_id = get_datasource_id(database_id, cookies)
    
    # Import dashboard
    try:
        import_dashboard(database_id, datasource_id, cookies)
    except Exception as e:
        print(f"Dashboard import skipped or failed: {e}")
    
    print("Superset initialization complete!")


if __name__ == "__main__":
    main()
