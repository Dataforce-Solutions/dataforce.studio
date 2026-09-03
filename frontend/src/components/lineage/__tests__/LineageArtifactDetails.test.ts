import { shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { LineageNodeData } from '../lineage.interface'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import LineageArtifactDetails from '../LineageArtifactDetails.vue'

const route = vi.hoisted(() => ({
  params: {
    organizationId: 'org',
    id: 'orbit',
    collectionId: 'models',
    artifactId: 'focal',
  },
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, useRoute: () => route }
})

const DialogStub = defineComponent({
  name: 'UiDialogRight',
  props: { visible: Boolean },
  template: '<div v-if="visible"><slot></slot><footer><slot name="footer"></slot></footer></div>',
})

const RouterLinkStub = defineComponent({
  name: 'RouterLink',
  props: { to: { type: Object, required: true } },
  template: '<a><slot /></a>',
})

function artifact(): Artifact {
  return {
    id: 'dataset',
    name: 'Training data',
    collection_id: 'datasets',
    collection_name: 'Datasets',
    type: ArtifactTypeEnum.dataset,
    status: ArtifactStatusEnum.uploaded,
    created_at: '2026-01-02T03:04:05Z',
    deployments: [],
    tracks: [],
  } as unknown as Artifact
}

function nodeData(variant: LineageNodeData['variant'] = 'default'): LineageNodeData {
  return {
    nodeId: 'node-dataset',
    artifactId: 'dataset',
    collectionId: 'datasets',
    collectionName: 'Datasets',
    isDeleted: false,
    type: ArtifactTypeEnum.dataset,
    title: 'Training data',
    variant,
    data: artifact(),
    deployments: [],
    tracks: [],
  }
}

function mountDetails(data: LineageNodeData) {
  return shallowMount(LineageArtifactDetails, {
    props: { data, visible: true },
    global: {
      stubs: {
        UiDialogRight: DialogStub,
        RouterLink: RouterLinkStub,
        Tag: { template: '<span><slot /></span>' },
      },
    },
  })
}

describe('LineageArtifactDetails', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders live artifact metadata and cross-collection navigation', () => {
    const wrapper = mountDetails(nodeData())

    expect(wrapper.text()).toContain('Dataset')
    expect(wrapper.text()).toContain('Training data')
    expect(wrapper.text()).toContain('Datasets')
    expect(wrapper.text()).toContain('Created')
    expect(wrapper.text()).toContain('Uploaded')
    expect(wrapper.text()).toContain('Open artifact')
    expect(wrapper.text()).toContain('Focus lineage')

    const links = wrapper.findAllComponents(RouterLinkStub)
    expect(links.map((link) => link.props('to'))).toEqual([
      {
        name: 'artifact',
        params: {
          organizationId: 'org',
          id: 'orbit',
          collectionId: 'datasets',
          artifactId: 'dataset',
        },
      },
      {
        name: 'lineage',
        params: {
          organizationId: 'org',
          id: 'orbit',
          collectionId: 'datasets',
          artifactId: 'dataset',
        },
      },
    ])
  })

  it('hides Focus lineage for the focal artifact', () => {
    const wrapper = mountDetails(nodeData('main'))

    expect(wrapper.text()).toContain('Open artifact')
    expect(wrapper.text()).not.toContain('Focus lineage')
    expect(wrapper.findAllComponents(RouterLinkStub)).toHaveLength(1)
  })
})
