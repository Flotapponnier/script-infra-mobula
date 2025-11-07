package config

import (
	"os"
)

type Config struct {
	RedisHost         string
	RedisPassword     string
	RedisDB           int
	ClickHouseHost    string
	ClickHouseDB      string
	RedisInstanceName string
	LogLevel          string
}

func Load() *Config {
	return &Config{
		RedisHost:         getEnv("REDIS_HOST", "localhost:6379"),
		RedisPassword:     getEnv("REDIS_PASSWORD", ""),
		RedisDB:           0,
		ClickHouseHost:    getEnv("CLICKHOUSE_HOST", "localhost:9000"),
		ClickHouseDB:      getEnv("CLICKHOUSE_DB", "redis_tracking"),
		RedisInstanceName: getEnv("REDIS_INSTANCE_NAME", "redis"),
		LogLevel:          getEnv("LOG_LEVEL", "info"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
