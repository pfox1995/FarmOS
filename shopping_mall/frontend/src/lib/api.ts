import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:4000',
  withCredentials: true, // farmos_token 쿠키 자동 전송
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;
