# Plivo Pub/Sub System

A simplified in-memory Pub/Sub system built with Django and Django Channels, supporting both WebSocket and REST API interfaces.

## Features

- **WebSocket Pub/Sub**: Real-time message publishing and subscribing
- **REST API**: Topic management and system observability
- **In-Memory Storage**: No external databases required
- **Concurrent Safe**: Thread-safe operations with asyncio
- **Message Replay**: Support for historical message replay (`last_n`)
- **Backpressure Handling**: Bounded queues with overflow protection
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

## Architecture

- **WebSocket Endpoint**: `/ws/` - Real-time communication
- **REST Endpoints**: Topic management and health monitoring
- **State Management**: In-memory topic and subscriber tracking
- **Message History**: Ring buffer for recent messages (configurable size)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Server

For development with both HTTP and WebSocket support:

```bash
daphne -b 0.0.0.0 -p 8000 plivo_pub_sub.asgi:application
```

Or for HTTP-only testing:

```bash
python manage.py runserver
```

### 3. Test the System

Run the comprehensive test suite:

```bash
python test_pubsub.py
```

Or try the example client:

```bash
python example_client.py
```

### 4. View Logs

The system provides comprehensive logging:

- **Console Output**: Real-time logs in the terminal
- **Log File**: Detailed logs saved to `pubsub.log`
- **Log Levels**: INFO for operations, WARNING for issues, ERROR for failures

Run the logging demo to see logging in action:

```bash
python logging_demo.py
```

## API Reference

### Authentication

All endpoints require X-API-Key authentication. Valid keys for demo: `plivo-test-key`, `demo-key`, `test-123`.

**REST API**: Include in header `X-API-Key: your-key-here` or query parameter `?api_key=your-key-here`

**WebSocket**: Include in header `X-API-Key: your-key-here` or query parameter `?api_key=your-key-here`

Example WebSocket connection:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/?api_key=plivo-test-key');
```

### WebSocket Protocol

Connect to `ws://localhost:8000/ws/?api_key=your-key-here`

#### Client → Server Messages

**Subscribe to Topic:**
```json
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "s1",
  "last_n": 5,
  "request_id": "uuid-optional"
}
```

**Unsubscribe from Topic:**
```json
{
  "type": "unsubscribe",
  "topic": "orders",
  "client_id": "s1",
  "request_id": "uuid-optional"
}
```

**Publish Message:**
```json
{
  "type": "publish",
  "topic": "orders",
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "order_id": "ORD-123",
      "amount": 99.5,
      "currency": "USD"
    }
  },
  "request_id": "uuid-optional"
}
```

**Ping:**
```json
{
  "type": "ping",
  "request_id": "uuid-optional"
}
```

#### Server → Client Messages

**Acknowledgment:**
```json
{
  "type": "ack",
  "request_id": "uuid-optional",
  "topic": "orders",
  "status": "ok",
  "ts": "2025-01-01T10:00:00Z"
}
```

**Event (Published Message):**
```json
{
  "type": "event",
  "topic": "orders",
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "order_id": "ORD-123",
      "amount": 99.5,
      "currency": "USD"
    }
  },
  "ts": "2025-01-01T10:01:00Z"
}
```

**Error:**
```json
{
  "type": "error",
  "request_id": "uuid-optional",
  "error": {
    "code": "BAD_REQUEST|TOPIC_NOT_FOUND|SLOW_CONSUMER|SERVICE_UNAVAILABLE",
    "message": "Error description"
  },
  "ts": "2025-01-01T10:02:00Z"
}
```

**Info (System Messages):**
```json
{
  "type": "info",
  "msg": "Server shutting down gracefully",
  "topic": "orders",
  "ts": "2025-01-01T10:03:00Z"
}
```

**Pong:**
```json
{
  "type": "pong",
  "request_id": "uuid-optional",
  "ts": "2025-01-01T10:04:00Z"
}
```

### REST API

**Create Topic:**
```bash
POST /topics/
Content-Type: application/json
X-API-Key: plivo-test-key

{
  "name": "orders",
  "ring_size": 100
}
```

**Delete Topic:**
```bash
DELETE /topics/orders/
X-API-Key: plivo-test-key
```

**List Topics:**
```bash
GET /topics/
X-API-Key: plivo-test-key
```

**Health Check:**
```bash
GET /health/
X-API-Key: plivo-test-key
```

**Statistics:**
```bash
GET /stats/
X-API-Key: plivo-test-key
```

**Graceful Shutdown:**
```bash
POST /shutdown/
X-API-Key: plivo-test-key
```

## Policies and Configuration

### Backpressure Policy

The system implements bounded per-subscriber queues to handle backpressure:

- **Queue Size**: Each subscriber has a bounded queue (default: 50 messages)
- **Overflow Handling**: When queue is full, the oldest message is dropped
- **Slow Consumer Protection**: After 3 consecutive message drops, the subscriber is disconnected with `SLOW_CONSUMER` error
- **WebSocket Close Code**: Slow consumers are disconnected with code `1008` (Policy Violation)

### Graceful Shutdown

The system supports graceful shutdown with the following behavior:

1. **Initiate Shutdown**: Call `POST /shutdown/` to start graceful shutdown
2. **Stop New Operations**: No new subscriptions, publications, or topic creations accepted
3. **Notify Subscribers**: All active subscribers receive info messages about shutdown
4. **Best-Effort Flush**: System attempts to deliver remaining messages (30-second timeout)
5. **Clean Disconnect**: All WebSocket connections closed with code `1001` (Going Away)

### Ring Buffer Configuration

- **Default Size**: 100 messages per topic
- **Configurable Range**: 1-10,000 messages
- **Per-Topic Setting**: Each topic can have different ring buffer sizes
- **Replay Support**: `last_n` parameter supports replay of recent messages

### Authentication

- **Required**: All endpoints require X-API-Key authentication
- **Default Keys**: `plivo-test-key`, `demo-key`, `test-123`
- **Methods**: Header `X-API-Key` or query parameter `api_key`
- **Configurable**: Keys can be customized via `PUBSUB_API_KEYS` environment variable

## Configuration

### Quick Configuration

Set environment variables to customize behavior:

```bash
# API Keys (comma-separated)
export PUBSUB_API_KEYS=my-key-1,my-key-2,my-key-3

# Performance tuning
export PUBSUB_SUBSCRIBER_QUEUE_SIZE=100
export PUBSUB_DEFAULT_RING_BUFFER_SIZE=200
export PUBSUB_SLOW_CONSUMER_THRESHOLD=5
```

### Full Configuration Guide

See [CONFIGURATION.md](CONFIGURATION.md) for complete configuration options including:
- API key management
- Performance tuning
- Docker configuration  
- Production recommendations

### Backpressure Policy

The system implements bounded queues for each subscriber with the following policy:
- **Queue Size**: 50 messages per subscriber
- **Overflow Handling**: **DROP OLDEST MESSAGE** when queue is full
- **Implementation**: When a subscriber's queue is full, the oldest message is removed and the new message is added
- **Error Handling**: Graceful degradation with no connection drops
- **Alternative**: System is ready to implement SLOW_CONSUMER error disconnection if needed

**Policy Details:**
```python
# When queue is full (50 messages):
except asyncio.QueueFull:
    try:
        subscriber.queue.get_nowait()  # Remove oldest message
        await subscriber.queue.put(message)  # Add new message
    except asyncio.QueueEmpty:
        pass  # Queue was already empty
```

This ensures the system remains responsive under high load while preserving the most recent messages.

### Message History

- **Ring Buffer**: Last 100 messages per topic (configurable)
- **Replay Support**: Subscribe with `last_n` parameter to receive recent messages
- **Memory Efficient**: Automatic cleanup of old messages

## Development

### Project Structure

```
plivo_pub_sub/
├── manage.py
├── plivo_pub_sub/
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
├── pubsub/
│   ├── models.py
│   ├── views.py
│   ├── consumers.py
│   ├── routing.py
│   ├── state.py
│   ├── serializers.py
│   └── urls.py
├── requirements.txt
├── test_pubsub.py
├── example_client.py
└── README.md
```

### Key Components

- **`state.py`**: In-memory state management with thread safety
- **`consumers.py`**: WebSocket consumer handling all real-time operations
- **`views.py`**: REST API endpoints for topic management
- **`routing.py`**: WebSocket URL routing configuration

## Testing

The system includes comprehensive tests covering:

- ✅ REST API endpoints (create, delete, list topics)
- ✅ WebSocket communication (subscribe, publish, unsubscribe)
- ✅ Message fan-out to multiple subscribers
- ✅ Error handling and validation
- ✅ Health and statistics endpoints

Run tests:
```bash
python test_pubsub.py
```

## Docker Support

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "plivo_pub_sub.asgi:application"]
```

Build and run:
```bash
docker build -t plivo-pubsub .
docker run -p 8000:8000 plivo-pubsub
```

## Assumptions and Design Choices

1. **In-Memory Storage**: No persistence across restarts (as required)
2. **Backpressure Policy**: Drop oldest messages on queue overflow
3. **Message IDs**: Must be valid UUIDs
4. **Topic Names**: Alphanumeric with hyphens allowed
5. **Concurrency**: Thread-safe with asyncio locks
6. **Error Handling**: Graceful degradation with proper error codes
7. **Message Ordering**: Best-effort ordering within topics

## Performance Considerations

- **Memory Usage**: Bounded by ring buffer size (100 messages × topics)
- **Concurrent Connections**: Limited by system resources
- **Message Throughput**: Optimized for real-time delivery
- **Scalability**: Single-instance design (no clustering)

## License

This project is created for the Plivo technical assignment.
