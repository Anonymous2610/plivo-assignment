#!/usr/bin/env python3
"""
Docker-specific test script for final features.
Run this when the server is running in Docker.
"""

import asyncio
import websockets
import json
import requests
import time
import sys
import uuid


class DockerPubSubTester:
    def __init__(self):
        # Default Docker configuration
        self.host = "localhost"
        self.port = "8000"

        # Allow override via command line
        if len(sys.argv) > 1:
            self.host = sys.argv[1]
        if len(sys.argv) > 2:
            self.port = sys.argv[2]

        self.base_url = f"http://{self.host}:{self.port}"
        self.ws_url = f"ws://{self.host}:{self.port}/ws"
        # Use first default API key (configurable via PUBSUB_API_KEYS)
        self.api_key = "plivo-test-key"
        self.headers = {"X-API-Key": self.api_key}

        print(f"🐳 Testing Docker server at {self.base_url}")

    def test_server_connectivity(self):
        """Test if server is reachable"""
        print("🔌 Testing Server Connectivity...")
        try:
            response = requests.get(f"{self.base_url}/health/",
                                    headers=self.headers, timeout=5)
            if response.status_code == 200:
                print("  ✓ Server is reachable")
                return True
            else:
                print(f"  ✗ Server returned status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Cannot reach server: {e}")
            return False

    def test_authentication(self):
        """Test API key authentication"""
        print("🔐 Testing Authentication...")

        # Test without API key (should fail)
        try:
            response = requests.get(f"{self.base_url}/health/", timeout=5)
            if response.status_code == 401:
                print("  ✓ REST API correctly rejects requests without API key")
            else:
                print(f"  ✗ Expected 401, got {response.status_code}")
                return False
        except Exception as e:
            print(f"  ✗ Error testing without API key: {e}")
            return False

        # Test with API key (should succeed)
        try:
            response = requests.get(f"{self.base_url}/health/",
                                    headers=self.headers, timeout=5)
            if response.status_code == 200:
                print("  ✓ REST API accepts requests with valid API key")
                return True
            else:
                print(f"  ✗ Expected 200, got {response.status_code}")
                return False
        except Exception as e:
            print(f"  ✗ Error testing with API key: {e}")
            return False

    async def test_websocket_basic(self):
        """Test basic WebSocket functionality"""
        print("🔌 Testing WebSocket Basic Functionality...")

        try:
            # Test with API key (should succeed)
            uri = f"{self.ws_url}?api_key={self.api_key}"
            async with websockets.connect(uri, timeout=10) as ws:
                # Send ping to verify connection
                ping_msg = {"type": "ping", "request_id": "test-ping"}
                await ws.send(json.dumps(ping_msg))

                # Wait for pong response
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)

                if data["type"] == "pong":
                    print("  ✓ WebSocket connection and ping/pong works")
                    return True
                else:
                    print(f"  ✗ Expected pong, got {data['type']}")
                    return False

        except websockets.exceptions.ConnectionClosed as e:
            print(f"  ✗ WebSocket connection closed: {e}")
            return False
        except websockets.exceptions.InvalidStatusCode as e:
            print(f"  ✗ WebSocket connection failed with status: {e}")
            return False
        except Exception as e:
            print(f"  ✗ WebSocket test failed: {e}")
            return False

    def test_topic_operations(self):
        """Test topic creation and listing"""
        print("📋 Testing Topic Operations...")

        # Create topic
        topic_data = {"name": "docker-test", "ring_size": 50}
        try:
            response = requests.post(f"{self.base_url}/topics/",
                                     json=topic_data, headers=self.headers, timeout=5)
            if response.status_code == 201:
                print("  ✓ Topic creation works")
            else:
                print(f"  ✗ Topic creation failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"  ✗ Topic creation error: {e}")
            return False

        # List topics
        try:
            response = requests.get(f"{self.base_url}/topics/",
                                    headers=self.headers, timeout=5)
            if response.status_code == 200:
                topics = response.json()["topics"]
                docker_topic = next(
                    (t for t in topics if t["name"] == "docker-test"), None)
                if docker_topic and docker_topic["ring_buffer_size"] == 50:
                    print("  ✓ Topic listing and ring buffer configuration works")
                else:
                    print("  ✗ Topic not found or incorrect configuration")
                    return False
            else:
                print(f"  ✗ Topic listing failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"  ✗ Topic listing error: {e}")
            return False

        # Clean up
        try:
            requests.delete(f"{self.base_url}/topics/docker-test/",
                            headers=self.headers, timeout=5)
            print("  ✓ Topic cleanup completed")
        except Exception as e:
            print(f"  ⚠ Topic cleanup warning: {e}")

        return True

    async def test_pubsub_flow(self):
        """Test complete pub/sub flow"""
        print("📡 Testing Pub/Sub Flow...")

        # Create topic first
        topic_data = {"name": "pubsub-test"}
        requests.post(f"{self.base_url}/topics/",
                      json=topic_data, headers=self.headers)

        try:
            uri = f"{self.ws_url}?api_key={self.api_key}"
            async with websockets.connect(uri, timeout=10) as ws:
                # Subscribe to topic
                subscribe_msg = {
                    "type": "subscribe",
                    "topic": "pubsub-test",
                    "client_id": "docker-client",
                    "request_id": "sub-1"
                }
                await ws.send(json.dumps(subscribe_msg))

                # Wait for ack
                ack = await asyncio.wait_for(ws.recv(), timeout=5)
                ack_data = json.loads(ack)
                if ack_data["type"] != "ack":
                    print(f"  ✗ Expected ack, got {ack_data['type']}")
                    return False

                # Publish message
                publish_msg = {
                    "type": "publish",
                    "topic": "pubsub-test",
                    "message": {
                        "id": str(uuid.uuid4()),
                        "payload": {"test": "docker"}
                    },
                    "request_id": "pub-1"
                }
                await ws.send(json.dumps(publish_msg))

                # Wait for publish ack
                pub_ack = await asyncio.wait_for(ws.recv(), timeout=5)

                # Wait for event message
                event = await asyncio.wait_for(ws.recv(), timeout=5)
                event_data = json.loads(event)

                if (event_data["type"] == "event" and
                    event_data["topic"] == "pubsub-test" and
                    "id" in event_data["message"] and
                        event_data["message"]["payload"]["test"] == "docker"):
                    print("  ✓ Complete pub/sub flow works")
                    return True
                else:
                    print(f"  ✗ Unexpected event data: {event_data}")
                    return False

        except Exception as e:
            print(f"  ✗ Pub/sub flow error: {e}")
            return False
        finally:
            # Clean up
            try:
                requests.delete(f"{self.base_url}/topics/pubsub-test/",
                                headers=self.headers)
            except:
                pass

    async def run_all_tests(self):
        """Run all Docker-specific tests"""
        print("🚀 Docker Test Suite")
        print("=" * 50)

        tests_passed = 0
        total_tests = 5

        # Test server connectivity first
        if self.test_server_connectivity():
            tests_passed += 1
        else:
            print("❌ Cannot reach server - check if Docker container is running")
            return False

        # Test authentication
        if self.test_authentication():
            tests_passed += 1

        # Test WebSocket basic functionality
        if await self.test_websocket_basic():
            tests_passed += 1

        # Test topic operations
        if self.test_topic_operations():
            tests_passed += 1

        # Test pub/sub flow
        if await self.test_pubsub_flow():
            tests_passed += 1

        print("\n" + "=" * 50)
        print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")

        if tests_passed == total_tests:
            print("✅ All Docker tests completed successfully!")
            print("\n🎉 Your pub/sub system is working correctly in Docker!")
            return True
        else:
            print("❌ Some tests failed - check the output above")
            return False


if __name__ == "__main__":
    print("Docker Pub/Sub Test Suite")
    print("Usage: python test_docker.py [host] [port]")
    print("Example: python test_docker.py localhost 8000")
    print("=" * 50)

    tester = DockerPubSubTester()
    success = asyncio.run(tester.run_all_tests())

    if not success:
        sys.exit(1)
