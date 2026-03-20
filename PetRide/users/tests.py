from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal

from .models import User, CustomerProfile, DriverProfile
from .verification import VerificationToken


class UserModelTest(TestCase):
    """Test User model"""
    
    def setUp(self):
        self.customer_user = User.objects.create_user(
            username='testcustomer',
            email='customer@test.com',
            password='testpass123',
            phone='+1234567890',
            role='customer'
        )
        
    def test_user_creation(self):
        """Test user is created correctly"""
        self.assertEqual(self.customer_user.username, 'testcustomer')
        self.assertEqual(self.customer_user.role, 'customer')
        self.assertFalse(self.customer_user.is_verified)
        
    def test_user_str_representation(self):
        """Test user string representation"""
        expected = f"testcustomer (Customer)"
        self.assertEqual(str(self.customer_user), expected)
        
    def test_soft_delete(self):
        """Test soft delete functionality"""
        self.customer_user.soft_delete()
        self.assertTrue(self.customer_user.is_deleted)
        self.assertFalse(self.customer_user.is_active)
        self.assertIsNotNone(self.customer_user.deleted_at)


class CustomerRegistrationTest(APITestCase):
    """Test customer registration endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('register-customer')  # Update with your URL name
        self.valid_payload = {
            'username': 'newcustomer',
            'email': 'newcustomer@test.com',
            'password': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'phone': '+1234567890',
            'first_name': 'John',
            'last_name': 'Doe',
            'address': '123 Main St',
            'latitude': '40.712776',
            'longitude': '-74.005974'
        }
        
    def test_valid_customer_registration(self):
        """Test successful customer registration"""
        response = self.client.post(self.register_url, self.valid_payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['username'], 'newcustomer')
        
        # Verify user was created
        user = User.objects.get(username='newcustomer')
        self.assertEqual(user.role, 'customer')
        self.assertFalse(user.is_verified)
        
        # Verify profile was created
        self.assertTrue(hasattr(user, 'customer_profile'))
        self.assertEqual(user.customer_profile.address, '123 Main St')
        
        # Verify verification token was created
        self.assertTrue(VerificationToken.objects.filter(user=user).exists())
        
    def test_password_mismatch(self):
        """Test registration fails when passwords don't match"""
        payload = self.valid_payload.copy()
        payload['password2'] = 'DifferentPass123!'
        
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_duplicate_email(self):
        """Test registration fails with duplicate email"""
        # Create first user
        self.client.post(self.register_url, self.valid_payload, format='json')
        
        # Try to create second user with same email
        payload = self.valid_payload.copy()
        payload['username'] = 'different'
        response = self.client.post(self.register_url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_registration_without_coordinates(self):
        """Test registration succeeds without lat/lng"""
        payload = self.valid_payload.copy()
        del payload['latitude']
        del payload['longitude']
        
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
    def test_registration_with_partial_coordinates(self):
        """Test registration fails with only latitude or longitude"""
        payload = self.valid_payload.copy()
        del payload['longitude']
        
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DriverRegistrationTest(APITestCase):
    """Test driver registration endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('register-driver')  # Update with your URL name
        self.valid_payload = {
            'username': 'newdriver',
            'email': 'driver@test.com',
            'password': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'phone': '+1234567890',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'license_number': 'DL123456',
            'vehicle_number': 'ABC123',
            'vehicle_type': 'Sedan',
            'vehicle_capacity': '50.00'
        }
        
    def test_valid_driver_registration(self):
        """Test successful driver registration"""
        response = self.client.post(self.register_url, self.valid_payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify user was created
        user = User.objects.get(username='newdriver')
        self.assertEqual(user.role, 'driver')
        
        # Verify profile was created with pending status
        self.assertTrue(hasattr(user, 'driver_profile'))
        self.assertEqual(user.driver_profile.approval_status, 'pending')
        self.assertEqual(user.driver_profile.license_number, 'DL123456')
        
    def test_duplicate_license_number(self):
        """Test registration fails with duplicate license number"""
        # Create first driver
        self.client.post(self.register_url, self.valid_payload, format='json')
        
        # Try with same license number
        payload = self.valid_payload.copy()
        payload['username'] = 'different'
        payload['email'] = 'different@test.com'
        payload['phone'] = '+9876543210'
        payload['vehicle_number'] = 'XYZ789'
        
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailVerificationTest(TransactionTestCase):
    """Test email verification endpoint"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            phone='+1234567890',
            role='customer'
        )
        self.token = VerificationToken.objects.create(user=self.user)
        
    def test_valid_email_verification(self):
        """Test successful email verification"""
        url = reverse('verify-email', kwargs={'token': self.token.token})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user is marked as verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        
        # Verify token was deleted
        self.assertFalse(VerificationToken.objects.filter(user=self.user).exists())
        
    def test_invalid_token(self):
        """Test verification fails with invalid token"""
        url = reverse('verify-email', kwargs={'token': 'invalid-token-123'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_already_verified(self):
        """Test verification with already verified user"""
        self.user.is_verified = True
        self.user.save()
        
        url = reverse('verify-email', kwargs={'token': self.token.token})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CustomerProfileViewSetTest(APITestCase):
    """Test customer profile endpoints"""
    
    def setUp(self):
        self.customer_user = User.objects.create_user(
            username='customer',
            email='customer@test.com',
            password='testpass123',
            phone='+1234567890',
            role='customer',
            is_verified=True
        )
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            address='123 Main St',
            latitude=Decimal('40.712776'),
            longitude=Decimal('-74.005974')
        )
        
        self.driver_user = User.objects.create_user(
            username='driver',
            email='driver@test.com',
            password='testpass123',
            phone='+9876543210',
            role='driver',
            is_verified=True
        )
        
        self.client = APIClient()
        
    def test_customer_can_view_own_profile(self):
        """Test customer can view their own profile"""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse('customerprofile-me')  # Update with your URL name
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['address'], '123 Main St')
        
    def test_driver_cannot_access_customer_endpoint(self):
        """Test driver cannot access customer endpoints"""
        self.client.force_authenticate(user=self.driver_user)
        url = reverse('customerprofile-me')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_unauthenticated_access_denied(self):
        """Test unauthenticated users cannot access profile"""
        url = reverse('customerprofile-me')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_customer_can_update_profile(self):
        """Test customer can update their profile"""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse('customerprofile-update-me')  # Update with your URL name
        
        payload = {'address': '456 New St'}
        response = self.client.patch(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer_profile.refresh_from_db()
        self.assertEqual(self.customer_profile.address, '456 New St')


class DriverProfileViewSetTest(APITestCase):
    """Test driver profile endpoints"""
    
    def setUp(self):
        self.driver_user = User.objects.create_user(
            username='driver',
            email='driver@test.com',
            password='testpass123',
            phone='+1234567890',
            role='driver',
            is_verified=True
        )
        self.driver_profile = DriverProfile.objects.create(
            user=self.driver_user,
            license_number='DL123456',
            vehicle_number='ABC123',
            vehicle_type='Sedan',
            vehicle_capacity=Decimal('50.00'),
            approval_status='approved'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.driver_user)
        
    def test_driver_can_toggle_availability(self):
        """Test driver can toggle availability"""
        url = reverse('driverprofile-toggle-availability')  # Update with your URL name
        
        initial_status = self.driver_profile.is_available
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.driver_profile.refresh_from_db()
        self.assertEqual(self.driver_profile.is_available, not initial_status)
        
    def test_driver_can_update_location(self):
        """Test driver can update location"""
        url = reverse('driverprofile-update-location')  # Update with your URL name
        
        payload = {
            'latitude': '34.052235',
            'longitude': '-118.243683'
        }
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.driver_profile.refresh_from_db()
        self.assertEqual(str(self.driver_profile.current_latitude), '34.052235')
        
    def test_invalid_coordinates_rejected(self):
        """Test invalid coordinates are rejected"""
        url = reverse('driverprofile-update-location')
        
        payload = {
            'latitude': '200.0',  # Invalid
            'longitude': '-118.243683'
        }
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_driver_cannot_update_rating(self):
        """Test driver cannot update their own rating"""
        url = reverse('driverprofile-update-me')  # Update with your URL name
        
        payload = {'rating': '5.00'}
        response = self.client.patch(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.driver_profile.refresh_from_db()
        self.assertEqual(self.driver_profile.rating, Decimal('0.00'))


class PermissionTest(APITestCase):
    
    def setUp(self):
        self.customer = User.objects.create_user(
            username='customer',
            email='customer@test.com',
            password='testpass123',
            phone='+1234567890',
            role='customer'
        )
        
        self.driver = User.objects.create_user(
            username='driver',
            email='driver@test.com',
            password='testpass123',
            phone='+9876543210',
            role='driver'
        )
        
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123',
            phone='+1111111111'
        )
        
    def test_customer_role_permission(self):
        from .permissions import IsCustomer
        
        permission = IsCustomer()
        
        from unittest.mock import Mock
        request = Mock()
        request.user = self.customer
        
        self.assertTrue(permission.has_permission(request, None))
        
        request.user = self.driver
        self.assertFalse(permission.has_permission(request, None))
        
    def test_driver_role_permission(self):
        from .permissions import IsDriver
        
        permission = IsDriver()
        
        from unittest.mock import Mock
        request = Mock()
        request.user = self.driver
        
        self.assertTrue(permission.has_permission(request, None))
        
        request.user = self.customer
        self.assertFalse(permission.has_permission(request, None))