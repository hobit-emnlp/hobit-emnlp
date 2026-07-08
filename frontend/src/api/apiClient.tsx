import axios from 'axios';
import { envs } from '../envs';

const endpoint = `${envs.HOBIT_BACKEND_ENDPOINT!}/api/v0`;

const apiClient = axios.create({
	baseURL: endpoint,
	headers: {
		'Content-Type': 'application/json',
	},
	withCredentials: true,
});

// 모든 요청에 X-Session-ID 헤더 자동 주입
apiClient.interceptors.request.use((config) => {
	let sessionId = localStorage.getItem('hobit_session_id');
	if (!sessionId) {
		sessionId = crypto.randomUUID();
		localStorage.setItem('hobit_session_id', sessionId);
	}
	config.headers['X-Session-ID'] = sessionId;
	return config;
});

export default apiClient;
