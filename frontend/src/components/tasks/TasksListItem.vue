<template>
  <d-card>
    <template #header>
      <div class="header">
        <img alt="user header" :src="task.icon" />
        <div v-tooltip="task.tooltipData">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
          >
            <g clip-path="url(#clip0_29_311)">
              <path
                d="M10 18.3327C14.6024 18.3327 18.3333 14.6017 18.3333 9.99935C18.3333 5.39698 14.6024 1.66602 10 1.66602C5.39763 1.66602 1.66667 5.39698 1.66667 9.99935C1.66667 14.6017 5.39763 18.3327 10 18.3327Z"
                stroke="#5B6676"
                stroke-width="1.66667"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M7.575 7.50047C7.77092 6.94353 8.15762 6.4739 8.66663 6.17475C9.17563 5.87561 9.77408 5.76626 10.356 5.86607C10.9379 5.96588 11.4657 6.26841 11.8459 6.72008C12.2261 7.17175 12.4342 7.74341 12.4333 8.33381C12.4333 10.0005 9.93333 10.8338 9.93333 10.8338"
                stroke="#5B6676"
                stroke-width="1.66667"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M10 14.166H10.0083"
                stroke="#5B6676"
                stroke-width="1.66667"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </g>
            <defs>
              <clipPath id="clip0_29_311">
                <rect width="20" height="20" fill="white" />
              </clipPath>
            </defs>
          </svg>
        </div>
      </div>
    </template>
    <template #title>{{ task.title }}</template>
    <template #content>
      <p class="m-0">
        {{ task.description }}
      </p>
    </template>
    <template v-if="task.linkName" #footer>
      <d-button :label="task.btnText" />
    </template>
  </d-card>
</template>

<script setup lang="ts">
import type { ITaskData } from './types'

type TProps = {
  task: ITaskData
}

defineProps<TProps>()
</script>

<style scoped>
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px;
}
</style>
