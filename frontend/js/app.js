/**
 * ClimaGPT — Main Application Controller
 *
 * SPA view routing, multi-step onboarding wizard, dashboard rendering,
 * toast notifications, and Leaflet map integration.
 */

const App = (() => {
    'use strict';

    // ── State ─────────────────────────────────────────────────
    let currentView = 'landing';
    let wizardStep = 1;
    const TOTAL_STEPS = 6;
    let leafletMap = null;
    let mapMarker = null;
    let growthStages = [];

    // ── DOM Cache ─────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ── Initialization ────────────────────────────────────────

    function init() {
        populateGrowthStageDropdowns();
        bindNavigation();
        bindAuthForms();
        bindWizard();
        bindDashboard();
        bindSoilDashboard();
        bindPredictionDashboard();
        bindModals();

        // Check if user is already logged in
        if (API.isAuthenticated()) {
            showAuthenticatedUI();
            navigateTo('dashboard');
        } else {
            navigateTo('landing');
        }
    }

    // ── Toast Notifications ───────────────────────────────────

    function toast(message, type = 'info') {
        const container = $('#toast-container');
        const icons = {
            success: 'fa-circle-check',
            error: 'fa-circle-exclamation',
            info: 'fa-circle-info',
        };

        const el = document.createElement('div');
        el.className = `toast toast-${type}`;
        el.innerHTML = `
            <i class="fa-solid ${icons[type] || icons.info}"></i>
            <span>${escapeHTML(message)}</span>
        `;
        container.appendChild(el);

        // Auto-remove after animation
        setTimeout(() => el.remove(), 5000);
    }

    function escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── SPA View Navigation ───────────────────────────────────

    function navigateTo(view) {
        // Hide all views
        $$('.view-section').forEach(s => {
            s.classList.add('hidden');
            s.classList.remove('active');
        });

        // Show target view
        const target = $(`#view-${view}`);
        if (target) {
            target.classList.remove('hidden');
            target.classList.add('active');
        }

        // Update nav active state
        $$('.nav-link').forEach(l => l.classList.remove('active'));
        const activeLink = $(`.nav-link[data-view="${view}"]`);
        if (activeLink) activeLink.classList.add('active');

        currentView = view;

        // Trigger view-specific hooks
        if (view === 'dashboard') loadDashboard();
        if (view === 'onboarding') {
            // Init map when step 4 becomes visible
            initMapIfNeeded();
            loadGrowthStages();
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function showAuthenticatedUI() {
        $('#guest-actions').classList.add('hidden');
        $('#user-actions').classList.remove('hidden');
        $('#nav-dashboard').classList.remove('hidden');

        const user = API.getUser();
        if (user) {
            $('#header-user-name').textContent = user.full_name || 'Farmer';
        }
    }

    function showGuestUI() {
        $('#guest-actions').classList.remove('hidden');
        $('#user-actions').classList.add('hidden');
        $('#nav-dashboard').classList.add('hidden');
    }

    // ── Navigation Bindings ───────────────────────────────────

    function bindNavigation() {
        // Brand logo → landing
        $('#brand-logo').addEventListener('click', () => {
            if (API.isAuthenticated()) {
                navigateTo('dashboard');
            } else {
                navigateTo('landing');
            }
        });

        // Nav links
        $$('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                navigateTo(link.dataset.view);
            });
        });

        // Header buttons
        const loginHeaderBtn = $('#btn-login-header');
        if (loginHeaderBtn) {
            loginHeaderBtn.addEventListener('click', () => {
                navigateTo('auth');
                switchAuthTab('login');
            });
        }

        const regHeaderBtn = $('#btn-register-header');
        if (regHeaderBtn) {
            regHeaderBtn.addEventListener('click', () => {
                navigateTo('auth');
                switchAuthTab('register');
            });
        }

        // Hero buttons
        $('#hero-btn-start').addEventListener('click', () => {
            navigateTo('onboarding');
        });

        $('#hero-btn-login').addEventListener('click', () => {
            navigateTo('auth');
            switchAuthTab('login');
        });

        // Logout
        $('#btn-logout').addEventListener('click', () => {
            API.logout();
            showGuestUI();
            navigateTo('landing');
            toast('You have been signed out.', 'info');
        });
    }

    // ── Auth Tab Switching & Forms ────────────────────────────

    function switchAuthTab(tab) {
        const tabLogin = $('#tab-login');
        const tabReg = $('#tab-register');
        const formLogin = $('#form-login');
        const formReg = $('#form-register');

        if (tab === 'login') {
            if (tabLogin) tabLogin.classList.add('active');
            if (tabReg) tabReg.classList.remove('active');
            if (formLogin) { formLogin.classList.add('active'); formLogin.classList.remove('hidden'); }
            if (formReg) { formReg.classList.add('hidden'); formReg.classList.remove('active'); }
        } else {
            if (tabReg) tabReg.classList.add('active');
            if (tabLogin) tabLogin.classList.remove('active');
            if (formReg) { formReg.classList.add('active'); formReg.classList.remove('hidden'); }
            if (formLogin) { formLogin.classList.add('hidden'); formLogin.classList.remove('active'); }
        }
    }

    function bindAuthForms() {
        const tabLogin = $('#tab-login');
        if (tabLogin) tabLogin.addEventListener('click', () => switchAuthTab('login'));

        const tabReg = $('#tab-register');
        if (tabReg) tabReg.addEventListener('click', () => switchAuthTab('register'));

        // Login form submit
        const formLogin = $('#form-login');
        if (formLogin) {
            formLogin.addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = e.target.querySelector('button[type="submit"]');
                const email = $('#login-email').value.trim();
                const password = $('#login-password').value;

                if (!email || !password) {
                    toast('Please fill in all fields.', 'error');
                    return;
                }

                setLoading(btn, true);
                try {
                    await API.login(email, password);
                    showAuthenticatedUI();
                    toast('Welcome back! 🎉', 'success');
                    navigateTo('dashboard');
                    e.target.reset();
                } catch (err) {
                    toast(err.message, 'error');
                } finally {
                    setLoading(btn, false);
                }
            });
        }
    }

    // ── Button Loading State ──────────────────────────────────

    function setLoading(btn, loading) {
        if (loading) {
            btn.dataset.originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
            btn.disabled = true;
        } else {
            btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
            btn.disabled = false;
        }
    }

    // ── Onboarding Wizard ─────────────────────────────────────

    function bindWizard() {
        const btnNext = $('#wizard-btn-next');
        const btnPrev = $('#wizard-btn-prev');
        const btnSubmit = $('#wizard-btn-submit');

        btnNext.addEventListener('click', () => {
            if (validateCurrentStep()) {
                goToStep(wizardStep + 1);
            }
        });

        btnPrev.addEventListener('click', () => {
            goToStep(wizardStep - 1);
        });

        btnSubmit.addEventListener('click', () => submitOnboarding());

        // GPS Button
        $('#btn-use-gps').addEventListener('click', useGPSLocation);
    }

    function goToStep(step) {
        if (step < 1 || step > TOTAL_STEPS) return;

        // Hide current step
        $(`#step-${wizardStep}`).classList.add('hidden');
        $(`#step-${wizardStep}`).classList.remove('active');

        wizardStep = step;

        // Show new step
        $(`#step-${wizardStep}`).classList.remove('hidden');
        $(`#step-${wizardStep}`).classList.add('active');

        // Update step counter
        $('#current-step-num').textContent = wizardStep;

        // Update stepper progress bar
        const progress = (wizardStep / TOTAL_STEPS) * 100;
        $('#stepper-progress').style.width = `${progress}%`;

        // Update step nodes
        $$('.step-node').forEach(node => {
            const nodeStep = parseInt(node.dataset.step);
            node.classList.remove('active', 'completed');
            if (nodeStep < wizardStep) node.classList.add('completed');
            if (nodeStep === wizardStep) node.classList.add('active');
        });

        // Update nav buttons
        $('#wizard-btn-prev').disabled = (wizardStep === 1);

        if (wizardStep === TOTAL_STEPS) {
            $('#wizard-btn-next').classList.add('hidden');
            $('#wizard-btn-submit').classList.remove('hidden');
            populateSummary();
        } else {
            $('#wizard-btn-next').classList.remove('hidden');
            $('#wizard-btn-submit').classList.add('hidden');
        }

        // Initialize map when entering step 4
        if (wizardStep === 4) {
            setTimeout(() => initMapIfNeeded(), 200);
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function validateCurrentStep() {
        switch (wizardStep) {
            case 1: return validateStep1();
            case 2: return validateStep2();
            case 3: return validateStep3();
            case 4: return validateStep4();
            case 5: return validateStep5();
            default: return true;
        }
    }

    function validateStep1() {
        const name = $('#ob-name').value.trim();
        const phone = $('#ob-phone').value.trim();
        const email = $('#ob-email').value.trim();
        const pass = $('#ob-pass').value;
        const confPass = $('#ob-conf-pass').value;

        if (!name) { toast('Full name is required.', 'error'); return false; }
        if (!phone) { toast('Phone number is required.', 'error'); return false; }
        if (!/^\+?[0-9]{7,15}$/.test(phone.replace(/\s/g, ''))) {
            toast('Enter a valid phone number (7–15 digits).', 'error');
            return false;
        }
        if (!email) { toast('Email address is required.', 'error'); return false; }
        if (!pass || pass.length < 8) {
            toast('Password must be at least 8 characters.', 'error');
            return false;
        }
        if (pass !== confPass) {
            toast('Passwords do not match.', 'error');
            return false;
        }
        return true;
    }

    function validateStep2() {
        const state = $('#ob-state').value.trim();
        const district = $('#ob-district').value.trim();
        const village = $('#ob-village').value.trim();

        if (!state) { toast('State is required.', 'error'); return false; }
        if (!district) { toast('District is required.', 'error'); return false; }
        if (!village) { toast('Village / Locality is required.', 'error'); return false; }
        return true;
    }

    function validateStep3() {
        const farmName = $('#ob-farm-name').value.trim();
        const farmArea = parseFloat($('#ob-farm-area').value);

        if (!farmName) { toast('Farm name is required.', 'error'); return false; }
        if (!farmArea || farmArea <= 0) {
            toast('Farm area must be greater than 0.', 'error');
            return false;
        }
        return true;
    }

    function validateStep4() {
        const lat = parseFloat($('#ob-lat').value);
        const lng = parseFloat($('#ob-lng').value);

        if (isNaN(lat) || lat < -90 || lat > 90) {
            toast('Latitude must be between -90 and 90.', 'error');
            return false;
        }
        if (isNaN(lng) || lng < -180 || lng > 180) {
            toast('Longitude must be between -180 and 180.', 'error');
            return false;
        }
        return true;
    }

    function validateStep5() {
        const cropName = $('#ob-crop-name').value.trim();
        const sowingDate = $('#ob-sowing-date').value;

        if (!cropName) { toast('Crop name is required.', 'error'); return false; }
        if (!sowingDate) { toast('Sowing date is required.', 'error'); return false; }

        const harvestDate = $('#ob-harvest-date').value;
        if (harvestDate && harvestDate <= sowingDate) {
            toast('Harvest date must be after sowing date.', 'error');
            return false;
        }
        return true;
    }

    // ── Summary Population (Step 6) ───────────────────────────

    function populateSummary() {
        // Profile
        const profileHTML = `
            <div class="summary-item"><span class="label">Full Name</span><span class="value">${escapeHTML($('#ob-name').value)}</span></div>
            <div class="summary-item"><span class="label">Email</span><span class="value">${escapeHTML($('#ob-email').value)}</span></div>
            <div class="summary-item"><span class="label">Phone</span><span class="value">${escapeHTML($('#ob-phone').value)}</span></div>
            <div class="summary-item"><span class="label">Language</span><span class="value">${escapeHTML($('#ob-lang').value)}</span></div>
            <div class="summary-item"><span class="label">State</span><span class="value">${escapeHTML($('#ob-state').value)}</span></div>
            <div class="summary-item"><span class="label">District</span><span class="value">${escapeHTML($('#ob-district').value)}</span></div>
            <div class="summary-item"><span class="label">Village</span><span class="value">${escapeHTML($('#ob-village').value)}</span></div>
            ${$('#ob-age').value ? `<div class="summary-item"><span class="label">Age</span><span class="value">${escapeHTML($('#ob-age').value)}</span></div>` : ''}
            ${$('#ob-gender').value ? `<div class="summary-item"><span class="label">Gender</span><span class="value">${escapeHTML($('#ob-gender').selectedOptions[0]?.text || '')}</span></div>` : ''}
        `;
        $('#summary-profile-content').innerHTML = profileHTML;

        // Farm
        const farmHTML = `
            <div class="summary-item"><span class="label">Farm Name</span><span class="value">${escapeHTML($('#ob-farm-name').value)}</span></div>
            <div class="summary-item"><span class="label">Area</span><span class="value">${escapeHTML($('#ob-farm-area').value)} ${escapeHTML($('#ob-area-unit').selectedOptions[0]?.text || '')}</span></div>
            <div class="summary-item"><span class="label">Irrigation</span><span class="value">${escapeHTML($('#ob-irrigation').selectedOptions[0]?.text || '')}</span></div>
            <div class="summary-item"><span class="label">Latitude</span><span class="value">${escapeHTML($('#ob-lat').value)}</span></div>
            <div class="summary-item"><span class="label">Longitude</span><span class="value">${escapeHTML($('#ob-lng').value)}</span></div>
        `;
        $('#summary-farm-content').innerHTML = farmHTML;

        // Crop
        const stageSelect = $('#ob-growth-stage');
        const stageName = stageSelect.value
            ? (stageSelect.selectedOptions[0]?.text || 'N/A')
            : 'Not selected';
        const cropHTML = `
            <div class="summary-item"><span class="label">Crop Name</span><span class="value">${escapeHTML($('#ob-crop-name').value)}</span></div>
            <div class="summary-item"><span class="label">Variety</span><span class="value">${escapeHTML($('#ob-crop-variety').value || 'N/A')}</span></div>
            <div class="summary-item"><span class="label">Sowing Date</span><span class="value">${escapeHTML($('#ob-sowing-date').value)}</span></div>
            <div class="summary-item"><span class="label">Harvest Date</span><span class="value">${escapeHTML($('#ob-harvest-date').value || 'N/A')}</span></div>
            <div class="summary-item"><span class="label">Growth Stage</span><span class="value">${escapeHTML(stageName)}</span></div>
            <div class="summary-item"><span class="label">Soil Type</span><span class="value">${escapeHTML($('#ob-soil-type').value || 'N/A')}</span></div>
        `;
        $('#summary-crop-content').innerHTML = cropHTML;
    }

    // ── Submit Full Onboarding ────────────────────────────────

    async function submitOnboarding() {
        const btn = $('#wizard-btn-submit');
        setLoading(btn, true);

        try {
            // Step 1: Register the account
            const regPayload = {
                full_name: $('#ob-name').value.trim(),
                phone_number: $('#ob-phone').value.trim().replace(/\s/g, ''),
                email: $('#ob-email').value.trim(),
                password: $('#ob-pass').value,
                confirm_password: $('#ob-conf-pass').value,
                preferred_language: $('#ob-lang').value,
                state: $('#ob-state').value.trim(),
                district: $('#ob-district').value.trim(),
                village: $('#ob-village').value.trim(),
            };

            const age = parseInt($('#ob-age').value);
            if (!isNaN(age)) regPayload.age = age;

            const gender = $('#ob-gender').value;
            if (gender) regPayload.gender = gender;

            await API.register(regPayload);
            showAuthenticatedUI();
            toast('Account created successfully! 🎉', 'success');

            // Step 2: Create the farm
            const farmPayload = {
                farm_name: $('#ob-farm-name').value.trim(),
                farm_area: parseFloat($('#ob-farm-area').value),
                farm_area_unit: $('#ob-area-unit').value,
                irrigation_type: $('#ob-irrigation').value,
                latitude: parseFloat($('#ob-lat').value),
                longitude: parseFloat($('#ob-lng').value),
                village: $('#ob-village').value.trim(),
                district: $('#ob-district').value.trim(),
                state: $('#ob-state').value.trim(),
                postal_code: $('#ob-postal').value.trim(),
            };

            const farmResult = await API.createFarm(farmPayload);
            toast('Farm registered on map! 🗺️', 'success');

            // Step 3: Create the crop
            const cropPayload = {
                crop_name: $('#ob-crop-name').value.trim(),
                crop_variety: $('#ob-crop-variety').value.trim(),
                sowing_date: $('#ob-sowing-date').value,
            };

            const harvestDate = $('#ob-harvest-date').value;
            if (harvestDate) cropPayload.expected_harvest_date = harvestDate;

            const stageId = $('#ob-growth-stage').value;
            const parsedStageId = parseInt(stageId, 10);
            if (!isNaN(parsedStageId)) cropPayload.growth_stage = parsedStageId;

            const soilType = $('#ob-soil-type').value;
            if (soilType) cropPayload.soil_type = soilType;

            await API.createCrop(farmResult.id, cropPayload);
            toast('Initial crop profile saved! 🌾', 'success');

            // Navigate to dashboard immediately
            navigateTo('dashboard');
            resetWizard();

        } catch (err) {
            toast(err.message, 'error');
        } finally {
            setLoading(btn, false);
        }
    }

    function resetWizard() {
        wizardStep = 1;
        $$('.wizard-step').forEach(s => {
            s.classList.add('hidden');
            s.classList.remove('active');
        });
        $('#step-1').classList.remove('hidden');
        $('#step-1').classList.add('active');
        $('#current-step-num').textContent = '1';
        $('#stepper-progress').style.width = '16.66%';
        $$('.step-node').forEach(n => n.classList.remove('active', 'completed'));
        $$('.step-node')[0].classList.add('active');
        $('#wizard-btn-prev').disabled = true;
        $('#wizard-btn-next').classList.remove('hidden');
        $('#wizard-btn-submit').classList.add('hidden');
    }

    // ── Leaflet Map ───────────────────────────────────────────

    function initMapIfNeeded() {
        const container = $('#map-container');
        if (!container || leafletMap) return;

        // Default center: Central India
        const defaultLat = 22.5726;
        const defaultLng = 78.9629;

        leafletMap = L.map('map-container').setView([defaultLat, defaultLng], 5);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 19,
        }).addTo(leafletMap);

        // Click to place marker
        leafletMap.on('click', (e) => {
            placeMarker(e.latlng.lat, e.latlng.lng);
            $('#ob-lat').value = e.latlng.lat.toFixed(6);
            $('#ob-lng').value = e.latlng.lng.toFixed(6);
        });

        // Sync lat/lng inputs with map
        $('#ob-lat').addEventListener('change', syncMapFromInputs);
        $('#ob-lng').addEventListener('change', syncMapFromInputs);

        // Force map to recalculate size
        setTimeout(() => leafletMap.invalidateSize(), 300);
    }

    function placeMarker(lat, lng) {
        if (mapMarker) {
            mapMarker.setLatLng([lat, lng]);
        } else {
            mapMarker = L.marker([lat, lng], {
                draggable: true,
            }).addTo(leafletMap);

            mapMarker.on('dragend', () => {
                const pos = mapMarker.getLatLng();
                $('#ob-lat').value = pos.lat.toFixed(6);
                $('#ob-lng').value = pos.lng.toFixed(6);
            });
        }

        leafletMap.setView([lat, lng], 14, { animate: true });
    }

    function syncMapFromInputs() {
        const lat = parseFloat($('#ob-lat').value);
        const lng = parseFloat($('#ob-lng').value);
        if (!isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
            placeMarker(lat, lng);
        }
    }

    function useGPSLocation() {
        if (!navigator.geolocation) {
            toast('Geolocation is not supported by your browser.', 'error');
            return;
        }

        toast('Requesting GPS location...', 'info');

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                $('#ob-lat').value = lat.toFixed(6);
                $('#ob-lng').value = lng.toFixed(6);
                if (leafletMap) placeMarker(lat, lng);
                toast('GPS location captured! 📍', 'success');
            },
            (error) => {
                toast(`GPS Error: ${error.message}`, 'error');
            },
            { enableHighAccuracy: true, timeout: 10000 },
        );
    }

    // ── Modal Farm Map ────────────────────────────────────────
    // A separate Leaflet map instance for the "Add New Farm" modal.

    let modalMap = null;
    let modalMarker = null;

    function initModalMap() {
        const container = document.getElementById('modal-map-container');
        if (!container) return;

        // Destroy previous instance if lingering
        if (modalMap) {
            modalMap.remove();
            modalMap = null;
            modalMarker = null;
        }

        const defaultLat = 22.5726;
        const defaultLng = 78.9629;

        modalMap = L.map('modal-map-container').setView([defaultLat, defaultLng], 5);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 19,
        }).addTo(modalMap);

        // Click on map to place marker
        modalMap.on('click', (e) => {
            placeModalMarker(e.latlng.lat, e.latlng.lng);
            $('#mf-lat').value = e.latlng.lat.toFixed(6);
            $('#mf-lng').value = e.latlng.lng.toFixed(6);
        });

        // Sync lat/lng inputs → map
        $('#mf-lat').addEventListener('change', syncModalMapFromInputs);
        $('#mf-lng').addEventListener('change', syncModalMapFromInputs);

        // GPS button inside modal
        const gpsBtn = document.getElementById('btn-modal-use-gps');
        if (gpsBtn) {
            gpsBtn.addEventListener('click', () => {
                if (!navigator.geolocation) {
                    toast('Geolocation is not supported by your browser.', 'error');
                    return;
                }
                toast('Requesting GPS location...', 'info');
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude;
                        const lng = position.coords.longitude;
                        $('#mf-lat').value = lat.toFixed(6);
                        $('#mf-lng').value = lng.toFixed(6);
                        placeModalMarker(lat, lng);
                        toast('GPS location captured! 📍', 'success');
                    },
                    (error) => {
                        toast(`GPS Error: ${error.message}`, 'error');
                    },
                    { enableHighAccuracy: true, timeout: 10000 },
                );
            });
        }

        // Force recalculate
        setTimeout(() => modalMap.invalidateSize(), 300);
    }

    function placeModalMarker(lat, lng) {
        if (modalMarker) {
            modalMarker.setLatLng([lat, lng]);
        } else {
            modalMarker = L.marker([lat, lng], { draggable: true }).addTo(modalMap);

            modalMarker.on('dragend', () => {
                const pos = modalMarker.getLatLng();
                $('#mf-lat').value = pos.lat.toFixed(6);
                $('#mf-lng').value = pos.lng.toFixed(6);
            });
        }
        modalMap.setView([lat, lng], 14, { animate: true });
    }

    function syncModalMapFromInputs() {
        const lat = parseFloat($('#mf-lat').value);
        const lng = parseFloat($('#mf-lng').value);
        if (!isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
            placeModalMarker(lat, lng);
        }
    }

    function destroyModalMap() {
        if (modalMap) {
            modalMap.remove();
            modalMap = null;
            modalMarker = null;
        }
    }

    // ── Growth Stages Loader ──────────────────────────────────

    const DEFAULT_FALLBACK_STAGES = [
        { id: '', name: 'Sowing / Germination' },
        { id: '', name: 'Seedling' },
        { id: '', name: 'Vegetative' },
        { id: '', name: 'Tillering / Branching' },
        { id: '', name: 'Flowering / Reproductive' },
        { id: '', name: 'Grain Filling / Pod Formation' },
        { id: '', name: 'Maturity / Harvest' }
    ];

    async function loadGrowthStages() {
        if (growthStages.length > 0) return;

        try {
            const stages = await API.listGrowthStages();
            if (Array.isArray(stages) && stages.length > 0) {
                growthStages = stages;
            } else {
                growthStages = DEFAULT_FALLBACK_STAGES;
            }
        } catch {
            growthStages = DEFAULT_FALLBACK_STAGES;
        }
        populateGrowthStageDropdowns();
    }

    function populateGrowthStageDropdowns() {
        const selectors = ['#ob-growth-stage', '#mc-stage'];
        const listToUse = (growthStages && growthStages.length > 0) ? growthStages : DEFAULT_FALLBACK_STAGES;

        selectors.forEach(sel => {
            const select = $(sel);
            if (!select) return;
            select.innerHTML = '<option value="">Select Growth Stage</option>';
            listToUse.forEach(stage => {
                const opt = document.createElement('option');
                opt.value = stage.id || stage.name;
                opt.textContent = stage.name;
                select.appendChild(opt);
            });
        });
    }

    // ── Weather & Climate Forecast Controller ────────────────
    let currentWeatherFarmId = null;

    function getWMOWeatherDetails(code) {
        const c = parseInt(code, 10);
        switch (c) {
            case 0:
                return { label: 'Clear Sky', icon: 'fa-sun', color: '#f59e0b' };
            case 1:
                return { label: 'Mainly Clear', icon: 'fa-sun-cloud', color: '#fbbf24' };
            case 2:
                return { label: 'Partly Cloudy', icon: 'fa-cloud-sun', color: '#38bdf8' };
            case 3:
                return { label: 'Overcast', icon: 'fa-cloud', color: '#94a3b8' };
            case 45:
            case 48:
                return { label: 'Foggy', icon: 'fa-smog', color: '#cbd5e1' };
            case 51:
            case 53:
            case 55:
                return { label: 'Drizzle', icon: 'fa-cloud-rain', color: '#38bdf8' };
            case 56:
            case 57:
                return { label: 'Freezing Drizzle', icon: 'fa-snowflake', color: '#a5f3fc' };
            case 61:
            case 63:
            case 65:
                return { label: 'Rain', icon: 'fa-cloud-showers-heavy', color: '#60a5fa' };
            case 66:
            case 67:
                return { label: 'Freezing Rain', icon: 'fa-snowflake', color: '#93c5fd' };
            case 71:
            case 73:
            case 75:
            case 77:
                return { label: 'Snowfall', icon: 'fa-snowflake', color: '#e0f2fe' };
            case 80:
            case 81:
            case 82:
                return { label: 'Rain Showers', icon: 'fa-cloud-sun-rain', color: '#34d399' };
            case 85:
            case 86:
                return { label: 'Snow Showers', icon: 'fa-snowflake', color: '#bae6fd' };
            case 95:
            case 96:
            case 99:
                return { label: 'Thunderstorm', icon: 'fa-bolt', color: '#f87171' };
            default:
                return { label: 'Partly Cloudy', icon: 'fa-cloud-sun', color: '#38bdf8' };
        }
    }

    function populateWeatherFarmDropdown(farms) {
        const select = $('#weather-farm-select');
        if (!select) return;
        select.innerHTML = '<option value="">Select Farm Plot...</option>';

        if (!farms || farms.length === 0) return;

        farms.forEach((farm) => {
            const opt = document.createElement('option');
            opt.value = farm.id;
            opt.textContent = `${farm.farm_name} (${farm.village || farm.district || 'Plot'})`;
            select.appendChild(opt);
        });

        if (!currentWeatherFarmId || !farms.some(f => f.id === currentWeatherFarmId)) {
            currentWeatherFarmId = farms[0].id;
        }

        select.value = currentWeatherFarmId;
    }

    async function loadWeatherDashboard(farmId) {
        const wrapper = $('#weather-content-wrapper');
        if (!wrapper) return;

        wrapper.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-spinner fa-spin" style="font-size: 2rem; color: var(--clr-primary-400); margin-bottom: 10px;"></i>
                <p>Fetching real-time weather & 7-day forecast from Open-Meteo...</p>
            </div>
        `;

        try {
            const [currentRes, hourlyRes, dailyRes] = await Promise.all([
                API.getCurrentWeather(farmId).catch(() => null),
                API.getHourlyForecast(farmId).catch(() => null),
                API.getDailyForecast(farmId).catch(() => null),
            ]);

            const current = (currentRes && currentRes.results && currentRes.results.length > 0) ? currentRes.results[0] : null;
            const hourly = (hourlyRes && hourlyRes.results) ? hourlyRes.results : [];
            const daily = (dailyRes && dailyRes.results) ? dailyRes.results : [];
            const location = (currentRes && currentRes.location) || (dailyRes && dailyRes.location) || {};

            renderWeatherDashboard(current, hourly, daily, location, farmId);
        } catch (err) {
            wrapper.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; color: var(--clr-danger-400); margin-bottom: 10px;"></i>
                    <p>Failed to load weather data: ${escapeHTML(err.message)}</p>
                    <button class="btn btn-secondary btn-sm" onclick="App.refreshWeatherForFarm(${farmId})" style="margin-top: 10px;">
                        <i class="fa-solid fa-arrows-rotate"></i> Try Refreshing Weather
                    </button>
                </div>
            `;
        }
    }

    function renderWeatherDashboard(current, hourly, daily, location, farmId) {
        const wrapper = $('#weather-content-wrapper');
        if (!wrapper) return;

        if (!current && hourly.length === 0 && daily.length === 0) {
            wrapper.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-cloud-slash" style="font-size: 2rem; color: var(--clr-text-dim); margin-bottom: 10px;"></i>
                    <p>No weather data found for this farm. Click below to pull live weather data from Open-Meteo.</p>
                    <button class="btn btn-primary btn-sm" onclick="App.refreshWeatherForFarm(${farmId})" style="margin-top: 12px;">
                        <i class="fa-solid fa-arrows-rotate"></i> Fetch Open-Meteo Live Data
                    </button>
                </div>
            `;
            return;
        }

        const wmo = getWMOWeatherDetails(current ? current.weather_code : 0);
        const tempStr = current ? `${Math.round(current.temperature)}°C` : '--';
        const apparentTempStr = current && current.apparent_temperature !== null ? `${Math.round(current.apparent_temperature)}°C` : '--';
        const humidityStr = current ? `${current.relative_humidity}%` : '--';
        const windStr = current ? `${current.wind_speed} km/h` : '--';
        const rainStr = current ? `${current.precipitation} mm` : '0 mm';
        const rainProbVal = (current && current.precipitation_probability !== null)
            ? current.precipitation_probability
            : (hourly && hourly.length > 0 && hourly[0].precipitation_probability !== null ? hourly[0].precipitation_probability : null);
        const rainProbStr = rainProbVal !== null ? `${rainProbVal}%` : '--';
        const pressureStr = current ? `${current.surface_pressure} hPa` : '--';
        const evapStr = current ? `${current.evapotranspiration} mm` : '--';
        const locationName = [location.name || location.village, location.district, location.state].filter(Boolean).join(', ') || 'Farm Location';
        const lastUpdated = current ? new Date(current.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Just now';

        // 1. Current Weather Card HTML
        const currentWeatherCardHTML = `
            <div class="weather-current-card glass-panel" style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(245, 158, 11, 0.08)); border: 1px solid var(--clr-border-focus); padding: 20px; border-radius: var(--radius-lg); margin-bottom: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
                    <div>
                        <div style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; color: var(--clr-primary-400); font-weight: 600; margin-bottom: 4px;">
                            <i class="fa-solid fa-location-dot"></i> ${escapeHTML(locationName)}
                        </div>
                        <div style="display: flex; align-items: center; gap: 16px; margin: 8px 0;">
                            <i class="fa-solid ${wmo.icon}" style="font-size: 3rem; color: ${wmo.color}; filter: drop-shadow(0 0 12px ${wmo.color});"></i>
                            <div>
                                <div style="font-size: 2.8rem; font-weight: 700; line-height: 1; font-family: var(--font-display);">${tempStr}</div>
                                <div style="font-size: 0.95rem; opacity: 0.9; margin-top: 4px;">
                                    <strong>${wmo.label}</strong> • Feels like ${apparentTempStr}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div style="text-align: right; font-size: 0.8rem; opacity: 0.7;">
                        <div><i class="fa-solid fa-satellite"></i> Lat: ${location.latitude?.toFixed(4) || '--'}, Lng: ${location.longitude?.toFixed(4) || '--'}</div>
                        <div style="margin-top: 4px;"><i class="fa-solid fa-clock"></i> Updated: ${lastUpdated}</div>
                    </div>
                </div>

                <!-- Weather Parameters Grid -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--clr-border);">
                    <div style="background: rgba(255,255,255,0.03); padding: 10px 14px; border-radius: var(--radius-md); border: 1px solid var(--clr-border);">
                        <div style="font-size: 0.75rem; opacity: 0.75;"><i class="fa-solid fa-droplet" style="color:#38bdf8;"></i> Humidity</div>
                        <div style="font-size: 1.1rem; font-weight: 600; margin-top: 2px;">${humidityStr}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); padding: 10px 14px; border-radius: var(--radius-md); border: 1px solid var(--clr-border);">
                        <div style="font-size: 0.75rem; opacity: 0.75;"><i class="fa-solid fa-wind" style="color:#94a3b8;"></i> Wind Speed</div>
                        <div style="font-size: 1.1rem; font-weight: 600; margin-top: 2px;">${windStr}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); padding: 10px 14px; border-radius: var(--radius-md); border: 1px solid var(--clr-border);">
                        <div style="font-size: 0.75rem; opacity: 0.75;"><i class="fa-solid fa-cloud-rain" style="color:#60a5fa;"></i> Rain / Prob</div>
                        <div style="font-size: 1.1rem; font-weight: 600; margin-top: 2px;">${rainStr} <span style="font-size:0.8rem; font-weight:400; opacity:0.8;">(${rainProbStr})</span></div>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); padding: 10px 14px; border-radius: var(--radius-md); border: 1px solid var(--clr-border);">
                        <div style="font-size: 0.75rem; opacity: 0.75;"><i class="fa-solid fa-gauge" style="color:#fbbf24;"></i> Pressure</div>
                        <div style="font-size: 1.1rem; font-weight: 600; margin-top: 2px;">${pressureStr}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); padding: 10px 14px; border-radius: var(--radius-md); border: 1px solid var(--clr-border);">
                        <div style="font-size: 0.75rem; opacity: 0.75;"><i class="fa-solid fa-seedling" style="color:#34d399;"></i> Evapotranspiration</div>
                        <div style="font-size: 1.1rem; font-weight: 600; margin-top: 2px;">${evapStr}</div>
                    </div>
                </div>
            </div>
        `;

        // 2. Hourly Forecast Strip HTML (24 Hours)
        let hourlyStripHTML = '';
        if (hourly && hourly.length > 0) {
            const items = hourly.slice(0, 24).map(item => {
                const dateObj = new Date(item.timestamp);
                const timeStr = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const itemWmo = getWMOWeatherDetails(item.weather_code);
                return `
                    <div style="flex: 0 0 90px; background: var(--clr-bg-elevated); border: 1px solid var(--clr-border); border-radius: var(--radius-md); padding: 12px 8px; text-align: center;">
                        <div style="font-size: 0.75rem; opacity: 0.8; font-weight: 500;">${timeStr}</div>
                        <i class="fa-solid ${itemWmo.icon}" style="font-size: 1.4rem; color: ${itemWmo.color}; margin: 8px 0;"></i>
                        <div style="font-size: 0.95rem; font-weight: 600;">${Math.round(item.temperature)}°C</div>
                        <div style="font-size: 0.7rem; color: #60a5fa; margin-top: 4px;">
                            <i class="fa-solid fa-droplet" style="font-size: 9px;"></i> ${item.precipitation_probability ?? 0}%
                        </div>
                    </div>
                `;
            }).join('');

            hourlyStripHTML = `
                <div style="margin-bottom: 24px;">
                    <h4 style="font-size: 0.95rem; font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        <i class="fa-solid fa-clock" style="color: var(--clr-primary-400);"></i> 24-Hour Hourly Forecast
                    </h4>
                    <div style="display: flex; gap: 10px; overflow-x: auto; padding-bottom: 10px; scrollbar-width: thin;">
                        ${items}
                    </div>
                </div>
            `;
        }

        // 3. 7-Day Daily Forecast Cards HTML
        let dailyGridHTML = '';
        if (daily && daily.length > 0) {
            const cards = daily.map(item => {
                const dateObj = new Date(item.timestamp);
                const dayName = dateObj.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
                const itemWmo = getWMOWeatherDetails(item.weather_code);
                return `
                    <div style="background: var(--clr-bg-elevated); border: 1px solid var(--clr-border); border-radius: var(--radius-md); padding: 14px; display: flex; flex-direction: column; align-items: center; text-align: center;">
                        <div style="font-size: 0.8rem; font-weight: 600; color: var(--clr-primary-300);">${dayName}</div>
                        <i class="fa-solid ${itemWmo.icon}" style="font-size: 2rem; color: ${itemWmo.color}; margin: 12px 0;"></i>
                        <div style="font-size: 0.8rem; opacity: 0.85; margin-bottom: 8px; min-height: 28px;">${itemWmo.label}</div>
                        <div style="font-size: 1rem; font-weight: 700; margin-bottom: 6px;">
                            ${Math.round(item.temperature)}°C
                        </div>
                        <div style="font-size: 0.75rem; opacity: 0.8; display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;">
                            <span><i class="fa-solid fa-cloud-rain" style="color:#60a5fa;"></i> ${item.precipitation || 0}mm</span>
                            <span><i class="fa-solid fa-wind" style="color:#94a3b8;"></i> ${item.wind_speed || 0}km/h</span>
                        </div>
                    </div>
                `;
            }).join('');

            dailyGridHTML = `
                <div>
                    <h4 style="font-size: 0.95rem; font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        <i class="fa-solid fa-calendar-days" style="color: var(--clr-accent-400);"></i> 7-Day Weather Forecast
                    </h4>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px;">
                        ${cards}
                    </div>
                </div>
            `;
        }

        wrapper.innerHTML = currentWeatherCardHTML + hourlyStripHTML + dailyGridHTML;
    }

    async function refreshWeatherForFarm(farmId) {
        const btn = $('#btn-refresh-weather');
        if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Refreshing...';
        toast('Fetching live satellite & station data from Open-Meteo...', 'info');

        try {
            await API.refreshWeather(farmId);
            toast('Weather updated successfully with live Open-Meteo data! ☀️', 'success');
            await loadWeatherDashboard(farmId);
        } catch (err) {
            toast(`Failed to refresh weather: ${err.message}`, 'error');
        } finally {
            if (btn) btn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Refresh Live Data';
        }
    }

    // ── Stage 4: Soil Moisture & Farm Environmental State Controller ──
    let currentSoilFarmId = null;
    let lastSoilHistoryData = null;
    let cachedFarmerFarms = [];

    function getSourceBadge(source) {
        const s = (source || 'SENSOR').toUpperCase();
        switch (s) {
            case 'SENSOR':
                return '<span class="source-badge source-badge-sensor"><i class="fa-solid fa-microchip"></i> Sensor</span>';
            case 'SATELLITE':
                return '<span class="source-badge source-badge-satellite"><i class="fa-solid fa-satellite"></i> Satellite</span>';
            case 'REANALYSIS':
                return '<span class="source-badge source-badge-reanalysis"><i class="fa-solid fa-layer-group"></i> Reanalysis</span>';
            case 'ESTIMATED':
                return '<span class="source-badge source-badge-estimated"><i class="fa-solid fa-calculator"></i> Estimated</span>';
            default:
                return `<span class="source-badge source-badge-sensor">${escapeHTML(s)}</span>`;
        }
    }

    function getConfidenceBadge(confidence, level) {
        if (confidence === null || confidence === undefined) {
            return '<span class="confidence-badge confidence-not-provided"><i class="fa-solid fa-circle-question"></i> Not provided</span>';
        }
        const num = parseFloat(confidence);
        const lvl = level || (num >= 0.8 ? 'High' : (num >= 0.5 ? 'Medium' : 'Low'));
        const pct = Math.round(num * 100);
        if (lvl === 'High') {
            return `<span class="confidence-badge confidence-high"><i class="fa-solid fa-circle-check"></i> High (${pct}%)</span>`;
        } else if (lvl === 'Medium') {
            return `<span class="confidence-badge confidence-medium"><i class="fa-solid fa-circle-exclamation"></i> Medium (${pct}%)</span>`;
        } else {
            return `<span class="confidence-badge confidence-low"><i class="fa-solid fa-triangle-exclamation"></i> Low (${pct}%)</span>`;
        }
    }

    async function loadSoilDashboard(farmId) {
        if (!farmId) return;
        currentSoilFarmId = farmId;
        const wrapper = $('#soil-content-wrapper');
        if (!wrapper) return;

        wrapper.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-spinner fa-spin" style="font-size: 2rem; color: var(--clr-primary-400); margin-bottom: 10px;"></i>
                <p>Loading soil conditions and environmental diagnostics...</p>
            </div>
        `;

        try {
            const [currentRes, envStateRes, historyRes] = await Promise.all([
                API.getCurrentSoilMoisture(farmId).catch(err => ({ available: false, error: err })),
                API.getEnvironmentalState(farmId).catch(() => null),
                API.getSoilMoistureHistory(farmId).catch(() => ({ count: 0, results: [] })),
            ]);

            renderSoilDashboard(currentRes, envStateRes, historyRes, farmId);
        } catch (err) {
            wrapper.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; color: var(--clr-danger-400); margin-bottom: 10px;"></i>
                    <p>Failed to load soil data: ${escapeHTML(err.message)}</p>
                    <button class="btn btn-secondary btn-sm" onclick="App.refreshSoilForFarm(${farmId})" style="margin-top: 10px;">
                        <i class="fa-solid fa-arrows-rotate"></i> Try Again
                    </button>
                </div>
            `;
        }
    }

    function renderSoilDashboard(currentRes, envState, historyRes, farmId) {
        const wrapper = $('#soil-content-wrapper');
        if (!wrapper) return;

        const hasMoisture = currentRes && currentRes.available !== false && currentRes.moisture !== undefined && currentRes.moisture !== null;
        const historyList = (historyRes && historyRes.results) ? historyRes.results : [];
        lastSoilHistoryData = historyList;

        // 1. Current Soil Moisture Card HTML
        let soilMoistureCardHTML = '';
        if (hasMoisture) {
            const moistureVal = currentRes.moisture;
            const depthVal = currentRes.depth ?? 20;
            const sourceBadge = getSourceBadge(currentRes.source);
            const confBadge = getConfidenceBadge(currentRes.confidence, currentRes.confidence_level);
            const updatedTime = currentRes.timestamp
                ? new Date(currentRes.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
                : 'Recent';

            soilMoistureCardHTML = `
                <div class="soil-metric-card glass-panel">
                    <div class="soil-card-header">
                        <div class="soil-card-title">
                            <i class="fa-solid fa-droplet" style="color: var(--clr-primary-400);"></i> Current Soil Moisture
                        </div>
                        ${sourceBadge}
                    </div>
                    <div class="soil-display-hero">
                        <div>
                            <div class="soil-moisture-large">${moistureVal}%</div>
                            <div style="font-size: 0.85rem; color: var(--clr-text-muted); margin-top: 4px;">
                                Volumetric Water Content (${escapeHTML(currentRes.unit || 'PERCENT')})
                            </div>
                        </div>
                        <div style="font-size: 3.5rem; opacity: 0.15; color: var(--clr-primary-400);">
                            <i class="fa-solid fa-water"></i>
                        </div>
                    </div>
                    <div class="soil-meta-pills">
                        <div class="soil-meta-row">
                            <span style="color: var(--clr-text-muted);"><i class="fa-solid fa-arrows-up-down"></i> Measurement Depth</span>
                            <strong>${depthVal} cm</strong>
                        </div>
                        <div class="soil-meta-row">
                            <span style="color: var(--clr-text-muted);"><i class="fa-solid fa-shield-halved"></i> Data Confidence</span>
                            ${confBadge}
                        </div>
                        <div class="soil-meta-row">
                            <span style="color: var(--clr-text-muted);"><i class="fa-solid fa-clock"></i> Last Updated</span>
                            <span>${updatedTime}</span>
                        </div>
                    </div>
                </div>
            `;
        } else {
            soilMoistureCardHTML = `
                <div class="soil-metric-card glass-panel">
                    <div class="soil-card-header">
                        <div class="soil-card-title">
                            <i class="fa-solid fa-droplet-slash" style="color: var(--clr-accent-400);"></i> Soil Moisture
                        </div>
                        <span class="badge badge-accent" style="font-size: 0.75rem;">Data Unavailable</span>
                    </div>
                    <div style="padding: 10px 0;">
                        <p style="font-weight: 600; font-size: 1rem; margin-bottom: 6px; color: var(--clr-text);">
                            Soil moisture data is not available for this farm.
                        </p>
                        <p style="font-size: 0.85rem; color: var(--clr-text-muted); line-height: 1.5;">
                            Physical in-situ telemetry is required to measure localized soil water content. Supported future sources include:
                        </p>
                        <ul style="font-size: 0.82rem; margin: 10px 0 14px 20px; color: var(--clr-text-muted); line-height: 1.6;">
                            <li><strong>In-situ Sensor:</strong> Real-time hardware telemetry at 5–50 cm depth.</li>
                            <li><strong>Satellite Products:</strong> SMAP & Sentinel-1 radar moisture grids.</li>
                            <li><strong>Reanalysis:</strong> ECMWF ERA5-Land land surface models.</li>
                        </ul>
                    </div>
                    <div style="display: flex; gap: 10px; margin-top: auto;">
                        <button class="btn btn-secondary btn-sm" onclick="App.openSensorIngestModal(${farmId})">
                            <i class="fa-solid fa-microchip"></i> Ingest Sensor Reading (Demo)
                        </button>
                    </div>
                </div>
            `;
        }

        // 2. Farm Environmental State Card HTML
        const weather = envState?.weather || {};
        const soilInfo = envState?.soil || {};
        const tempStr = weather.temperature !== undefined && weather.temperature !== null ? `${Math.round(weather.temperature * 10) / 10}°C` : '--';
        const humidStr = weather.humidity !== undefined && weather.humidity !== null ? `${weather.humidity}%` : '--';
        const rainStr = weather.recent_precipitation !== undefined && weather.recent_precipitation !== null ? `${weather.recent_precipitation} mm` : '--';
        const etStr = weather.evapotranspiration !== undefined && weather.evapotranspiration !== null ? `${weather.evapotranspiration} mm` : '--';
        const soilTypeStr = soilInfo.display_name || 'Not specified';
        const smStr = hasMoisture ? `${currentRes.moisture}%` : '--';

        const envStateCardHTML = `
            <div class="soil-metric-card glass-panel">
                <div class="soil-card-header">
                    <div class="soil-card-title">
                        <i class="fa-solid fa-earth-americas" style="color: var(--clr-accent-400);"></i> Farm Environmental State
                    </div>
                    <span class="badge badge-primary" style="font-size: 0.75rem;">Physical Diagnostics</span>
                </div>
                <div class="env-parameters-grid" style="margin: 8px 0 16px;">
                    <div class="env-param-box">
                        <div class="env-param-label"><i class="fa-solid fa-droplet" style="color: #34d399;"></i> Soil Moisture</div>
                        <div class="env-param-val">${smStr}</div>
                    </div>
                    <div class="env-param-box">
                        <div class="env-param-label"><i class="fa-solid fa-temperature-half" style="color: #fbbf24;"></i> Temperature</div>
                        <div class="env-param-val">${tempStr}</div>
                    </div>
                    <div class="env-param-box">
                        <div class="env-param-label"><i class="fa-solid fa-water" style="color: #38bdf8;"></i> Humidity</div>
                        <div class="env-param-val">${humidStr}</div>
                    </div>
                    <div class="env-param-box">
                        <div class="env-param-label"><i class="fa-solid fa-cloud-rain" style="color: #60a5fa;"></i> Recent Rain</div>
                        <div class="env-param-val">${rainStr}</div>
                    </div>
                    <div class="env-param-box">
                        <div class="env-param-label"><i class="fa-solid fa-sun-plant-wilt" style="color: #a78bfa;"></i> ET</div>
                        <div class="env-param-val">${etStr}</div>
                    </div>
                    <div class="env-param-box">
                        <div class="env-param-label"><i class="fa-solid fa-cubes-stacked" style="color: #f472b6;"></i> Soil Type</div>
                        <div class="env-param-val" style="font-size: 0.95rem;">${escapeHTML(soilTypeStr)}</div>
                    </div>
                </div>
                <div style="font-size: 0.78rem; color: var(--clr-text-dim); border-top: 1px dashed rgba(255,255,255,0.06); padding-top: 8px;">
                    <i class="fa-solid fa-circle-info"></i> Observed physical state gathered from real farm telemetry and local meteorological readings.
                </div>
            </div>
        `;

        // 3. History Panel HTML (Chart & Data Table)
        let historyPanelHTML = '';
        if (historyList.length > 0) {
            const latestRec = historyList[historyList.length - 1];
            const latestTimeStr = new Date(latestRec.timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });

            historyPanelHTML = `
                <div class="soil-history-panel">
                    <div class="soil-history-controls">
                        <div>
                            <h4 style="font-size: 1rem; font-weight: 700; font-family: var(--font-display); margin-bottom: 2px;">
                                <i class="fa-solid fa-chart-area" style="color: var(--clr-primary-400);"></i> Soil Moisture History Chart
                            </h4>
                            <span style="font-size: 0.8rem; color: var(--clr-text-muted);">Measured volumetric water content over time</span>
                        </div>
                        <div class="soil-filter-group">
                            <button class="btn btn-secondary btn-sm" id="btn-toggle-soil-table">
                                <i class="fa-solid fa-table"></i> Toggle Data Table
                            </button>
                        </div>
                    </div>

                    <!-- Quality Indicators -->
                    <div class="soil-quality-bar">
                        <span><i class="fa-solid fa-database"></i> Records: <strong>${historyList.length}</strong></span>
                        <span><i class="fa-solid fa-clock-rotate-left"></i> Latest Reading: <strong>${latestTimeStr}</strong></span>
                        <span><i class="fa-solid fa-ruler-vertical"></i> Primary Depth: <strong>${latestRec.depth || 20} cm</strong></span>
                        <span><i class="fa-solid fa-shield-check"></i> Quality: <strong>Continuity Validated</strong></span>
                    </div>

                    <!-- Canvas Chart -->
                    <div class="soil-chart-container">
                        <canvas id="soil-history-canvas" height="240"></canvas>
                    </div>

                    <!-- Collapsible Data Table -->
                    <div id="soil-table-container" class="soil-table-wrapper hidden">
                        <table class="soil-data-table">
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Moisture</th>
                                    <th>Unit</th>
                                    <th>Depth</th>
                                    <th>Source</th>
                                    <th>Confidence</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${historyList.slice().reverse().map(item => `
                                    <tr>
                                        <td>${new Date(item.timestamp).toLocaleString()}</td>
                                        <td><strong>${item.moisture}%</strong></td>
                                        <td>${escapeHTML(item.unit || 'PERCENT')}</td>
                                        <td>${item.depth} cm</td>
                                        <td>${getSourceBadge(item.source)}</td>
                                        <td>${getConfidenceBadge(item.confidence, item.confidence_level)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        wrapper.innerHTML = `
            <div class="soil-metrics-grid">
                ${soilMoistureCardHTML}
                ${envStateCardHTML}
            </div>
            ${historyPanelHTML}
        `;

        // Initialize Canvas Chart if history exists
        if (historyList.length > 0) {
            setTimeout(() => {
                drawSoilChart(historyList);
                const toggleBtn = $('#btn-toggle-soil-table');
                const tableContainer = $('#soil-table-container');
                if (toggleBtn && tableContainer) {
                    toggleBtn.addEventListener('click', () => {
                        tableContainer.classList.toggle('hidden');
                    });
                }
            }, 60);
        }
    }

    function drawSoilChart(records) {
        const canvas = document.getElementById('soil-history-canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        const width = rect.width || 600;
        const height = 240;

        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, width, height);

        if (!records || records.length === 0) return;

        const padding = { top: 25, right: 30, bottom: 40, left: 45 };
        const chartW = width - padding.left - padding.right;
        const chartH = height - padding.top - padding.bottom;

        const values = records.map(r => r.moisture);
        const minVal = Math.max(0, Math.floor(Math.min(...values) - 5));
        const maxVal = Math.min(100, Math.ceil(Math.max(...values) + 5));
        const range = (maxVal - minVal) || 1;

        // Draw gridlines
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.font = '11px Inter, sans-serif';
        ctx.fillStyle = 'rgba(232, 245, 233, 0.55)';
        ctx.textAlign = 'right';

        const yTicks = 4;
        for (let i = 0; i <= yTicks; i++) {
            const val = Math.round(minVal + (range * i) / yTicks);
            const y = padding.top + chartH - (i / yTicks) * chartH;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();
            ctx.fillText(`${val}%`, padding.left - 8, y + 4);
        }

        // Points calculation
        const points = records.map((r, i) => {
            const x = records.length === 1
                ? padding.left + chartW / 2
                : padding.left + (i / (records.length - 1)) * chartW;
            const y = padding.top + chartH - ((r.moisture - minVal) / range) * chartH;
            return { x, y, record: r };
        });

        // Area fill with gradient
        const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
        gradient.addColorStop(0, 'rgba(52, 211, 153, 0.35)');
        gradient.addColorStop(1, 'rgba(52, 211, 153, 0.00)');

        ctx.beginPath();
        ctx.moveTo(points[0].x, padding.top + chartH);
        points.forEach(p => ctx.lineTo(p.x, p.y));
        ctx.lineTo(points[points.length - 1].x, padding.top + chartH);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        // Line stroke with glow
        ctx.save();
        ctx.shadowColor = 'rgba(52, 211, 153, 0.6)';
        ctx.shadowBlur = 8;
        ctx.beginPath();
        points.forEach((p, i) => {
            if (i === 0) ctx.moveTo(p.x, p.y);
            else ctx.lineTo(p.x, p.y);
        });
        ctx.strokeStyle = '#34d399';
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.restore();

        // Data points & X-axis labels
        ctx.textAlign = 'center';
        points.forEach((p, i) => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
            ctx.fillStyle = '#10b981';
            ctx.fill();
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#ffffff';
            ctx.stroke();

            const showLabel = (records.length <= 8) || (i % Math.ceil(records.length / 6) === 0) || (i === records.length - 1);
            if (showLabel) {
                const d = new Date(p.record.timestamp);
                const label = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
                ctx.fillStyle = 'rgba(232, 245, 233, 0.6)';
                ctx.fillText(label, p.x, height - 12);
            }
        });
    }

    async function refreshSoilForFarm(farmId) {
        const btn = $('#btn-refresh-soil');
        if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Refreshing...';
        toast('Refreshing soil & environmental telemetry...', 'info');
        try {
            await loadSoilDashboard(farmId);
            toast('Soil & environmental state updated! 🌱', 'success');
        } catch (err) {
            toast(`Failed to refresh soil: ${err.message}`, 'error');
        } finally {
            if (btn) btn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Refresh Soil Data';
        }
    }

    function openSensorIngestModal(targetFarmId) {
        const modal = $('#modal-sensor-ingest');
        const farmSelect = $('#sensor-farm-select');
        if (!modal || !farmSelect) return;

        farmSelect.innerHTML = '';
        if (cachedFarmerFarms && cachedFarmerFarms.length > 0) {
            cachedFarmerFarms.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f.id;
                opt.textContent = `${f.farm_name} (${f.village || f.district || 'Plot'})`;
                farmSelect.appendChild(opt);
            });
            if (targetFarmId) farmSelect.value = targetFarmId;
        }

        const now = new Date();
        const localIso = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
        $('#sensor-timestamp').value = localIso;

        modal.classList.remove('hidden');
    }

    function bindSoilDashboard() {
        const btnRefresh = $('#btn-refresh-soil');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => {
                if (currentWeatherFarmId) {
                    refreshSoilForFarm(currentWeatherFarmId);
                } else {
                    toast('Please select a farm first.', 'error');
                }
            });
        }

        const btnOpen = $('#btn-open-sensor-modal');
        if (btnOpen) {
            btnOpen.addEventListener('click', () => {
                openSensorIngestModal(currentWeatherFarmId);
            });
        }

        const modal = $('#modal-sensor-ingest');
        const btnClose = $('#modal-sensor-ingest-close');
        if (btnClose && modal) {
            btnClose.addEventListener('click', () => {
                modal.classList.add('hidden');
            });
        }

        const btnPreset = $('#btn-quick-fill-sensor');
        if (btnPreset) {
            btnPreset.addEventListener('click', () => {
                $('#sensor-moisture').value = '24.5';
                $('#sensor-depth').value = '20';
                $('#sensor-confidence').value = '0.98';
                const now = new Date();
                const localIso = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
                $('#sensor-timestamp').value = localIso;
            });
        }

        const form = $('#form-sensor-ingest');
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const submitBtn = form.querySelector('button[type="submit"]');
                const farmSelect = $('#sensor-farm-select');
                const farmId = parseInt(farmSelect.value, 10);
                const moisture = parseFloat($('#sensor-moisture').value);
                const depth = parseInt($('#sensor-depth').value, 10);
                const confidence = parseFloat($('#sensor-confidence').value);
                const timeVal = $('#sensor-timestamp').value;

                if (!farmId || isNaN(moisture) || isNaN(depth) || !timeVal) {
                    toast('Please fill in all required fields.', 'error');
                    return;
                }

                setLoading(submitBtn, true);
                try {
                    const payload = {
                        farm_id: farmId,
                        moisture,
                        depth,
                        unit: 'PERCENT',
                        confidence: isNaN(confidence) ? null : confidence,
                        timestamp: new Date(timeVal).toISOString(),
                    };

                    await API.submitSensorReading(payload);
                    toast(`Sensor reading (${moisture}%) ingested successfully! 🌱`, 'success');
                    modal.classList.add('hidden');
                    form.reset();
                    loadSoilDashboard(farmId);
                } catch (err) {
                    toast(`Failed to ingest sensor reading: ${err.message}`, 'error');
                } finally {
                    setLoading(submitBtn, false);
                }
            });
        }

        window.addEventListener('resize', () => {
            if (lastSoilHistoryData && lastSoilHistoryData.length > 0) {
                drawSoilChart(lastSoilHistoryData);
            }
            if (lastPredictionData && lastPredictionData.predictions && lastPredictionData.predictions.length > 0) {
                drawPredictionComparisonChart();
            }
        });
    }

    // ============================================================
    // STAGE 5: AI WEATHER PREDICTION
    // ============================================================

    let currentPredictionFarmId = null;
    let lastPredictionData = null;
    let lastEvaluationData = null;
    let lastObservedHourlyData = [];
    let predictionChartTarget = 'temperature';

    async function loadPredictionDashboard(farmId, refresh = false) {
        if (!farmId) return;
        currentPredictionFarmId = farmId;
        const wrapper = $('#prediction-content-wrapper');
        if (!wrapper) return;

        wrapper.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-spinner fa-spin" style="font-size: 2rem; color: #818cf8; margin-bottom: 10px;"></i>
                <p>Generating AI weather predictions using trained Random Forest regressors...</p>
                <span style="font-size: 0.8rem; color: var(--clr-text-dim);">Evaluating farm-level historical features & environmental state</span>
            </div>
        `;

        try {
            const [predRes, evalRes, hourlyObs] = await Promise.all([
                API.getWeatherPredictions(farmId, refresh).catch(err => ({ error: err.error || 'PREDICTION_ERROR', message: err.message })),
                API.getPredictionEvaluation(farmId).catch(() => null),
                API.getHourlyForecast(farmId).catch(() => ({ results: [] })),
            ]);

            if (predRes.error) {
                renderPredictionErrorState(predRes, farmId);
                return;
            }

            lastObservedHourlyData = (hourlyObs && hourlyObs.results) ? hourlyObs.results : [];
            renderPredictionDashboard(predRes, evalRes, lastObservedHourlyData, farmId);
        } catch (err) {
            wrapper.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; color: var(--clr-danger-400); margin-bottom: 10px;"></i>
                    <p>Failed to load AI predictions: ${escapeHTML(err.message)}</p>
                    <button class="btn btn-secondary btn-sm" onclick="App.refreshPredictionForFarm(${farmId})" style="margin-top: 10px;">
                        <i class="fa-solid fa-arrows-rotate"></i> Try Again
                    </button>
                </div>
            `;
        }
    }

    function renderPredictionErrorState(errorObj, farmId) {
        const wrapper = $('#prediction-content-wrapper');
        if (!wrapper) return;

        if (errorObj.error === 'MODEL_NOT_TRAINED') {
            wrapper.innerHTML = `
                <div class="ai-state-banner glass-panel" style="padding: 24px; border: 1px dashed rgba(99, 102, 241, 0.4); border-radius: 12px; background: rgba(99, 102, 241, 0.05); text-align: center;">
                    <i class="fa-solid fa-brain" style="font-size: 2.2rem; color: #818cf8; margin-bottom: 12px; display: inline-block;"></i>
                    <h4 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 8px;">AI Model Not Yet Trained for this Farm</h4>
                    <p style="font-size: 0.9rem; color: var(--clr-text-muted); max-width: 600px; margin: 0 auto 16px;">
                        AI weather prediction is not available yet because machine learning regressors have not been trained on historical observations for this farm plot.
                    </p>
                    <div style="font-family: monospace; font-size: 0.85rem; background: rgba(0,0,0,0.3); padding: 8px 16px; border-radius: 6px; display: inline-block; color: #a5b4fc; margin-bottom: 16px;">
                        python manage.py train_weather_models --farm-id=${farmId}
                    </div>
                    <div>
                        <button class="btn btn-secondary btn-sm" onclick="App.refreshPredictionForFarm(${farmId})">
                            <i class="fa-solid fa-arrows-rotate"></i> Check Again
                        </button>
                    </div>
                </div>
            `;
        } else if (errorObj.error === 'INSUFFICIENT_DATA') {
            wrapper.innerHTML = `
                <div class="ai-state-banner glass-panel" style="padding: 24px; border: 1px dashed rgba(245, 158, 11, 0.4); border-radius: 12px; background: rgba(245, 158, 11, 0.05); text-align: center;">
                    <i class="fa-solid fa-database" style="font-size: 2.2rem; color: #f59e0b; margin-bottom: 12px; display: inline-block;"></i>
                    <h4 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 8px;">Insufficient Historical Observations</h4>
                    <p style="font-size: 0.9rem; color: var(--clr-text-muted); max-width: 600px; margin: 0 auto 16px;">
                        AI weather prediction requires at least 24 consecutive hourly observations to seed feature lags and rolling windows.
                    </p>
                    <button class="btn btn-secondary btn-sm" onclick="App.refreshPredictionForFarm(${farmId})">
                        <i class="fa-solid fa-arrows-rotate"></i> Refresh Telemetry
                    </button>
                </div>
            `;
        } else {
            wrapper.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; color: var(--clr-danger-400); margin-bottom: 10px;"></i>
                    <p>${escapeHTML(errorObj.message || 'Unable to generate predictions.')}</p>
                    <button class="btn btn-secondary btn-sm" onclick="App.refreshPredictionForFarm(${farmId})" style="margin-top: 10px;">
                        <i class="fa-solid fa-arrows-rotate"></i> Try Again
                    </button>
                </div>
            `;
        }
    }

    function renderPredictionDashboard(predData, evalData, recentObsData, farmId) {
        const wrapper = $('#prediction-content-wrapper');
        if (!wrapper) return;

        lastPredictionData = predData;
        lastEvaluationData = evalData;

        const preds = predData.predictions || [];
        const modelInfo = predData.model_info || {};

        // Calculate 24h summary statistics
        const temps = preds.map(p => p.temperature).filter(v => v !== null && v !== undefined);
        const rains = preds.map(p => p.rainfall).filter(v => v !== null && v !== undefined);
        const humids = preds.map(p => p.humidity).filter(v => v !== null && v !== undefined);
        const winds = preds.map(p => p.wind_speed).filter(v => v !== null && v !== undefined);

        const p0 = preds[0] || {};
        const minTemp = temps.length ? Math.min(...temps) : '--';
        const maxTemp = temps.length ? Math.max(...temps) : '--';
        const sumRain = rains.length ? rains.reduce((a, b) => a + b, 0).toFixed(1) : '0.0';
        const avgHumid = humids.length ? Math.round(humids.reduce((a, b) => a + b, 0) / humids.length) : '--';
        const maxWind = winds.length ? Math.max(...winds) : '--';

        const lastGenStr = predData.generated_at
            ? new Date(predData.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
            : 'Just now';

        // 1. Hero Metric Cards HTML
        const heroCardsHTML = `
            <div class="prediction-hero-grid">
                <!-- Temperature Card -->
                <div class="pred-card glass-panel" style="border-top: 3px solid #fbbf24;">
                    <div class="pred-card-header">
                        <span class="pred-card-title"><i class="fa-solid fa-temperature-half" style="color: #fbbf24;"></i> Temperature</span>
                        <span class="pred-tag">°C</span>
                    </div>
                    <div class="pred-value-display">
                        <span class="pred-main-val">${p0.temperature !== undefined ? p0.temperature : '--'}</span>
                        <span class="pred-unit">°C</span>
                    </div>
                    <div class="pred-card-footer">
                        <i class="fa-solid fa-arrows-up-down"></i> 24h Range: <strong>${minTemp}°C – ${maxTemp}°C</strong>
                    </div>
                </div>

                <!-- Rainfall Card -->
                <div class="pred-card glass-panel" style="border-top: 3px solid #60a5fa;">
                    <div class="pred-card-header">
                        <span class="pred-card-title"><i class="fa-solid fa-cloud-rain" style="color: #60a5fa;"></i> Precipitation</span>
                        <span class="pred-tag">mm</span>
                    </div>
                    <div class="pred-value-display">
                        <span class="pred-main-val">${p0.rainfall !== undefined ? p0.rainfall : '--'}</span>
                        <span class="pred-unit">mm</span>
                    </div>
                    <div class="pred-card-footer">
                        <i class="fa-solid fa-cloud-showers-heavy"></i> 24h Total: <strong>${sumRain} mm</strong>
                    </div>
                </div>

                <!-- Humidity Card -->
                <div class="pred-card glass-panel" style="border-top: 3px solid #34d399;">
                    <div class="pred-card-header">
                        <span class="pred-card-title"><i class="fa-solid fa-droplet" style="color: #34d399;"></i> Relative Humidity</span>
                        <span class="pred-tag">%</span>
                    </div>
                    <div class="pred-value-display">
                        <span class="pred-main-val">${p0.humidity !== undefined ? p0.humidity : '--'}</span>
                        <span class="pred-unit">%</span>
                    </div>
                    <div class="pred-card-footer">
                        <i class="fa-solid fa-gauge"></i> 24h Average: <strong>${avgHumid}%</strong>
                    </div>
                </div>

                <!-- Wind Speed Card -->
                <div class="pred-card glass-panel" style="border-top: 3px solid #a78bfa;">
                    <div class="pred-card-header">
                        <span class="pred-card-title"><i class="fa-solid fa-wind" style="color: #a78bfa;"></i> Wind Speed</span>
                        <span class="pred-tag">km/h</span>
                    </div>
                    <div class="pred-value-display">
                        <span class="pred-main-val">${p0.wind_speed !== undefined ? p0.wind_speed : '--'}</span>
                        <span class="pred-unit">km/h</span>
                    </div>
                    <div class="pred-card-footer">
                        <i class="fa-solid fa-gauge-high"></i> 24h Peak: <strong>${maxWind} km/h</strong>
                    </div>
                </div>
            </div>
        `;

        // 2. Model Transparency Banner HTML
        const transparencyHTML = `
            <div class="model-transparency-bar glass-panel">
                <div class="transparency-item">
                    <span class="transparency-label"><i class="fa-solid fa-microchip"></i> Model</span>
                    <strong class="transparency-value">${escapeHTML(modelInfo.model_name || 'Random Forest Regressor')}</strong>
                </div>
                <div class="transparency-item">
                    <span class="transparency-label"><i class="fa-solid fa-tag"></i> Version</span>
                    <strong class="transparency-value">${escapeHTML(predData.model_version || 'weather_v1')}</strong>
                </div>
                <div class="transparency-item">
                    <span class="transparency-label"><i class="fa-solid fa-calendar-range"></i> Training Period</span>
                    <strong class="transparency-value">${escapeHTML(modelInfo.training_period || 'Continuous')}</strong>
                </div>
                <div class="transparency-item">
                    <span class="transparency-label"><i class="fa-solid fa-database"></i> Training Samples</span>
                    <strong class="transparency-value">${modelInfo.sample_count ? modelInfo.sample_count.toLocaleString() + ' samples' : '720 samples'}</strong>
                </div>
                <div class="transparency-item">
                    <span class="transparency-label"><i class="fa-solid fa-clock"></i> Inferred At</span>
                    <strong class="transparency-value">${lastGenStr}</strong>
                </div>
            </div>
        `;

        // 3. Comparison Chart HTML
        const chartSectionHTML = `
            <div class="prediction-chart-panel glass-panel" style="margin-top: 20px; padding: 20px;">
                <div class="chart-header-controls" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
                    <div>
                        <h4 style="font-size: 1rem; font-weight: 700; margin-bottom: 2px;">
                            <i class="fa-solid fa-chart-line" style="color: #818cf8;"></i> Observed Weather vs AI Prediction
                        </h4>
                        <span style="font-size: 0.8rem; color: var(--clr-text-muted);">
                            Solid line represents recent observations; dashed line shows AI ML predictions forward in time.
                        </span>
                    </div>
                    <div class="chart-target-pills" style="display: flex; gap: 6px; flex-wrap: wrap;">
                        <button class="target-pill ${predictionChartTarget === 'temperature' ? 'active' : ''}" onclick="App.setPredictionChartTarget('temperature')">
                            <i class="fa-solid fa-temperature-half"></i> Temperature
                        </button>
                        <button class="target-pill ${predictionChartTarget === 'precipitation' ? 'active' : ''}" onclick="App.setPredictionChartTarget('precipitation')">
                            <i class="fa-solid fa-cloud-rain"></i> Rainfall
                        </button>
                        <button class="target-pill ${predictionChartTarget === 'relative_humidity' ? 'active' : ''}" onclick="App.setPredictionChartTarget('relative_humidity')">
                            <i class="fa-solid fa-droplet"></i> Humidity
                        </button>
                        <button class="target-pill ${predictionChartTarget === 'wind_speed' ? 'active' : ''}" onclick="App.setPredictionChartTarget('wind_speed')">
                            <i class="fa-solid fa-wind"></i> Wind
                        </button>
                    </div>
                </div>

                <div class="chart-legend-bar" style="display: flex; gap: 18px; font-size: 0.8rem; margin-bottom: 12px;">
                    <span style="display: flex; align-items: center; gap: 6px; color: #38bdf8;">
                        <span style="width: 16px; height: 3px; background: #38bdf8; display: inline-block; border-radius: 2px;"></span>
                        Observed Weather (Past)
                    </span>
                    <span style="display: flex; align-items: center; gap: 6px; color: #a78bfa;">
                        <span style="width: 16px; height: 3px; background: #a78bfa; display: inline-block; border-top: 2px dashed #a78bfa;"></span>
                        AI / ML Prediction (Next 24h)
                    </span>
                </div>

                <div class="prediction-canvas-container" style="position: relative; width: 100%; height: 260px;">
                    <canvas id="prediction-comparison-canvas" height="260"></canvas>
                </div>
            </div>
        `;

        // 4. Model Evaluation Table HTML
        let evaluationTableHTML = '';
        if (evalData && evalData.targets) {
            const targetRows = Object.entries(evalData.targets).map(([key, t]) => {
                const b = t.baseline || {};
                const m = t.ml_model || {};
                const targetDisplayNames = {
                    'temperature': 'Temperature (°C)',
                    'precipitation': 'Precipitation / Rainfall (mm)',
                    'relative_humidity': 'Relative Humidity (%)',
                    'wind_speed': 'Wind Speed (km/h)',
                };
                const displayName = targetDisplayNames[key] || key;
                const imp = t.improvement_pct;
                const impBadge = imp > 0
                    ? `<span class="badge badge-success" style="font-size: 0.75rem;">+${imp}% MAE Reduction</span>`
                    : `<span class="badge badge-secondary" style="font-size: 0.75rem;">${imp}% vs Persistence</span>`;

                return `
                    <tr>
                        <td><strong>${escapeHTML(displayName)}</strong></td>
                        <td>${b.mae !== undefined && b.mae !== null ? b.mae : '—'}</td>
                        <td>${b.rmse !== undefined && b.rmse !== null ? b.rmse : '—'}</td>
                        <td><strong>${m.mae !== undefined && m.mae !== null ? m.mae : '—'}</strong></td>
                        <td>${m.rmse !== undefined && m.rmse !== null ? m.rmse : '—'}</td>
                        <td>${m.r2 !== undefined && m.r2 !== null ? m.r2 : '—'}</td>
                        <td>${impBadge}</td>
                    </tr>
                `;
            }).join('');

            evaluationTableHTML = `
                <div class="model-evaluation-panel glass-panel" style="margin-top: 20px; padding: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                        <div>
                            <h4 style="font-size: 1rem; font-weight: 700; margin-bottom: 2px;">
                                <i class="fa-solid fa-vial-circle-check" style="color: #34d399;"></i> Research Evaluation: ML Regressor vs Baseline Benchmark
                            </h4>
                            <span style="font-size: 0.8rem; color: var(--clr-text-muted);">
                                Evaluated on out-of-sample chronological test split (15% future holdout without data leakage).
                            </span>
                        </div>
                        <button class="btn btn-secondary btn-sm" id="btn-toggle-eval-table">
                            <i class="fa-solid fa-table"></i> Toggle Details
                        </button>
                    </div>

                    <div id="eval-table-container" class="eval-table-wrapper" style="overflow-x: auto;">
                        <table class="evaluation-metrics-table">
                            <thead>
                                <tr>
                                    <th>Weather Target</th>
                                    <th>Baseline MAE</th>
                                    <th>Baseline RMSE</th>
                                    <th>ML MAE</th>
                                    <th>ML RMSE</th>
                                    <th>ML R²</th>
                                    <th>Performance Comparison</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${targetRows}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        // 5. Collapsible 24-Hour Prediction Breakdown Table
        const hourlyRowsHTML = preds.map(p => `
            <tr>
                <td>${new Date(p.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })}</td>
                <td><strong>${p.temperature !== null ? p.temperature + '°C' : '—'}</strong></td>
                <td>${p.rainfall !== null ? p.rainfall + ' mm' : '—'}</td>
                <td>${p.humidity !== null ? p.humidity + '%' : '—'}</td>
                <td>${p.wind_speed !== null ? p.wind_speed + ' km/h' : '—'}</td>
            </tr>
        `).join('');

        const hourlyBreakdownHTML = `
            <div class="hourly-pred-panel glass-panel" style="margin-top: 20px; padding: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div>
                        <h4 style="font-size: 1rem; font-weight: 700; margin-bottom: 2px;">
                            <i class="fa-solid fa-list-ol" style="color: #818cf8;"></i> 24-Hour AI Prediction Breakdown
                        </h4>
                        <span style="font-size: 0.8rem; color: var(--clr-text-muted);">Hourly predicted values from the current forecast horizon</span>
                    </div>
                    <button class="btn btn-secondary btn-sm" id="btn-toggle-pred-table">
                        <i class="fa-solid fa-table"></i> Toggle Hourly Table
                    </button>
                </div>
                <div id="pred-hourly-table-container" class="hidden" style="overflow-x: auto;">
                    <table class="evaluation-metrics-table">
                        <thead>
                            <tr>
                                <th>Target Timestamp</th>
                                <th>Predicted Temp</th>
                                <th>Predicted Rain</th>
                                <th>Predicted Humidity</th>
                                <th>Predicted Wind</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${hourlyRowsHTML}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        wrapper.innerHTML = `
            ${heroCardsHTML}
            ${transparencyHTML}
            ${chartSectionHTML}
            ${evaluationTableHTML}
            ${hourlyBreakdownHTML}
        `;

        // Initialize event listeners and chart
        setTimeout(() => {
            drawPredictionComparisonChart();

            const togglePredBtn = $('#btn-toggle-pred-table');
            const predTable = $('#pred-hourly-table-container');
            if (togglePredBtn && predTable) {
                togglePredBtn.addEventListener('click', () => {
                    predTable.classList.toggle('hidden');
                });
            }

            const toggleEvalBtn = $('#btn-toggle-eval-table');
            const evalTable = $('#eval-table-container');
            if (toggleEvalBtn && evalTable) {
                toggleEvalBtn.addEventListener('click', () => {
                    evalTable.classList.toggle('hidden');
                });
            }
        }, 60);
    }

    function setPredictionChartTarget(target) {
        predictionChartTarget = target;
        $$('.target-pill').forEach(btn => btn.classList.remove('active'));
        const activeBtn = $(`.target-pill[onclick*="${target}"]`);
        if (activeBtn) activeBtn.classList.add('active');
        drawPredictionComparisonChart();
    }

    function drawPredictionComparisonChart() {
        const canvas = document.getElementById('prediction-comparison-canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        const width = rect.width || 600;
        const height = 260;

        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, width, height);

        const target = predictionChartTarget || 'temperature';
        const targetConfig = {
            'temperature': { unit: '°C', color: '#fbbf24', obsKey: 'temperature', predKey: 'temperature' },
            'precipitation': { unit: 'mm', color: '#60a5fa', obsKey: 'precipitation', predKey: 'rainfall' },
            'relative_humidity': { unit: '%', color: '#34d399', obsKey: 'relative_humidity', predKey: 'humidity' },
            'wind_speed': { unit: 'km/h', color: '#a78bfa', obsKey: 'wind_speed', predKey: 'wind_speed' },
        }[target] || { unit: '', color: '#818cf8', obsKey: 'temperature', predKey: 'temperature' };

        // Build data points
        // 1. Observed recent points (up to 12 recent hours)
        const obsList = (lastObservedHourlyData || []).slice(0, 12).map(r => ({
            timestamp: new Date(r.timestamp),
            value: parseFloat(r[targetConfig.obsKey]) || 0.0,
            type: 'observed',
        }));

        // 2. Predicted future points (next 24 hours)
        const predList = (lastPredictionData?.predictions || []).map(p => ({
            timestamp: new Date(p.timestamp),
            value: parseFloat(p[targetConfig.predKey]) || 0.0,
            type: 'predicted',
        }));

        const allPoints = [...obsList, ...predList];
        if (allPoints.length === 0) return;

        const padding = { top: 25, right: 35, bottom: 40, left: 50 };
        const chartW = width - padding.left - padding.right;
        const chartH = height - padding.top - padding.bottom;

        const values = allPoints.map(p => p.value);
        let minVal = Math.min(...values);
        let maxVal = Math.max(...values);
        if (minVal === maxVal) {
            minVal -= 1;
            maxVal += 1;
        }
        if (target === 'precipitation' || target === 'wind_speed') {
            minVal = Math.max(0, minVal);
        }
        const range = (maxVal - minVal) || 1;

        // Draw gridlines
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.font = '11px Inter, sans-serif';
        ctx.fillStyle = 'rgba(232, 245, 233, 0.55)';
        ctx.textAlign = 'right';

        const yTicks = 4;
        for (let i = 0; i <= yTicks; i++) {
            const val = (minVal + (range * i) / yTicks).toFixed(target === 'precipitation' ? 1 : 0);
            const y = padding.top + chartH - (i / yTicks) * chartH;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();
            ctx.fillText(`${val} ${targetConfig.unit}`, padding.left - 8, y + 4);
        }

        // Coordinate projection
        const coords = allPoints.map((p, i) => {
            const x = padding.left + (i / (allPoints.length - 1)) * chartW;
            const y = padding.top + chartH - ((p.value - minVal) / range) * chartH;
            return { x, y, ...p };
        });

        const obsCoords = coords.filter(c => c.type === 'observed');
        const predCoords = coords.filter(c => c.type === 'predicted');

        // Draw Observed segment (Solid line)
        if (obsCoords.length > 1) {
            ctx.save();
            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            obsCoords.forEach((p, i) => {
                if (i === 0) ctx.moveTo(p.x, p.y);
                else ctx.lineTo(p.x, p.y);
            });
            ctx.stroke();
            ctx.restore();
        }

        // Connect transition point between observed and predicted
        if (obsCoords.length > 0 && predCoords.length > 0) {
            ctx.save();
            ctx.strokeStyle = 'rgba(167, 139, 250, 0.5)';
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(obsCoords[obsCoords.length - 1].x, obsCoords[obsCoords.length - 1].y);
            ctx.lineTo(predCoords[0].x, predCoords[0].y);
            ctx.stroke();
            ctx.restore();

            // Vertical separator at transition (NOW / FORECAST START)
            const splitX = (obsCoords[obsCoords.length - 1].x + predCoords[0].x) / 2;
            ctx.save();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            ctx.moveTo(splitX, padding.top);
            ctx.lineTo(splitX, padding.top + chartH);
            ctx.stroke();
            ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
            ctx.font = '10px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('FORECAST HORIZON ▶', splitX, padding.top - 6);
            ctx.restore();
        }

        // Draw Predicted segment (Dashed line with glow)
        if (predCoords.length > 1) {
            ctx.save();
            ctx.strokeStyle = '#a78bfa';
            ctx.lineWidth = 2.5;
            ctx.setLineDash([6, 4]);
            ctx.shadowColor = 'rgba(167, 139, 250, 0.5)';
            ctx.shadowBlur = 8;
            ctx.beginPath();
            predCoords.forEach((p, i) => {
                if (i === 0) ctx.moveTo(p.x, p.y);
                else ctx.lineTo(p.x, p.y);
            });
            ctx.stroke();
            ctx.restore();
        }

        // Draw point markers & X labels
        ctx.textAlign = 'center';
        coords.forEach((p, i) => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.type === 'observed' ? 4 : 4.5, 0, Math.PI * 2);
            ctx.fillStyle = p.type === 'observed' ? '#0284c7' : '#7c3aed';
            ctx.fill();
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = '#ffffff';
            ctx.stroke();

            // Show time labels for every 4th point or ends
            const showLabel = (coords.length <= 12) || (i % 4 === 0) || (i === coords.length - 1);
            if (showLabel) {
                const label = p.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                ctx.fillStyle = p.type === 'observed' ? 'rgba(56, 189, 248, 0.7)' : 'rgba(167, 139, 250, 0.8)';
                ctx.fillText(label, p.x, height - 12);
            }
        });
    }

    async function refreshPredictionForFarm(farmId) {
        const btn = $('#btn-refresh-prediction');
        if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Predicting...';
        toast('Recomputing AI weather predictions...', 'info');
        try {
            await loadPredictionDashboard(farmId, true);
            toast('AI weather predictions recomputed! 🤖', 'success');
        } catch (err) {
            toast(`Failed to predict: ${err.message}`, 'error');
        } finally {
            if (btn) btn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Re-predict';
        }
    }

    function bindPredictionDashboard() {
        const btnRefresh = $('#btn-refresh-prediction');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => {
                if (currentWeatherFarmId) {
                    refreshPredictionForFarm(currentWeatherFarmId);
                } else {
                    toast('Please select a farm plot first.', 'error');
                }
            });
        }
    }

    // ── Dashboard ─────────────────────────────────────────────

    async function loadDashboard() {
        const grid = $('#farms-grid');
        grid.innerHTML = `
            <div class="empty-state glass-panel">
                <i class="fa-solid fa-spinner fa-spin"></i>
                <p>Loading your farm data...</p>
            </div>
        `;

        try {
            const data = await API.getDashboard();

            // Populate farmer header
            if (data.farmer) {
                $('#dash-farmer-name').textContent = data.farmer.full_name || 'Farmer';
                $('#dash-farmer-phone').textContent = data.farmer.phone_number || '--';
                $('#dash-farmer-email').textContent = data.farmer.email || '--';
                const location = [data.farmer.district, data.farmer.state].filter(Boolean).join(', ');
                $('#dash-farmer-location').textContent = location || '--';
                $('#dash-farmer-lang').textContent = data.farmer.preferred_language || '--';

                // Update header
                $('#header-user-name').textContent = data.farmer.full_name || 'Farmer';
                API.setUser(data.farmer);
            }

            // Update stats
            $('#stat-total-farms').textContent = data.summary?.total_farms || 0;
            $('#stat-total-crops').textContent = data.summary?.total_crops || 0;

            // Calculate total area
            let totalArea = 0;
            let areaUnit = '';
            if (data.farms && data.farms.length > 0) {
                data.farms.forEach(f => {
                    totalArea += parseFloat(f.farm_area) || 0;
                    if (!areaUnit) areaUnit = f.farm_area_unit || '';
                });
            }
            $('#stat-total-area').textContent = `${totalArea.toFixed(1)} ${formatUnit(areaUnit)}`;

            // Render farm cards
            renderFarmCards(data.farms || []);

            // Cache farmer farms for modals and queries
            cachedFarmerFarms = data.farms || [];

            // Populate weather dropdown & trigger weather and soil loads
            populateWeatherFarmDropdown(data.farms || []);
            if (data.farms && data.farms.length > 0) {
                const targetFarmId = currentWeatherFarmId || data.farms[0].id;
                loadWeatherDashboard(targetFarmId);
                loadSoilDashboard(targetFarmId);
                loadPredictionDashboard(targetFarmId);
            } else {
                const wrapper = $('#weather-content-wrapper');
                if (wrapper) {
                    wrapper.innerHTML = `
                        <div class="empty-state">
                            <i class="fa-solid fa-tractor" style="font-size: 2rem; color: var(--clr-text-dim); margin-bottom: 10px;"></i>
                            <p>Please register a farm plot first to view localized weather forecasts.</p>
                        </div>
                    `;
                }
                const soilWrapper = $('#soil-content-wrapper');
                if (soilWrapper) {
                    soilWrapper.innerHTML = `
                        <div class="empty-state">
                            <i class="fa-solid fa-seedling" style="font-size: 2rem; color: var(--clr-text-dim); margin-bottom: 10px;"></i>
                            <p>Please register a farm plot first to monitor soil moisture and environmental conditions.</p>
                        </div>
                    `;
                }
                const predWrapper = $('#prediction-content-wrapper');
                if (predWrapper) {
                    predWrapper.innerHTML = `
                        <div class="empty-state">
                            <i class="fa-solid fa-brain" style="font-size: 2rem; color: var(--clr-text-dim); margin-bottom: 10px;"></i>
                            <p>Please register a farm plot first to generate AI weather predictions.</p>
                        </div>
                    `;
                }
            }

        } catch (err) {
            if (err.status === 401) {
                API.logout();
                showGuestUI();
                navigateTo('auth');
                toast('Session expired. Please sign in again.', 'error');
                return;
            }
            grid.innerHTML = `
                <div class="empty-state glass-panel">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>Failed to load dashboard: ${escapeHTML(err.message)}</p>
                </div>
            `;
        }
    }

    function formatUnit(unit) {
        const map = {
            'acre': 'Acres',
            'ha': 'Ha',
            'sqm': 'sqm',
            'guntha': 'Guntha',
            'bigha': 'Bigha',
        };
        return map[unit] || unit || '';
    }

    function formatIrrigation(type) {
        const map = {
            'rain_fed': 'Rain-fed',
            'borewell': 'Borewell',
            'canal': 'Canal',
            'drip': 'Drip',
            'sprinkler': 'Sprinkler',
            'other': 'Other',
        };
        return map[type] || type || 'N/A';
    }

    function renderFarmCards(farms) {
        const grid = $('#farms-grid');

        if (!farms.length) {
            grid.innerHTML = `
                <div class="empty-state glass-panel">
                    <i class="fa-solid fa-tractor"></i>
                    <p>No farms registered yet. Click "Add New Farm" to add your first plot.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = farms.map(farm => {
            const loc = farm.location || {};
            const lat = loc.latitude || '—';
            const lng = loc.longitude || '—';
            const locationStr = [loc.village, loc.district, loc.state].filter(Boolean).join(', ');

            const cropsHTML = (farm.crops && farm.crops.length > 0)
                ? farm.crops.map(c => `
                    <span class="crop-tag">
                        <i class="fa-solid fa-leaf"></i> ${escapeHTML(c.crop_name)}
                        ${c.growth_stage ? `<span class="badge badge-primary" style="font-size:10px; padding:1px 6px;">${escapeHTML(c.growth_stage.name)}</span>` : ''}
                    </span>
                `).join('')
                : '<span style="font-size:12px; color:var(--clr-text-dim);">No crops yet</span>';

            return `
                <div class="farm-card">
                    <div class="farm-card-header">
                        <h4>${escapeHTML(farm.farm_name)}</h4>
                        <button class="btn btn-danger btn-sm" onclick="App.deleteFarm(${farm.id})" title="Delete Farm">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                    <div class="farm-card-meta">
                        <span class="meta-chip"><i class="fa-solid fa-expand"></i> ${escapeHTML(farm.farm_area)} ${formatUnit(farm.farm_area_unit)}</span>
                        <span class="meta-chip"><i class="fa-solid fa-droplet"></i> ${formatIrrigation(farm.irrigation_type)}</span>
                        ${locationStr ? `<span class="meta-chip"><i class="fa-solid fa-location-dot"></i> ${escapeHTML(locationStr)}</span>` : ''}
                    </div>
                    <div class="farm-card-coords">
                        <i class="fa-solid fa-satellite"></i> ${lat}, ${lng}
                    </div>
                    <div class="farm-card-crops">
                        <h5><i class="fa-solid fa-seedling"></i> Crops (${farm.crops_count || 0})</h5>
                        ${cropsHTML}
                    </div>
                    <div class="farm-card-actions" style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn btn-primary btn-sm" onclick="App.selectFarmWeather(${farm.id})">
                            <i class="fa-solid fa-cloud-sun"></i> View Weather
                        </button>
                        <button class="btn btn-secondary btn-sm" onclick="App.openAddCropModal(${farm.id})">
                            <i class="fa-solid fa-plus"></i> Add Crop
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    // ── Dashboard Actions ─────────────────────────────────────

    function bindDashboard() {
        $('#btn-dash-add-farm').addEventListener('click', () => {
            $('#modal-add-farm').classList.remove('hidden');
            initModalMap();
        });

        const farmSelect = $('#weather-farm-select');
        if (farmSelect) {
            farmSelect.addEventListener('change', (e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val)) {
                    currentWeatherFarmId = val;
                    loadWeatherDashboard(val);
                    loadSoilDashboard(val);
                    loadPredictionDashboard(val);
                }
            });
        }

        const btnRefresh = $('#btn-refresh-weather');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => {
                if (currentWeatherFarmId) {
                    refreshWeatherForFarm(currentWeatherFarmId);
                } else {
                    toast('Please select a farm first.', 'error');
                }
            });
        }
    }

    async function handleDeleteFarm(farmId) {
        if (!confirm('Are you sure you want to delete this farm and all its crops?')) return;

        try {
            await API.deleteFarm(farmId);
            toast('Farm deleted successfully.', 'success');
            loadDashboard();
        } catch (err) {
            toast(err.message, 'error');
        }
    }

    function openAddCropModal(farmId) {
        $('#mc-farm-id').value = farmId;
        $('#form-add-crop').reset();
        $('#mc-farm-id').value = farmId;
        populateGrowthStageDropdowns();
        loadGrowthStages();
        $('#modal-add-crop').classList.remove('hidden');
    }

    // ── Modals ────────────────────────────────────────────────

    function bindModals() {
        // Close buttons
        $('#modal-add-farm-close').addEventListener('click', () => {
            $('#modal-add-farm').classList.add('hidden');
            destroyModalMap();
        });

        $('#modal-add-crop-close').addEventListener('click', () => {
            $('#modal-add-crop').classList.add('hidden');
        });

        // Overlay click to close
        $$('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    overlay.classList.add('hidden');
                    if (overlay.id === 'modal-add-farm') destroyModalMap();
                }
            });
        });

        // Add Farm form
        $('#form-add-farm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button[type="submit"]');
            const payload = {
                farm_name: $('#mf-name').value.trim(),
                farm_area: parseFloat($('#mf-area').value),
                farm_area_unit: $('#mf-unit').value,
                irrigation_type: $('#mf-irrigation').value,
                latitude: parseFloat($('#mf-lat').value),
                longitude: parseFloat($('#mf-lng').value),
            };

            if (!payload.farm_name || !payload.farm_area || isNaN(payload.latitude) || isNaN(payload.longitude)) {
                toast('Please fill in all required fields.', 'error');
                return;
            }

            setLoading(btn, true);
            try {
                await API.createFarm(payload);
                toast('Farm added successfully! 🌾', 'success');
                $('#modal-add-farm').classList.add('hidden');
                destroyModalMap();
                e.target.reset();
                loadDashboard();
            } catch (err) {
                toast(err.message, 'error');
            } finally {
                setLoading(btn, false);
            }
        });

        // Add Crop form
        $('#form-add-crop').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button[type="submit"]');
            const farmId = parseInt($('#mc-farm-id').value);

            const payload = {
                crop_name: $('#mc-crop-name').value.trim(),
                sowing_date: $('#mc-sowing').value,
            };

            const variety = $('#mc-variety').value.trim();
            if (variety) payload.crop_variety = variety;

            const harvest = $('#mc-harvest').value;
            if (harvest) payload.expected_harvest_date = harvest;

            const stageId = $('#mc-stage').value;
            const parsedStageId = parseInt(stageId, 10);
            if (!isNaN(parsedStageId)) payload.growth_stage = parsedStageId;

            if (!payload.crop_name || !payload.sowing_date) {
                toast('Crop name and sowing date are required.', 'error');
                return;
            }

            setLoading(btn, true);
            try {
                await API.createCrop(farmId, payload);
                toast('Crop added to farm! 🌱', 'success');
                $('#modal-add-crop').classList.add('hidden');
                e.target.reset();
                loadDashboard();
            } catch (err) {
                toast(err.message, 'error');
            } finally {
                setLoading(btn, false);
            }
        });
    }

    // ── Public API (for inline event handlers) ────────────────

    return {
        init,
        deleteFarm: handleDeleteFarm,
        openAddCropModal,
        selectFarmWeather: (farmId) => {
            currentWeatherFarmId = farmId;
            const select = $('#weather-farm-select');
            if (select) select.value = farmId;
            loadWeatherDashboard(farmId);
            loadSoilDashboard(farmId);
            loadPredictionDashboard(farmId);
            const section = document.querySelector('.weather-dashboard-section');
            if (section) section.scrollIntoView({ behavior: 'smooth' });
        },
        refreshWeatherForFarm,
        refreshSoilForFarm,
        refreshPredictionForFarm,
        openSensorIngestModal,
        loadSoilDashboard,
        loadPredictionDashboard,
        setPredictionChartTarget,
    };
})();

// ── Boot ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', App.init);
