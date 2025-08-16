#!/usr/bin/env python3

import cgi
import json
import sys
import os
from datetime import datetime
import mysql.connector
from mysql.connector import Error

class Database:
    def __init__(self):
        self.config = {
            'host': 'localhost',
            'user': 'vehicle_user',
            'password': 'your_password',
            'database': 'vehicle_maintenance',
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci'
        }

    def get_connection(self):
        try:
            connection = mysql.connector.connect(**self.config)
            return connection
        except Error as e:
            raise Exception(f"Database connection failed: {e}")

    def init_database(self):
        try:
            # Connect without specifying database to create it
            temp_config = self.config.copy()
            temp_config.pop('database')
            connection = mysql.connector.connect(**temp_config)
            cursor = connection.cursor()

            # Create database if it doesn't exist
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.config['database']}")
            cursor.close()
            connection.close()

            # Now connect to the database and create table
            connection = self.get_connection()
            cursor = connection.cursor()

            create_table_query = """
            CREATE TABLE IF NOT EXISTS vehicles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                make_model VARCHAR(255) NOT NULL,
                license_plate VARCHAR(50) NOT NULL,
                vin_number VARCHAR(17) UNIQUE NOT NULL,
                last_maintenance DATE NOT NULL,
                last_mileage INT,
                maintenance_interval_miles INT,                                          
                maintenance_interval_months INT,
                notes TEXT,
                date_added DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
            cursor.execute(create_table_query)
            connection.commit()
            cursor.close()
            connection.close()
            return True
        except Error as e:
            return False


def print_json_headers():
    print("Content-Type: application/json")
    print("Access-Control-Allow-Origin: *")
    print("Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS")
    print("Access-Control-Allow-Headers: Content-Type")
    print()

def send_error(message, status=500):
    print(f"Status: {status}")
    print_json_headers()
    print(json.dumps({"error": message}))
    sys.exit()

def send_success(data, status=200):
    if status != 200:
        print(f"Status: {status}")
    print_json_headers()
    print(json.dumps(data, default=str))
    sys.exit()

def get_vehicles():
    try:
        db = Database()
        connection = db.get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM vehicles ORDER BY date_added DESC")
        vehicles = cursor.fetchall()
        cursor.close()
        connection.close()
        send_success(vehicles)
    except Exception as e:
        send_error(f"Failed to fetch vehicles: {str(e)}")

def create_vehicle():
    try:
        # Read JSON data from stdin
        content_length = int(os.environ.get('CONTENT_LENGTH', 0))
        if content_length == 0:
            send_error("No data provided", 400)
        
        post_data = sys.stdin.read(content_length)
        data = json.loads(post_data)
        
        # Validate required fields
        required_fields = ['makeModel', 'licensePlate', 'vinNumber', 'lastMaintenance', 'lastMileage']
        for field in required_fields:
            if field not in data or not data[field]:
                send_error(f"Missing required field: {field}", 400)
        
        db = Database()
        connection = db.get_connection()
        cursor = connection.cursor()
        
        # Check for duplicate VIN
        cursor.execute("SELECT id FROM vehicles WHERE vin_number = %s", (data['vinNumber'],))
        if cursor.fetchone():
            send_error("A vehicle with this VIN number already exists!", 400)
        
        # Insert new vehicle
        insert_query = """
        INSERT INTO vehicles (
            make_model, license_plate, vin_number, last_maintenance,
            last_mileage, maintenance_interval_miles, maintenance_interval_months, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        values = (
            data['makeModel'],
            data['licensePlate'],
            data['vinNumber'],
            data['lastMaintenance'],
            data.get('lastMileage'),
            data.get('maintenanceIntervalMiles'),
            data.get('maintenanceIntervalMonths'),
            data.get('notes')
        )
        
        cursor.execute(insert_query, values)
        vehicle_id = cursor.lastrowid
        connection.commit()
        
        # Fetch and return the created vehicle
        cursor.execute("SELECT * FROM vehicles WHERE id = %s", (vehicle_id,))
        new_vehicle = cursor.fetchone()
        cursor.close()
        connection.close()
        
        # Convert to dictionary format
        columns = ['id', 'make_model', 'license_plate', 'vin_number', 'last_maintenance', 
                  'last_mileage', 'maintenance_interval_miles', 'maintenance_interval_months', 
                  'notes', 'date_added', 'updated_at']
        vehicle_dict = dict(zip(columns, new_vehicle))
        
        send_success(vehicle_dict, 201)
        
    except json.JSONDecodeError:
        send_error("Invalid JSON data", 400)
    except Exception as e:
        send_error(f"Failed to create vehicle: {str(e)}")

def update_vehicle():
    try:
        # Get vehicle ID from query string
        query_string = os.environ.get('QUERY_STRING', '')
        if not query_string.startswith('id='):
            send_error("Vehicle ID required", 400)
        
        vehicle_id = query_string.split('=')[1]
        
        # Read JSON data
        content_length = int(os.environ.get('CONTENT_LENGTH', 0))
        post_data = sys.stdin.read(content_length)
        data = json.loads(post_data)
        
        db = Database()
        connection = db.get_connection()
        cursor = connection.cursor()
        
        # Check for duplicate VIN (excluding current vehicle)
        cursor.execute("SELECT id FROM vehicles WHERE vin_number = %s AND id != %s", 
                      (data['vinNumber'], vehicle_id))
        if cursor.fetchone():
            send_error("A vehicle with this VIN number already exists!", 400)
        
        # Update vehicle
        update_query = """
        UPDATE vehicles SET
            make_model = %s, license_plate = %s, vin_number = %s, last_maintenance = %s,
            last_mileage = %s, maintenance_interval_miles = %s, maintenance_interval_months = %s, notes = %s
        WHERE id = %s
        """
        
        values = (
            data['makeModel'],
            data['licensePlate'],
            data['vinNumber'],
            data['lastMaintenance'],
            data.get('lastMileage'),
            data.get('maintenanceIntervalMiles'),
            data.get('maintenanceIntervalMonths'),
            data.get('notes'),
            vehicle_id
        )
        
        cursor.execute(update_query, values)
        
        if cursor.rowcount == 0:
            send_error("Vehicle not found", 404)
        
        connection.commit()
        
        # Fetch and return updated vehicle
        cursor.execute("SELECT * FROM vehicles WHERE id = %s", (vehicle_id,))
        updated_vehicle = cursor.fetchone()
        cursor.close()
        connection.close()
        
        columns = ['id', 'make_model', 'license_plate', 'vin_number', 'last_maintenance', 
                  'last_mileage', 'maintenance_interval_miles', 'maintenance_interval_months', 
                  'notes', 'date_added', 'updated_at']
        vehicle_dict = dict(zip(columns, updated_vehicle))
        
        send_success(vehicle_dict)
        
    except Exception as e:
        send_error(f"Failed to update vehicle: {str(e)}")

def delete_vehicle():
    try:
        query_string = os.environ.get('QUERY_STRING', '')
        if not query_string.startswith('id='):
            send_error("Vehicle ID required", 400)
        
        vehicle_id = query_string.split('=')[1]
        
        db = Database()
        connection = db.get_connection()
        cursor = connection.cursor()
        
        cursor.execute("DELETE FROM vehicles WHERE id = %s", (vehicle_id,))
        
        if cursor.rowcount == 0:
            send_error("Vehicle not found", 404)
        
        connection.commit()
        cursor.close()
        connection.close()
        
        send_success({"message": "Vehicle deleted successfully"})
        
    except Exception as e:
        send_error(f"Failed to delete vehicle: {str(e)}")

def main():
    # Handle preflight OPTIONS requests
    request_method = os.environ.get('REQUEST_METHOD', 'GET')
    
    if request_method == 'OPTIONS':
        print_json_headers()
        return
    
    # Initialize database on first request
    db = Database()
    db.init_database()
    
    # Route requests
    if request_method == 'GET':
        get_vehicles()
    elif request_method == 'POST':
        create_vehicle()
    elif request_method == 'PUT':
        update_vehicle()
    elif request_method == 'DELETE':
        delete_vehicle()
    else:
        send_error("Method not allowed", 405)

if __name__ == "__main__":
    main()
