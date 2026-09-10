/**
 * ClimaGPT — API Communication Layer
 *
 * Handles all HTTP requests to the Django REST Framework backend.
 * Uses DRF Token Authentication (Authorization: Token <key>).
 *
 * API Endpoints mapped:
 *   POST /api/auth/register/          — Create account + profile
 *   POST /api/auth/login/             — Authenticate → token
 *   GET  /api/farmer/profile/         — Get own profile
 *   PUT  /api/farmer/profile/         — Update profile
 *   GET  /api/farms/                  — List own farms
 *   POST /api/farms/                  — Create farm
 *   GET  /api/farms/<id>/             — Farm detail
 *   PUT  /api/farms/<id>/             — Update farm
 *   DELETE /api/farms/<id>/           — Delete farm
 *   GET  /api/farms/<farm_id>/crops/  — List crops for farm
 *   POST /api/farms/<farm_id>/crops/  — Add crop to farm
 *   GET  /api/crops/<id>/             — Crop detail
 *   PUT  /api/crops/<id>/             — Update crop
 *   DELETE /api/crops/<id>/           — Delete crop
 *   GET  /api/crops/growth-stages/    — List growth stages
 *   GET  /api/dashboard/              — Dashboard summary
 *   GET  /api/health/                 — Health check
 */

const API = (() => {
    'use strict';

    // ── Configuration ─────────────────────────────────────────
    const BASE_URL = 'http://localhost:8000';
    const TOKEN_KEY = 'climagpt_token';
    const USER_KEY = 'climagpt_user';

    // ── Token Management ──────────────────────────────────────

    function getToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    function setToken(token) {
        localStorage.setItem(TOKEN_KEY, token);
    }

    function clearToken() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
    }

    function isAuthenticated() {
        return !!getToken();
    }

    function setUser(userData) {
        localStorage.setItem(USER_KEY, JSON.stringify(userData));
    }

    function getUser() {
        try {
            return JSON.parse(localStorage.getItem(USER_KEY));
        } catch {
            return null;
        }
    }

    // ── HTTP Helper ───────────────────────────────────────────

    /**
     * Core fetch wrapper with automatic token injection and error handling.
     * @param {string} endpoint  — relative path (e.g. '/api/auth/login/')
     * @param {object} options   — { method, body, auth }
     * @returns {Promise<object>} — parsed JSON response
     */
    async function request(endpoint, options = {}) {
        const { method = 'GET', body = null, auth = true } = options;

        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        };

        if (auth && getToken()) {
            headers['Authorization'] = `Token ${getToken()}`;
        }

        const config = {
            method,
            headers,
        };

        if (body && method !== 'GET') {
            config.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${BASE_URL}${endpoint}`, config);

            // Handle 204 No Content (e.g., DELETE)
            if (response.status === 204) {
                return { success: true };
            }

            const data = await response.json();

            if (!response.ok) {
                // Format DRF error responses consistently
                const errorMsg = data.details
                    ? (typeof data.details === 'string'
                        ? data.details
                        : formatValidationErrors(data.details))
                    : data.error || data.detail || 'Request failed';

                throw new APIError(errorMsg, response.status, data);
            }

            return data;
        } catch (err) {
            if (err instanceof APIError) throw err;

            // Network or CORS errors
            throw new APIError(
                'Unable to connect to the server. Please ensure the backend is running.',
                0,
                null,
            );
        }
    }

    /**
     * Convert DRF nested validation errors to a readable string.
     */
    function formatValidationErrors(details) {
        if (typeof details === 'string') return details;

        const messages = [];
        for (const [field, errors] of Object.entries(details)) {
            const fieldLabel = field.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const errorList = Array.isArray(errors) ? errors : [errors];
            for (const e of errorList) {
                if (typeof e === 'string') {
                    messages.push(`${fieldLabel}: ${e}`);
                } else if (typeof e === 'object') {
                    // Nested objects (rare but possible)
                    messages.push(`${fieldLabel}: ${JSON.stringify(e)}`);
                }
            }
        }
        return messages.join('\n');
    }

    // ── Custom Error Class ────────────────────────────────────

    class APIError extends Error {
        constructor(message, status, data) {
            super(message);
            this.name = 'APIError';
            this.status = status;
            this.data = data;
        }
    }

    // ── Auth Endpoints ────────────────────────────────────────

    async function register(payload) {
        const data = await request('/api/auth/register/', {
            method: 'POST',
            body: payload,
            auth: false,
        });
        if (data.token) {
            setToken(data.token);
            setUser(data.farmer);
        }
        return data;
    }

    async function login(email, password) {
        const data = await request('/api/auth/login/', {
            method: 'POST',
            body: { email, password },
            auth: false,
        });
        if (data.token) {
            setToken(data.token);
            setUser(data.farmer);
        }
        return data;
    }

    function logout() {
        clearToken();
    }

    // ── Farmer Profile ────────────────────────────────────────

    async function getProfile() {
        return request('/api/farmer/profile/');
    }

    async function updateProfile(payload) {
        return request('/api/farmer/profile/', {
            method: 'PUT',
            body: payload,
        });
    }

    // ── Farms ─────────────────────────────────────────────────

    async function listFarms() {
        return request('/api/farms/');
    }

    async function createFarm(payload) {
        return request('/api/farms/', {
            method: 'POST',
            body: payload,
        });
    }

    async function getFarm(farmId) {
        return request(`/api/farms/${farmId}/`);
    }

    async function updateFarm(farmId, payload) {
        return request(`/api/farms/${farmId}/`, {
            method: 'PUT',
            body: payload,
        });
    }

    async function deleteFarm(farmId) {
        return request(`/api/farms/${farmId}/`, {
            method: 'DELETE',
        });
    }

    // ── Crops ─────────────────────────────────────────────────

    async function listCrops(farmId) {
        return request(`/api/farms/${farmId}/crops/`);
    }

    async function createCrop(farmId, payload) {
        return request(`/api/farms/${farmId}/crops/`, {
            method: 'POST',
            body: payload,
        });
    }

    async function getCrop(cropId) {
        return request(`/api/crops/${cropId}/`);
    }

    async function updateCrop(cropId, payload) {
        return request(`/api/crops/${cropId}/`, {
            method: 'PUT',
            body: payload,
        });
    }

    async function deleteCrop(cropId) {
        return request(`/api/crops/${cropId}/`, {
            method: 'DELETE',
        });
    }

    // ── Growth Stages ─────────────────────────────────────────

    async function listGrowthStages() {
        return request('/api/crops/growth-stages/', { auth: true });
    }

    // ── Dashboard ─────────────────────────────────────────────

    async function getDashboard() {
        return request('/api/dashboard/');
    }

    // ── Health Check ──────────────────────────────────────────

    async function healthCheck() {
        return request('/api/health/', { auth: false });
    }

    // ── Public API ────────────────────────────────────────────

    return {
        // Auth
        register,
        login,
        logout,
        isAuthenticated,
        getToken,
        getUser,
        setUser,

        // Profile
        getProfile,
        updateProfile,

        // Farms
        listFarms,
        createFarm,
        getFarm,
        updateFarm,
        deleteFarm,

        // Crops
        listCrops,
        createCrop,
        getCrop,
        updateCrop,
        deleteCrop,

        // Growth Stages
        listGrowthStages,

        // Dashboard
        getDashboard,

        // Utility
        healthCheck,
        APIError,
    };
})();
