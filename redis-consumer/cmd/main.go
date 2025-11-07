package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"redis-consumer/internal/clickhouse"
	"redis-consumer/internal/config"
	"redis-consumer/internal/redis"
)

func main() {
	log.Println("Starting Redis Consumer...")

	// Load configuration
	cfg := config.Load()
	log.Printf("Configuration loaded: Redis=%s ClickHouse=%s Instance=%s",
		cfg.RedisHost, cfg.ClickHouseHost, cfg.RedisInstanceName)

	// Create context that can be cancelled
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Initialize ClickHouse writer
	writer, err := clickhouse.NewWriter(
		cfg.ClickHouseHost,
		cfg.ClickHouseDB,
		cfg.RedisInstanceName,
	)
	if err != nil {
		log.Fatalf("Failed to create ClickHouse writer: %v", err)
	}
	defer writer.Close()

	// Initialize Redis listener
	listener, err := redis.NewListener(
		cfg.RedisHost,
		cfg.RedisPassword,
		cfg.RedisDB,
		writer,
	)
	if err != nil {
		log.Fatalf("Failed to create Redis listener: %v", err)
	}
	defer listener.Close()

	// Handle shutdown gracefully
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	// Start listener in goroutine
	errChan := make(chan error, 1)
	go func() {
		if err := listener.Start(ctx); err != nil {
			errChan <- err
		}
	}()

	log.Println("Redis Consumer is running. Press Ctrl+C to stop.")

	// Wait for shutdown signal or error
	select {
	case <-sigChan:
		log.Println("Received shutdown signal...")
		cancel()
	case err := <-errChan:
		log.Printf("Listener error: %v", err)
		cancel()
	}

	log.Println("Redis Consumer stopped.")
}
