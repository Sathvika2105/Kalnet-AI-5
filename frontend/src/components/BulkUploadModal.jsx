import { useState, useRef } from 'react'
import api from '../api/client'
import { Upload, X, FileText, AlertCircle, CheckCircle, Loader2, AlertTriangle } from 'lucide-react'

const COLUMN_ALIASES = {
  name: ['name', 'full name', 'full_name', 'first name', 'first_name', 'contact name', 'contact_name', 'prospect'],
  email: ['email', 'e-mail', 'mail', 'email address', 'email_address', 'email id', 'e-mail id'],
  company: ['company', 'company name', 'company_name', 'organization', 'organisation', 'org', 'business', 'business name', 'business_name', 'account', 'account name'],
  tier: ['tier', 'level', 'priority', 'segment', 'tier level'],
  subject_line: ['subject line', 'subject', 'subject_line', 'email subject', 'topic', 'email topic'],
}

function findColumnIndex(headers, key) {
  const aliases = COLUMN_ALIASES[key]
  for (let i = 0; i < headers.length; i++) {
    const h = headers[i].replace(/^"|"$/g, '').trim().toLowerCase()
    if (aliases.some(a => h === a)) return i
  }
  return -1
}

function parseRowsFromParts(lines, delimiter) {
  if (lines.length === 0) return []
  const partsList = lines.map(l => {
    return l.split(delimiter).map(p => p.trim().replace(/^"|"$/g, ''))
  })

  const headerIdx = {}
  const first = partsList[0]
  for (const key of Object.keys(COLUMN_ALIASES)) {
    const idx = findColumnIndex(first, key)
    if (idx !== -1) headerIdx[key] = idx
  }

  const hasHeaders = Object.keys(headerIdx).length >= 2
  const startRow = hasHeaders ? 1 : 0

  const rows = []
  for (let i = startRow; i < partsList.length; i++) {
    const parts = partsList[i]
    if (parts.length < 2) continue
    let name, email
    if (hasHeaders) {
      name = (parts[headerIdx.name] || '').trim()
      email = (parts[headerIdx.email] || '').trim()
    } else {
      name = (parts[0] || '').trim()
      email = (parts[1] || '').trim()
    }
    if (!name || !email || !email.includes('@')) continue
    const company = hasHeaders ? (parts[headerIdx.company] || '').trim() : (parts[2] || '').trim()
    const tierRaw = hasHeaders ? (parts[headerIdx.tier] || '1').trim() : (parts[3] || '1').trim()
    const subject_line = hasHeaders ? (parts[headerIdx.subject_line] || '').trim() : (parts[4] || '').trim()
    rows.push({ name, email, company, tier: parseInt(tierRaw) || 1, subject_line })
  }
  return rows
}

function parseCSV(text) {
  return parseRowsFromParts(text.split('\n').map(l => l.trim()).filter(Boolean), /,(?=(?:[^"]*"[^"]*")*[^"]*$)/)
}

function parsePasted(text) {
  return parseRowsFromParts(text.split('\n').map(l => l.trim()).filter(Boolean), /[\t,]/)
}

export default function BulkUploadModal({ isOpen, onClose, onSuccess }) {
  const [tab, setTab] = useState('csv')
  const [file, setFile] = useState(null)
  const [pasteText, setPasteText] = useState('')
  const [parsedRows, setParsedRows] = useState([])
  const [step, setStep] = useState('input')
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [skipped, setSkipped] = useState(0)
  const fileRef = useRef(null)

  if (!isOpen) return null

  const reset = () => {
    setTab('csv')
    setFile(null)
    setPasteText('')
    setParsedRows([])
    setStep('input')
    setUploading(false)
    setResult(null)
    setSkipped(0)
  }

  const handleFileChange = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    const reader = new FileReader()
    reader.onload = (ev) => {
      const rows = parseCSV(ev.target?.result || '')
      setParsedRows(rows)
      setStep('preview')
    }
    reader.readAsText(f)
  }

  const handleParsePaste = () => {
    const rows = parsePasted(pasteText)
    setParsedRows(rows)
    setStep('preview')
  }

  const handleUpload = async () => {
    if (parsedRows.length === 0) return
    setUploading(true)
    setResult(null)
    setSkipped(0)
    try {
      const res = await api.post('/leads/bulk', parsedRows)
      setSkipped(res.data.skipped || 0)
      setResult({ success: true, message: res.data.message })
      setTimeout(() => {
        reset()
        onClose()
        onSuccess()
      }, 1500)
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Upload failed'
      setResult({ success: false, message: detail })
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-card-bg border border-card-border rounded-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-6 border-b border-card-border">
          <div className="flex items-center gap-3">
            <Upload size={20} className="text-blue-400" />
            <h2 className="text-xl font-bold text-white">Bulk Upload Leads</h2>
          </div>
          <button onClick={() => { reset(); onClose() }} className="text-slate-400 hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>

        {step === 'input' && (
          <div className="p-6 space-y-6">
            <div className="flex gap-2">
              <button
                onClick={() => setTab('csv')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === 'csv' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
              >
                <FileText size={16} className="inline mr-2" />
                CSV File
              </button>
              <button
                onClick={() => setTab('paste')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === 'paste' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
              >
                Paste Data
              </button>
            </div>

            {tab === 'csv' ? (
              <div className="border-2 border-dashed border-slate-600 rounded-xl p-10 text-center hover:border-blue-500/50 transition-colors cursor-pointer" onClick={() => fileRef.current?.click()}>
                <Upload size={40} className="mx-auto text-slate-500 mb-4" />
                <p className="text-slate-300 font-medium">
                  {file ? file.name : 'Click to select a CSV file'}
                </p>
                <p className="text-slate-500 text-sm mt-1">Columns: name, email, company, tier, subject_line</p>
                <input ref={fileRef} type="file" accept=".csv" onChange={handleFileChange} className="hidden" />
              </div>
            ) : (
              <div className="space-y-4">
                <textarea
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  placeholder="name, email, company, tier, subject_line&#10;John, john@example.com, Acme Inc, 1, Let&#39;s connect&#10;Jane, jane@test.com, Corp Ltd, 2, Quick question"
                  rows={8}
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm font-mono resize-none focus:border-blue-500 outline-none"
                />
                <button
                  onClick={handleParsePaste}
                  disabled={!pasteText.trim()}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
                >
                  Preview Leads
                </button>
              </div>
            )}
          </div>
        )}

        {step === 'preview' && (
          <div className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-400">
                <span className="text-white font-semibold">{parsedRows.length}</span> leads parsed
              </p>
              <button onClick={() => setStep('input')} className="text-sm text-blue-400 hover:text-blue-300 transition-colors">
                Change input
              </button>
            </div>

            {parsedRows.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-card-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-800 text-slate-400 text-left">
                      <th className="px-4 py-3 font-medium">Name</th>
                      <th className="px-4 py-3 font-medium">Email</th>
                      <th className="px-4 py-3 font-medium">Company</th>
                      <th className="px-4 py-3 font-medium">Tier</th>
                      <th className="px-4 py-3 font-medium">Subject Line</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-card-border">
                    {parsedRows.map((row, i) => (
                      <tr key={row.email || i} className="text-slate-300 hover:bg-slate-800/50">
                        <td className="px-4 py-2.5">{row.name}</td>
                        <td className="px-4 py-2.5 text-slate-400">{row.email}</td>
                        <td className="px-4 py-2.5">{row.company}</td>
                        <td className="px-4 py-2.5">{row.tier}</td>
                        <td className="px-4 py-2.5 text-slate-400 max-w-[200px] truncate">{row.subject_line}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4 text-yellow-400 text-sm flex items-center gap-2">
                <AlertCircle size={16} />
                No valid rows found. Make sure each row has at least a name and email.
              </div>
            )}

            {result && (
              <div className={`p-3 rounded-lg flex items-center gap-2 text-sm ${
                result.success
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
              }`}>
                {result.success ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                {result.message}
              </div>
            )}

            {skipped > 0 && (
              <div className="p-3 rounded-lg flex items-center gap-2 text-sm bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                <AlertTriangle size={16} />
                {skipped} lead{skipped !== 1 ? 's' : ''} skipped — email already exists in the sheet.
              </div>
            )}

            <div className="flex gap-3 justify-end pt-2">
              <button
                onClick={() => { reset(); onClose() }}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg text-sm transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={parsedRows.length === 0 || uploading}
                className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload size={16} />
                    Upload {parsedRows.length} Lead{parsedRows.length !== 1 ? 's' : ''}
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
