<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  formKey: {
    type: String,
    default: '',
  },
  config: {
    type: Object,
    required: true,
  },
  submitting: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['complete'])

const fieldValues = reactive({})
const choiceInputs = reactive({})

function initializeState() {
  Object.keys(fieldValues).forEach((key) => delete fieldValues[key])
  Object.keys(choiceInputs).forEach((key) => delete choiceInputs[key])

  props.config.fields.forEach((field, idx) => {
    const fieldKey = String(idx)
    if (field.type === 'multi_choice') {
      fieldValues[fieldKey] = []
      choiceInputs[fieldKey] = {}
    } else if (field.type === 'single_choice') {
      fieldValues[fieldKey] = null
      choiceInputs[fieldKey] = {}
    } else {
      fieldValues[fieldKey] = ''
    }
  })
}

watch(
  () => props.config,
  () => {
    initializeState()
  },
  { immediate: true, deep: true }
)

const displayIntroduction = computed(() => {
  const intro = props.config.introduction
  if (intro === null || intro === undefined) {
    return ''
  }
  return String(intro).trim()
})

function choiceNeedsInput(choiceText) {
  return /\{\{(text|num(?::[^}]+)?)\}\}/.test(choiceText)
}

function flattenTemplate(template, value) {
  if (!template) {
    return value ?? ''
  }
  return template.replace(/\{\{(text|num(?::[^}]+)?)\}\}/g, value ?? '')
}

function takeLabel(field, choiceIndex) {
  const labelArray = field.label
  if (Array.isArray(labelArray) && labelArray[choiceIndex] !== undefined) {
    return String(labelArray[choiceIndex])
  }
  const choice = field.choices?.[choiceIndex]
  return typeof choice === 'string' ? choice : String(choice)
}

function parseNumberBounds(display) {
  const match = /\{\{num:(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)\}\}/.exec(display)
  if (!match) {
    return {}
  }
  return {
    min: Number(match[1]),
    max: Number(match[2]),
  }
}

function getDisplaySuffix(display) {
  if (!display) {
    return ''
  }
  return display.replace(/\{\{(text|num(?::[^}]+)?)\}\}/g, '').trim()
}

function textInputClasses(field) {
  const classes = ['q-input']
  if (field.size === 'small') {
    classes.push('q-input-short')
  }
  if (field.size === 'medium') {
    classes.push('q-input-medium')
  }
  return classes.join(' ')
}

function fieldPlaceholder(field) {
  if (!field.display) {
    return '请填写'
  }
  const sanitized = field.display.replace(/\{\{(text|num(?::[^}]+)?)\}\}/g, '').trim()
  return sanitized || '请填写'
}

function resolveTextValue(value) {
  if (value === null || value === undefined) {
    return ''
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : ''
  }
  return String(value).trim()
}

function isNumericChoice(field) {
  if (!Array.isArray(field.choices) || field.choices.length === 0) {
    return false
  }
  return field.choices.every((choice) => {
    if (typeof choice === 'number') {
      return Number.isFinite(choice)
    }
    if (typeof choice === 'string') {
      return /^\s*-?\d+(?:\.\d+)?\s*$/.test(choice)
    }
    return false
  })
}

function computeSequentialScale(field) {
  if (!Array.isArray(field.choices) || field.choices.length < 2) {
    return null
  }
  const normalized = []
  for (let idx = 0; idx < field.choices.length; idx += 1) {
    const choice = field.choices[idx]
    let numberValue
    if (typeof choice === 'number') {
      numberValue = choice
    } else if (typeof choice === 'string') {
      const trimmed = choice.trim()
      if (!/^\d+(?:\.\d+)?$/.test(trimmed)) {
        return null
      }
      numberValue = Number(trimmed)
    } else {
      return null
    }
    if (!Number.isFinite(numberValue)) {
      return null
    }
    normalized.push(numberValue)
  }

  for (let idx = 0; idx < normalized.length; idx += 1) {
    if (normalized[idx] !== idx + 1) {
      return null
    }
  }

  return normalized.map((value, idx) => ({
    index: idx,
    value,
    display:
      Array.isArray(field.label) && field.label[idx] !== undefined
        ? String(field.label[idx])
        : String(value),
  }))
}

const sequentialScales = computed(() => props.config.fields.map((field) => computeSequentialScale(field)))

function selectScale(fieldIdx, choiceIdx) {
  fieldValues[String(fieldIdx)] = choiceIdx
}

function handleCheckboxToggle(fieldKey, optionIndex, checked) {
  const current = fieldValues[fieldKey]
  if (!Array.isArray(current)) {
    return
  }
  if (checked) {
    if (!current.includes(optionIndex)) {
      current.push(optionIndex)
    }
  } else {
    const next = current.filter((idx) => idx !== optionIndex)
    fieldValues[fieldKey] = next
  }
}

function formatFieldAnswer(field, fieldKey) {
  if (field.type === 'text') {
    return resolveTextValue(fieldValues[fieldKey])
  }
  if (field.type === 'single_choice') {
    const selectedIndex = fieldValues[fieldKey]
    if (selectedIndex === null || selectedIndex === undefined) {
      return ''
    }
    const template = takeLabel(field, selectedIndex)
    const extraValue = choiceInputs[fieldKey]?.[selectedIndex] ?? ''
    if (choiceNeedsInput(template)) {
      return flattenTemplate(template, extraValue)
    }
    const rawChoice = takeLabel(field, selectedIndex)
    return choiceNeedsInput(rawChoice) ? flattenTemplate(rawChoice, extraValue) : rawChoice
  }
  if (field.type === 'multi_choice') {
    const selections = fieldValues[fieldKey] ?? []
    return selections.map((choiceIndex) => {
      const template = takeLabel(field, choiceIndex)
      const extraValue = choiceInputs[fieldKey]?.[choiceIndex] ?? ''
      return choiceNeedsInput(template) ? flattenTemplate(template, extraValue) : template
    })
  }
  return ''
}

function fieldCompleted(field, fieldKey) {
  if (field.type === 'text') {
    const value = fieldValues[fieldKey]
    if (value === null || value === undefined) {
      return false
    }
    if (typeof value === 'number') {
      return Number.isFinite(value)
    }
    return Boolean(String(value).trim())
  }
  if (field.type === 'single_choice') {
    const selectedIndex = fieldValues[fieldKey]
    if (selectedIndex === null || selectedIndex === undefined) {
      return false
    }
    const template = takeLabel(field, selectedIndex)
    if (choiceNeedsInput(template)) {
      return Boolean(String(choiceInputs[fieldKey]?.[selectedIndex] ?? '').trim())
    }
    return true
  }
  if (field.type === 'multi_choice') {
    const selections = fieldValues[fieldKey]
    if (!Array.isArray(selections) || selections.length === 0) {
      return false
    }
    return selections.every((choiceIndex) => {
      const template = takeLabel(field, choiceIndex)
      if (!choiceNeedsInput(template)) {
        return true
      }
      return Boolean(String(choiceInputs[fieldKey]?.[choiceIndex] ?? '').trim())
    })
  }
  return true
}

function onSubmit() {
  const incomplete = props.config.fields.some((field, idx) => !fieldCompleted(field, String(idx)))
  if (incomplete) {
    window.alert('请完整填写所有问题后再提交。')
    return
  }

  const answers = props.config.fields.map((field, idx) => {
    const fieldKey = String(idx)
    const selected = formatFieldAnswer(field, fieldKey)
    return {
      index: field.index ?? idx + 1,
      question: field.question ?? '',
      selected_choice: selected,
    }
  })

  emit('complete', {
    form_key: props.formKey || props.config.form_key || '',
    answers,
  })
}
</script>

<template>
  <div class="form-stage">
    <div v-if="displayIntroduction" class="form-intro">{{ displayIntroduction }}</div>
    <form class="form-content" @submit.prevent="onSubmit">
      <div
        v-for="(field, idx) in config.fields"
        :key="`${formKey}-${idx}`"
        class="form-field"
      >
        <div class="field-question">
          <span v-if="field.index" class="question-index">{{ field.index }}.</span>
          <span>{{ field.question }}</span>
        </div>
        <div class="field-body">
          <div v-if="field.type === 'text'" class="field-text-input">
            <template v-if="field.size === 'large'">
              <textarea
                v-model="fieldValues[String(idx)]"
                class="q-input q-input-large"
                :placeholder="fieldPlaceholder(field)"
                rows="6"
              ></textarea>
            </template>
            <template v-else>
              <div class="text-input-wrapper">
                <input
                  v-if="/\{\{num/.test(field.display ?? '')"
                  v-model.number="fieldValues[String(idx)]"
                  :class="textInputClasses(field)"
                  type="number"
                  :min="parseNumberBounds(field.display).min"
                  :max="parseNumberBounds(field.display).max"
                  :placeholder="fieldPlaceholder(field)"
                />
                <input
                  v-else
                  v-model="fieldValues[String(idx)]"
                  :class="textInputClasses(field)"
                  type="text"
                  :placeholder="fieldPlaceholder(field)"
                />
                <span v-if="getDisplaySuffix(field.display)" class="input-suffix">
                  {{ getDisplaySuffix(field.display) }}
                </span>
              </div>
            </template>
          </div>

          <div v-else-if="field.type === 'single_choice'" class="field-choice">
            <div
              v-if="sequentialScales[idx]"
              class="choice-scale"
              role="radiogroup"
              :aria-label="field.question"
            >
              <div class="scale-track"></div>
              <button
                v-for="scale in sequentialScales[idx]"
                :key="`scale-${idx}-${scale.index}`"
                type="button"
                class="scale-point"
                :class="{ active: fieldValues[String(idx)] === scale.index }"
                role="radio"
                :aria-checked="fieldValues[String(idx)] === scale.index"
                @click="selectScale(idx, scale.index)"
                @keydown.enter.prevent="selectScale(idx, scale.index)"
                @keydown.space.prevent="selectScale(idx, scale.index)"
              >
                <span class="point-dot"></span>
                <span class="point-label">{{ scale.display }}</span>
              </button>
            </div>
            <div
              v-else
              :class="['field-choice-list', { 'choice-inline': isNumericChoice(field) }]"
            >
              <label
                v-for="(choice, choiceIndex) in field.choices"
                :key="`single-${idx}-${choiceIndex}`"
                class="choice-item"
              >
                <input
                  type="radio"
                  :name="`single-${formKey}-${idx}`"
                  :value="choiceIndex"
                  v-model.number="fieldValues[String(idx)]"
                />
                <span class="choice-label">
                  <span>{{ typeof choice === 'string' ? choice.replace(/\{\{(text|num(?::[^}]+)?)\}\}/g, '').trim() : choice }}</span>
                  <input
                    v-if="choiceNeedsInput(String(choice))"
                    v-model="choiceInputs[String(idx)][choiceIndex]"
                    type="text"
                    class="choice-inline-input"
                    placeholder="请补充"
                  />
                </span>
              </label>
            </div>
          </div>

          <div
            v-else-if="field.type === 'multi_choice'"
            :class="['field-choice-list', { 'choice-inline': isNumericChoice(field) }]"
          >
            <label
              v-for="(choice, choiceIndex) in field.choices"
              :key="`multi-${idx}-${choiceIndex}`"
              class="choice-item"
            >
              <input
                type="checkbox"
                :value="choiceIndex"
                :checked="fieldValues[String(idx)].includes(choiceIndex)"
                @change="(event) => handleCheckboxToggle(String(idx), choiceIndex, event.target.checked)"
              />
              <span class="choice-label">
                <span>{{ typeof choice === 'string' ? choice.replace(/\{\{(text|num(?::[^}]+)?)\}\}/g, '').trim() : choice }}</span>
                <input
                  v-if="choiceNeedsInput(String(choice))"
                  v-model="choiceInputs[String(idx)][choiceIndex]"
                  type="text"
                  class="choice-inline-input"
                  placeholder="请补充"
                />
              </span>
            </label>
          </div>
        </div>
      </div>

      <div class="form-actions">
        <button type="submit" class="submit-button" :disabled="submitting">
          {{ submitting ? '提交中…' : '提交' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.form-stage {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-intro {
  padding: 1rem 1.25rem;
  border-radius: 0.9rem;
  background: rgba(248, 250, 252, 0.85);
  color: #1f2937;
  line-height: 1.6;
  font-size: 0.95rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  white-space: pre-line;
}

.form-content {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1.5rem;
  border-radius: 1rem;
  background: #ffffff;
  border: 1px solid rgba(148, 163, 184, 0.35);
  box-shadow: 0 12px 24px -20px rgba(15, 23, 42, 0.4);
}

.field-question {
  font-weight: 600;
  color: #0f172a;
  display: flex;
  gap: 0.5rem;
  align-items: baseline;
  line-height: 1.6;
}

.question-index {
  color: #3b82f6;
}

.field-body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.field-text-input {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.field-choice {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.text-input-wrapper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.q-input {
  flex: 1;
  padding: 0.625rem 0.75rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.45);
  background: #ffffff;
  color: #0f172a;
  font-size: 0.95rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.q-input:focus {
  outline: none;
  border-color: rgba(59, 130, 246, 0.8);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.q-input-large {
  min-height: 160px;
  resize: vertical;
}

.q-input-short {
  max-width: 140px;
}

.q-input-medium {
  max-width: 320px;
}

.input-suffix {
  color: #64748b;
  font-size: 0.9rem;
}

.field-choice-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.choice-inline {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.choice-inline .choice-item {
  flex: 0 1 calc(20% - 0.6rem);
  min-width: 80px;
  justify-content: center;
  align-items: center;
}

.choice-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 0.9rem;
  border-radius: 0.85rem;
  background: rgba(248, 250, 252, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.4);
  color: #1f2937;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.choice-item:hover {
  border-color: rgba(59, 130, 246, 0.6);
  background: rgba(219, 234, 254, 0.6);
}

.choice-item input[type='radio'],
.choice-item input[type='checkbox'] {
  width: 18px;
  height: 18px;
  margin-top: 0;
  accent-color: #2563eb;
}

.choice-label {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
}

.choice-inline .choice-label {
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
}

.choice-inline-input {
  max-width: 240px;
  padding: 0.45rem 0.65rem;
  border-radius: 0.6rem;
  border: 1px solid rgba(148, 163, 184, 0.45);
  background: #ffffff;
  color: #0f172a;
  font-size: 0.9rem;
}

.choice-inline-input:focus {
  outline: none;
  border-color: rgba(59, 130, 246, 0.8);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
}

.choice-scale {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  padding: 1.25rem 0.5rem 0.4rem;
}

.scale-track {
  position: absolute;
  left: 1.25rem;
  right: 1.25rem;
  top: 1.8rem;
  height: 2px;
  background: rgba(148, 163, 184, 0.45);
  pointer-events: none;
}

.scale-point {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #1f2937;
  font-size: 0.9rem;
  padding: 0;
}

.scale-point:focus-visible {
  outline: none;
}

.scale-point:focus-visible .point-dot {
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2);
}

.scale-point.active .point-dot {
  background: #2563eb;
  border-color: #1d4ed8;
}

.scale-point.active .point-label {
  color: #1d4ed8;
  font-weight: 600;
}

.point-dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(148, 163, 184, 0.65);
  background: #ffffff;
  transition: all 0.2s ease;
}

.scale-point:hover .point-dot {
  border-color: rgba(59, 130, 246, 0.75);
}

.point-label {
  font-size: 0.85rem;
  color: #475569;
  transition: color 0.2s ease;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 0.5rem;
}

.submit-button {
  padding: 0.75rem 1.75rem;
  border-radius: 0.9rem;
  border: none;
  background: linear-gradient(135deg, #3b82f6, #60a5fa);
  color: #ffffff;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}

.submit-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 20px -10px rgba(59, 130, 246, 0.55);
}

.submit-button:active {
  transform: translateY(0);
}

.submit-button[disabled] {
  cursor: not-allowed;
  opacity: 0.75;
  box-shadow: none;
  transform: none;
}

@media (max-width: 720px) {
  .form-field {
    padding: 1.2rem 1.1rem;
  }

  .choice-inline .choice-item {
    flex: 1 1 calc(33% - 0.6rem);
  }

  .choice-item {
    align-items: flex-start;
  }

  .choice-label {
    align-items: flex-start;
  }

  .scale-track {
    left: 1rem;
    right: 1rem;
  }
}
</style>
