import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

class OrderTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f'tracking_{self.order_id}'

        # Check if the user is authenticated
        # user = self.scope.get("user", None)
        # if not user or isinstance(user, AnonymousUser):
        #     await self.close()
        #     return
        
        # has_access = await self.check_order_access(user, self.order_id)
        # if not has_access:
        #     await self.close()
        #     return
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the order group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get('type')

            if event_type == 'location_update':
                latitude = data.get('latitude')
                longitude = data.get('longitude')

                if latitude is None or longitude is None:
                    return

                await self.update_driver_location(self.order_id, latitude, longitude)

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'location_broadcast',
                        'latitude': latitude,
                        'longitude': longitude,
                        'order_id': self.order_id
                    }
                )
            elif event_type == 'status_update':
                status = data.get('status')
                if status is None:
                    return
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'status_broadcast',
                        'status': status,
                        'order_id': self.order_id
                    }
                )
        except json.JSONDecodeError:
            pass

    async def location_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'latitude': event['latitude'],
            'longitude': event['longitude'],
            'order_id': event['order_id']
        }))

    async def status_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'status': event['status'],
            'order_id': event['order_id']
        }))

    @database_sync_to_async
    def check_order_access(self, user, order_id):
        from .models import Order
        try:
            order = Order.objects.select_related('customer__user', 'driver__user').get(id=order_id)
            return order.customer.user == user or (order.driver and order.driver.user == user) or user.is_staff
        except Order.DoesNotExist:
            return False
        
    @database_sync_to_async
    def update_driver_location(self, order_id, latitude, longitude):
        from .models import Order
        from django.utils import timezone
        try:
            order = Order.objects.select_related('driver').get(id=order_id)
            if order.driver:
                order.driver.current_latitude = latitude
                order.driver.current_longitude = longitude
                order.driver.last_location_update = timezone.now()
                order.driver.save(update_fields=['current_latitude', 'current_longitude', 'last_location_update'])
        except Order.DoesNotExist:
            pass