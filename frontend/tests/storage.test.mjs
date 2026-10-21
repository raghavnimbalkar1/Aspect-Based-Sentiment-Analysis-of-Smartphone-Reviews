import assert from 'node:assert/strict'
import test from 'node:test'
import { readStored, writeStored } from '../src/storage.ts'

test('preferences round-trip through the requested storage', () => {
  const values = new Map()
  const storage = (kind) => ({
    getItem: (key) => values.get(`${kind}:${key}`) ?? null,
    setItem: (key, value) => values.set(`${kind}:${key}`, value),
  })
  assert.equal(readStored('draft', 'session', storage), null)
  assert.equal(writeStored('draft', 'Camera is good.', 'session', storage), true)
  assert.equal(readStored('draft', 'session', storage), 'Camera is good.')
  assert.equal(readStored('draft', 'local', storage), null)
})

test('blocked storage access does not stop rendering or a successful server save', () => {
  const blocked = () => { throw new DOMException('Storage blocked', 'SecurityError') }
  assert.equal(readStored('annotator', 'local', blocked), null)
  assert.equal(writeStored('annotator', 'Reviewer', 'local', blocked), false)
})

test('full browser storage does not turn preference persistence into a save failure', () => {
  const full = () => ({
    getItem: () => 'old preference',
    setItem: () => { throw new DOMException('Full', 'QuotaExceededError') },
  })
  assert.equal(writeStored('annotator', 'Reviewer', 'local', full), false)
  assert.equal(readStored('annotator', 'local', full), 'old preference')
})
