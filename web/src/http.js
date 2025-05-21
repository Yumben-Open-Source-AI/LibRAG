import axios from "axios";

const api = axios.create({
    baseURL: '/ai/',
    timeout: 120000,
})

export {
    api
}