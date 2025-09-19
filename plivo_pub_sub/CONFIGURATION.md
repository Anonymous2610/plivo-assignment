# Configuration Guide

## Environment Variables

The pub/sub system can be configured using environment variables. Here are all available configuration options:

### API Authentication

```bash
# API Keys for authentication (comma-separated list)
# Default: plivo-test-key,demo-key,test-123
PUBSUB_API_KEYS=plivo-test-key,demo-key,test-123,production-key
```

### Subscriber Configuration

```bash
# Maximum queue size per subscriber (messages)
# Default: 50
PUBSUB_SUBSCRIBER_QUEUE_SIZE=50

# Number of message drops before disconnecting slow consumer
# Default: 3
PUBSUB_SLOW_CONSUMER_THRESHOLD=3
```

### Topic Configuration

```bash
# Default ring buffer size for new topics (messages)
# Default: 100
PUBSUB_DEFAULT_RING_BUFFER_SIZE=100

# Maximum allowed ring buffer size (messages)
# Default: 10000
PUBSUB_MAX_RING_BUFFER_SIZE=10000
```

### Shutdown Configuration

```bash
# Timeout for graceful shutdown process (seconds)
# Default: 30
PUBSUB_SHUTDOWN_TIMEOUT=30
```

### Django Settings

```bash
# Django debug mode
DEBUG=True

# Django secret key (change in production!)
SECRET_KEY=your-secret-key-here

# Allowed hosts (comma-separated)
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
```

## Docker Configuration

### Environment File

Create a `.env` file for Docker:

```bash
# .env file for Docker
PUBSUB_API_KEYS=plivo-test-key,demo-key,production-key
PUBSUB_SUBSCRIBER_QUEUE_SIZE=100
PUBSUB_SLOW_CONSUMER_THRESHOLD=5
PUBSUB_DEFAULT_RING_BUFFER_SIZE=200
PUBSUB_MAX_RING_BUFFER_SIZE=20000
PUBSUB_SHUTDOWN_TIMEOUT=60
DEBUG=False
SECRET_KEY=production-secret-key
ALLOWED_HOSTS=*
```

### Docker Run with Environment

```bash
# Run with environment variables
docker run -p 8000:8000 \
  -e PUBSUB_API_KEYS=custom-key-1,custom-key-2 \
  -e PUBSUB_SUBSCRIBER_QUEUE_SIZE=100 \
  -e DEBUG=False \
  plivo-pubsub
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  pubsub:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PUBSUB_API_KEYS=production-key-1,production-key-2
      - PUBSUB_SUBSCRIBER_QUEUE_SIZE=100
      - PUBSUB_SLOW_CONSUMER_THRESHOLD=5
      - PUBSUB_DEFAULT_RING_BUFFER_SIZE=200
      - PUBSUB_SHUTDOWN_TIMEOUT=60
      - DEBUG=false
      - SECRET_KEY=production-secret-key
      - ALLOWED_HOSTS=*
```

## Production Recommendations

### Security

- **API Keys**: Use strong, randomly generated API keys in production
- **Secret Key**: Generate a new Django secret key for production
- **Debug Mode**: Set `DEBUG=False` in production
- **Allowed Hosts**: Specify exact hostnames instead of `*`

### Performance Tuning

```bash
# High-throughput configuration
PUBSUB_SUBSCRIBER_QUEUE_SIZE=200
PUBSUB_DEFAULT_RING_BUFFER_SIZE=500
PUBSUB_MAX_RING_BUFFER_SIZE=50000
PUBSUB_SLOW_CONSUMER_THRESHOLD=10
PUBSUB_SHUTDOWN_TIMEOUT=120
```

### Memory-Constrained Environment

```bash
# Low-memory configuration
PUBSUB_SUBSCRIBER_QUEUE_SIZE=20
PUBSUB_DEFAULT_RING_BUFFER_SIZE=50
PUBSUB_MAX_RING_BUFFER_SIZE=1000
PUBSUB_SLOW_CONSUMER_THRESHOLD=2
PUBSUB_SHUTDOWN_TIMEOUT=15
```

## Configuration Validation

The system validates configuration values:

- **API Keys**: Must be non-empty strings
- **Queue Size**: Must be positive integer
- **Ring Buffer Size**: Must be between 1 and `PUBSUB_MAX_RING_BUFFER_SIZE`
- **Thresholds**: Must be positive integers
- **Timeouts**: Must be positive numbers

## Runtime Configuration Changes

Configuration changes require service restart. The system reads environment variables only at startup.

## Monitoring Configuration

Check current configuration via health endpoint:

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/health/
```

The response includes configuration-derived metrics like queue sizes and timeouts.
