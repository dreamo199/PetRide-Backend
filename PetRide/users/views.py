from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django_ratelimit.decorators import ratelimit
from django.db import transaction
import logging
from .permissions import IsApprovedDriver, IsCustomer, IsDriver, IsOwnerOrAdmin, IsVerifiedUser
from .models import User, CustomerProfile, DriverProfile, VerificationToken
from .serializers import (UserSerializer, CustomerProfileSerializer, 
                          DriverProfileSerializer, CustomerRegistrationSerializer,
                          DriverRegistrationSerializer)

logger = logging.getLogger(__name__)

@ratelimit(key='ip', rate='5/h', method='POST')
@api_view(['POST'])
@permission_classes([AllowAny])
def register_customer(request):
    serializer = CustomerRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = serializer.save()
            return Response({'user': UserSerializer(user).data, 'message': 'Registeration Successful. Please Check your mail to verify account'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Customer registration failed: {str(e)}")
            return Response({'error': 'Registration failed. Please try again'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@ratelimit(key='ip', rate='5/h', method='POST')
@api_view(['POST'])
@permission_classes([AllowAny])
def register_driver(request):
    serializer = DriverRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = serializer.save()
            return Response({'user': UserSerializer(user).data, 'message': 'Registeration Successful. Please Check your mail to verify account'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Driver registration failed: {str(e)}")
            return Response({'error': 'Registration failed. Please try again'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@ratelimit(key='ip', rate='10/h', method='GET')
@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, token):
    try:
        with transaction.atomic():
            verification_token = VerificationToken.objects.select_for_update().get(token=token)
            if verification_token.user.is_verified:
                return Response(
                    {'message': 'Email already verified.'},
                    status=status.HTTP_200_OK
                )
            user = verification_token.user
            user.is_verified = True
            user.save()
            verification_token.delete()
            logger.info(f"Email verified for user: {user.username}")
            return Response({'message': 'Email verified successfully.'}, status=status.HTTP_200_OK)
    except VerificationToken.DoesNotExist:
        return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Email verification failed: {str(e)}")
        return Response({'error': 'Verification failed. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class CustomerProfileViewSet(viewsets.ModelViewSet):
    queryset = CustomerProfile.objects.select_related("user").all()
    serializer_class = CustomerProfileSerializer
    permission_classes = [IsAuthenticated, IsCustomer]

    http_method_names = ['get', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.request.user.is_staff:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsCustomer()]

    def partial_update(self, request, *args, **kwargs):
        return Response({'error': 'You cannot perform this task using this endpoint'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def get_queryset(self):
        if self.request.user.is_staff:
            return CustomerProfile.objects.select_related("user").all()
        return CustomerProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        try:
            profile = CustomerProfile.objects.select_related("user").get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except CustomerProfile.DoesNotExist:
            logger.error(f"Customer profile not found for user: {request.user.username}")
            return Response({'error': 'Customer profile not found. Please contact our support team'}, 
                          status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        try:
            profile = CustomerProfile.objects.select_related("user").get(user=request.user)
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                logger.info(f"Customer profile updated for user: {request.user.username}")
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except CustomerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, 
                          status=status.HTTP_404_NOT_FOUND)


class DriverProfileViewSet(viewsets.ModelViewSet):
    queryset = DriverProfile.objects.select_related("user").all()
    serializer_class = DriverProfileSerializer
    permission_classes = [IsAuthenticated, IsDriver]
    http_method_names = ['get', 'patch', 'head', 'options', 'put']

    def create(self, request, *args, **kwargs):
        return Response({'error': 'Creation of driver profiles is not allowed via this endpoint.'}, 
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def get_permissions(self):
        if self.request.user.is_staff:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsDriver()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return DriverProfile.objects.select_related("user").all()
        return DriverProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        try:
            profile = DriverProfile.objects.select_related("user").get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except DriverProfile.DoesNotExist:
            logger.error(f"Driver profile not found for user: {request.user.username}")
            return Response({'error': 'Driver profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        try:
            profile = DriverProfile.objects.select_related("user").get(user=request.user)
            data = request.data.copy()
            data.pop('rating', None) 
            data.pop('total_deliveries', None)
            serializer = self.get_serializer(profile, data=data, partial=True)
            if serializer.is_valid():
                instance = serializer.save()
                print(instance)
                logger.info(f"Driver profile updated for user: {request.user.username}")
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except DriverProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['put'], permission_classes=[IsAuthenticated ,IsApprovedDriver])
    def toggle_availability(self, request):
        try:
            profile = DriverProfile.objects.select_related("user").get(user=request.user)
            profile.is_available = not profile.is_available
            profile.save()
            logger.info(f"Driver {request.user.username} availability changed to: {profile.is_available}")
            return Response({
                'is_available': profile.is_available,
                'message': f"You are now {'available' if profile.is_available else 'unavailable'} for deliveries."
            })
        except DriverProfile.DoesNotExist:
            return Response({'error': 'Driver profile not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated ,IsApprovedDriver])
    def update_location(self, request):
        try:
            profile = DriverProfile.objects.select_related("user").get(user=request.user)
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')

            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (TypeError, ValueError):
                return Response({'error': 'Invalid latitude or longitude'}, status=status.HTTP_400_BAD_REQUEST)

            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return Response({'error': 'Latitude must be -90 to 90, longitude -180 to 180'}, status=status.HTTP_400_BAD_REQUEST)

            profile.current_latitude = latitude
            profile.current_longitude = longitude
            profile.save()
            return Response({'status': 'location updated'})
        except DriverProfile.DoesNotExist:
            return Response({'error': 'Driver profile not found'}, status=status.HTTP_404_NOT_FOUND)