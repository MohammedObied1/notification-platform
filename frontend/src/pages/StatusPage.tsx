import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { ReadinessStatus } from '../api/types'

function Dot({ ok }: { ok: boolean }) {
  return <span className={`dot ${ok ? 'dot-ok' : 'dot-down'}`} />
}

export default function StatusPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['readiness'],
    queryFn: async () => (await api.get<ReadinessStatus>('/health/ready')).data,
    refetchInterval: 10_000,
  })

  return (
    <div className="status-card">
      <h1>System Status</h1>
      <p className="muted">
        This is the project foundation stage — no organizations, API keys, or notifications exist yet. This page exists to prove the
        backend and its infrastructure dependencies are reachable.
      </p>

      {isLoading && <p>Checking...</p>}
      {isError && <p className="error-text">Could not reach the API at all.</p>}

      {data && (
        <ul className="status-list">
          <li>
            <Dot ok={data.database === 'connected'} /> Database — {data.database}
          </li>
          <li>
            <Dot ok={data.redis !== 'disconnected'} /> Redis — {data.redis}
          </li>
          <li>
            <Dot ok={data.rabbitmq !== 'disconnected'} /> RabbitMQ — {data.rabbitmq}
          </li>
        </ul>
      )}
    </div>
  )
}
