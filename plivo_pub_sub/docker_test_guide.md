# Docker Testing Guide

## Quick Start

### 1. Build and Run Docker Container

```bash
# Build the Docker image
docker build -t plivo-pubsub .

# Run the container (expose port 8000)
docker run -p 8000:8000 plivo-pubsub
```

### 2. Test the System

```bash
# Run the Docker-specific test suite
python test_docker.py

# Or test with custom host/port
python test_docker.py localhost 8000
```

## Manual Testing

### REST API Testing

```bash
# Test authentication (should fail)
curl http://localhost:8000/health/

# Test with API key (should succeed)
curl -H "X-API-Key: plivo-test-key" http://localhost:8000/health/

# Create topic
curl -X POST -H "Content-Type: application/json" \
     -H "X-API-Key: plivo-test-key" \
     -d '{"name": "test-topic", "ring_size": 100}' \
     http://localhost:8000/topics/

# List topics
curl -H "X-API-Key: plivo-test-key" http://localhost:8000/topics/

# Get stats
curl -H "X-API-Key: plivo-test-key" http://localhost:8000/stats/
```

### WebSocket Testing

Use a WebSocket client or browser console:

```javascript
// Connect with API key
const ws = new WebSocket('ws://localhost:8000/ws/?api_key=plivo-test-key');

ws.onopen = function() {
    console.log('Connected');
    
    // Subscribe to topic
    ws.send(JSON.stringify({
        type: 'subscribe',
        topic: 'test-topic',
        client_id: 'test-client',
        last_n: 5,
        request_id: 'sub-1'
    }));
};

ws.onmessage = function(event) {
    console.log('Received:', JSON.parse(event.data));
};

// Publish a message
ws.send(JSON.stringify({
    type: 'publish',
    topic: 'test-topic',
    message: {
        id: 'msg-123',
        payload: { hello: 'world' }
    },
    request_id: 'pub-1'
}));
```

## Troubleshooting

### Common Issues

1. **Port not accessible**: Make sure Docker port mapping is correct (`-p 8000:8000`)
2. **Authentication failures**: Ensure you're using valid API keys (`plivo-test-key`, `demo-key`, `test-123`)
3. **WebSocket connection fails**: Check if the server is running and accessible

### Check Docker Container

```bash
# List running containers
docker ps

# Check container logs
docker logs <container-id>

# Access container shell
docker exec -it <container-id> /bin/bash
```

### Verify Server is Running

```bash
# Check if server responds
curl -I http://localhost:8000/health/

# Should return HTTP 401 (authentication required)
```

## Expected Test Results

When running `python test_docker.py`, you should see:

```
🚀 Docker Test Suite
==================================================
🐳 Testing Docker server at http://localhost:8000
🔌 Testing Server Connectivity...
  ✓ Server is reachable
🔐 Testing Authentication...
  ✓ REST API correctly rejects requests without API key
  ✓ REST API accepts requests with valid API key
🔌 Testing WebSocket Basic Functionality...
  ✓ WebSocket connection and ping/pong works
📋 Testing Topic Operations...
  ✓ Topic creation works
  ✓ Topic listing and ring buffer configuration works
  ✓ Topic cleanup completed
📡 Testing Pub/Sub Flow...
  ✓ Complete pub/sub flow works

==================================================
📊 Test Results: 5/5 tests passed
✅ All Docker tests completed successfully!

🎉 Your pub/sub system is working correctly in Docker!
```

## Features Tested

- ✅ X-API-Key authentication (REST & WebSocket)
- ✅ Topic creation with configurable ring buffer
- ✅ WebSocket pub/sub functionality
- ✅ Message replay with `last_n`
- ✅ Backpressure handling
- ✅ Graceful shutdown capability
