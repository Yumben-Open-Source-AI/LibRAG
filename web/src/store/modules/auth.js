import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null);
  const refreshToken = ref(localStorage.getItem('refreshToken') || null);

  const setToken = (newToken, freshToken) => {
    token.value = newToken;
    refreshToken.value = freshToken

    // 存储到 localStorage 持久化
    localStorage.setItem("token", newToken);
    localStorage.setItem("refreshToken", freshToken);
    console.log(refreshToken.value);

  };

  const clearToken = () => {
    token.value = null;
    refreshToken.value = null;

    // 删除 localStorage 持久化
    localStorage.removeItem("token");
    localStorage.removeItem("refreshToken");
  };

  const isAuthenticated = () => !!token.value;

  persist: true;

  return {
    token,
    refreshToken,
    setToken,
    clearToken,
    isAuthenticated
  };
});