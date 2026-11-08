import { Outlet } from 'react-router-dom'

export default function Layout() {
  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">Notification Platform</span>
        <span className="muted">tenant dashboard — foundation stage</span>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
