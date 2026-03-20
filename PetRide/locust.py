import json
import random
import uuid
import logging
from locust import HttpUser, task, between, events

# Configure logging
logging.basicConfig(level=logging.INFO)

CUSTOMER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY5MzEzNTIwLCJpYXQiOjE3NjkzMDk5MjAsImp0aSI6ImUzYjllM2Q2YTRjODQwZGNiY2UzZGM2ZTA0OTFiOGExIiwidXNlcl9pZCI6IjIifQ.XcLXg_C9Iv7vY_2VoCxAFX1DsftZy7mUi2ywk9UYUNo"
DRIVER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY5MzEzNDU5LCJpYXQiOjE3NjkzMDk4NjAsImp0aSI6IjA3ZmZhZDVlMjQzZjQwODBiZmNlMDZiN2M2ZjRkMjA4IiwidXNlcl9pZCI6IjYifQ.KEKdq_MKNzmzD-DCM0Gy6v9i4zzY6u3rAozqSu6I09M"

class PetRideUser(HttpUser):

    wait_time = between(1, 5)  # Corrected from wait_times

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = None
        self.role = None  # 'customer' or 'driver'
        self.order_id = None  # Track created order for follow-ups

    def on_start(self):
        # Register and login once at start
        self.login()

    # @task(1)
    # def register(self):
    #     if self.role is None:
    #         self.role = "customer" if random.random() < 0.7 else "driver"

    #     unique_id = uuid.uuid4().hex[:8]  # Unique suffix for username/email/phone
    #     if self.role == "customer":
    #         payload = {
    #             "username": f"testuser_{unique_id}",
    #             "email": f"test_{unique_id}@example.com",
    #             "password": "strongpass123",
    #             "password2": "strongpass123",
    #             "phone": f"+234{random.randint(1000000000, 9999999999)}",
    #             "first_name": "Test",
    #             "last_name": "User",
    #             "address": "10 Allen Avenue, Ikeja, Lagos",
    #             "latitude": 6.6018,
    #             "longitude": 3.3515
    #         }
    #         response = self.client.post("/api/register/customer/", json=payload)
    #     else:
    #         payload = {
    #             "username": f"testdriver_{unique_id}",
    #             "email": f"driver_{unique_id}@example.com",
    #             "password": "strongpass123",
    #             "password2": "strongpass123",
    #             "phone": f"+234{random.randint(1000000000, 9999999999)}",
    #             "first_name": "Test",
    #             "last_name": "Driver",
    #             "license_number": f"LIC{unique_id}",
    #             "vehicle_number": f"VEH{unique_id}",
    #             "vehicle_type": "Truck",
    #             "vehicle_capacity": 1000.0
    #         }
    #         response = self.client.post("/api/register/driver/", json=payload)

    #     if response.status_code == 201:
    #         logging.info(f"Registered {self.role} successfully")
    #     else:
    #         events.request_failure.fire(
    #             request_type="POST",
    #             name="Register",
    #             response_time=response.elapsed.total_seconds() * 1000,
    #             exception=response.text
    #         )

    @task(2)
    def login(self):
        payload = {
            "username": "bola",
            "password": "myballs"
        }

        with self.client.post("/api/login/", json=payload, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Login failed: {response.text}")

    @task(5)
    def create_order(self):
        if self.role != "customer" or not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "fuel_type": 1,
            "quantity_liters": 50.0,
            "delivery_address": "10 Allen Avenue, Ikeja, Lagos",
            "delivery_latitude": 6.6018,
            "delivery_longitude": 3.3515,
            "scheduled_time": "2026-01-25T10:00:00Z",
            "notes": "Deliver to gate"
        }
        response = self.client.post("/api/orders/orders/", json=payload, headers=headers)
        if response.status_code == 201:
            try:
                data = response.json()
                self.order_id = data.get("id")
                logging.info(f"Created order ID: {self.order_id}")
            except json.JSONDecodeError:
                logging.error(f"Failed to parse JSON in create_order: {response.text}")
        else:
            events.request_failure.fire(
                request_type="POST",
                name="Create Order",
                response_time=response.elapsed.total_seconds() * 1000,
                exception=response.text
            )

    @task(3)
    def update_order_status(self):
        if self.role != "driver" or not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        # Fetch pending or assigned orders dynamically
        response = self.client.get("/api/orders/orders/", headers=headers)
        if response.status_code != 200:
            events.request_failure.fire(
                request_type="GET",
                name="Fetch Orders",
                response_time=response.elapsed.total_seconds() * 1000,
                exception=response.text
            )
            return

        try:
            orders = response.json().get("results", [])
        except json.JSONDecodeError:
            logging.error(f"Failed to parse JSON in update_order_status: {response.text}")
            return

        for order in orders:
            if order['status'] == "pending" and order['driver'] is None:
                # Accept order
                self.client.post(
                    f"/api/orders/orders/{order['id']}/update_status/",
                    json={"status": "assigned"},
                    headers=headers
                )
                logging.info(f"Driver accepted order {order['id']}")
                break
            elif order['status'] == "assigned":
                # Move to in_transit
                self.client.post(
                    f"/api/orders/orders/{order['id']}/update_status/",
                    json={"status": "in_transit"},
                    headers=headers
                )
                logging.info(f"Driver updated order {order['id']} to in_transit")
                break

    @task(2)
    def get_analytics(self):
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        endpoint = "/api/analytics/customer/" if self.role == "customer" else "/api/analytics/driver/"
        response = self.client.get(endpoint, headers=headers)
        if response.status_code == 200:
            logging.info(f"Fetched {self.role} analytics")
        else:
            events.request_failure.fire(
                request_type="GET",
                name="Analytics",
                response_time=response.elapsed.total_seconds() * 1000,
                exception=response.text
            )

    @task(1)
    def rate_order(self):
        if self.role != "customer" or not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {"rating": 4, "feedback": "Good delivery in Lagos traffic"}
        if not self.order_id:
            return
        response = self.client.post(f"/api/orders/orders/{self.order_id}/rate_order/", json=payload, headers=headers)
        if response.status_code == 200:
            logging.info(f"Rated order {self.order_id}")
        else:
            events.request_failure.fire(
                request_type="POST",
                name="Rate Order",
                response_time=response.elapsed.total_seconds() * 1000,
                exception=response.text
            )

# Optional admin simulation
class AdminUser(PetRideUser):
    @task
    def business_analytics(self):
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        response = self.client.get("/api/analytics/business/?days=7", headers=headers)
        if response.status_code == 200:
            logging.info("Fetched business analytics")
        else:
            events.request_failure.fire(
                request_type="GET",
                name="Business Analytics",
                response_time=response.elapsed.total_seconds() * 1000,
                exception=response.text
            )
