import asyncio
import time
import logging
from collections import deque
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from django.conf import settings

logger = logging.getLogger(__name__)


# -----------------------------
# Data structures
# -----------------------------

@dataclass
class Message:
    id: str
    payload: dict
    timestamp: float


class Subscriber:
    """
    Represents a single WebSocket subscriber.
    Queue is bounded to provide backpressure.
    """

    def __init__(self, client_id: str, ws, last_n: int = 0, queue_size: int = None):
        self.client_id = client_id
        self.ws = ws
        self.last_n = last_n
        if queue_size is None:
            queue_size = getattr(settings, 'PUBSUB_SUBSCRIBER_QUEUE_SIZE', 50)
        self.queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=queue_size)
        self.slow_consumer_threshold = getattr(
            settings, 'PUBSUB_SLOW_CONSUMER_THRESHOLD', 3)
        self.drop_count = 0


class Topic:
    """
    Holds messages and subscribers for a single topic.
    Subscribers are stored in a dict keyed by client_id.
    """

    def __init__(self, name: str, ring_size: int = None):
        self.name = name
        self.subscribers: Dict[str, Subscriber] = {}       # <-- dict, not set
        if ring_size is None:
            ring_size = getattr(
                settings, 'PUBSUB_DEFAULT_RING_BUFFER_SIZE', 100)
        self.history: deque[Message] = deque(maxlen=ring_size)
        self.ring_size = ring_size  # Store for configuration access
        self.lock = asyncio.Lock()
        self.message_count = 0

    async def add_subscriber(self, subscriber: Subscriber) -> None:
        """
        Add or replace a subscriber by client_id.
        """
        async with self.lock:
            self.subscribers[subscriber.client_id] = subscriber
            logger.debug("Subscriber %s added to topic %s",
                         subscriber.client_id, self.name)

    async def remove_subscriber(self, client_id: str) -> None:
        """
        Remove a subscriber by client_id.
        """
        async with self.lock:
            removed = self.subscribers.pop(client_id, None)
            if removed:
                logger.debug("Subscriber %s removed from topic %s",
                             client_id, self.name)

    async def publish_message(self, message: Message) -> None:
        """
        Append message to history and enqueue to each subscriber.
        Drop oldest if queue is full (drop-oldest backpressure).
        Disconnect slow consumers after threshold breaches.
        """
        async with self.lock:
            self.history.append(message)
            self.message_count += 1
            slow_consumers = []

            for sub in self.subscribers.values():
                try:
                    sub.queue.put_nowait(message)
                    # Reset drop count on successful delivery
                    sub.drop_count = 0
                except asyncio.QueueFull:
                    # backpressure: drop oldest
                    try:
                        _ = sub.queue.get_nowait()
                        sub.queue.put_nowait(message)
                        sub.drop_count += 1
                        logger.warning("Queue full: dropped oldest for %s on topic %s (drop count: %d)",
                                       sub.client_id, self.name, sub.drop_count)

                        # Check if subscriber should be disconnected
                        if sub.drop_count >= sub.slow_consumer_threshold:
                            slow_consumers.append(sub)
                    except asyncio.QueueEmpty:
                        pass  # very unlikely immediately after QueueFull

            # Disconnect slow consumers outside the main loop
            for slow_sub in slow_consumers:
                logger.error("Disconnecting slow consumer %s from topic %s (exceeded threshold)",
                             slow_sub.client_id, self.name)
                try:
                    await slow_sub.ws._send_error(None, "SLOW_CONSUMER",
                                                  "Consumer too slow, disconnecting")
                    await slow_sub.ws.close(code=1008)  # Policy violation
                except Exception as e:
                    logger.warning("Error disconnecting slow consumer %s: %s",
                                   slow_sub.client_id, e)
                # Remove from subscribers
                self.subscribers.pop(slow_sub.client_id, None)

    async def get_recent_messages(self, last_n: int) -> List[Message]:
        """
        Return up to last_n most recent messages.
        """
        async with self.lock:
            if last_n <= 0:
                return list(self.history)
            return list(self.history)[-last_n:]


class TopicManager:
    """
    Global manager for all topics.
    Provides concurrency-safe operations.
    """

    def __init__(self) -> None:
        self.topics: Dict[str, Topic] = {}
        self.lock = asyncio.Lock()
        self.start_time = time.time()
        self.shutdown_initiated = False
        self.shutdown_event = asyncio.Event()

    async def create_topic(self, name: str, ring_size: int = None) -> bool:
        if self.shutdown_initiated:
            logger.warning("Cannot create topic during shutdown: %s", name)
            return False

        async with self.lock:
            if name in self.topics:
                logger.warning("Topic '%s' already exists", name)
                return False
            topic = Topic(name, ring_size=ring_size)
            self.topics[name] = topic
            logger.info("Created topic: %s with ring buffer size: %d",
                        name, topic.ring_size)
            return True

    async def delete_topic(self, name: str) -> bool:
        async with self.lock:
            topic = self.topics.pop(name, None)
            if not topic:
                logger.warning("Topic '%s' not found for deletion", name)
                return False

        # Close all subscriber connections outside the lock
        subscriber_count = len(topic.subscribers)
        logger.info("Deleting topic '%s' with %d subscribers",
                    name, subscriber_count)
        for sub in list(topic.subscribers.values()):
            try:
                await sub.ws.close()
            except Exception as e:
                logger.warning("Error closing subscriber %s: %s",
                               sub.client_id, e)
        logger.info("Successfully deleted topic: %s", name)
        return True

    async def get_topic(self, name: str) -> Optional[Topic]:
        async with self.lock:
            return self.topics.get(name)

    async def list_topics(self) -> List[Dict[str, Any]]:
        async with self.lock:
            return [
                {
                    "name": n,
                    "subscribers": len(t.subscribers),
                    "ring_buffer_size": t.ring_size,
                    "messages_in_history": len(t.history),
                    "total_messages": t.message_count
                }
                for n, t in self.topics.items()
            ]

    async def get_health(self) -> Dict[str, Any]:
        async with self.lock:
            total_subscribers = sum(len(t.subscribers)
                                    for t in self.topics.values())
            return {
                "uptime_sec": int(time.time() - self.start_time),
                "topics": len(self.topics),
                "subscribers": total_subscribers,
            }

    async def get_stats(self) -> Dict[str, Any]:
        async with self.lock:
            return {
                name: {
                    "messages": topic.message_count,
                    "subscribers": len(topic.subscribers),
                }
                for name, topic in self.topics.items()
            }

    async def initiate_shutdown(self) -> None:
        """
        Initiate graceful shutdown process.
        Stop accepting new operations and prepare for shutdown.
        """
        logger.info("Initiating graceful shutdown...")
        self.shutdown_initiated = True

        # Notify all subscribers about shutdown
        async with self.lock:
            for topic in self.topics.values():
                for subscriber in list(topic.subscribers.values()):
                    try:
                        await subscriber.ws._send_info("Server shutting down gracefully", topic.name)
                    except Exception as e:
                        logger.warning("Error notifying subscriber %s about shutdown: %s",
                                       subscriber.client_id, e)

        # Set shutdown event to notify waiting operations
        self.shutdown_event.set()
        logger.info("Shutdown initiated - no new operations accepted")

    async def shutdown(self, timeout: float = None) -> None:
        """
        Complete shutdown process with best-effort flush.
        """
        if not self.shutdown_initiated:
            await self.initiate_shutdown()

        if timeout is None:
            timeout = getattr(settings, 'PUBSUB_SHUTDOWN_TIMEOUT', 30)

        logger.info("Starting shutdown process with %s second timeout", timeout)

        # Give subscribers time to process remaining messages
        try:
            await asyncio.wait_for(self._flush_all_queues(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "Timeout during queue flush, proceeding with shutdown")

        # Close all connections
        async with self.lock:
            total_connections = 0
            for topic in self.topics.values():
                for subscriber in list(topic.subscribers.values()):
                    total_connections += 1
                    try:
                        await subscriber.ws.close(code=1001)  # Going away
                    except Exception as e:
                        logger.warning("Error closing subscriber %s: %s",
                                       subscriber.client_id, e)
                topic.subscribers.clear()

            logger.info("Closed %d connections during shutdown",
                        total_connections)
            self.topics.clear()

        logger.info("Graceful shutdown completed")

    async def _flush_all_queues(self) -> None:
        """
        Best-effort flush of all subscriber queues.
        """
        logger.info("Flushing all subscriber queues...")

        while True:
            empty_count = 0
            total_queues = 0

            async with self.lock:
                for topic in self.topics.values():
                    for subscriber in topic.subscribers.values():
                        total_queues += 1
                        if subscriber.queue.empty():
                            empty_count += 1

            if total_queues == 0 or empty_count == total_queues:
                break

            # Small delay to allow message processing
            await asyncio.sleep(0.1)

        logger.info("Queue flush completed")


# Global singleton instance
manager = TopicManager()
