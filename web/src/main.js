import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import { createApp } from 'vue'
import { api } from './http.js'
import App from './App.vue'

const app = createApp(App)

app.provide('$api', api)
app.use(ElementPlus)
app.mount('#app')

