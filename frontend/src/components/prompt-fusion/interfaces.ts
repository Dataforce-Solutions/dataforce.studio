import { Position, type Node } from '@vue-flow/core'
import { CaseUpper, Hash, Braces, CircleArrowDown, CircleArrowUp, Cpu, BetweenHorizonalStart } from 'lucide-vue-next'

export const PROMPT_FIELDS_ICONS = {
  text: CaseUpper,
  number: Hash,
  float: Hash,
  complex: Braces
}

export const PROMPT_NODES_ICONS = {
  input: CircleArrowDown,
  cpu: Cpu,
  gate: BetweenHorizonalStart,
  output: CircleArrowUp,
}

export interface PromptNode extends Node {
  type: 'custom'
  data: NodeData
  selected: boolean
}

export interface NodeData {
  label: string
  icon: keyof typeof PROMPT_NODES_ICONS
  iconColor: NodeIconColor
  fields: NodeField[]
  showMenu: boolean
  hint?: string
}

export interface NodeField {
  id: string
  value: string
  handlePosition: Position.Left | Position.Right
  variant: FieldVariant
  type?: keyof typeof PROMPT_FIELDS_ICONS
  variadic?: boolean
  label?: string
}

type FieldVariant = 'input' | 'output' | 'condition'

type NodeIconColor = 'var(--p-primary-color)' | 'var(--p-badge-warn-background)' | 'var(--p-badge-success-background)'
