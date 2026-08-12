import { describe, expect, it } from 'vitest'

import {
  branches,
  cellsByBranch,
  churnFixture,
  mainCells,
  trainModel,
} from '@/flow/workbench/fixtures'
import { formatBytes, formatCost, formatMetric } from '@/flow/workbench/model/format'
import {
  primaryOutput,
  producerOf,
  rankOf,
  sliceEdges,
  topologicalOrder,
} from '@/flow/workbench/model/registry'

describe('primary output ranking', () => {
  it('opens a training cell on the experiment, not the model or a config dump', () => {
    expect(primaryOutput(trainModel)?.name).toBe('run')
  })

  it('honors an explicit primaryOutput over the ranking', () => {
    const cell = { ...trainModel, primaryOutput: 'curves' }
    expect(primaryOutput(cell)?.name).toBe('curves')
  })

  it('falls back to the ranking when the declared primary is missing', () => {
    const cell = { ...trainModel, primaryOutput: 'nonexistent' }
    expect(primaryOutput(cell)?.name).toBe('run')
  })

  it('ranks experiment above eval above plot above frame', () => {
    expect(rankOf('experiment')).toBeLessThan(rankOf('eval'))
    expect(rankOf('eval')).toBeLessThan(rankOf('plot'))
    expect(rankOf('plot')).toBeLessThan(rankOf('frame'))
  })
})

describe('slice wiring', () => {
  it('derives edges from declared consumes references', () => {
    const edges = sliceEdges(mainCells)
    expect(edges).toContainEqual({ from: 'features', to: 'train_model' })
    expect(edges).toContainEqual({ from: 'train_model', to: 'holdout_eval' })
  })

  it('orders dependencies before consumers with authoring-step tiebreak', () => {
    const order = topologicalOrder(mainCells).map((cell) => cell.slug)
    expect(order.indexOf('features')).toBeLessThan(order.indexOf('train_model'))
    expect(order.indexOf('train_model')).toBeLessThan(order.indexOf('holdout_eval'))
    expect(order.indexOf('holdout_eval')).toBeLessThan(order.indexOf('roc_curve'))
    // Deterministic: same input, same order.
    expect(topologicalOrder(mainCells).map((cell) => cell.slug)).toEqual(order)
  })

  it('parses producers from reference strings', () => {
    expect(producerOf('features.train_split')).toBe('features')
    expect(producerOf('train_split')).toBe('train_split')
  })
})

describe('fixture integrity', () => {
  it('resolves every consumes reference within its branch slice', () => {
    for (const [branch, cells] of Object.entries(cellsByBranch)) {
      const slugs = new Set(cells.map((cell) => cell.slug))
      for (const cell of cells) {
        if (cell.flag) continue // deliberately dangling (did-you-mean specimen)
        for (const reference of cell.consumes) {
          expect(slugs.has(producerOf(reference)), `${branch}: ${cell.slug} → ${reference}`).toBe(
            true,
          )
        }
      }
    }
  })

  it('gives every branch a resolvable parent and every slice a branch record', () => {
    const names = new Set(branches.map((branch) => branch.name))
    for (const branch of branches) {
      if (branch.parent !== null) expect(names.has(branch.parent)).toBe(true)
    }
    for (const name of Object.keys(cellsByBranch)) expect(names.has(name)).toBe(true)
  })

  it('marks stale cells with a worded cause, and only stale cells', () => {
    for (const cells of Object.values(cellsByBranch)) {
      for (const cell of cells) {
        if (cell.status === 'stale') {
          expect(cell.stale?.cause, cell.slug).toBeTruthy()
          expect(cell.stale?.cause).not.toMatch(/^(definition-changed|deps-rewired)$/)
        }
        if (cell.status === 'unmaterialized') expect(cell.stale).toBeUndefined()
      }
    }
  })

  it('leaks no internal identifiers into user-facing strings', () => {
    const userFacing: string[] = []
    for (const cells of Object.values(cellsByBranch)) {
      for (const cell of cells) {
        userFacing.push(cell.slug, cell.doc, cell.stale?.cause ?? '', cell.provenance.intent)
      }
    }
    for (const entry of churnFixture.journal) userFacing.push(entry.intent, entry.summary)
    const blob = userFacing.join('\n')
    expect(blob).not.toMatch(/\buid\b/i)
    expect(blob).not.toMatch(/memo key/i)
    expect(blob).not.toMatch(/\b[0-9a-f]{12,}\b/i) // hash-looking tokens
    expect(blob).not.toMatch(/\b[0-7][0-9A-HJKMNP-TV-Z]{25}\b/) // ULIDs
  })
})

describe('formatters', () => {
  it('formats costs across magnitudes', () => {
    expect(formatCost(0.04)).toBe('<0.1s')
    expect(formatCost(9.8)).toBe('9.8s')
    expect(formatCost(312)).toBe('5m 12s')
    expect(formatCost(5400)).toBe('1h 30m')
  })

  it('formats bytes and metrics', () => {
    expect(formatBytes(890)).toBe('890 B')
    expect(formatBytes(14_680_064)).toBe('14.0 MB')
    expect(formatMetric(0.8412)).toBe('0.841')
    expect(formatMetric(84312)).toBe('84312')
  })
})
