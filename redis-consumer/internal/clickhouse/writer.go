package clickhouse

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"strings"
	"time"

	_ "github.com/ClickHouse/clickhouse-go/v2"
)

type Writer struct {
	db           *sql.DB
	instanceName string
	tableName    string
}

type RedisEvent struct {
	Timestamp    time.Time
	Operation    string
	Key          string
	Value        string
	TTL          *int32
	Field        *string
	ClientInfo   *string
}

func NewWriter(host, database, instanceName string) (*Writer, error) {
	// Build connection string
	dsn := fmt.Sprintf("clickhouse://%s/%s", host, database)

	db, err := sql.Open("clickhouse", dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to ClickHouse: %w", err)
	}

	// Test connection
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping ClickHouse: %w", err)
	}

	log.Printf("Connected to ClickHouse: %s/%s", host, database)

	// Determine table name based on instance
	// Replace - with _ for valid table name
	safeInstanceName := strings.ReplaceAll(instanceName, "-", "_")
	tableName := fmt.Sprintf("%s_updates", safeInstanceName)

	return &Writer{
		db:           db,
		instanceName: instanceName,
		tableName:    tableName,
	}, nil
}

func (w *Writer) WriteEvent(ctx context.Context, event RedisEvent) error {
	query := fmt.Sprintf(`
		INSERT INTO %s (timestamp, redis_instance, operation, key, value, ttl, field, client_info)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`, w.tableName)

	_, err := w.db.ExecContext(
		ctx,
		query,
		event.Timestamp,
		w.instanceName,
		event.Operation,
		event.Key,
		event.Value,
		event.TTL,
		event.Field,
		event.ClientInfo,
	)

	if err != nil {
		return fmt.Errorf("failed to insert into ClickHouse: %w", err)
	}

	log.Printf("Inserted event: op=%s key=%s", event.Operation, event.Key)
	return nil
}

func (w *Writer) Close() error {
	return w.db.Close()
}
