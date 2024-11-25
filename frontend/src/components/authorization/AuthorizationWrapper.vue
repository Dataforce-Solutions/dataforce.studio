<template>
  <div class="wrapper">
    <div class="body">
      <div class="content">
        <div class="headings">
          <h1 class="main-title">{{ title }}</h1>
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
            <span class="service-label">{{ service.label }}</span>
            <img :src="service.icon" alt="" width="24" height="24" class="icon" />
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
  background-color: var(--color-card-background);
  border-radius: 16px;
  max-width: 1360px;
  margin: 0 auto;
  overflow: hidden;
  box-shadow: var(--card-shadow);
}

.body {
  padding: 48px 64px;
}

.content {
  max-width: 399px;
  width: 100%;
  margin: 0 auto;
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

.main-title {
  font-weight: 600;
}

.sub-title {
  color: var(--color-text-muted);
  font-size: 16px;
}

.form-wrapper {
  margin-bottom: 24px;
}

.line {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  align-items: center;
  line-height: 1;
  margin-bottom: 24px;
  color: var(--color-text-muted);

  &::before,
  &::after {
    content: '';
    height: 1px;
    background-color: var(--color-divider-border);
  }
}

.services {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 32px;
}

.service-label {
  font-weight: 500;
}

.icon {
  width: 24px;
  height: 24px;
  object-fit: contain;
}

.footer {
  text-align: center;
  color: var(--color-text-muted);
}

.img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

@media (max-width: 992px) {
  .wrapper {
    max-width: 527px;
    display: block;
  }

  img {
    display: none;
  }
}

@media (max-width: 768px) {
  .body {
    padding: 30px;
  }
}
</style>
