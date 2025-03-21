import { NodeTypeEnum, type PromptNode } from '@/components/prompt-fusion/interfaces'
import { Position } from '@vue-flow/core'
import { v4 as uuidv4 } from 'uuid'

export const emptyInputNode: PromptNode = {
  id: uuidv4(),
  type: 'custom',
  data: {
    label: 'Input',
    icon: 'input',
    iconColor: 'var(--p-primary-color)',
    fields: [{ id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'input' }],
    showMenu: false,
    type: NodeTypeEnum.input,
  },
  position: { x: 20, y: 20 },
  selected: false,
}

export const emptyGateNode: PromptNode = {
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
  position: { x: 20, y: 20 },
  selected: false,
}

export const emptyProcessorNode: PromptNode = {
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
  position: { x: 20, y: 20 },
  selected: false,
}

export const emptyOutputNode: PromptNode = {
  id: uuidv4(),
  type: 'custom',
  data: {
    label: 'Output',
    icon: 'output',
    iconColor: 'var(--p-primary-color)',
    fields: [{ id: uuidv4(), value: '', handlePosition: Position.Left, variant: 'output' }],
    showMenu: false,
    type: NodeTypeEnum.output,
  },
  position: { x: 20, y: 20 },
  selected: false,
}

const getInitialNodes = () => {
  const inputNode = structuredClone(emptyInputNode)
  const outputNode = structuredClone(emptyOutputNode)
  inputNode.position = { x: 100, y: 200 }
  outputNode.position = { x: 1000, y: 200 }
  return [ inputNode, outputNode ]
}

export const initialNodes: PromptNode[] = getInitialNodes()
