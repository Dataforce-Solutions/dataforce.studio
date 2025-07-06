<template>
  <Tabs :value="$route.name as string">
    <TabList :pt="tabsListPT">
      <Tab
        :pt="tabPT"
        v-for="tab in items"
        :key="tab.label"
        :value="tab.routeName"
        class="tab"
        :disabled="tab.disabled"
        @click="$router.push({ name: tab.routeName })"
      >
        <component :is="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
      </Tab>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import { Tabs, TabList, Tab, type TabPassThroughOptions } from 'primevue'
import { Folders, Rocket } from 'lucide-vue-next'

const tabsListPT = {
  tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
}

const tabPT: TabPassThroughOptions = {}

const items = [
  {
    label: 'Registry',
    routeName: 'orbit-registry',
    icon: Folders,
    disabled: false,
  },
  {
    label: 'Deployments',
    routeName: 'orbit-deployments',
    icon: Rocket,
    disabled: true,
  },
]
</script>

<style scoped>
.tab {
  border: none;
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
