import { NodeTypeEnum, type PromptNode } from '@/components/prompt-fusion/interfaces'
import { Position } from '@vue-flow/core'
import { v4 as uuidv4 } from 'uuid'

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

export const getInputNode = (fields?: string[]): PromptNode => {
  return {
    id: uuidv4(),
    type: 'custom',
    data: {
      label: 'Input',
      icon: 'input',
      iconColor: 'var(--p-primary-color)',
      fields: fields
        ? fields.map((field) => ({
            id: uuidv4(),
            value: field,
            handlePosition: Position.Right,
            variant: 'input',
          }))
        : [{ id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'input' }],
      showMenu: false,
      type: NodeTypeEnum.input,
    },
    position: { x: 20, y: 20 },
    selected: false,
  }
}

export const getOutputNode = (fields?: string[]): PromptNode => {
  return {
    id: uuidv4(),
    type: 'custom',
    data: {
      label: 'Output',
      icon: 'output',
      iconColor: 'var(--p-primary-color)',
      fields: fields
        ? fields.map((field) => ({
            id: uuidv4(),
            value: field,
            handlePosition: Position.Left,
            variant: 'output',
          }))
        : [{ id: uuidv4(), value: '', handlePosition: Position.Left, variant: 'output' }],
      showMenu: false,
      type: NodeTypeEnum.output,
    },
    position: { x: 20, y: 20 },
    selected: false,
  }
}

export const getInitialNodes = (inputFields?: string[], outputFields?: string[]) => {
  const inputNode = structuredClone(getInputNode(inputFields))
  const outputNode = structuredClone(getOutputNode(outputFields))
  inputNode.position = { x: 100, y: 200 }
  outputNode.position = { x: 1000, y: 200 }
  return [inputNode, outputNode]
}

export const initialNodes: PromptNode[] = getInitialNodes()
