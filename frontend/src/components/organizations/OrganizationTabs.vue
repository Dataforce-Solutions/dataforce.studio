<template>
  <Tabs value="0">
    <TabList :pt="tabsListPT">
      <Tab value="0" class="tab"><Users :size="14" />Members</Tab>
      <Tab value="1" class="tab"><Orbit :size="14" />Orbits</Tab>
      <Tab value="2" class="tab"><FolderDot :size="14" />Registry</Tab>
    </TabList>
    <TabPanels style="padding-left: 0; padding-right: 0">
      <TabPanel value="0">
        <OrganizationMembers></OrganizationMembers>
      </TabPanel>
      <TabPanel value="1">
        <OrganizationOrbits></OrganizationOrbits>
      </TabPanel>
      <TabPanel value="2">
        <OrganizationRegistry></OrganizationRegistry>
      </TabPanel>
    </TabPanels>
  </Tabs>
</template>

<script setup lang="ts">
import { Tabs, TabList, Tab, TabPanels, TabPanel } from 'primevue'
import { Users, Orbit, FolderDot } from 'lucide-vue-next'
import OrganizationMembers from './OrganizationMembers.vue'
import OrganizationOrbits from './OrganizationOrbits.vue'
import OrganizationRegistry from './registry/OrganizationRegistry.vue'

const tabsListPT = {
  tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
}
</script>

<style scoped>
.tab {
  border: none;
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
