<script setup lang="ts">
import { onBeforeMount, ref } from 'vue'
import { ElMessage } from 'element-plus-secondary'
import ChatComponent from '@/views/chat/index.vue'
import { useUserStore } from '@/stores/user'
import { useAssistantStore } from '@/stores/assistant'
import { request } from '@/utils/request'

const userStore = useUserStore()
const assistantStore = useAssistantStore()

const loading = ref(true)
const loginError = ref('')

const publicLogin = async () => {
  try {
    const res: any = await request.post('/open/public-token')
    const token = res?.access_token || res?.data?.access_token
    if (!token) {
      throw new Error('无法获取公开访问令牌')
    }
    userStore.setToken(token)
    await userStore.info()
    assistantStore.setAssistant(true)
    assistantStore.setHistory(false)
    assistantStore.setAutoDs(true)
    assistantStore.setPageEmbedded(true)
  } catch (err: any) {
    loginError.value = err?.message || String(err)
    ElMessage.error(loginError.value)
  } finally {
    loading.value = false
  }
}

onBeforeMount(async () => {
  await publicLogin()
})
</script>

<template>
  <div class="zcgl-chat-wrapper">
    <div v-if="loading" class="loading">正在初始化...</div>
    <div v-else-if="loginError" class="error">初始化失败：{{ loginError }}</div>
    <chat-component v-else :start-chat-ds-id="1" :page-embedded="true" app-name="资产助手" />
  </div>
</template>

<style lang="less" scoped>
.zcgl-chat-wrapper {
  height: 100vh;
  background: #f7f8fa;
}

.loading,
.error {
  padding: 20px;
  color: #646a73;
}

.error {
  color: #e23d3d;
}
</style>
