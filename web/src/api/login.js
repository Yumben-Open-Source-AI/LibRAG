import { api } from '@/http.js'

export function getToken(formData) {
    return api.post('token', {
        username: formData.username,
        password: formData.password
    }, {
        headers: { 'content-type': 'application/x-www-form-urlencoded' },
    })
}