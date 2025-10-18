<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { fetchUserGroup, submitLessonSummary } from '../services/api'

import group1 from '../assets/lesson/group1.json'
import group2 from '../assets/lesson/group2.json'
import group3 from '../assets/lesson/group3.json'
import group4 from '../assets/lesson/group4.json'

const lessons = {
  group1,
  group2,
  group3,
  group4,
}

const props = defineProps({
  userId: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['complete'])

const state = reactive({
  loading: false,
  error: '',
  lesson: null,
  group: '',
  messages: [],
  partIndex: 0,
  stepIndex: 0,
  introductionShown: false,
  pendingStep: null,
  lastUserId: '',
  lessonStartedAt: 0,
  awaitingContinueAfterFeedback: false,
  interactionLocked: false,
})

const aiTyping = ref(false)
const showStep = ref(true)

const selections = reactive({
  single: null,
  multi: [],
})

const lessonResults = reactive([])
let messageCounter = 0
const chatBodyRef = ref(null)

const avatarUrl = computed(() => {
  if (!state.lesson || !state.lesson.icon) {
    return defaultAvatarUrl()
  }
  return resolveTeacherAvatar(state.lesson.icon)
})

const hasUserId = computed(() => Boolean(props.userId))

const pendingPictureUrl = computed(() => {
  if (!state.pendingStep || !state.pendingStep.picture) {
    return ''
  }
  return resolveLessonPicture(state.pendingStep.picture)
})

const canContinue = computed(() => {
  if (state.awaitingContinueAfterFeedback) {
    return true
  }

  const step = state.pendingStep
  if (!step) {
    return false
  }

  if (aiTyping.value) {
    return false
  }

  if (step.type === 'intro' || step.type === 'chat') {
    return true
  }

  if (step.type === 'single_choice') {
    return selections.single !== null
  }

  if (step.type === 'multi_choice') {
    return Array.isArray(selections.multi) && selections.multi.length > 0
  }

  return true
})

const showContinueButton = computed(() => {
  if (state.loading || !hasUserId.value) {
    return false
  }
  return Boolean(state.pendingStep) || state.awaitingContinueAfterFeedback
})

watch(
  () => props.userId,
  (value) => {
    if (value && value !== state.lastUserId) {
      initializeLesson(value)
    }
  },
  { immediate: true }
)

watch(
  () => state.messages.length,
  async () => {
    await smoothScrollToBottom()
  }
)

watch(
  () => state.pendingStep,
  async (step) => {
    if (step) {
      state.awaitingContinueAfterFeedback = false
      state.interactionLocked = false
      markLessonStarted()
    }
    await smoothScrollToBottom()
  }
)

watch(aiTyping, async (value) => {
  if (value) {
    await smoothScrollToBottom()
  }
})

async function smoothScrollToBottom(retry = 3) {
  await nextTick()
  await new Promise(r => requestAnimationFrame(r))

  // 改成滚动 html（即 document.documentElement）
  const container = document.documentElement
  if (!container) return

  if (container._scrollTimer) {
    cancelAnimationFrame(container._scrollTimer)
    container._scrollTimer = null
  }

  const target = container.scrollHeight
  const start = container.scrollTop
  const distance = target - start
  const duration = 400
  const startTime = performance.now()

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3)
  }

  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1)
    container.scrollTop = start + distance * easeOutCubic(progress)
    if (progress < 1) {
      container._scrollTimer = requestAnimationFrame(step)
    } else {
      container._scrollTimer = null
    }
  }

  requestAnimationFrame(step)

  // 内容可能还在加载，重试几次
  if (retry > 0) {
    setTimeout(() => {
      const atBottom =
        Math.abs(container.scrollHeight - container.scrollTop - container.clientHeight) < 2
      if (!atBottom) smoothScrollToBottom(retry - 1)
    }, 500)
  }
}

function resetSelections() {
  selections.single = null
  selections.multi = []
}

function markLessonStarted() {
  if (!state.lessonStartedAt) {
    state.lessonStartedAt = Date.now()
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function randomDelay(min = 500, max = 3000) {
  return Math.random() * (max - min) + min
}

async function initializeLesson(userId) {
  if (state.loading) {
    return
  }

  state.loading = true
  state.error = ''
  state.lesson = null
  state.group = ''
  state.messages = []
  state.partIndex = 0
  state.stepIndex = 0
  state.introductionShown = false
  state.pendingStep = null
  state.lessonStartedAt = 0
  state.awaitingContinueAfterFeedback = false
  state.interactionLocked = false
  aiTyping.value = false
  resetSelections()
  lessonResults.splice(0, lessonResults.length)

  try {
    const response = await fetchUserGroup(userId)
    const group = response?.group
    if (!group || !lessons[group]) {
      throw new Error('未找到对应的课程内容')
    }
    console.log(group)

    state.lastUserId = userId
    state.group = group
    state.lesson = lessons[group]
    state.introductionShown = !state.lesson.introduction
    state.pendingStep = resolveCurrentStep()
    if (state.pendingStep) {
      markLessonStarted()
    }
  } catch (error) {
    console.error('加载课程失败', error)
    state.error = error?.message || '加载课程失败，请稍后重试'
  } finally {
    state.loading = false
  }
}

function resolveCurrentStep() {
  if (!state.lesson) {
    return null
  }

  if (!state.introductionShown && state.lesson.introduction) {
    return {
      type: 'intro',
      content: state.lesson.introduction,
    }
  }

  const currentPart = state.lesson.parts?.[state.partIndex]
  if (!currentPart) {
    return null
  }

  return currentPart.steps?.[state.stepIndex] ?? null
}

function formatChoiceLabel(choice, index) {
  const letter = String.fromCharCode(65 + index)
  if (typeof choice === 'string') {
    return `${letter}. ${choice}`
  }
  return `${letter}. ${String(choice)}`
}

async function sendAiMessage(content, options = {}) {
  if (!content) {
    return
  }
  await nextTick()
  const avatar = avatarUrl.value
  state.messages.push({
    id: `ai-${messageCounter++}`,
    role: 'ai',
    content,
    pictureUrl: options.pictureUrl ?? '',
    avatar,
  })
  if (!options.dontShowContinue) {addUserMessage('继续')}
  await nextTick()
}

function addUserMessage(content) {
  state.messages.push({
    id: `user-${messageCounter++}`,
    role: 'user',
    content,
  })
}

function selectSingle(index) {
  if (state.interactionLocked) {
    return
  }
  selections.single = index
}

function toggleMulti(index) {
  if (state.interactionLocked) {
    return
  }
  const position = selections.multi.indexOf(index)
  if (position === -1) {
    selections.multi.push(index)
  } else {
    selections.multi.splice(position, 1)
  }
}

function handleRetry() {
  if (!props.userId) {
    return
  }
  initializeLesson(props.userId)
}

function compareAnswers(userAnswers, correctAnswers) {
  if (!Array.isArray(correctAnswers) || correctAnswers.length === 0) {
    return false
  }
  const normalizedUser = [...new Set(userAnswers.map((ans) => ans.toUpperCase()))]
  const normalizedCorrect = [...new Set(correctAnswers.map((ans) => ans.toUpperCase()))]
  if (normalizedUser.length !== normalizedCorrect.length) {
    return false
  }
  normalizedUser.sort()
  normalizedCorrect.sort()
  return normalizedUser.every((ans, idx) => ans === normalizedCorrect[idx])
}

function resolveLessonPicture(name) {
  try {
    return new URL(`../assets/lesson-pic/${name}.png`, import.meta.url).href
  } catch (error) {
    console.warn('未找到课程图片资源', name)
    return ''
  }
}

function resolveTeacherAvatar(name) {
  try {
    return new URL(`../assets/teacher/${name}.png`, import.meta.url).href
  } catch (error) {
    console.warn('未找到头像资源', name)
    return defaultAvatarUrl()
  }
}

function defaultAvatarUrl() {
  return new URL('../assets/teacher/gpt.png', import.meta.url).href
}

function buildUserSelectionSummary(step, selectedIndexes) {
  if (!Array.isArray(selectedIndexes) || selectedIndexes.length === 0) {
    return '暂未选择答案'
  }
  const labels = selectedIndexes.map((index) => formatChoiceLabel(step.choices[index], index))
  return `我选择了：${labels.join('、')}`
}

function recordLessonResult(step, selectedIndexes, isCorrect) {
  lessonResults.push({
    part: state.partIndex + 1,
    step: state.stepIndex + 1,
    question: step.question ?? '',
    selected_answers: selectedIndexes.map((index) => formatChoiceLabel(step.choices[index], index)),
    is_correct: isCorrect,
  })
}

async function advanceToNextStep() {
  if (!state.lesson) {
    await finishLesson()
    return
  }

  if (!state.introductionShown && state.lesson.introduction) {
    state.introductionShown = true
  } else {
    const currentPart = state.lesson.parts?.[state.partIndex]
    if (currentPart && state.stepIndex < currentPart.steps.length - 1) {
      state.stepIndex += 1
    } else {
      state.stepIndex = 0
      state.partIndex += 1
    }
  }

  resetSelections()
  const nextStep = resolveCurrentStep()
  if (nextStep) {
    aiTyping.value = true
    const delayMs = randomDelay()
    state.pendingStep = nextStep
    await sleep(delayMs)
    aiTyping.value = false
  } else {
    await finishLesson()
  }
}

function snapshotLessonResults() {
  return lessonResults.map((entry) => ({
    part: entry.part,
    step: entry.step,
    question: entry.question,
    selected_answers: [...entry.selected_answers],
    is_correct: entry.is_correct,
  }))
}

async function finishLesson() {
  state.pendingStep = null
  state.awaitingContinueAfterFeedback = false
  state.interactionLocked = false
  aiTyping.value = false
  const durationMs = state.lessonStartedAt ? Math.max(0, Date.now() - state.lessonStartedAt) : 0
  const resultsSnapshot = snapshotLessonResults()
  let submissionStatus = 'success'

  if (props.userId) {
    try {
      await submitLessonSummary({
        userid: props.userId,
        group: state.group,
        duration_ms: durationMs,
        completed_at: new Date().toISOString(),
        results: resultsSnapshot,
      })
    } catch (error) {
      submissionStatus = 'error'
      console.error('提交课程总结失败', error)
    }
  }

  emit('complete', {
    group: state.group,
    results: resultsSnapshot,
    durationMs,
    submissionStatus,
  })
}

async function handleContinue() {
  if (state.awaitingContinueAfterFeedback) {
    state.awaitingContinueAfterFeedback = false
    state.interactionLocked = false
    showStep.value = true
    addUserMessage('继续')
    await advanceToNextStep()
    return
  }

  const step = state.pendingStep
  if (!step) {
    await finishLesson()
    return
  }

  if (step.type === 'intro' || step.type === 'chat') {
    await sendAiMessage(step.content, {
      pictureUrl: step.picture ? resolveLessonPicture(step.picture) : '',
    })
    await advanceToNextStep()
    return
  }
  else if (step.type === 'single_choice' || step.type === 'multi_choice') {
    state.interactionLocked = true
    await sendAiMessage(step.question, {dontShowContinue: true})
    
    const selectedIndexes =
      step.type === 'single_choice' ? [selections.single] : [...selections.multi]

    const userMessage = buildUserSelectionSummary(step, selectedIndexes)
    addUserMessage(userMessage)

    const userAnswers = selectedIndexes.map((index) => String.fromCharCode(65 + index))
    const correctAnswers = Array.isArray(step.correct_answer) ? step.correct_answer : []
    const isCorrect = compareAnswers(userAnswers, correctAnswers)

    recordLessonResult(step, selectedIndexes, isCorrect)

    const feedback = step.response ? (isCorrect ? step.response.correct : step.response.incorrect) : ''
    if (feedback) {
      aiTyping.value = true
      const delayMs = randomDelay()
      await sleep(delayMs)
      aiTyping.value = false
      showStep.value = false
      await sendAiMessage(feedback, {dontShowContinue: true})
    }

    state.awaitingContinueAfterFeedback = true
    return
  }

  await advanceToNextStep()
}
</script>

<template>
  <div class="lesson-stage">
    <div class="chat-timeline" ref="chatBodyRef">
      <div v-if="state.loading" class="status-card">正在为你准备课程…</div>
      <div v-else-if="!hasUserId" class="status-card">正在等待用户信息…</div>
      <div v-else-if="state.error" class="status-card error">
        <p>{{ state.error }}</p>
        <button type="button" class="primary-button" @click="handleRetry">重试</button>
      </div>
      <template v-else>
        <div v-for="message in state.messages" :key="message.id" :class="['chat-message', message.role]">
          <template v-if="message.role === 'ai'">
            <img :src="message.avatar" alt="AI Avatar" class="avatar" />
            <div class="message-bubble">
              <p class="message-content">{{ message.content }}</p>
              <img v-if="message.pictureUrl" :src="message.pictureUrl" alt="lesson visual" class="message-picture" />
            </div>
          </template>
          <template v-else>
            <div class="message-bubble">
              <p class="message-content">{{ message.content }}</p>
            </div>
          </template>
        </div>

        <div v-if="state.pendingStep && !aiTyping && showStep" :class="['chat-message', 'ai', 'pending']">
          <img :src="avatarUrl" alt="AI Avatar" class="avatar" />
          <div class="message-bubble interactive">
            <p class="message-content">{{ state.pendingStep.content || state.pendingStep.question }}</p>
            <img v-if="pendingPictureUrl" :src="pendingPictureUrl" alt="lesson visual" class="message-picture" />

            <div v-if="state.pendingStep.type === 'single_choice'" class="choice-group">
              <button
                v-for="(choice, index) in state.pendingStep.choices"
                :key="`single-choice-${index}`"
                type="button"
                :class="['choice-chip', { active: selections.single === index, locked: state.interactionLocked }]"
                :disabled="state.interactionLocked"
                @click="selectSingle(index)"
              >
                {{ formatChoiceLabel(choice, index) }}
              </button>
            </div>

            <div v-else-if="state.pendingStep.type === 'multi_choice'" class="choice-group">
              <button
                v-for="(choice, index) in state.pendingStep.choices"
                :key="`multi-choice-${index}`"
                type="button"
                :class="['choice-chip', { active: selections.multi.includes(index), locked: state.interactionLocked }]"
                :disabled="state.interactionLocked"
                @click="toggleMulti(index)"
              >
                {{ formatChoiceLabel(choice, index) }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="aiTyping" class="chat-message ai typing">
          <img :src="avatarUrl" alt="AI Avatar" class="avatar" />
          <div class="message-bubble typing">
            <div class="typing-dots">
              <span
                v-for="index in 3"
                :key="`typing-dot-${index}`"
                class="typing-dot"
                :style="{ animationDelay: `${(index - 1) * 0.15}s` }"
              ></span>
            </div>
          </div>
        </div>
      </template>
    </div>
    <div v-if="showContinueButton" class="continue-bar">
      <button type="button" class="primary-button" :disabled="!canContinue" @click="handleContinue">
        继续
      </button>
    </div>
  </div>
</template>

<style scoped>
.lesson-stage {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  width: 100%;
  height: 100%;
}

.chat-timeline {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.chat-message {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
}

.chat-message.user {
  justify-content: flex-end;
}

.chat-message.user .message-bubble {
  background: linear-gradient(135deg, #3b82f6, #60a5fa);
  color: #ffffff;
  border-top-right-radius: 0.3rem;
  border-top-left-radius: 1rem;
}

.chat-message.user .message-content {
  color: #ffffff;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
  object-fit: cover;
  box-shadow: 0 4px 12px -6px rgba(15, 23, 42, 0.5);
}

.message-bubble {
  background: #ffffff;
  border-radius: 1rem;
  padding: 0.85rem 1.1rem;
  box-shadow: 0 10px 28px -18px rgba(15, 23, 42, 0.35);
  max-width: min(100%, 520px);
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.message-content {
  margin: 0;
  color: #1f2937;
  line-height: 1.6;
  font-size: 0.96rem;
  white-space: pre-line;
}

.message-picture {
  width: 100%;
  max-width: 100%;
  border-radius: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  object-fit: contain;
}

.status-card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 1rem;
  padding: 1.5rem;
  box-shadow: 0 12px 28px -20px rgba(15, 23, 42, 0.35);
  align-self: center;
  max-width: min(100%, 520px);
}

.chat-message.ai.pending .message-bubble,
.chat-message.ai.typing .message-bubble,
.message-bubble.interactive {
  width: 100%;
}

.message-bubble.interactive {
  background: rgba(241, 245, 249, 0.95);
}

.message-bubble.typing {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 48px;
}

.typing-dots {
  display: inline-flex;
  gap: 0.35rem;
}

.typing-dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.35);
  animation: typingBounce 1.1s infinite ease-in-out;
}

.chat-message.ai.typing .typing-dot {
  background: rgba(37, 99, 235, 0.55);
}

@keyframes typingBounce {
  0%,
  80%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

.status-card.error {
  border-color: rgba(239, 68, 68, 0.45);
  color: #b91c1c;
}

.choice-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.choice-chip {
  padding: 0.6rem 1rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: #ffffff;
  color: #1f2937;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.choice-chip:hover {
  border-color: rgba(59, 130, 246, 0.6);
  background: rgba(219, 234, 254, 0.55);
}

.choice-chip.active {
  border-color: rgba(37, 99, 235, 0.8);
  background: rgba(191, 219, 254, 0.65);
  color: #1d4ed8;
  font-weight: 600;
}

.choice-chip:disabled,
.choice-chip.locked {
  cursor: default;
  opacity: 0.75;
  box-shadow: none;
}

.primary-button {
  align-self: flex-end;
  padding: 0.75rem 1.75rem;
  border-radius: 0.9rem;
  border: none;
  background: linear-gradient(135deg, #6366f1, #22d3ee);
  color: #ffffff;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}

.primary-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
  box-shadow: none;
  transform: none;
}

.primary-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 22px -12px rgba(99, 102, 241, 0.55);
}

.continue-bar {
  display: flex;
  justify-content: flex-end;
  padding: 0.5rem 0;
}

@media (max-width: 720px) {
  .lesson-stage {
    gap: 1rem;
  }

  .message-bubble {
    max-width: 100%;
  }

  .choice-group {
    justify-content: flex-start;
  }

  .primary-button {
    width: 100%;
    justify-content: center;
  }

  .continue-bar {
    justify-content: center;
  }
}
</style>
