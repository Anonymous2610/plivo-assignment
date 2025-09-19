import json
import uuid
import time
import asyncio
import logging
from django.conf import settings
from channels.generic.websocket import AsyncWebsocketConsumer
from .state import manager, Message, Subscriber

logger = logging.getLogger(__name__)


class PubSubConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Check for API key authentication
        api_key = None

        # Check query parameters first
        query_string = self.scope.get('query_string', b'').decode()
        query_params = {}
        if query_string:
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    query_params[key] = value
        api_key = query_params.get('api_key')

        # Check headers if not in query params
        if not api_key:
            headers = dict(self.scope.get('headers', []))
            api_key = headers.get(b'x-api-key', b'').decode() or None

        # Validate API key
        if not self._validate_api_key(api_key):
            logger.warning(
                f"WebSocket connection rejected: Invalid or missing API key. Provided: {api_key}")
            await self.close(code=1008)  # Policy violation
            return

        await self.accept()
        self.client_id = str(uuid.uuid4())
        self.subscribed_topics = set()
        self.user_client_ids = {}  # Map topic -> user_provided_client_id
        self.message_processor_task = None
        logger.info(f"WebSocket client connected: {self.client_id}")

    async def disconnect(self, close_code):
        logger.info(
            f"WebSocket client disconnecting: {self.client_id}, close_code: {close_code}")
        if self.message_processor_task:
            self.message_processor_task.cancel()
        for topic_name in list(self.subscribed_topics):
            await self._unsubscribe(topic_name)
        logger.info(f"WebSocket client disconnected: {self.client_id}")

    async def receive(self, text_data):
        # Check if shutdown is initiated
        if manager.shutdown_initiated:
            await self._send_error(None, "SERVICE_UNAVAILABLE", "Server is shutting down")
            await self.close(code=1001)  # Going away
            return

        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            request_id = data.get('request_id')

            if message_type == 'subscribe':
                await self._handle_subscribe(data, request_id)
            elif message_type == 'unsubscribe':
                await self._handle_unsubscribe(data, request_id)
            elif message_type == 'publish':
                await self._handle_publish(data, request_id)
            elif message_type == 'ping':
                await self._handle_ping(request_id)
            else:
                await self._send_error(request_id, "BAD_REQUEST", f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self._send_error(None, "BAD_REQUEST", "Invalid JSON")
        except Exception as e:
            logger.error(
                f"Internal error processing message from {self.client_id}: {e}", exc_info=True)
            await self._send_error(None, "INTERNAL", f"Internal error: {str(e)}")

    async def _handle_subscribe(self, data, request_id):
        topic = data.get('topic')
        client_id = data.get('client_id')
        last_n = data.get('last_n', 0)

        if not topic or not client_id:
            logger.warning(
                f"Subscribe failed - missing fields from {self.client_id}: topic={topic}, client_id={client_id}")
            await self._send_error(request_id, "BAD_REQUEST", "Missing required fields: topic, client_id")
            return

        logger.info(
            f"Subscribing {client_id} to topic '{topic}' with last_n={last_n}")

        # Get or create topic
        topic_obj = await manager.get_topic(topic)
        if not topic_obj:
            logger.info(f"Creating new topic: {topic}")
            created = await manager.create_topic(topic)
            if not created:
                logger.error(f"Failed to create topic: {topic}")
                await self._send_error(request_id, "INTERNAL", "Failed to create topic")
                return
            topic_obj = await manager.get_topic(topic)

        # Create subscriber with configured queue size
        queue_size = getattr(settings, 'PUBSUB_SUBSCRIBER_QUEUE_SIZE', 50)
        subscriber = Subscriber(client_id=client_id,
                                ws=self, last_n=last_n, queue_size=queue_size)
        await topic_obj.add_subscriber(subscriber)
        self.subscribed_topics.add(topic)
        # Store user-provided client_id
        self.user_client_ids[topic] = client_id
        logger.info(f"Successfully subscribed {client_id} to topic '{topic}'")

        # Start message processor if not already running
        if not self.message_processor_task:
            self.message_processor_task = asyncio.create_task(
                self._process_messages())

        # Send historical messages if requested
        if last_n > 0:
            historical_messages = await topic_obj.get_recent_messages(last_n)
            logger.info(
                f"Sending {len(historical_messages)} historical messages to {client_id}")
            for msg in historical_messages:
                await self._send_event(topic, msg)

        # Send acknowledgment
        await self._send_ack(request_id, topic, "ok")

    async def _handle_unsubscribe(self, data, request_id):
        topic = data.get('topic')
        client_id = data.get('client_id')

        if not topic or not client_id:
            await self._send_error(request_id, "BAD_REQUEST", "Missing required fields: topic, client_id")
            return

        success = await self._unsubscribe(topic, client_id)
        if success:
            await self._send_ack(request_id, topic, "ok")
        else:
            await self._send_error(request_id, "TOPIC_NOT_FOUND", f"Topic '{topic}' not found")

    async def _handle_publish(self, data, request_id):
        topic = data.get('topic')
        message_data = data.get('message')

        if not topic or not message_data:
            logger.warning(
                f"Publish failed - missing fields from {self.client_id}: topic={topic}, message={message_data}")
            await self._send_error(request_id, "BAD_REQUEST", "Missing required fields: topic, message")
            return

        message_id = message_data.get('id')
        payload = message_data.get('payload')

        if not message_id or not payload:
            logger.warning(
                f"Publish failed - missing message fields from {self.client_id}: id={message_id}, payload={payload}")
            await self._send_error(request_id, "BAD_REQUEST", "Missing required fields: message.id, message.payload")
            return

        # Validate UUID
        try:
            uuid.UUID(message_id)
        except ValueError:
            logger.warning(
                f"Publish failed - invalid UUID from {self.client_id}: {message_id}")
            await self._send_error(request_id, "BAD_REQUEST", "message.id must be a valid UUID")
            return

        # Get topic
        topic_obj = await manager.get_topic(topic)
        if not topic_obj:
            logger.warning(
                f"Publish failed - topic not found from {self.client_id}: {topic}")
            await self._send_error(request_id, "TOPIC_NOT_FOUND", f"Topic '{topic}' not found")
            return

        # Create and publish message
        message = Message(
            id=message_id,
            payload=payload,
            timestamp=time.time()
        )

        logger.info(
            f"Publishing message {message_id} to topic '{topic}' from {self.client_id}")
        await topic_obj.publish_message(message)
        logger.info(
            f"Successfully published message {message_id} to topic '{topic}'")
        await self._send_ack(request_id, topic, "ok")

    async def _handle_ping(self, request_id):
        await self._send_pong(request_id)

    async def _unsubscribe(self, topic_name, client_id=None):
        topic_obj = await manager.get_topic(topic_name)
        if not topic_obj:
            return False

        # Use provided client_id or get from mapping
        user_client_id = client_id or self.user_client_ids.get(topic_name)
        if not user_client_id:
            return False

        await topic_obj.remove_subscriber(user_client_id)
        self.subscribed_topics.discard(topic_name)
        self.user_client_ids.pop(topic_name, None)  # Clean up mapping
        logger.info(f"Unsubscribed {user_client_id} from topic '{topic_name}'")
        return True

    async def _process_messages(self):
        """Background task to process messages from subscriber queues"""
        try:
            while True:
                # Get all topics this client is subscribed to
                topics = list(self.subscribed_topics)
                if not topics:
                    await asyncio.sleep(0.1)
                    continue

                # Check each topic for messages
                for topic_name in topics:
                    topic_obj = await manager.get_topic(topic_name)
                    if not topic_obj:
                        continue

                    # Get the user-provided client_id for this topic
                    user_client_id = self.user_client_ids.get(topic_name)
                    if not user_client_id:
                        continue

                    # Directly fetch this client's Subscriber object
                    subscriber = topic_obj.subscribers.get(user_client_id)
                    if not subscriber:
                        continue

                    try:
                        # Wait briefly for a message in this subscriber's queue
                        message = await asyncio.wait_for(subscriber.queue.get(), timeout=0.1)
                        await self._send_event(topic_name, message)
                    except asyncio.TimeoutError:
                        # No message available right now
                        pass
                    except Exception as e:
                        logger.error(
                            "Error processing message for %s on topic %s: %s",
                            user_client_id, topic_name, e,
                        )

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            logger.info(f"Message processor cancelled for {self.client_id}")
        except Exception as e:
            logger.error(f"Message processor error for {self.client_id}: {e}")

    async def _send_ack(self, request_id, topic, status):
        response = {
            "type": "ack",
            "request_id": request_id,
            "topic": topic,
            "status": status,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        await self.send(text_data=json.dumps(response))

    async def _send_event(self, topic, message):
        response = {
            "type": "event",
            "topic": topic,
            "message": {
                "id": message.id,
                "payload": message.payload
            },
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(message.timestamp))
        }
        await self.send(text_data=json.dumps(response))

    async def _send_error(self, request_id, code, message):
        response = {
            "type": "error",
            "request_id": request_id,
            "error": {
                "code": code,
                "message": message
            },
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        await self.send(text_data=json.dumps(response))

    async def _send_pong(self, request_id):
        response = {
            "type": "pong",
            "request_id": request_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        await self.send(text_data=json.dumps(response))

    async def _send_info(self, msg, topic=None, request_id=None):
        response = {
            "type": "info",
            "msg": msg,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        if topic:
            response["topic"] = topic
        if request_id:
            response["request_id"] = request_id
        await self.send(text_data=json.dumps(response))

    def _validate_api_key(self, api_key: str) -> bool:
        """
        Validate API key using configured valid keys from settings.
        """
        if not api_key:
            return False

        valid_keys = getattr(settings, 'PUBSUB_API_KEYS', [
                             'plivo-test-key', 'demo-key', 'test-123'])
        return api_key in valid_keys
