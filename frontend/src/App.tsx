import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'

async function fetchHealth() {
  const { data } = await api.GET('/health')
  if (!data) throw new Error('the API did not answer /health')
  return data // typed from the schema as { status: "ok" }
}

export default function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth })

  return (
    <main className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold">Tessera</h1>
      <p className="mt-4">
        API status:{' '}
        {health.isPending && <span className="text-gray-500">checking…</span>}
        {health.isError && (
          <span className="text-red-600">unreachable ({health.error.message})</span>
        )}
        {health.isSuccess && <span className="text-green-700">{health.data.status}</span>}
      </p>
    </main>
  )
}
