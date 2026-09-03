"""
ResQAI - Kafka Event Manager
Event-driven communication between microservices and AI agents.
"""

import json
from typing import Optional, Callable
from loguru import logger

from app.config import settings


class KafkaManager:
    """
    Manages Kafka producers and consumers.
    Provides a clean async interface for event-driven operations.
    """

    def __init__(self) -> None:
        self._producer = None
        self._consumers = []
        self._running = False

    async def start(self) -> None:
        """Initialize Kafka producer and start consumers."""
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka.BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode(),
                acks="all",
                retry_backoff_ms=100,
            )
            await self._producer.start()
            self._running = True
            logger.info("Kafka producer started")

            # Start event consumer
            await self._start_donation_consumer()
        except Exception as e:
            logger.warning(f"Kafka unavailable (running without events): {e}")

    async def stop(self) -> None:
        """Gracefully stop all Kafka connections."""
        if self._producer:
            await self._producer.stop()
        for consumer in self._consumers:
            await consumer.stop()
        self._running = False
        logger.info("Kafka connections closed")

    async def produce(self, topic: str, payload: dict) -> None:
        """Publish a message to a Kafka topic."""
        if not self._producer or not self._running:
            logger.debug(f"Kafka not running, skipping event to {topic}")
            return
        try:
            await self._producer.send_and_wait(topic, payload)
            logger.debug(f"Kafka event sent: {topic} → {payload.get('event', 'unknown')}")
        except Exception as e:
            logger.error(f"Kafka produce failed: {e}")

    async def _start_donation_consumer(self) -> None:
        """Consume donation events and dispatch to AI orchestrator."""
        import asyncio
        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                settings.kafka.TOPIC_DONATIONS,
                bootstrap_servers=settings.kafka.BOOTSTRAP_SERVERS,
                group_id=settings.kafka.CONSUMER_GROUP,
                auto_offset_reset="earliest",
                value_deserializer=lambda v: json.loads(v.decode()),
            )
            await consumer.start()
            self._consumers.append(consumer)

            asyncio.create_task(self._consume_loop(consumer))
            logger.info(f"Kafka consumer started: {settings.kafka.TOPIC_DONATIONS}")
        except Exception as e:
            logger.warning(f"Kafka consumer failed to start: {e}")

    async def _consume_loop(self, consumer) -> None:
        """Process incoming Kafka messages and dispatch to AI pipeline."""
        try:
            async for msg in consumer:
                payload = msg.value
                event = payload.get("event", "")
                logger.debug(f"Kafka event received: {event}")

                if event == "donation.created":
                    donation_id = payload.get("donation_id")
                    if donation_id:
                        from app.tasks.ai_tasks import analyze_food_images_task
                        analyze_food_images_task.delay(donation_id, [])
        except Exception as e:
            logger.error(f"Kafka consumer loop error: {e}")


# Module-level singleton
_kafka_manager: Optional[KafkaManager] = None


def get_kafka_manager() -> Optional[KafkaManager]:
    return _kafka_manager


def set_kafka_manager(manager: KafkaManager) -> None:
    global _kafka_manager
    _kafka_manager = manager
