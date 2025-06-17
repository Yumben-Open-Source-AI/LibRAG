<template>
  <div class="login-wrapper">
    <el-form :model="form" :rules="rules" ref="loginForm" class="login-container" @submit.prevent="submitForm">
      <div class="login-header">
        <el-image style="width: 100px; height: 100px" :src="logUrl" :fit="fit"/>
        <h2>
          嗨，最近如何？
        </h2>
        <h3>欢迎来到 LibRAG, 登录以继续👏</h3>
      </div>

      <el-form-item prop="username">
        <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" size="large" clearable></el-input>
      </el-form-item>

      <el-form-item prop="password">
        <el-input type="password" v-model="form.password" placeholder="密码" :prefix-icon="Lock" size="large"
          show-password></el-input>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" native-type="submit" class="login-btn" :loading="loading">
          登录
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getToken } from '@/api/login'
import { Lock, User } from '@element-plus/icons-vue';
import { useAuthStore } from '@/store/modules/auth';
import logUrl from '@/static/log(500x500).png';

const router = useRouter()
const loginForm = ref(null)
const loading = ref(false)
const authStore = useAuthStore()

const form = reactive({
  username: '',
  password: ''
})

const rules = reactive({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ]
})

const submitForm = async () => {
  if (!loginForm.value) return

  try {
    const valid = await loginForm.value.validate()
    if (!valid) return

    loading.value = true
    const response = await getToken({
      username: form.username,
      password: form.password
    })

    if (response?.data.access_token) {
      ElMessage.success('登录成功')
      const token = response.data.access_token;
      
      authStore.setToken(token)
      router.push({ name: 'home' })
    }

  } catch (error) {
    console.error('登录失败:', error)
    ElMessage.error(error.response?.data?.detail || '登录失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.login-container {
  width: 100%;
  max-width: 420px;
  padding: 40px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
}

.login-header {
  text-align: center;
  margin-bottom: 36px;
}

.login-header h2 {
  font-size: 28px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 8px;
}

.login-header p {
  color: #95a5a6;
  font-size: 15px;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  letter-spacing: 2px;
  margin-top: 10px;
}
</style>