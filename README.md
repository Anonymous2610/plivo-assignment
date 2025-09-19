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

### WebSocket Protocol

Connect to `ws://localhost:8000/ws/`

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
    "code": "BAD_REQUEST",
    "message": "Missing required field: topic"
  },
  "ts": "2025-01-01T10:02:00Z"
}
```

### REST API

**Create Topic:**
```bash
POST /topics/
Content-Type: application/json

{
  "name": "orders"
}
```

**Delete Topic:**
```bash
DELETE /topics/orders/
```

**List Topics:**
```bash
GET /topics/
```

**Health Check:**
```bash
GET /health/
```

**Statistics:**
```bash
GET /stats/
```

## Configuration

### Environment Variables

- `DEBUG`: Enable debug mode (default: True)
- `SECRET_KEY`: Django secret key
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

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
