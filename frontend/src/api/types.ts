export interface ReadinessStatus {
  status: 'ready' | 'unavailable'
  database: 'connected' | 'disconnected'
  redis: 'connected' | 'disconnected' | 'not configured'
  rabbitmq: 'connected' | 'disconnected' | 'not configured'
}
