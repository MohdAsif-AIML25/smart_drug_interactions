#!/bin/bash
# ============================================
# Kafka Topic Setup Script (KRaft Mode)
# Creates required topics for the pipeline
# ============================================

set -e

# Full path — kafka-topics.sh is NOT in PATH in apache/kafka:3.7.0
KAFKA_BIN="/opt/kafka/bin"
KAFKA_BOOTSTRAP="kafka:9092"
TOPIC_REPLICATION=1
TOPIC_PARTITIONS=3

echo "⏳ Waiting for Kafka to be ready..."
sleep 15

echo "📌 Creating Kafka topics..."

# Topic 1: Raw drug events from OpenFDA/PubMed
$KAFKA_BIN/kafka-topics.sh \
  --bootstrap-server $KAFKA_BOOTSTRAP \
  --create \
  --if-not-exists \
  --topic raw_drug_events \
  --partitions $TOPIC_PARTITIONS \
  --replication-factor $TOPIC_REPLICATION \
  --config retention.ms=86400000

echo "✅ Created: raw_drug_events"

# Topic 2: Processed features for ML inference
$KAFKA_BIN/kafka-topics.sh \
  --bootstrap-server $KAFKA_BOOTSTRAP \
  --create \
  --if-not-exists \
  --topic processed_features \
  --partitions $TOPIC_PARTITIONS \
  --replication-factor $TOPIC_REPLICATION \
  --config retention.ms=86400000

echo "✅ Created: processed_features"

echo "📋 Current topics:"
$KAFKA_BIN/kafka-topics.sh --bootstrap-server $KAFKA_BOOTSTRAP --list

echo "🎉 Kafka topics setup complete!"
