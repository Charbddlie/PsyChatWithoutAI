<script setup>
const props = defineProps({
  headline: {
    type: String,
    default: '',
  },
  description: {
    type: String,
    default: '',
  },
  primaryActionLabel: {
    type: String,
    default: '继续',
  },
  showAction: {
    type: Boolean,
    default: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  loadingLabel: {
    type: String,
    default: '处理中…',
  },
})

const emit = defineEmits(['complete'])

function triggerNext() {
  if (props.loading) {
    return
  }
  emit('complete')
}
</script>

<template>
  <div class="static-stage">
    <div class="static-card">
      <h2 v-if="headline" class="static-headline">{{ headline }}</h2>
      <p v-if="description" class="static-description">{{ description }}</p>
      <button
        v-if="showAction"
        type="button"
        class="static-button"
        :disabled="loading"
        @click="triggerNext"
      >
        {{ loading ? loadingLabel : primaryActionLabel }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.static-stage {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2rem 1.5rem;
  min-height: 420px;
}

.static-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 1.5rem;
  padding: clamp(2rem, 5vw, 3rem);
  border-radius: 1.25rem;
  background: #ffffff;
  border: 1px solid rgba(148, 163, 184, 0.35);
  box-shadow: 0 24px 50px -32px rgba(15, 23, 42, 0.4);
  color: #1f2937;
  max-width: 540px;
}

.static-headline {
  font-size: clamp(1.4rem, 3vw, 1.8rem);
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.static-description {
  font-size: 1rem;
  line-height: 1.7;
  margin: 0;
  color: #475569;
  white-space: pre-line;
}

.static-button {
  padding: 0.85rem 2.5rem;
  border-radius: 1rem;
  border: none;
  background: linear-gradient(135deg, #22c55e, #38bdf8);
  color: #ffffff;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}

.static-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 30px -18px rgba(34, 197, 94, 0.55);
}

.static-button:active {
  transform: translateY(0);
}

.static-button[disabled] {
  opacity: 0.7;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}
</style>
