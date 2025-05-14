import axios from "axios";

const api = axios.create({
    baseURL: '/ai/'
})

export {
    api
}