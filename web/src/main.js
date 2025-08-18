import ElementPlus from 'element-plus';
import './style.css';
import zhCN from "element-plus/dist/locale/zh-cn.mjs"
import 'element-plus/dist/index.css';

import { createApp } from 'vue';
import { api } from './http.js';
import { createPinia } from 'pinia';
import piniaPluginPersist from 'pinia-plugin-persist'
import { router } from '@/router/index.js';
import App from '@/App.vue';

const app = createApp(App);
app.provide('$api', api);
app.use(ElementPlus, {locale:zhCN})
app.use(router);

const pinia = createPinia();
pinia.use(piniaPluginPersist);
app.use(pinia);
app.mount('#app');

