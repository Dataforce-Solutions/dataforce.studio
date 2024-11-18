<template>
  <div class="wrapper">
    <div class="body">
      <div class="content">
        <div class="headings">
          <h1 class="title">{{ title }}</h1>
          <h3 class="sub-title">{{ subTitle }}</h3>
        </div>
        <div class="form-wrapper">
          <slot name="form"></slot>
        </div>

        <span class="line">or</span>
        <div class="services">
          <d-button
            v-for="service in services"
            :key="service.id"
            variant="outlined"
            @click="() => service.action()"
          >
            <span>{{ service.label }}</span>
            <img :src="service.icon" alt="" />
          </d-button>
        </div>
        <div class="footer">
          <slot name="footer"></slot>
        </div>
      </div>
    </div>
    <img :src="image" alt="dataforce.studio" class="img" />
  </div>
</template>

<script setup lang="ts">
import type { TAuthorizationWrapperProps } from './types'

defineProps<TAuthorizationWrapperProps>()
</script>

<style scoped>
.wrapper {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  background-color: var(--color-background);
  border-radius: 16px;
  padding: 48px;
  max-width: 1360px;
  margin: 0 auto;
}
.content {
  max-width: 528px;
  padding: 64px;
}
.form-wrapper {
  margin-bottom: 20px;
}
.headings {
  margin-bottom: 32px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.line {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  align-items: center;
  line-height: 1;
  margin-bottom: 20px;
  &::before,
  &::after {
    content: '';
    height: 2px;
    background-color: #dce4ef;
  }
}
.services {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 32px;
}
.footer {
  text-align: center;
}
.img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
