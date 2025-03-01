import type { PromptNode } from '@/components/prompt-fusion/interfaces'
import { Position } from '@vue-flow/core'
import { v4 as uuidv4 } from 'uuid';

export const initialNodes: PromptNode[] = [
  {
    id: uuidv4(),
    type: 'custom',
    data: {
      label: 'Input',
      icon: 'input',
      iconColor: 'var(--p-primary-color)',
      fields: [
        { id: uuidv4(), type: 'text', value: "long text that doesn't fit in this box", handlePosition: Position.Right, variant: 'input' },
      ],
      showMenu: false
    },
    position: { x: 100, y: 200 },
    selected: false,
  },
  {
    id: uuidv4(),
    type: 'custom',
    data: {
      label: 'Gate',
      icon: 'gate',
      iconColor: 'var(--p-badge-success-background)',
      fields: [
        { id: uuidv4(), type: 'text', value: 'short description', handlePosition: Position.Left, variant: 'output' },
        { id: uuidv4(), label: 'Condition 1', value: "long text that doesn't fit in this box", handlePosition: Position.Right, variant: 'condition' },
        { id: uuidv4(), label: 'Condition 2', value: "long text that doesn't fit in this box", handlePosition: Position.Right, variant: 'condition' },
      ],
      showMenu: true,
      hint: '',
    },
    position: { x: 400, y: 200 },
    selected: false,
  },
  {
    id: uuidv4(),
    type: 'custom',
    data: {
      label: 'Processor',
      icon: 'cpu',
      iconColor: 'var(--p-badge-warn-background)',
      fields: [
        { id: uuidv4(), type: 'text', value: 'short description', handlePosition: Position.Left, variant: 'input' },
        { id: uuidv4(), type: 'text', value: 'short description', handlePosition: Position.Right, variant: 'output' },
      ],
      showMenu: true,
      hint: '',
    },
    position: { x: 700, y: 200 },
    selected: false,
  },
  {
    id: uuidv4(),
    type: 'custom',
    data: {
      label: 'Output',
      icon: 'output',
      iconColor: 'var(--p-primary-color)',
      fields: [
        { id: uuidv4(), type: 'text', value: 'short description', handlePosition: Position.Left, variant: 'output' },
      ],
      showMenu: false
    },
    position: { x: 1000, y: 200 },
    selected: false,
  },
]
