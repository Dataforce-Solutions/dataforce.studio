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
        <p class="m-0">
          At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium
          voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati
          cupiditate non provident, similique sunt in culpa qui officia deserunt mollitia animi, id
          est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio. Nam
          libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit quo minus.
        </p>
      </TabPanel>
    </TabPanels>
  </Tabs>
</template>

<script setup lang="ts">
import { Tabs, TabList, Tab, TabPanels, TabPanel } from 'primevue'
import { Users, Orbit, FolderDot } from 'lucide-vue-next'
import OrganizationMembers from './OrganizationMembers.vue'
import OrganizationOrbits from './OrganizationOrbits.vue'

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
