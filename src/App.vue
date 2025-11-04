<script setup>
import { computed, reactive, ref, watch, nextTick } from 'vue'

import FormRenderer from './components/FormRenderer.vue'
import LessonRenderer from './components/LessonRenderer.vue'
import StaticStep from './components/StaticStep.vue'

import {
  registerUser,
  submitForm,
  checkExperimentCompletion,
  markExperimentComplete,
} from './services/api'

import pre1Info from './assets/forms/pre1-info.json'
import pre2Emotion from './assets/forms/pre2-emotion.json'
import pre3Background from './assets/forms/pre3-background_knowledge.json'
import pre4Anthropomorphism from './assets/forms/pre4-anthropomorphism.json'
import post1Personification from './assets/forms/post1-personification.json'
import post2Cogload from './assets/forms/post2-cogload.json'
import post3Emotion from './assets/forms/post3-emotion.json'
import post4Trust from './assets/forms/post4-trust.json'
import post5Like from './assets/forms/post5-like.json'
import post6Mem from './assets/forms/post6_1-mem.json'
import post6Migration from './assets/forms/post6_2-migration.json'

const componentRegistry = {
  static: StaticStep,
  form: FormRenderer,
  lesson: LessonRenderer,
}

function createFormStep(id, config) {
  return {
    id,
    type: 'form',
    formKey: config.form_key || id,
    config,
  }
}

const steps = [
  {
    id: 'intro',
    type: 'static',
    props: {
      headline: '亲爱的参与者：',
      description:
        '您好！感谢您参与本次学习研究。\n本研究旨在探索人工智能辅助学习的效果。您将通过与AI学习助手互动的方式，学习一个关于生物学的主题。整个过程大约需要25分钟。\n\n实验流程概览\n1) 前测（约5分钟）：填写一些基本信息和背景问卷\n2) 交互学习（约10分钟）：与AI学习助手一起学习新知识\n3) 学习评估（约10分钟）：完成学习效果测试和体验评价\n\n重要说明\n1) 请在整个过程中保持专注，认真对待每个环节\n2) 请根据您的真实感受和理解作答\n3) 如有任何疑问，请随时询问研究人员\n4) 您的所有回答将严格保密，仅用于学术研究\n\n参与权利\n您有权在任何时候退出实验，不会有任何不良后果\n\n准备好了吗？请点击“开始实验”进入第一阶段——前测。',
      primaryActionLabel: '开始实验',
    },
  },
  createFormStep('pre1-info', pre1Info),
  createFormStep('pre2-emotion', pre2Emotion),
  createFormStep('pre3-background', pre3Background),
  createFormStep('pre4-anthropomorphism', pre4Anthropomorphism),
  {
    id: 'lesson-intro',
    type: 'static',
    props: {
      headline: '欢迎进入学习阶段！',
      description:
        '学习内容\n接下来您将学习一个生物学主题：流感病毒如何入侵人体。这是一个既有趣又重要的科学话题，了解这个过程有助于我们更好地预防疾病。\n\n学习方式\n1) 您将与一个AI学习助手进行互动学习。AI助手会：\n2) 为您呈现学习材料（包括图文内容）\n3) 与您进行交流和互动\n4) 在适当时候提供小测试来帮助您巩固知识\n\n学习建议\n1) 主动参与：积极与AI助手互动，有疑问可以随时提出\n2) 认真学习：专心阅读材料，理解其中的科学原理\n3) 真实回应：根据您的真实感受与AI助手交流',
      primaryActionLabel: '进入学习',
    },
  },
  {
    id: 'lesson-session',
    type: 'lesson',
  },
  {
    id: 'post-intro',
    type: 'static',
    props: {
      headline: '恭喜您完成了与AI学习助手的互动学习！',
      description:
        '评估目的\n为了了解您的学习效果和体验感受，我们需要进行一些评估。\n\n重要提醒\n1) 请根据您刚才的学习内容和真实感受作答\n2) 请独立完成，不要查看学习材料\n3) 如果遇到不确定的问题，请选择您认为最合适的答案',
      primaryActionLabel: '开始评估',
    },
  },
  createFormStep('post1-personification', post1Personification),
  createFormStep('post2-cogload', post2Cogload),
  createFormStep('post3-emotion', post3Emotion),
  createFormStep('post4-trust', post4Trust),
  createFormStep('post5-like', post5Like),
  createFormStep('post6_1-mem', post6Mem),
  createFormStep('post6_2-migration', post6Migration),
  {
    id: 'complete',
    type: 'static',
    props: {
      headline: '实验完成',
      description: '恭喜完成了所有实验内容，感谢认真参与！',
      showAction: false,
    },
  },
]

const formSteps = steps.filter((entry) => entry.type === 'form')
const formIndexLookup = new Map(formSteps.map((entry, idx) => [entry.id, idx]))

const stepIndex = ref(0)
const responses = reactive({})
const userId = ref('')
const registering = ref(false)
const submittingStepId = ref(null)
const toast = reactive({ visible: false, message: '' })
const experimentCompleted = ref(false)
const completionChecked = ref(false)
const completionMarkInFlight = ref(false)
const completionErrorNotified = ref(false)

const currentStep = computed(() => steps[stepIndex.value] ?? null)
const currentComponent = computed(() => {
  const step = currentStep.value
  if (!step) {
    return null
  }
  return componentRegistry[step.type] || StaticStep
})

const currentProps = computed(() => {
  const step = currentStep.value
  if (!step) {
    return {}
  }
  if (step.type === 'form') {
    return {
      formKey: step.formKey,
      config: step.config,
      submitting: submittingStepId.value === step.id,
    }
  }
  if (step.type === 'lesson') {
    return {
      userId: userId.value,
    }
  }
  if (step.type === 'static') {
    return {
      ...(step.props || {}),
      loading: step.id === 'intro' ? registering.value : false,
    }
  }
  return step.props || {}
})

const formProgress = computed(() => {
  const step = currentStep.value
  if (!step || step.type !== 'form') {
    return null
  }
  const index = formIndexLookup.get(step.id) ?? 0
  return {
    current: index + 1,
    total: formSteps.length,
  }
})

function getCookie(name) {
  if (typeof document === 'undefined') {
    return ''
  }
  const cookieString = document.cookie || ''
  const segments = cookieString.split(';')
  for (const segment of segments) {
    const trimmed = segment.trim()
    if (trimmed.startsWith(`${name}=`)) {
      return decodeURIComponent(trimmed.slice(name.length + 1))
    }
  }
  return ''
}

function setCookie(name, value, days = 365) {
  if (typeof document === 'undefined') {
    return
  }
  const expires = new Date(Date.now() + days * 86400000).toUTCString()
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/`
}

function getStoredUserId() {
  return null
  // return getCookie('psychat_user_id')
}

function persistUserId(id) {
  if (!id) {
    return
  }
  setCookie('psychat_user_id', id)
}

function advanceStep() {
  if (stepIndex.value < steps.length - 1) {
    stepIndex.value += 1
  }
}

function skipToCompletion() {
  const targetIndex = steps.findIndex((entry) => entry.id === 'complete')
  if (targetIndex !== -1) {
    stepIndex.value = targetIndex
  }
}

async function attemptCompletionMark() {
  if (!userId.value || experimentCompleted.value || completionMarkInFlight.value) {
    return
  }
  completionMarkInFlight.value = true
  try {
    await markExperimentComplete(userId.value)
    experimentCompleted.value = true
    completionErrorNotified.value = false
  } catch (error) {
    console.error('标记实验完成失败', error)
    if (!completionErrorNotified.value) {
      showToast('同步完成状态失败，请稍后再试。')
      completionErrorNotified.value = true
    }
    setTimeout(() => {
      if (!experimentCompleted.value) {
        attemptCompletionMark()
      }
    }, 3000)
  } finally {
    completionMarkInFlight.value = false
  }
}

async function handleStepComplete(payload) {
  const step = currentStep.value
  if (!step) {
    return
  }

  if (step.type === 'form') {
    if (!userId.value) {
      showToast('用户信息尚未初始化，请稍后重试。')
      return
    }
    const nextStep = steps[stepIndex.value + 1] ?? null
    submittingStepId.value = step.id
    try {
      const payloadWithUser = {
        ...payload,
        userid: userId.value,
      }
      responses[payload.form_key || step.formKey] = payloadWithUser
      await submitForm(payloadWithUser)
      advanceStep()
      if (nextStep?.id === 'complete') {
        attemptCompletionMark()
      }
    } catch (error) {
      console.error('表单提交失败', error)
      showToast('提交超时或失败，请检查网络后重试。')
      delete responses[payload.form_key || step.formKey]
    } finally {
      submittingStepId.value = null
    }
    return
  }

  if (step.type === 'lesson') {
    if (payload) {
      responses.lesson = payload
      if (payload.submissionStatus === 'error') {
        showToast('课程记录保存失败，请检查网络后继续。')
      }
    }
    advanceStep()
    return
  }

  if (step.id === 'intro') {
    const result = await ensureUserId()
    if (!result.success) {
      return
    }
    if (result.completed) {
      showToast('该账号已完成实验，感谢参与。')
      skipToCompletion()
      return
    }
    advanceStep()
    return
  }

  if (payload && step?.formKey) {
    responses[step.formKey] = payload
  }
  advanceStep()
}

watch(currentStep, async (step) => {
  if (step?.type === 'form') {
    await nextTick()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  if (step?.id === 'complete') {
    attemptCompletionMark()
  }
})

const hasUserId = computed(() => Boolean(userId.value))

function showToast(message) {
  toast.message = message
  toast.visible = true
}

function hideToast() {
  toast.visible = false
  toast.message = ''
}

async function ensureUserId() {
  if (registering.value) {
    return { success: false, completed: false }
  }
  if (completionChecked.value && hasUserId.value) {
    return { success: true, completed: experimentCompleted.value }
  }

  if (typeof window === 'undefined') {
    return { success: false, completed: false }
  }

  registering.value = true
  try {
    if (!hasUserId.value) {
      const stored = getStoredUserId()
      if (stored) {
        userId.value = stored
      } else {
        const response = await registerUser()
        if (!response?.userid) {
          throw new Error('注册接口未返回有效的用户编号')
        }
        userId.value = response.userid
      }
    }

    persistUserId(userId.value)

  const completionResponse = await checkExperimentCompletion(userId.value)
  const completed = Boolean(completionResponse?.completed)
  experimentCompleted.value = completed
  completionChecked.value = true
  completionErrorNotified.value = false
    return { success: true, completed }
  } catch (error) {
    console.error('初始化用户信息失败', error)
    const message = error?.name === 'TimeoutError' ? '网络错误，请检查连接后重试。' : '网络错误，请稍后再试。'
    showToast(message)
    return { success: false, completed: false }
  } finally {
    registering.value = false
  }
}
</script>

<template>
  <div class="app-shell">
    <div class="chat-container">
      <header class="chat-header">
        <div class="header-branding">
          <span class="brand-accent"></span>
          <span class="brand-text">Psy Chat</span>
        </div>
        <div v-if="formProgress" class="header-status">
          <span>问卷进度</span>
          <strong>{{ formProgress.current }} / {{ formProgress.total }}</strong>
        </div>
        <div v-else-if="hasUserId" class="header-status subtle">
          <span>ID</span>
          <strong>{{ userId }}</strong>
        </div>
      </header>
      <section class="chat-body">
        <component
          v-if="currentComponent"
          :is="currentComponent"
          :key="currentStep?.id"
          v-bind="currentProps"
          @complete="handleStepComplete"
        />
      </section>
    </div>
    <div v-if="toast.visible" class="toast" @click="hideToast">
      <p>{{ toast.message }}</p>
      <span class="toast-hint">点击关闭</span>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  justify-content: center;
  align-items: stretch;
  min-height: 100vh;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2f6 100%);
}

.chat-container {
  display: flex;
  flex-direction: column;
  width: min(100%, 960px);
  border-radius: clamp(0.75rem, 1vw, 1.25rem);
  background-color: #ffffff;
  box-shadow: 0 30px 60px -45px rgba(15, 23, 42, 0.45), 0 25px 45px -35px rgba(15, 23, 42, 0.25);
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2rem);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 252, 0.82));
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.header-branding {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  font-weight: 600;
  font-size: clamp(1.1rem, 2.2vw, 1.5rem);
  color: #1f2937;
}

.brand-accent {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #38bdf8, #22d3ee);
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.6);
}

.header-status {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  color: #475569;
  font-size: 0.95rem;
}

.header-status.subtle {
  color: rgba(71, 85, 105, 0.85);
}

.header-status strong {
  font-size: 1.05rem;
  color: #0f172a;
  font-weight: 600;
}

.chat-body {
  flex: 1;
  padding: clamp(1.25rem, 3vw, 2.5rem);
  color: #1f2937;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.65) 0%, rgba(255, 255, 255, 0.9) 45%, #ffffff 100%);
}

.registration-warning {
  margin-top: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 0.75rem;
  background: rgba(254, 226, 226, 0.8);
  border: 1px solid rgba(248, 113, 113, 0.4);
  color: #b91c1c;
  font-size: 0.9rem;
}

.toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  max-width: 320px;
  width: calc(100% - 2rem);
  padding: 1rem 1.25rem;
  border-radius: 1rem;
  background: rgba(15, 23, 42, 0.9);
  color: #f8fafc;
  box-shadow: 0 18px 36px -24px rgba(15, 23, 42, 0.7);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  z-index: 1000;
}

.toast p {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.4;
}

.toast-hint {
  font-size: 0.78rem;
  color: rgba(226, 232, 240, 0.7);
}

@media (max-width: 600px) {
  .chat-container {
    border-radius: clamp(0.5rem, 3vw, 1rem);
    box-shadow: 0 20px 45px -30px rgba(15, 23, 42, 0.35);
  }

  .chat-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }
}
</style>
