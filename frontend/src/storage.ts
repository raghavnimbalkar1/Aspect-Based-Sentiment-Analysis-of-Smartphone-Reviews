type StorageKind = 'local' | 'session'
type StorageSource = (kind: StorageKind) => Pick<Storage, 'getItem' | 'setItem'>

// Preferences are optional. A browser policy or full quota must not block an
// API-confirmed save, or prevent the dashboard from mounting.
const source: StorageSource = (kind) => window[kind === 'local' ? 'localStorage' : 'sessionStorage']

export function readStored(key: string, kind: StorageKind = 'local', getStorage = source) {
  try {
    return getStorage(kind).getItem(key)
  } catch {
    return null
  }
}

export function writeStored(
  key: string,
  value: string,
  kind: StorageKind = 'local',
  getStorage = source,
) {
  try {
    getStorage(kind).setItem(key, value)
    return true
  } catch {
    return false
  }
}
