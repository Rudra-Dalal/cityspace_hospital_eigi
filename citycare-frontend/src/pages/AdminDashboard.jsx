import { useEffect, useState } from 'react'
import { api, formatApiDetail } from '../api/client'

// ─── Tiny reusable components ────────────────────────────────────────────────

function StatCard({ label, value, color = 'clinic' }) {
  return (
    <div className={`card-surface flex flex-col gap-1 border-l-4 border-${color}-500`}>
      <p className="text-sm text-clinic-600">{label}</p>
      <p className="text-3xl font-bold text-clinic-900">{value ?? '—'}</p>
    </div>
  )
}

function Badge({ status }) {
  const map = {
    active:   'bg-green-100 text-green-800',
    inactive: 'bg-red-100   text-red-800',
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${map[status] ?? 'bg-gray-100 text-gray-700'}`}>
      {status}
    </span>
  )
}

// ─── Hospital Modal ───────────────────────────────────────────────────────────

function HospitalModal({ hospital, onClose, onSave }) {
  const isEdit = !!hospital?.id
  const [form, setForm] = useState({
    name:          hospital?.name          ?? '',
    address:       hospital?.address       ?? '',
    city:          hospital?.city          ?? '',
    state:         hospital?.state         ?? '',
    contact_phone: hospital?.contact_phone ?? '',
    contact_email: hospital?.contact_email ?? '',
    status:        hospital?.status        ?? 'active',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (isEdit) {
        await api.adminUpdateHospital(hospital.id, form)
      } else {
        await api.adminCreateHospital(form)
      }
      onSave()
    } catch (err) {
      setError(formatApiDetail(err.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="card-surface w-full max-w-lg">
        <h2 className="font-display text-xl font-bold text-clinic-900 mb-4">
          {isEdit ? 'Edit Hospital' : 'Add Hospital'}
        </h2>
        {error && <div className="error-banner mb-4">{error}</div>}
        <form onSubmit={submit} className="space-y-3">
          {[
            ['name',          'Hospital Name'],
            ['address',       'Address'],
            ['city',          'City'],
            ['state',         'State'],
            ['contact_phone', 'Contact Phone'],
            ['contact_email', 'Contact Email'],
          ].map(([k, label]) => (
            <div key={k}>
              <label className="block text-sm font-medium text-clinic-700 mb-1">{label}</label>
              <input
                className="input-field"
                value={form[k]}
                onChange={set(k)}
                required
              />
            </div>
          ))}
          {isEdit && (
            <div>
              <label className="block text-sm font-medium text-clinic-700 mb-1">Status</label>
              <select className="input-field" value={form.status} onChange={set('status')}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
          )}
          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Saving…' : 'Save'}
            </button>
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Create User Modal ────────────────────────────────────────────────────────

function UserModal({ hospitals, onClose, onSave }) {
  const [role,    setRole]    = useState('hospital_manager')
  const [form,    setForm]    = useState({ first_name:'', last_name:'', email:'', mobile:'+91', password:'', hospital_id:'' })
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (role === 'hospital_manager') await api.adminCreateManager(form)
      else                              await api.adminCreateDoctor(form)
      onSave()
    } catch (err) {
      setError(formatApiDetail(err.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="card-surface w-full max-w-lg">
        <h2 className="font-display text-xl font-bold text-clinic-900 mb-4">Create User</h2>
        {error && <div className="error-banner mb-4">{error}</div>}
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-clinic-700 mb-1">Role</label>
            <select className="input-field" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="hospital_manager">Hospital Manager</option>
              <option value="doctor">Doctor</option>
            </select>
          </div>
          {[
            ['first_name', 'First Name'],
            ['last_name',  'Last Name'],
            ['email',      'Email'],
            ['mobile',     'Mobile (+91…)'],
            ['password',   'Password'],
          ].map(([k, label]) => (
            <div key={k}>
              <label className="block text-sm font-medium text-clinic-700 mb-1">{label}</label>
              <input
                className="input-field"
                type={k === 'password' ? 'password' : 'text'}
                value={form[k]}
                onChange={set(k)}
                required
              />
            </div>
          ))}
          <div>
            <label className="block text-sm font-medium text-clinic-700 mb-1">Hospital</label>
            <select className="input-field" value={form.hospital_id} onChange={set('hospital_id')} required>
              <option value="">Select hospital…</option>
              {hospitals.map((h) => (
                <option key={h.id} value={h.id}>{h.name} — {h.city}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Creating…' : 'Create'}
            </button>
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AdminDashboard({ tab: initialTab = 'hospitals' }) {
  const [tab,         setTab]         = useState(initialTab)
  const [hospitals,   setHospitals]   = useState([])
  const [users,       setUsers]       = useState([])
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState('')
  const [modal,       setModal]       = useState(null) // 'hospital' | 'edit-hospital' | 'user'
  const [editTarget,  setEditTarget]  = useState(null)

  async function loadHospitals() {
    setLoading(true)
    try {
      setHospitals(await api.adminListHospitals())
    } catch (err) {
      setError(formatApiDetail(err.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  async function loadUsers() {
    setLoading(true)
    try {
      setUsers(await api.adminListUsers())
    } catch (err) {
      setError(formatApiDetail(err.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHospitals()
    loadUsers()
  }, [])

  const activeHospitals = hospitals.filter((h) => h.status === 'active').length
  const totalDoctors    = users.filter((u) => u.role === 'doctor').length
  const totalManagers   = users.filter((u) => u.role === 'hospital_manager').length
  const totalCustomers  = users.filter((u) => u.role === 'customer' || u.role === 'patient').length

  return (
    <div className="page-wrap py-8">
      <div className="mb-6">
        <h1 className="font-display text-3xl font-bold text-clinic-900">Super Admin Dashboard</h1>
        <p className="text-clinic-600 mt-1">Manage hospitals, staff, and platform settings.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Hospitals"  value={hospitals.length} />
        <StatCard label="Active Hospitals" value={activeHospitals}  color="green" />
        <StatCard label="Doctors"          value={totalDoctors}     color="blue" />
        <StatCard label="Customers"        value={totalCustomers}   color="purple" />
      </div>

      {error && <div className="error-banner mb-4">{error}</div>}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-clinic-200 mb-6">
        {['hospitals', 'users'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition capitalize ${
              tab === t
                ? 'border-clinic-600 text-clinic-900'
                : 'border-transparent text-clinic-500 hover:text-clinic-700'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Hospitals Tab */}
      {tab === 'hospitals' && (
        <div>
          <div className="flex justify-end mb-4">
            <button className="btn-primary" onClick={() => { setEditTarget(null); setModal('hospital') }}>
              + Add Hospital
            </button>
          </div>
          {loading ? (
            <p className="text-clinic-600">Loading…</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-clinic-200 text-left text-clinic-600">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">City</th>
                    <th className="py-2 pr-4">Contact</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {hospitals.map((h) => (
                    <tr key={h.id} className="border-b border-clinic-100 hover:bg-clinic-50">
                      <td className="py-2 pr-4 font-medium text-clinic-900">{h.name}</td>
                      <td className="py-2 pr-4 text-clinic-600">{h.city}, {h.state}</td>
                      <td className="py-2 pr-4 text-clinic-600">{h.contact_email}</td>
                      <td className="py-2 pr-4"><Badge status={h.status} /></td>
                      <td className="py-2">
                        <button
                          className="text-clinic-600 hover:text-clinic-900 text-xs font-medium underline"
                          onClick={() => { setEditTarget(h); setModal('hospital') }}
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                  {hospitals.length === 0 && (
                    <tr><td colSpan={5} className="py-6 text-center text-clinic-400">No hospitals yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Users Tab */}
      {tab === 'users' && (
        <div>
          <div className="flex justify-end mb-4">
            <button className="btn-primary" onClick={() => setModal('user')}>
              + Add User
            </button>
          </div>
          {loading ? (
            <p className="text-clinic-600">Loading…</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-clinic-200 text-left text-clinic-600">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Email</th>
                    <th className="py-2 pr-4">Role</th>
                    <th className="py-2 pr-4">Hospital</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-clinic-100 hover:bg-clinic-50">
                      <td className="py-2 pr-4 font-medium text-clinic-900">
                        {u.first_name} {u.last_name}
                      </td>
                      <td className="py-2 pr-4 text-clinic-600">{u.email}</td>
                      <td className="py-2 pr-4">
                        <span className="capitalize text-xs font-semibold bg-clinic-100 text-clinic-700 px-2 py-0.5 rounded-full">
                          {u.role.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-clinic-600 text-xs font-mono">
                        {u.hospital_id ? u.hospital_id.slice(-6) : '—'}
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr><td colSpan={4} className="py-6 text-center text-clinic-400">No users yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      {modal === 'hospital' && (
        <HospitalModal
          hospital={editTarget}
          onClose={() => setModal(null)}
          onSave={() => { setModal(null); loadHospitals() }}
        />
      )}
      {modal === 'user' && (
        <UserModal
          hospitals={hospitals.filter((h) => h.status === 'active')}
          onClose={() => setModal(null)}
          onSave={() => { setModal(null); loadUsers() }}
        />
      )}
    </div>
  )
}
