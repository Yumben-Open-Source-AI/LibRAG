import axios from "axios"
import { useAuthStore } from '@/store/modules/auth';
import { router } from '@/router/index.js';
const base_url = import.meta.env.VITE_APP_API_URL

const api = axios.create({
    baseURL: base_url,
    timeout: 240000,
})

// 配置请求拦截器
api.interceptors.request.use(config => {
    const authStore = useAuthStore();
    if (authStore.token) {
        config.headers.Authorization = `Bearer ${authStore.token}`;
    }
    return config;
}, error => Promise.reject(error))

// 配置响应拦截器
api.interceptors.response.use(
    response => response,
    async error => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true; // 标记为已尝试刷新
            const authStore = useAuthStore();

            try {
                const params = {
                    refresh_token: authStore.refreshToken
                }
                // 重置token
                const { data } = await api.post("refresh", params, {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                });

                // 更新token
                authStore.setToken(data.access_token, data.refresh_token);

                // 使用新token重新请求
                originalRequest.headers.Authorization = `Bearer ${data.token}`;
                return api(originalRequest);
            } catch (refreshError) {
                // 刷新失败，跳转登录
                authStore.clearToken();
                router.push('/login');
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
)

export { api }
