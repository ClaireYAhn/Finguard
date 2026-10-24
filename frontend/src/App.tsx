import { Navigate, Route, Routes } from 'react-router-dom'
import { useApp } from './context'
import { Banner } from './components/Layout'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import Login from './pages/Login'
import Overview from './pages/Overview'
import Apps from './pages/Apps'
import Live from './pages/Live'
import Reviews from './pages/Reviews'
import Policies from './pages/Policies'
import Evaluation from './pages/Evaluation'
import Audit from './pages/Audit'
import Reports from './pages/Reports'
import Demo from './pages/Demo'
import About from './pages/About'

export default function App() {
  const { config, configError, signedIn } = useApp()

  if (!config) {
    if (configError) {
      return (
        <div className="min-h-screen">
          <Banner />
          <main className="mx-auto max-w-3xl p-6">
            <div role="alert" className="card border-red-700">
              <h1 className="mb-2 text-xl font-bold">Cannot reach the backend</h1>
              <p className="mb-3 text-sm">{configError}</p>
              <p className="text-sm">The Demo page can still show the last results saved in this browser.</p>
            </div>
            <div className="mt-4"><Demo offline /></div>
          </main>
        </div>
      )
    }
    return (
      <div className="min-h-screen">
        <Banner />
        <Spinner label="Loading configuration…" />
      </div>
    )
  }

  if (!signedIn) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="apps" element={<Apps />} />
        <Route path="live" element={<Live />} />
        <Route path="reviews" element={<Reviews />} />
        <Route path="policies" element={<Policies />} />
        <Route path="evaluation" element={<Evaluation />} />
        <Route path="audit" element={<Audit />} />
        <Route path="reports" element={<Reports />} />
        <Route path="demo" element={<Demo />} />
        <Route path="about" element={<About />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
