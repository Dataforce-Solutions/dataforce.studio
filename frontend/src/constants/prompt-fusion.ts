import { NodeTypeEnum, type PromptNode } from '@/components/prompt-fusion/interfaces'
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
        { id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'input' },
      ],
      showMenu: false,
      type: NodeTypeEnum.input,
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
        { id: uuidv4(), value: '', handlePosition: Position.Left, variant: 'output' },
        { id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'condition' },
        { id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'condition' },
      ],
      showMenu: true,
      hint: '',
      type: NodeTypeEnum.gate,
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
        { id: uuidv4(), value: '', handlePosition: Position.Left, variant: 'input' },
        { id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'output' },
      ],
      showMenu: true,
      hint: '',
      type: NodeTypeEnum.processor,
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
        { id: uuidv4(), value: '', handlePosition: Position.Left, variant: 'output' },
      ],
      showMenu: false,
      type: NodeTypeEnum.output,
    },
    position: { x: 1000, y: 200 },
    selected: false,
  },
]
