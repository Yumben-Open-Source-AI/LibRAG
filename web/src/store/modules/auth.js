import { defineStore } from 'pinia';
import { api } from '@/http.js';
import { ref } from 'vue';

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null);

  const setToken = (newToken) => {
    token.value = newToken;
    // 存储到 localStorage 持久化
    localStorage.setItem("token", newToken);
  };

  const clearToken = () => {
    token.value = null;
    localStorage.removeItem('token');
  };

  const isAuthenticated = () => !!token.value;

  persist: true;

  return { 
    token,
    setToken,
    clearToken,
    isAuthenticated
  };
});