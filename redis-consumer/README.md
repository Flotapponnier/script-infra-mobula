# Redis Consumer - ClickHouse Tracking

Consumer Go qui capture tous les updates Redis et les stocke dans ClickHouse pour traçabilité complète.

## Architecture

```
Redis → Keyspace Notifications → Go Consumer → ClickHouse
```

## Fonctionnalités

- ✅ Capture tous les events Redis (SET, DEL, EXPIRE, etc.)
- ✅ Récupère les valeurs et TTL
- ✅ Insère en temps réel dans ClickHouse
- ✅ Support multi-instances Redis
- ✅ Graceful shutdown
- ✅ Health checks

## Configuration

Variables d'environnement :

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Host:port Redis | `localhost:6379` |
| `REDIS_PASSWORD` | Mot de passe Redis | `""` |
| `CLICKHOUSE_HOST` | Host:port ClickHouse | `localhost:9000` |
| `CLICKHOUSE_DB` | Database ClickHouse | `redis_tracking` |
| `REDIS_INSTANCE_NAME` | Nom de l'instance (pour la table) | `redis` |
| `LOG_LEVEL` | Niveau de log | `info` |

## Build

### Local
```bash
go mod download
go build -o redis-consumer ./cmd/main.go
./redis-consumer
```

### Docker
```bash
docker build -t redis-consumer:latest .
docker run -e REDIS_HOST=redis:6379 -e CLICKHOUSE_HOST=clickhouse:9000 redis-consumer:latest
```

## Déploiement Kubernetes

### 1. Activer Redis keyspace notifications

**IMPORTANT** : Avant de déployer, activer les notifications sur chaque Redis :

```bash
# redis-preprod
kubectl exec -it redis-preprod-node-0 -n redis-preprod -- redis-cli CONFIG SET notify-keyspace-events AKE

# redis-cache-preprod
kubectl exec -it redis-cache-preprod-node-0 -n redis-cache-preprod -- redis-cli CONFIG SET notify-keyspace-events AKE

# redis-pubsub-preprod
kubectl exec -it redis-pubsub-preprod-node-0 -n redis-pubsub-preprod -- redis-cli CONFIG SET notify-keyspace-events AKE
```

### 2. Build et push l'image

```bash
# Build
docker build -t your-registry/redis-consumer:v1.0.0 .

# Push
docker push your-registry/redis-consumer:v1.0.0
```

### 3. Update les deployments

Modifier `k8s/preprod/*.yaml` et remplacer `your-registry` par ton registry.

### 4. Deploy

```bash
kubectl apply -f k8s/preprod/deployment-redis-preprod.yaml
kubectl apply -f k8s/preprod/deployment-redis-cache-preprod.yaml
kubectl apply -f k8s/preprod/deployment-redis-pubsub-preprod.yaml
```

### 5. Vérifier

```bash
kubectl get pods -n clickhouse-preprod -l app=redis-consumer
kubectl logs -n clickhouse-preprod -l app=redis-consumer --tail=50
```

## Tests

### Tester l'insertion

```bash
# Faire une opération Redis
kubectl exec -it redis-preprod-node-0 -n redis-preprod -- redis-cli SET test:key "hello world"

# Vérifier dans ClickHouse
kubectl exec clickhouse-0 -n clickhouse-preprod -- clickhouse-client --query="
SELECT * FROM redis_tracking.redis_preprod_updates
WHERE key = 'test:key'
ORDER BY timestamp DESC LIMIT 1;
"
```

## Structure du projet

```
redis-consumer/
├── cmd/
│   └── main.go                 # Entry point
├── internal/
│   ├── config/
│   │   └── config.go          # Configuration
│   ├── redis/
│   │   └── listener.go        # Redis listener
│   └── clickhouse/
│       └── writer.go          # ClickHouse writer
├── k8s/
│   └── preprod/               # Kubernetes manifests
├── Dockerfile
├── go.mod
└── README.md
```

## Monitoring

Logs à surveiller :
- `Connected to Redis` - Connexion Redis réussie
- `Connected to ClickHouse` - Connexion ClickHouse réussie
- `Subscribed to Redis keyspace events` - Subscription active
- `Received event: op=X key=Y` - Event reçu
- `Inserted event: op=X key=Y` - Insertion réussie

## Troubleshooting

### Pas d'events reçus
- Vérifier que `notify-keyspace-events` est activé sur Redis
- Vérifier les logs du consumer

### Erreurs d'insertion ClickHouse
- Vérifier que la table existe
- Vérifier la connectivité vers ClickHouse
- Vérifier les permissions

### Pod crashe
- Vérifier les resources (CPU/Memory)
- Vérifier les logs : `kubectl logs -n clickhouse-preprod <pod-name>`
