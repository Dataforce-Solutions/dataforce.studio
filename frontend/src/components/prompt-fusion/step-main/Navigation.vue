<template>
  <div class="navigation">
    <d-button severity="secondary" @click="onBackClick">
      <arrow-left :size="14" />
      <span>Back</span>
    </d-button>
    <d-button asChild severity="secondary" v-slot="slotProps">
      <router-link :to="{ name: 'home' }" :class="slotProps.class"> Finish </router-link>
    </d-button>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'

type Emits = {
  goBack: []
}

const emit = defineEmits<Emits>()

const route = useRoute()
const router = useRouter()

function onBackClick() {
  if (route.params.mode === 'data-driven') {
    emit('goBack')
  } else {
    router.back()
  }
}
</script>

<style scoped>
.navigation {
  position: absolute;
  left: 16px;
  bottom: -15px;
  display: flex;
  gap: 16px;
  z-index: 2;
}
</style>
