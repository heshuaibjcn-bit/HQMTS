import { describe, it, expect } from 'vitest'
import { cn, formatCurrency, formatPercent, formatDate, formatTime } from '../utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'active')).toBe('base active')
  })

  it('deduplicates tailwind classes', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })
})

describe('formatCurrency', () => {
  it('formats positive values', () => {
    const result = formatCurrency(1234.56)
    expect(result).toContain('1,234.56')
  })

  it('formats negative values', () => {
    const result = formatCurrency(-500)
    expect(result).toContain('-')
    expect(result).toContain('500')
  })

  it('formats zero', () => {
    const result = formatCurrency(0)
    expect(result).toContain('0.00')
  })
})

describe('formatPercent', () => {
  it('formats positive with plus sign', () => {
    expect(formatPercent(0.05)).toBe('+5.00%')
  })

  it('formats negative', () => {
    expect(formatPercent(-0.03)).toBe('-3.00%')
  })

  it('formats zero', () => {
    expect(formatPercent(0)).toBe('+0.00%')
  })
})

describe('formatDate', () => {
  it('formats ISO string to localized date', () => {
    const result = formatDate('2026-04-18T14:30:00Z')
    expect(result).toBeTruthy()
    expect(result.length).toBeGreaterThan(0)
  })
})

describe('formatTime', () => {
  it('formats ISO string to time', () => {
    const result = formatTime('2026-04-18T14:30:45Z')
    expect(result).toBeTruthy()
  })
})
