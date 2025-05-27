import axios from "axios"
const base_url = import.meta.env.VITE_APP_API_URL

const api = axios.create({
    baseURL: base_url,
    timeout: 120000,
})

export {
    api
}