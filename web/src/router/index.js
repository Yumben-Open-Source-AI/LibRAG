import { createWebHistory, createRouter } from 'vue-router'
import { useAuthStore } from '@/store/modules/auth';

// 基础路由
const constantRoutes = [
    {
        path: '/',
        redirect: '/login'
    },
    {
        path: '/login',
        name: 'Login',
        component: () => import('@/views/login/login.vue'),
        meta: {
            title: '登录',
        }
    },
    {
        path: '/home',
        name: 'home',
        component: () => import('@/views/home/home.vue'),
        meta: {
            title: '主页'
        }
    }
];


const router = createRouter({
    history: createWebHistory(),
    routes: constantRoutes,
})

// 配置全局路由守卫
router.beforeEach((to, from, next) => {
    const authStore = useAuthStore();
    const isAuthenticated = authStore.isAuthenticated;

    if (isAuthenticated) {
        next();
    } else {
        if (to.path == "/login") {
            next();
        } else {
            next({ path: "/login" });
        }
    }
});

export { router }