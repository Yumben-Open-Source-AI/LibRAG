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
}, error => {
    return Promise.reject(error)
})

// 配置响应拦截器
api.interceptors.response.use(
    response => response,
    error => {
        if (error.response.status == 401) {
            const authStore = useAuthStore();
            authStore.clearToken();
            router.push('/login');
        }
        return Promise.reject(error);
    }
)

export { api }