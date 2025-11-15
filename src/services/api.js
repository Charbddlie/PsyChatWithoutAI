import { BACKEND_ENDPOINTS } from '../config'

const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
}

function withTimeout(promise, timeoutMs) {
  let timeoutHandle
  const timeoutPromise = new Promise((_, reject) => {
    timeoutHandle = setTimeout(() => {
      const error = new Error('Request timed out')
      error.name = 'TimeoutError'
      reject(error)
    }, timeoutMs)
  })

  return Promise.race([
    promise.finally(() => clearTimeout(timeoutHandle)),
    timeoutPromise,
  ])
}

async function handleResponse(response) {
  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch (error) {
    throw new Error('服务器返回了无效的 JSON 响应')
  }

  if (!response.ok) {
    const message = data?.message || `请求失败，状态码 ${response.status}`
    const err = new Error(message)
    err.status = response.status
    err.payload = data
    throw err
  }

  return data
}

export async function registerUser(signal) {
  const request = fetch(BACKEND_ENDPOINTS.register, {
    method: 'POST',
    headers: DEFAULT_HEADERS,
    body: JSON.stringify({}),
    signal,
  })

  return withTimeout(request.then(handleResponse), 20000)
}

export async function submitForm(payload, signal) {
  const request = fetch(BACKEND_ENDPOINTS.submitForm, {
    method: 'POST',
    headers: DEFAULT_HEADERS,
    body: JSON.stringify(payload),
    signal,
  })

  return withTimeout(request.then(handleResponse), 20000)
}

export async function fetchUserGroup(userId, signal) {
  const url = new URL(BACKEND_ENDPOINTS.group)
  url.searchParams.set('userid', userId)

  const request = fetch(url.toString(), {
    method: 'GET',
    headers: DEFAULT_HEADERS,
    signal,
  })

  return withTimeout(request.then(handleResponse), 20000)
}

export async function checkExperimentCompletion(userId, signal) {
  const url = new URL(BACKEND_ENDPOINTS.completion)
  url.searchParams.set('userid', userId)

  const request = fetch(url.toString(), {
    method: 'GET',
    headers: DEFAULT_HEADERS,
    signal,
  })

  return withTimeout(request.then(handleResponse), 20000)
}

export async function markExperimentComplete(userId, signal) {
  const request = fetch(BACKEND_ENDPOINTS.completion, {
    method: 'POST',
    headers: DEFAULT_HEADERS,
    body: JSON.stringify({ userid: userId, completed: true }),
    signal,
  })

  return withTimeout(request.then(handleResponse), 20000)
}

export async function submitLessonSummary(payload, signal) {
  const request = fetch(BACKEND_ENDPOINTS.lessonComplete, {
    method: 'POST',
    headers: DEFAULT_HEADERS,
    body: JSON.stringify(payload),
    signal,
  })

  return withTimeout(request.then(handleResponse), 20000)
}
