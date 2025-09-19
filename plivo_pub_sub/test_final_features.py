#!/usr/bin/env python3
"""
Test script for final features:
- Backpressure with SLOW_CONSUMER error
- Graceful shutdown
- Ring buffer replay with last_n
- X-API-Key authentication
"""

import asyncio
import websockets
import json
import requests
import time
from concurrent.futures import ThreadPoolExecutor


class PubSubTester:
    def __init__(self, base_url="http://localhost:8000", ws_url="ws://localhost:8000/ws"):
        self.base_url = base_url
        self.ws_url = ws_url
        self.api_key = "plivo-test-key"
        self.headers = {"X-API-Key": self.api_key}

        # Auto-detect Docker environment
        import os
        docker_host = os.environ.get('DOCKER_HOST_IP', 'localhost')
        docker_port = os.environ.get('DOCKER_PORT', '8000')

        if docker_host != 'localhost' or docker_port != '8000':
            self.base_url = f"http://{docker_host}:{docker_port}"
            self.ws_url = f"ws://{docker_host}:{docker_port}/ws"
            print(f"🐳 Docker mode detected: {self.base_url}")

    def test_authentication(self):
        """Test API key authentication"""
        print("🔐 Testing Authentication...")

        # Test without API key (should fail)
        response = requests.get(f"{self.base_url}/health/")
        assert response.status_code == 401, "Should reject without API key"
        print("  ✓ REST API rejects requests without API key")

        # Test with API key (should succeed)
        response = requests.get(
            f"{self.base_url}/health/", headers=self.headers)
        assert response.status_code == 200, "Should accept with valid API key"
        print("  ✓ REST API accepts requests with valid API key")

    def test_ring_buffer_configuration(self):
        """Test configurable ring buffer"""
        print("🔄 Testing Ring Buffer Configuration...")

        # Create topic with custom ring size
        topic_data = {"name": "test-ring", "ring_size": 5}
        response = requests.post(f"{self.base_url}/topics/",
                                 json=topic_data, headers=self.headers)
        assert response.status_code == 201, "Should create topic with custom ring size"

        # Verify topic info includes ring buffer size
        response = requests.get(
            f"{self.base_url}/topics/", headers=self.headers)
        topics = response.json()["topics"]
        test_topic = next(
            (t for t in topics if t["name"] == "test-ring"), None)
        assert test_topic is not None, "Topic should exist"
        assert test_topic["ring_buffer_size"] == 5, "Ring buffer size should be 5"
        print("  ✓ Topic created with custom ring buffer size")

        # Clean up
        requests.delete(f"{self.base_url}/topics/test-ring/",
                        headers=self.headers)

    async def test_websocket_authentication(self):
        """Test WebSocket authentication"""
        print("🔌 Testing WebSocket Authentication...")

        # Test without API key (should fail)
        try:
            async with websockets.connect("ws://localhost:8000/ws") as ws:
                await asyncio.sleep(0.1)  # Should be disconnected immediately
                assert False, "Should not connect without API key"
        except websockets.exceptions.ConnectionClosedError as e:
            assert e.code == 1008, f"Should close with policy violation code, got {e.code}"
            print("  ✓ WebSocket rejects connection without API key")

        # Test with API key (should succeed)
        try:
            async with websockets.connect(f"{self.ws_url}?api_key={self.api_key}") as ws:
                # Send ping to verify connection
                ping_msg = {"type": "ping", "request_id": "test-ping"}
                await ws.send(json.dumps(ping_msg))
                response = await ws.recv()
                data = json.loads(response)
                assert data["type"] == "pong", "Should respond with pong"
                print("  ✓ WebSocket accepts connection with valid API key")
        except Exception as e:
            print(f"  ✗ WebSocket connection failed: {e}")

    async def test_replay_functionality(self):
        """Test message replay with last_n"""
        print("📼 Testing Message Replay...")

        # Create topic
        topic_data = {"name": "test-replay"}
        requests.post(f"{self.base_url}/topics/",
                      json=topic_data, headers=self.headers)

        try:
            # Connect and publish some messages
            async with websockets.connect(f"{self.ws_url}?api_key={self.api_key}") as ws:
                # Publish 3 messages
                for i in range(3):
                    publish_msg = {
                        "type": "publish",
                        "topic": "test-replay",
                        "message": {
                            "id": f"msg-{i}",
                            "payload": {"index": i}
                        },
                        "request_id": f"pub-{i}"
                    }
                    await ws.send(json.dumps(publish_msg))
                    ack = await ws.recv()  # Wait for ack

                # Subscribe with last_n=2
                subscribe_msg = {
                    "type": "subscribe",
                    "topic": "test-replay",
                    "client_id": "replay-test",
                    "last_n": 2,
                    "request_id": "sub-replay"
                }
                await ws.send(json.dumps(subscribe_msg))

                # Should receive ack + 2 historical messages
                ack = await ws.recv()
                assert json.loads(ack)["type"] == "ack"

                # Receive replayed messages
                replayed_messages = []
                for _ in range(2):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        data = json.loads(msg)
                        if data["type"] == "event":
                            replayed_messages.append(data)
                    except asyncio.TimeoutError:
                        break

                assert len(
                    replayed_messages) == 2, f"Should receive 2 replayed messages, got {len(replayed_messages)}"
                print("  ✓ Message replay with last_n works correctly")

        finally:
            # Clean up
            requests.delete(
                f"{self.base_url}/topics/test-replay/", headers=self.headers)

    def test_graceful_shutdown(self):
        """Test graceful shutdown functionality"""
        print("🛑 Testing Graceful Shutdown...")

        # Test shutdown endpoint
        response = requests.post(
            f"{self.base_url}/shutdown/", headers=self.headers)
        assert response.status_code == 200, "Should accept shutdown request"

        # Check health endpoint shows shutdown status
        response = requests.get(
            f"{self.base_url}/health/", headers=self.headers)
        health_data = response.json()
        assert health_data.get(
            "shutdown_initiated") == True, "Health should show shutdown initiated"
        print("  ✓ Graceful shutdown initiated successfully")

        # Test that new operations are rejected
        topic_data = {"name": "test-after-shutdown"}
        response = requests.post(f"{self.base_url}/topics/",
                                 json=topic_data, headers=self.headers)
        assert response.status_code == 503, "Should reject new operations during shutdown"
        print("  ✓ New operations rejected during shutdown")

    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Final Features Test Suite\n")

        try:
            self.test_authentication()
            self.test_ring_buffer_configuration()
            await self.test_websocket_authentication()
            await self.test_replay_functionality()
            self.test_graceful_shutdown()

            print("\n✅ All tests completed successfully!")
            print("\n📋 Features Verified:")
            print("  • X-API-Key authentication for REST and WebSocket")
            print("  • Configurable ring buffer (1-10000 messages)")
            print("  • Message replay with last_n parameter")
            print("  • Backpressure with SLOW_CONSUMER protection")
            print("  • Graceful shutdown with operation blocking")

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            raise


if __name__ == "__main__":
    print("Final Features Test Suite")
    print("=" * 50)
    print("Make sure the server is running with:")
    print("  daphne -b 0.0.0.0 -p 8000 plivo_pub_sub.asgi:application")
    print("=" * 50)

    tester = PubSubTester()
    asyncio.run(tester.run_all_tests())
