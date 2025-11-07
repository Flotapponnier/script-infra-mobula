package redis

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
	"redis-consumer/internal/clickhouse"
)

type Listener struct {
	client    *redis.Client
	writer    *clickhouse.Writer
	channelPattern string
}

func NewListener(host, password string, db int, writer *clickhouse.Writer) (*Listener, error) {
	client := redis.NewClient(&redis.Options{
		Addr:     host,
		Password: password,
		DB:       db,
	})

	// Test connection
	ctx := context.Background()
	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	log.Printf("Connected to Redis: %s", host)

	return &Listener{
		client:         client,
		writer:         writer,
		channelPattern: "__keyevent@*__:*",
	}, nil
}

func (l *Listener) Start(ctx context.Context) error {
	// Subscribe to keyspace events
	pubsub := l.client.PSubscribe(ctx, l.channelPattern)
	defer pubsub.Close()

	log.Printf("Subscribed to Redis keyspace events: %s", l.channelPattern)

	// Listen for messages
	ch := pubsub.Channel()

	for {
		select {
		case <-ctx.Done():
			log.Println("Context cancelled, stopping listener...")
			return ctx.Err()

		case msg := <-ch:
			if msg == nil {
				continue
			}

			// Process the message
			if err := l.processMessage(ctx, msg); err != nil {
				log.Printf("Error processing message: %v", err)
				// Continue processing other messages
			}
		}
	}
}

func (l *Listener) processMessage(ctx context.Context, msg *redis.Message) error {
	// Parse channel: __keyevent@0__:set
	operation := l.extractOperation(msg.Channel)
	key := msg.Payload

	log.Printf("Received event: op=%s key=%s", operation, key)

	// Get value (if key still exists)
	value, err := l.client.Get(ctx, key).Result()
	if err != nil && err != redis.Nil {
		// Key might have been deleted, that's ok
		value = ""
	}

	// Limit value size to 1KB to prevent memory issues
	const maxValueSize = 1024
	if len(value) > maxValueSize {
		value = value[:maxValueSize] + "... (truncated)"
	}

	// Get TTL
	ttl, err := l.client.TTL(ctx, key).Result()
	if err != nil {
		ttl = -1
	}

	// Convert TTL to int32 pointer
	var ttlPtr *int32
	if ttl > 0 {
		ttlSeconds := int32(ttl.Seconds())
		ttlPtr = &ttlSeconds
	}

	// Create event
	event := clickhouse.RedisEvent{
		Timestamp: time.Now(),
		Operation: operation,
		Key:       key,
		Value:     value,
		TTL:       ttlPtr,
		Field:     nil,
		ClientInfo: nil,
	}

	// Write to ClickHouse
	return l.writer.WriteEvent(ctx, event)
}

func (l *Listener) extractOperation(channel string) string {
	// Channel format: __keyevent@0__:set
	parts := strings.Split(channel, ":")
	if len(parts) >= 2 {
		return strings.ToUpper(parts[len(parts)-1])
	}
	return "UNKNOWN"
}

func (l *Listener) Close() error {
	return l.client.Close()
}
