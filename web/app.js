// --- Safe Icon Loader ---
function safeCreateIcons() {
    try {
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    } catch (e) {
        console.error("Lucide failed to load icons:", e);
    }
}


// --- Global State ---
let currentUser = null;
let activeTab = 'dashboard';
let apiBaseUrl = window.location.origin;
let pywebviewReady = false;

window.addEventListener('pywebviewready', function() {
    pywebviewReady = true;
    console.log('pywebview API ready');
});

// For Lecturer live attendance polling
let liveAttendanceInterval = null;

// For Student enrollment state
let enrollmentState = {
    step: 1,
    slots: Array(5).fill(null),
    stagedCount: 0,
    cameraActive: false
};

// --- Toast Notifications ---
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'info';
    if (type === 'success') icon = 'check-circle';
    if (type === 'error') icon = 'alert-triangle';
    if (type === 'warning') icon = 'alert-circle';
    
    toast.innerHTML = `
        <i data-lucide="${icon}"></i>
        <span>${message}</span>
    `;
    container.appendChild(toast);
    safeCreateIcons();
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// --- API Wrapper ---
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${apiBaseUrl}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'API Call failed');
        }
        return await response.json();
    } catch (error) {
        showToast(error.message, 'error');
        throw error;
    }
}

// --- App Bootstrap ---
document.addEventListener('DOMContentLoaded', () => {
    safeCreateIcons();
    setupEventListeners();
    
    // Check if user is cached in localStorage
    const cachedUser = localStorage.getItem('attendiq_user');
    if (cachedUser) {
        currentUser = JSON.parse(cachedUser);
        launchDashboard();
    }

    // Register Service Worker for PWA support
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('./service-worker.js')
            .then(reg => console.log('ServiceWorker registered:', reg.scope))
            .catch(err => console.warn('ServiceWorker registration failed:', err));
    }
});

function setupEventListeners() {
    // Login Form
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;
        
        try {
            const user = await apiCall('/api/auth/login', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            currentUser = user;
            localStorage.setItem('attendiq_user', JSON.stringify(user));
            showToast(`Welcome back, ${user.full_name}!`, 'success');
            launchDashboard();
        } catch (err) {}
    });

    // Logout
    document.getElementById('logout-btn').addEventListener('click', () => {
        stopLiveAttendancePolling();
        localStorage.removeItem('attendiq_user');
        currentUser = null;
        document.getElementById('dashboard-shell').classList.add('hidden');
        document.getElementById('login-screen').classList.remove('hidden');
        document.getElementById('username').value = '';
        document.getElementById('password').value = '';
    });

    // Modal Close
    document.getElementById('modal-close-btn').addEventListener('click', hideModal);
}

// --- Modal Management ---
function showModal(title, bodyHtml) {
    document.getElementById('modal-title').innerText = title;
    document.getElementById('modal-body').innerHTML = bodyHtml;
    document.getElementById('modal-container').classList.remove('hidden');
    safeCreateIcons();
}

function hideModal() {
    document.getElementById('modal-container').classList.add('hidden');
    document.getElementById('modal-body').innerHTML = '';
}

// --- Dashboard & Navigation ---
function launchDashboard() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('dashboard-shell').classList.remove('hidden');
    
    document.getElementById('user-display-name').innerText = currentUser.full_name;
    document.getElementById('user-display-role').innerText = currentUser.role;

    // Load Sidebar Navigation based on Role
    const navList = document.getElementById('nav-list');
    navList.innerHTML = '';
    
    const roleNavs = {
        admin: [
            { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard' },
            { id: 'classes', label: 'Classes', icon: 'book-open' },
            { id: 'users', label: 'Users', icon: 'users' },
            { id: 'bias', label: 'Bias Evaluation', icon: 'scale' },
            { id: 'settings', label: 'Settings', icon: 'settings' }
        ],
        lecturer: [
            { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard' },
            { id: 'live', label: 'Live Session', icon: 'video' },
            { id: 'history', label: 'History & Logs', icon: 'file-text' }
        ],
        student: [
            { id: 'dashboard', label: 'My Attendance', icon: 'calendar-check' },
            { id: 'enroll', label: 'Face Enrollment', icon: 'scan-face' }
        ]
    };

    const navs = roleNavs[currentUser.role] || [];
    navs.forEach(nav => {
        const li = document.createElement('li');
        li.innerHTML = `
            <a class="nav-item ${nav.id === activeTab ? 'active' : ''}" data-tab="${nav.id}">
                <i data-lucide="${nav.icon}"></i>
                <span>${nav.label}</span>
            </a>
        `;
        navList.appendChild(li);
    });

    safeCreateIcons();

    // Setup nav click events
    document.querySelectorAll('.nav-item').forEach(el => {
        el.addEventListener('click', (e) => {
            document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
            const tabId = el.getAttribute('data-tab');
            el.classList.add('active');
            switchTab(tabId);
        });
    });

    // Default tab
    switchTab(navs[0].id);
}

function switchTab(tabId) {
    activeTab = tabId;
    
    // Stop live attendance polling if leaving Live Session tab
    if (tabId !== 'live') {
        stopLiveAttendancePolling();
    }
    
    // Set Header Title
    const pageTitleMap = {
        dashboard: currentUser.role === 'student' ? 'My Attendance' : 'Dashboard',
        classes: 'Class Management',
        users: 'User Directory',
        bias: 'Bias & Fairness Evaluation',
        settings: 'System Configuration',
        live: 'Live Attendance Session',
        history: 'Attendance History Logs',
        enroll: 'Face Registration Wizard'
    };
    document.getElementById('page-title').innerText = pageTitleMap[tabId] || 'Dashboard';
    
    const container = document.getElementById('tab-content');
    container.innerHTML = `<div class="loader-wrapper"><div class="pulse"></div> Loading...</div>`;
    
    // Route content builder
    if (currentUser.role === 'admin') {
        if (tabId === 'dashboard') buildAdminDashboard(container);
        else if (tabId === 'classes') buildAdminClasses(container);
        else if (tabId === 'users') buildAdminUsers(container);
        else if (tabId === 'bias') buildAdminBias(container);
        else if (tabId === 'settings') buildAdminSettings(container);
    } else if (currentUser.role === 'lecturer') {
        if (tabId === 'dashboard') buildLecturerDashboard(container);
        else if (tabId === 'live') buildLecturerLive(container);
        else if (tabId === 'history') buildLecturerHistory(container);
    } else if (currentUser.role === 'student') {
        if (tabId === 'dashboard') buildStudentDashboard(container);
        else if (tabId === 'enroll') buildStudentEnrollment(container);
    }
}

// ==========================================
// ADMIN DASHBOARD & SCREENS
// ==========================================

async function buildAdminDashboard(container) {
    try {
        const users = await apiCall('/api/users');
        const classes = await apiCall('/api/classes');
        
        const studentsCount = users.filter(u => u.role === 'student').length;
        const lecturersCount = users.filter(u => u.role === 'lecturer').length;
        const enrolledFaces = users.filter(u => u.role === 'student' && u.face_enrolled).length;

        container.innerHTML = `
            <div class="dashboard-grid">
                <div class="col-3 dashboard-card glass stat-card">
                    <h3>Total Students</h3>
                    <div class="val">${studentsCount}</div>
                </div>
                <div class="col-3 dashboard-card glass stat-card">
                    <h3>Enrolled Faces</h3>
                    <div class="val text-success">${enrolledFaces}</div>
                </div>
                <div class="col-3 dashboard-card glass stat-card">
                    <h3>Total Lecturers</h3>
                    <div class="val">${lecturersCount}</div>
                </div>
                <div class="col-3 dashboard-card glass stat-card">
                    <h3>Total Classes</h3>
                    <div class="val">${classes.length}</div>
                </div>
                
                <div class="col-12 dashboard-card glass">
                    <div class="card-header">
                        <h3>Institution Directory Quick Access</h3>
                    </div>
                    <p style="color: var(--text-secondary)">Use the sidebar tabs to manage Classes, register Users, or run the Bias Analysis module.</p>
                </div>
            </div>
        `;
    } catch (e) {}
}

async function buildAdminClasses(container) {
    try {
        const classes = await apiCall('/api/classes');
        const lecturers = await apiCall('/api/users?role=lecturer');

        let rowsHtml = '';
        classes.forEach(c => {
            rowsHtml += `
                <tr>
                    <td><code>${c.code}</code></td>
                    <td><strong>${c.name}</strong></td>
                    <td>${c.lecturer_name || 'Unassigned'}</td>
                    <td>${c.schedule || '—'}</td>
                    <td>${c.room || '—'}</td>
                    <td><span class="status-badge">${c.enrolled_count} Enrolled</span></td>
                    <td>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn ghost-btn btn-icon" onclick="manageClassEnrollment(${c.id}, '${c.name}')" title="Manage Students">
                                <i data-lucide="users"></i>
                            </button>
                            <button class="btn danger-btn btn-icon" onclick="deleteClass(${c.id})" title="Delete Class">
                                <i data-lucide="trash-2"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        });

        container.innerHTML = `
            <div class="dashboard-grid">
                <div class="col-12 dashboard-card glass">
                    <div class="card-header">
                        <h3>Classes</h3>
                        <button class="btn primary-btn" id="create-class-btn">
                            <i data-lucide="plus"></i> New Class
                        </button>
                    </div>
                    <div class="table-wrapper">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Code</th>
                                    <th>Class Name</th>
                                    <th>Lecturer</th>
                                    <th>Schedule</th>
                                    <th>Room</th>
                                    <th>Students</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${rowsHtml || '<tr><td colspan="7" style="text-align: center;">No classes created yet.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
        safeCreateIcons();

        document.getElementById('create-class-btn').addEventListener('click', () => {
            let lecturerOptions = '';
            lecturers.forEach(l => {
                lecturerOptions += `<option value="${l.id}">${l.full_name}</option>`;
            });

            showModal('Create New Class', `
                <form id="create-class-form">
                    <div class="input-group">
                        <label>Class Name</label>
                        <div class="input-wrapper"><input type="text" id="c-name" required></div>
                    </div>
                    <div class="input-group">
                        <label>Class Code</label>
                        <div class="input-wrapper"><input type="text" id="c-code" required></div>
                    </div>
                    <div class="input-group">
                        <label>Lecturer</label>
                        <div class="input-wrapper">
                            <select id="c-lecturer" required>
                                ${lecturerOptions || '<option value="" disabled>No lecturers registered</option>'}
                            </select>
                        </div>
                    </div>
                    <div class="input-group">
                        <label>Schedule (e.g. Mon 10:00)</label>
                        <div class="input-wrapper"><input type="text" id="c-sched"></div>
                    </div>
                    <div class="input-group">
                        <label>Room</label>
                        <div class="input-wrapper"><input type="text" id="c-room"></div>
                    </div>
                    <button type="submit" class="btn primary-btn btn-full">Create Class</button>
                </form>
            `);

            document.getElementById('create-class-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const body = {
                    name: document.getElementById('c-name').value,
                    code: document.getElementById('c-code').value,
                    schedule: document.getElementById('c-sched').value,
                    room: document.getElementById('c-room').value
                };
                const lecturer_id = document.getElementById('c-lecturer').value;
                try {
                    await apiCall(`/api/classes?lecturer_id=${lecturer_id}`, {
                        method: 'POST',
                        body: JSON.stringify(body)
                    });
                    showToast('Class created successfully', 'success');
                    hideModal();
                    buildAdminClasses(container);
                } catch(err){}
            });
        });

    } catch (e) {}
}

async function manageClassEnrollment(classId, className) {
    try {
        const enrollments = await apiCall(`/api/classes/${classId}/enrollments`);
        
        let enrolledHtml = '';
        enrollments.enrolled.forEach(s => {
            enrolledHtml += `
                <div style="display: flex; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-color); align-items: center;">
                    <span>${s.full_name} (${s.student_id || 'no ID'})</span>
                    <button class="btn danger-btn" style="padding: 4px 8px;" onclick="unenrollStudent(${classId}, ${s.id}, '${className}')">Remove</button>
                </div>
            `;
        });

        let unenrolledOptions = '<option value="">Select student to enroll...</option>';
        enrollments.unenrolled.forEach(s => {
            unenrolledOptions += `<option value="${s.id}">${s.full_name} (${s.student_id || 'no ID'})</option>`;
        });

        showModal(`Enrollments — ${className}`, `
            <div style="margin-bottom: 16px;">
                <label style="display: block; font-weight: 600; margin-bottom: 8px; font-size: 0.85rem; color: var(--text-secondary)">Enroll Student</label>
                <div style="display: flex; gap: 8px;">
                    <div class="input-wrapper" style="flex: 1;">
                        <select id="enroll-student-select">${unenrolledOptions}</select>
                    </div>
                    <button class="btn primary-btn" onclick="enrollStudentAction(${classId}, '${className}')">Add</button>
                </div>
            </div>
            <div style="max-height: 240px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: var(--radius-md);">
                ${enrolledHtml || '<p style="padding: 16px; text-align: center; color: var(--text-secondary)">No students enrolled yet.</p>'}
            </div>
        `);
    } catch(e){}
}

async function enrollStudentAction(classId, className) {
    const studentId = document.getElementById('enroll-student-select').value;
    if (!studentId) return;
    try {
        await apiCall(`/api/classes/${classId}/enrollments?student_id=${studentId}`, { method: 'POST' });
        showToast('Student enrolled successfully', 'success');
        manageClassEnrollment(classId, className);
    } catch (e) {}
}

async function unenrollStudent(classId, studentId, className) {
    try {
        await apiCall(`/api/classes/${classId}/enrollments/${studentId}`, { method: 'DELETE' });
        showToast('Student removed from class', 'info');
        manageClassEnrollment(classId, className);
    } catch(e){}
}

async function deleteClass(classId) {
    if (!confirm('Are you sure you want to delete this class? All associated enrollments will be deleted.')) return;
    try {
        await apiCall(`/api/classes/${classId}`, { method: 'DELETE' });
        showToast('Class deleted', 'info');
        switchTab('classes');
    } catch(e){}
}

async function buildAdminUsers(container) {
    try {
        const users = await apiCall('/api/users');
        let rowsHtml = '';
        users.forEach(u => {
            rowsHtml += `
                <tr>
                    <td><strong>${u.full_name}</strong></td>
                    <td><code>${u.username}</code></td>
                    <td><span class="status-badge" style="text-transform: uppercase;">${u.role}</span></td>
                    <td>${u.student_id || '—'}</td>
                    <td>${u.email || '—'}</td>
                    <td>
                        <span class="status-badge ${u.face_enrolled ? 'success' : 'muted'}" style="background-color: ${u.face_enrolled ? 'var(--success-glow)' : 'transparent'}">
                            ${u.face_enrolled ? '✓ Registered' : 'Not Registered'}
                        </span>
                    </td>
                    <td>
                        <button class="btn danger-btn btn-icon" onclick="deleteUser(${u.id})" title="Delete User">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </td>
                </tr>
            `;
        });

        container.innerHTML = `
            <div class="dashboard-grid">
                <div class="col-12 dashboard-card glass">
                    <div class="card-header">
                        <h3>Users Directory</h3>
                        <button class="btn primary-btn" id="create-user-btn">
                            <i data-lucide="plus"></i> New User
                        </button>
                    </div>
                    <div class="table-wrapper">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Full Name</th>
                                    <th>Username</th>
                                    <th>Role</th>
                                    <th>Student/Staff ID</th>
                                    <th>Email</th>
                                    <th>Face Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${rowsHtml}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
        safeCreateIcons();

        document.getElementById('create-user-btn').addEventListener('click', () => {
            showModal('Create User Account', `
                <form id="create-user-form">
                    <div class="input-group">
                        <label>Full Name</label>
                        <div class="input-wrapper"><input type="text" id="u-fullname" required></div>
                    </div>
                    <div class="input-group">
                        <label>Username</label>
                        <div class="input-wrapper"><input type="text" id="u-username" required></div>
                    </div>
                    <div class="input-group">
                        <label>Password</label>
                        <div class="input-wrapper"><input type="password" id="u-password" required></div>
                    </div>
                    <div class="input-group">
                        <label>Role</label>
                        <div class="input-wrapper">
                            <select id="u-role" required>
                                <option value="student">Student</option>
                                <option value="lecturer">Lecturer</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                    </div>
                    <div class="input-group" id="student-only-fields">
                        <label>Department</label>
                        <div class="input-wrapper"><input type="text" id="u-dept" value="Computer Engineering"></div>
                        <label style="margin-top: 10px; display: block;">Level</label>
                        <div class="input-wrapper">
                            <select id="u-level">
                                <option value="500 Level">500 Level</option>
                                <option value="400 Level">400 Level</option>
                                <option value="300 Level">300 Level</option>
                                <option value="200 Level">200 Level</option>
                                <option value="100 Level">100 Level</option>
                            </select>
                        </div>
                    </div>
                    <div class="input-group">
                        <label>Student/Staff ID (optional)</label>
                        <div class="input-wrapper"><input type="text" id="u-id"></div>
                    </div>
                    <div class="input-group">
                        <label>Email (optional)</label>
                        <div class="input-wrapper"><input type="email" id="u-email"></div>
                    </div>
                    <button type="submit" class="btn primary-btn btn-full">Create Account</button>
                </form>
            `);

            // Dynamically show/hide student-specific fields
            document.getElementById('u-role').addEventListener('change', (e) => {
                const isStudent = e.target.value === 'student';
                document.getElementById('student-only-fields').style.display = isStudent ? 'block' : 'none';
            });

            document.getElementById('create-user-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const role = document.getElementById('u-role').value;
                const body = {
                    full_name: document.getElementById('u-fullname').value,
                    username: document.getElementById('u-username').value,
                    password: document.getElementById('u-password').value,
                    role: role,
                    student_id: document.getElementById('u-id').value || null,
                    email: document.getElementById('u-email').value || null,
                    department: role === 'student' ? document.getElementById('u-dept').value : null,
                    level: role === 'student' ? document.getElementById('u-level').value : null
                };
                try {
                    await apiCall('/api/users', {
                        method: 'POST',
                        body: JSON.stringify(body)
                    });
                    showToast('User created successfully', 'success');
                    hideModal();
                    buildAdminUsers(container);
                } catch(err){}
            });
        });

    } catch (e) {}
}

async function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user? All facial models and associated data will be deleted.')) return;
    try {
        await apiCall(`/api/users/${userId}`, { method: 'DELETE' });
        showToast('User deleted', 'info');
        switchTab('users');
    } catch(e){}
}

async function buildAdminSettings(container) {
    try {
        const c = await apiCall('/api/config');
        container.innerHTML = `
            <div class="dashboard-grid">
                <div class="col-8 dashboard-card glass">
                    <form id="settings-form">
                        <div class="input-group">
                            <label>Recognition Engine</label>
                            <div class="input-wrapper">
                                <select id="s-engine">
                                    <option value="auto" ${c.recognition_engine === 'auto' ? 'selected' : ''}>Auto (dlib default, LBPH fallback)</option>
                                    <option value="dlib" ${c.recognition_engine === 'dlib' ? 'selected' : ''}>Force dlib (128-d embeddings)</option>
                                    <option value="lbph" ${c.recognition_engine === 'lbph' ? 'selected' : ''}>Force LBPH (Gray Histograms)</option>
                                </select>
                            </div>
                        </div>
                        <div class="input-group">
                            <label>Camera Capture Index (e.g. 0 for built-in camera)</label>
                            <div class="input-wrapper"><input type="number" id="s-cam" value="${c.camera_index}"></div>
                        </div>
                        <div class="input-group">
                            <label>RTSP Stream URL (overrides Local Camera Index if set)</label>
                            <div class="input-wrapper"><input type="text" id="s-stream" value="${c.stream_url || ''}"></div>
                        </div>
                        <div class="input-group">
                            <label>Frame Scale Factor (lower is faster, default 0.25)</label>
                            <div class="input-wrapper"><input type="number" step="0.05" id="s-scale" value="${c.frame_scale}"></div>
                        </div>
                        <div class="input-group">
                            <label>Face Identification Tolerance (stricter is lower, default 0.6)</label>
                            <div class="input-wrapper"><input type="number" step="0.05" id="s-tol" value="${c.tolerance}"></div>
                        </div>
                        <button type="submit" class="btn primary-btn">Save Configurations</button>
                    </form>
                </div>
            </div>
        `;

        document.getElementById('settings-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const body = {
                camera_index: parseInt(document.getElementById('s-cam').value),
                frame_scale: parseFloat(document.getElementById('s-scale').value),
                tolerance: parseFloat(document.getElementById('s-tol').value),
                recognition_engine: document.getElementById('s-engine').value,
                stream_url: document.getElementById('s-stream').value
            };
            try {
                await apiCall('/api/config', {
                    method: 'POST',
                    body: JSON.stringify(body)
                });
                showToast('Configurations saved successfully', 'success');
            } catch (err) {}
        });
    } catch(e){}
}

async function buildAdminBias(container) {
    try {
        const data = await apiCall('/api/bias/results');
        
        if (data.status === 'no_metrics') {
            container.innerHTML = `
                <div class="dashboard-card glass" style="text-align: center; padding: 40px;">
                    <i data-lucide="scale" style="width: 48px; height: 48px; color: var(--text-secondary); margin-bottom: 16px;"></i>
                    <h3>Bias Evaluation Database Empty</h3>
                    <p style="margin-bottom: 24px; color: var(--text-secondary)">A sample evaluation dataset structure was generated at data/evaluation_dataset.<br>To perform bias evaluations, populate labels, and click evaluate below.</p>
                    <button class="btn primary-btn" id="run-eval-btn">Run Bias Evaluation</button>
                </div>
            `;
            safeCreateIcons();
            document.getElementById('run-eval-btn').addEventListener('click', runBiasEvalAction);
            return;
        }

        const overall = data.overall || {};
        container.innerHTML = `
            <div class="dashboard-grid">
                <div class="col-12" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <p style="color: var(--text-secondary)">Bias & Fairness metric breakdown using the Gender Shades methodology.</p>
                    <button class="btn ghost-btn" id="run-eval-btn"><i data-lucide="play"></i> Run Re-evaluation</button>
                </div>
                
                <div class="col-4 dashboard-card glass stat-card">
                    <h3>Overall Detection Rate</h3>
                    <div class="val text-success">${(overall.detection_rate * 100).toFixed(1)}%</div>
                </div>
                <div class="col-4 dashboard-card glass stat-card">
                    <h3>Overall Recognition Accuracy</h3>
                    <div class="val">${(overall.recognition_accuracy * 100).toFixed(1)}%</div>
                </div>
                <div class="col-4 dashboard-card glass stat-card">
                    <h3>Demographic Disparity Gap</h3>
                    <div class="val text-danger">${overall.disparity_gap ? (overall.disparity_gap * 100).toFixed(1) + '%' : 'N/A'}</div>
                </div>

                <div class="col-6 dashboard-card glass">
                    <div class="card-header"><h3>Accuracy by Skin Type (Fitzpatrick I-VI)</h3></div>
                    <div style="height: 240px; position: relative;">
                        <canvas id="skin-chart"></canvas>
                    </div>
                </div>
                
                <div class="col-6 dashboard-card glass">
                    <div class="card-header"><h3>Accuracy by Gender</h3></div>
                    <div style="height: 240px; position: relative;">
                        <canvas id="gender-chart"></canvas>
                    </div>
                </div>
            </div>
        `;
        safeCreateIcons();
        document.getElementById('run-eval-btn').addEventListener('click', runBiasEvalAction);

        // Render Charts
        const skinData = data.by_skin_type || {};
        const skinLabels = Object.keys(skinData).map(k => `Type ${k}`);
        const skinAccs = Object.values(skinData).map(v => (v.accuracy * 100).toFixed(1));

        new Chart(document.getElementById('skin-chart'), {
            type: 'bar',
            data: {
                labels: skinLabels,
                datasets: [{
                    label: 'Accuracy %',
                    data: skinAccs,
                    backgroundColor: '#e94560',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { min: 0, max: 100 }
                }
            }
        });

        const genderData = data.by_gender || {};
        const genderLabels = Object.keys(genderData);
        const genderAccs = Object.values(genderData).map(v => (v.accuracy * 100).toFixed(1));

        new Chart(document.getElementById('gender-chart'), {
            type: 'bar',
            data: {
                labels: genderLabels,
                datasets: [{
                    label: 'Accuracy %',
                    data: genderAccs,
                    backgroundColor: '#16c79a',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { min: 0, max: 100 }
                }
            }
        });

    } catch(e){}
}

async function runBiasEvalAction() {
    try {
        await apiCall('/api/bias/evaluate', { method: 'POST' });
        showToast('Bias evaluation job started. This takes a few seconds...', 'info');
        setTimeout(() => switchTab('bias'), 5000);
    } catch(e){}
}


// ==========================================
// LECTURER DASHBOARD & SCREENS
// ==========================================

async function buildLecturerDashboard(container) {
    try {
        const classes = await apiCall(`/api/classes?lecturer_id=${currentUser.id}`);
        container.innerHTML = `
            <div class="dashboard-grid">
                <div class="col-12 dashboard-card glass">
                    <div class="card-header">
                        <h3>My Classes Dashboard</h3>
                    </div>
                    <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-top: 12px;">
                        ${classes.map(c => `
                            <div class="dashboard-card glass" style="flex: 1; min-width: 250px; padding: 20px;">
                                <code>${c.code}</code>
                                <h3 style="margin: 8px 0;">${c.name}</h3>
                                <p style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 14px;">
                                    Room: ${c.room || 'N/A'}<br>
                                    Sched: ${c.schedule || 'N/A'}
                                </p>
                                <button class="btn primary-btn btn-full" onclick="switchTab('live')">Launch Live Session</button>
                            </div>
                        `).join('') || '<p style="color: var(--text-secondary)">No classes assigned to you.</p>'}
                    </div>
                </div>
            </div>
        `;
    } catch(e){}
}

async function buildLecturerLive(container) {
    try {
        const classes = await apiCall(`/api/classes?lecturer_id=${currentUser.id}`);
        const classOptions = classes.map(c => `<option value="${c.id}">${c.code} — ${c.name}</option>`).join('');

        container.innerHTML = `
            <div class="dashboard-grid">
                <div class="col-7 camera-section">
                    <div class="camera-viewport">
                        <img id="live-stream-feed" src="" alt="Webcam Live Stream" class="hidden">
                        <div id="live-stream-placeholder" style="text-align: center; color: var(--text-secondary)">
                            <i data-lucide="video" style="width: 48px; height: 48px; margin-bottom: 12px;"></i>
                            <p>Select a class and click Start Session to open camera</p>
                        </div>
                    </div>
                </div>
                
                <div class="col-5 dashboard-card glass" style="display: flex; flex-direction: column; max-height: 480px;">
                    <div class="input-group">
                        <label>Select Class</label>
                        <div class="input-wrapper">
                            <select id="session-class-select">
                                ${classOptions || '<option disabled selected>No classes assigned</option>'}
                            </select>
                        </div>
                    </div>

                    <div class="input-group">
                        <label>Camera Source</label>
                        <div class="input-wrapper">
                            <select id="session-camera-select">
                                <option value="0">Default Camera (0)</option>
                                <option value="1">External USB Camera (1)</option>
                                <option value="2">External USB Camera (2)</option>
                                <option value="3">External USB Camera (3)</option>
                            </select>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 12px; margin-bottom: 20px;">
                        <button class="btn success-btn" id="start-session-btn" style="flex: 1;">Start Session</button>
                        <button class="btn danger-btn" id="stop-session-btn" style="flex: 1;" disabled>Stop Session</button>
                    </div>

                    <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
                        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 8px; margin-bottom: 12px;">
                            <span style="font-weight: 600;">Present Students</span>
                            <button class="btn ghost-btn" style="padding: 2px 8px; font-size: 0.75rem;" id="manual-add-btn" disabled>+ Add Manually</button>
                        </div>
                        <div style="flex: 1; overflow-y: auto;" id="live-present-list">
                            <p style="text-align: center; color: var(--text-secondary); padding-top: 20px;">Present log is empty</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
        safeCreateIcons();

        const startBtn = document.getElementById('start-session-btn');
        const stopBtn = document.getElementById('stop-session-btn');
        const select = document.getElementById('session-class-select');
        const manualBtn = document.getElementById('manual-add-btn');

        startBtn.addEventListener('click', async () => {
            const classId = select.value;
            if (!classId) return;

            const cameraSource = document.getElementById('session-camera-select').value;

            try {
                await apiCall(`/api/session/start?class_id=${classId}&lecturer_id=${currentUser.id}&camera_source=${cameraSource}`, { method: 'POST' });
                showToast('Camera stream initialized', 'success');
                
                startBtn.disabled = true;
                stopBtn.disabled = false;
                select.disabled = true;
                manualBtn.disabled = false;
                
                document.getElementById('live-stream-placeholder').classList.add('hidden');
                const streamImg = document.getElementById('live-stream-feed');
                streamImg.src = `${apiBaseUrl}/api/session/video_feed?t=${Date.now()}`;
                streamImg.classList.remove('hidden');
                document.getElementById('system-status').classList.remove('hidden');

                startLiveAttendancePolling();
            } catch(e){}
        });

        stopBtn.addEventListener('click', async () => {
            try {
                await apiCall('/api/session/stop', { method: 'POST' });
                showToast('Camera session stopped', 'info');
                
                stopLiveAttendancePolling();
                
                startBtn.disabled = false;
                stopBtn.disabled = true;
                select.disabled = false;
                manualBtn.disabled = true;
                
                document.getElementById('live-stream-feed').classList.add('hidden');
                document.getElementById('live-stream-feed').src = '';
                document.getElementById('live-stream-placeholder').classList.remove('hidden');
                document.getElementById('system-status').classList.add('hidden');
            } catch(e){}
        });

        manualBtn.addEventListener('click', async () => {
            const classId = select.value;
            try {
                const students = await apiCall(`/api/classes/${classId}/enrollments`);
                let options = '<option value="">Select student...</option>';
                const allStudents = [...students.enrolled, ...students.unenrolled];
                allStudents.forEach(s => {
                    const tag = students.enrolled.some(e => e.id === s.id) ? '' : ' (unenrolled)';
                    options += `<option value="${s.id}">${s.full_name}${tag}</option>`;
                });

                showModal('Log Manual Attendance', `
                    <form id="manual-log-form">
                        <div class="input-group">
                            <label>Student</label>
                            <div class="input-wrapper">
                                <select id="manual-student-select">${options}</select>
                            </div>
                        </div>
                        <button type="submit" class="btn primary-btn btn-full">Mark Present</button>
                    </form>
                `);

                document.getElementById('manual-log-form').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const studentId = document.getElementById('manual-student-select').value;
                    if (!studentId) return;
                    try {
                        await apiCall('/api/attendance/manual', {
                            method: 'POST',
                            body: JSON.stringify({
                                student_id: parseInt(studentId),
                                class_id: parseInt(classId),
                                marked_by: currentUser.id
                            })
                        });
                        showToast('Attendance logged manually', 'success');
                        hideModal();
                        pollLiveSessionData(); // force list update
                    } catch(err){}
                });

            } catch (err) {}
        });

    } catch(e){}
}

function startLiveAttendancePolling() {
    stopLiveAttendancePolling();
    pollLiveSessionData();
    liveAttendanceInterval = setInterval(pollLiveSessionData, 1800);
}

function stopLiveAttendancePolling() {
    if (liveAttendanceInterval) {
        clearInterval(liveAttendanceInterval);
        liveAttendanceInterval = null;
    }
}

async function pollLiveSessionData() {
    try {
        const data = await apiCall('/api/session/live');
        const listDiv = document.getElementById('live-present-list');
        if (!listDiv) return;

        if (data.marked.length === 0) {
            listDiv.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding-top: 20px;">No one marked present yet.</p>';
            return;
        }

        let html = '';
        data.marked.forEach(m => {
            html += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: var(--radius-sm); margin-bottom: 6px;">
                    <div>
                        <strong style="display: block; font-size: 0.9rem;">${m.name}</strong>
                        <span style="font-size: 0.75rem; color: var(--text-secondary);">Logged at ${m.time}</span>
                    </div>
                    <span class="status-badge success" style="font-size: 0.75rem; padding: 2px 8px;">Conf: ${m.conf}</span>
                </div>
            `;
        });
        listDiv.innerHTML = html;
    } catch(e){}
}

function histFormatDate(d) {
    return d.toISOString().split('T')[0];
}

function histGetDateRange(preset) {
    const now = new Date();
    const d = (n) => { const x = new Date(now); x.setDate(x.getDate() + n); return x; };
    const mondayOf = (date) => { const x = new Date(date); const day = x.getDay(); x.setDate(x.getDate() - (day === 0 ? 6 : day - 1)); return x; };
    switch (preset) {
        case 'today': return { from: histFormatDate(now), to: histFormatDate(now) };
        case 'yesterday': return { from: histFormatDate(d(-1)), to: histFormatDate(d(-1)) };
        case 'this-week': { const mon = mondayOf(now); return { from: histFormatDate(mon), to: histFormatDate(now) }; }
        case 'last-week': { const mon = mondayOf(d(-7)); const sun = mondayOf(now); sun.setDate(sun.getDate() - 1); return { from: histFormatDate(mon), to: histFormatDate(sun) }; }
        case 'this-month': return { from: `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-01`, to: histFormatDate(now) };
        case 'last-month': { const lm = new Date(now.getFullYear(), now.getMonth()-1, 1); const lmEnd = new Date(now.getFullYear(), now.getMonth(), 0); return { from: histFormatDate(lm), to: histFormatDate(lmEnd) }; }
        case 'last-7': return { from: histFormatDate(d(-6)), to: histFormatDate(now) };
        case 'last-30': return { from: histFormatDate(d(-29)), to: histFormatDate(now) };
        default: return { from: histFormatDate(now), to: histFormatDate(now) };
    }
}

function histBuildCalendar(containerEl, currentDate, onSelect) {
    let viewDate = new Date(currentDate + 'T00:00:00');
    function render() {
        const year = viewDate.getFullYear();
        const month = viewDate.getMonth();
        const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
        const firstDay = new Date(year, month, 1);
        const startDow = (firstDay.getDay() + 6) % 7;
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const prevDays = new Date(year, month, 0).getDate();
        const todayStr = histFormatDate(new Date());

        let html = '<div class="cal-nav">'
            + '<button class="cal-nav-btn cal-prev" type="button">&larr;</button>'
            + '<span class="cal-nav-title">' + monthNames[month] + ' ' + year + '</span>'
            + '<button class="cal-nav-btn cal-next" type="button">&rarr;</button>'
            + '</div><div class="cal-grid">'
            + '<div class="cal-dow">Mo</div><div class="cal-dow">Tu</div><div class="cal-dow">We</div>'
            + '<div class="cal-dow">Th</div><div class="cal-dow">Fr</div><div class="cal-dow">Sa</div><div class="cal-dow">Su</div>';

        for (let i = 0; i < startDow; i++) {
            const day = prevDays - startDow + 1 + i;
            const ds = histFormatDate(new Date(year, month - 1, day));
            html += '<button class="cal-day other-month" data-date="' + ds + '" type="button">' + day + '</button>';
        }
        for (let day = 1; day <= daysInMonth; day++) {
            const ds = histFormatDate(new Date(year, month, day));
            const cls = ['cal-day'];
            if (ds === todayStr) cls.push('today');
            if (ds === currentDate) cls.push('selected');
            html += '<button class="' + cls.join(' ') + '" data-date="' + ds + '" type="button">' + day + '</button>';
        }
        const totalCells = startDow + daysInMonth;
        const remaining = (7 - (totalCells % 7)) % 7;
        for (let i = 1; i <= remaining; i++) {
            const ds = histFormatDate(new Date(year, month + 1, i));
            html += '<button class="cal-day other-month" data-date="' + ds + '" type="button">' + i + '</button>';
        }
        html += '</div>';
        containerEl.innerHTML = html;

        containerEl.querySelector('.cal-prev').addEventListener('click', (e) => { e.stopPropagation(); viewDate.setMonth(viewDate.getMonth() - 1); render(); });
        containerEl.querySelector('.cal-next').addEventListener('click', (e) => { e.stopPropagation(); viewDate.setMonth(viewDate.getMonth() + 1); render(); });
        containerEl.querySelectorAll('.cal-day:not(.other-month)').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                currentDate = btn.dataset.date;
                onSelect(btn.dataset.date);
                containerEl.classList.remove('open');
            });
        });
    }
    render();
}

let _histCalFrom = null;
let _histCalTo = null;

async function buildLecturerHistory(container) {
    try {
        const classes = await apiCall(`/api/classes?lecturer_id=${currentUser.id}`);
        const classOptions = classes.map(c => '<option value="' + c.id + '">' + c.code + ' \u2014 ' + c.name + '</option>').join('');
        const today = new Date();
        const todayStr = histFormatDate(today);

        container.innerHTML = '<div class="dashboard-grid">'
            + '<div class="col-12 dashboard-card glass">'
            + '<div style="display:flex;gap:16px;align-items:flex-end;margin-bottom:16px;flex-wrap:wrap;">'
            + '<div class="input-group" style="margin-bottom:0;flex:1;min-width:200px;">'
            + '<label>Class</label><div class="input-wrapper"><select id="hist-class-select">' + classOptions + '</select></div>'
            + '</div></div>'

            + '<div style="display:flex;gap:16px;align-items:flex-end;margin-bottom:20px;flex-wrap:wrap;">'
            + '<div class="input-group" style="margin-bottom:0;">'
            + '<label>Quick Range</label><div class="range-presets" id="range-presets">'
            + '<button class="range-preset-btn active" data-range="today">Today</button>'
            + '<button class="range-preset-btn" data-range="yesterday">Yesterday</button>'
            + '<button class="range-preset-btn" data-range="this-week">This Week</button>'
            + '<button class="range-preset-btn" data-range="last-week">Last Week</button>'
            + '<button class="range-preset-btn" data-range="this-month">This Month</button>'
            + '<button class="range-preset-btn" data-range="last-month">Last Month</button>'
            + '<button class="range-preset-btn" data-range="last-7">Last 7 Days</button>'
            + '<button class="range-preset-btn" data-range="last-30">Last 30 Days</button>'
            + '<button class="range-preset-btn" data-range="custom">Custom</button>'
            + '</div></div></div>'

            + '<div id="custom-date-row" style="display:none;margin-bottom:20px;">'
            + '<div style="display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap;">'
            + '<div class="input-group" style="margin-bottom:0;"><label>From</label>'
            + '<div class="cal-wrap" id="cal-from-wrap"><div class="cal-input" id="cal-from-input"><i data-lucide="calendar"></i><span id="cal-from-label">' + todayStr + '</span></div>'
            + '<div class="cal-dropdown" id="cal-from-dropdown"></div></div></div>'
            + '<div class="input-group" style="margin-bottom:0;"><label>To</label>'
            + '<div class="cal-wrap" id="cal-to-wrap"><div class="cal-input" id="cal-to-input"><i data-lucide="calendar"></i><span id="cal-to-label">' + todayStr + '</span></div>'
            + '<div class="cal-dropdown" id="cal-to-dropdown"></div></div></div>'
            + '</div></div>'

            + '<div style="display:flex;gap:12px;margin-bottom:24px;">'
            + '<button class="btn primary-btn" id="load-history-btn"><i data-lucide="search"></i> Load History</button>'
            + '<button class="btn success-btn" id="export-excel-btn"><i data-lucide="download"></i> Export Excel</button>'
            + '<button class="btn ghost-btn" id="export-csv-btn"><i data-lucide="file-text"></i> Export CSV</button>'
            + '</div>'

            + '<div class="table-wrapper"><table class="data-table"><thead><tr>'
            + '<th>Student ID</th><th>Full Name</th><th>Date</th><th>Log Time</th><th>Method</th><th>Confidence</th><th>Actions</th>'
            + '</tr></thead><tbody id="history-table-body">'
            + '<tr><td colspan="7" style="text-align:center;">Select a range and click Load History.</td></tr>'
            + '</tbody></table></div>'
            + '</div></div>';
        safeCreateIcons();

        let dateMode = 'preset';
        let datePreset = 'today';
        let dateFrom = todayStr;
        let dateTo = todayStr;

        document.querySelectorAll('.range-preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.range-preset-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                datePreset = btn.dataset.range;
                const customRow = document.getElementById('custom-date-row');
                if (datePreset === 'custom') {
                    dateMode = 'custom';
                    customRow.style.display = 'block';
                } else {
                    dateMode = 'preset';
                    customRow.style.display = 'none';
                    const range = histGetDateRange(datePreset);
                    dateFrom = range.from;
                    dateTo = range.to;
                }
            });
        });

        function setupCalendar(wrapId, dropdownId, labelId, initialDate, onPick) {
            const wrap = document.getElementById(wrapId);
            const dropdown = document.getElementById(dropdownId);
            const label = document.getElementById(labelId);
            histBuildCalendar(dropdown, initialDate, (dateStr) => {
                label.textContent = dateStr;
                onPick(dateStr);
            });
            wrap.querySelector('.cal-input').addEventListener('click', (e) => {
                e.stopPropagation();
                document.querySelectorAll('.cal-dropdown.open').forEach(d => { if (d !== dropdown) d.classList.remove('open'); });
                dropdown.classList.toggle('open');
            });
        }

        setupCalendar('cal-from-wrap', 'cal-from-dropdown', 'cal-from-label', todayStr, (d) => { dateFrom = d; });
        setupCalendar('cal-to-wrap', 'cal-to-dropdown', 'cal-to-label', todayStr, (d) => { dateTo = d; });

        document.addEventListener('click', () => {
            document.querySelectorAll('.cal-dropdown.open').forEach(d => d.classList.remove('open'));
        });

        async function loadHistory() {
            const classId = document.getElementById('hist-class-select').value;
            if (!classId) return;
            try {
                let logs;
                if (dateFrom === dateTo) {
                    logs = await apiCall('/api/attendance/history?class_id=' + classId + '&date=' + dateFrom);
                } else {
                    logs = await apiCall('/api/attendance/history-range?class_id=' + classId + '&date_from=' + dateFrom + '&date_to=' + dateTo);
                }
                const tbody = document.getElementById('history-table-body');
                if (logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary)">No attendance records found for this range.</td></tr>';
                    return;
                }
                let html = '';
                logs.forEach(l => {
                    html += '<tr>'
                        + '<td><code>' + (l.student_id_string || '\u2014') + '</code></td>'
                        + '<td><strong>' + l.full_name + '</strong></td>'
                        + '<td>' + (l.session_date || '\u2014') + '</td>'
                        + '<td>' + l.timestamp + '</td>'
                        + '<td><span class="status-badge" style="text-transform:uppercase;">' + l.method + '</span></td>'
                        + '<td>' + (l.confidence ? l.confidence.toFixed(2) : '\u2014') + '</td>'
                        + '<td><button class="btn danger-btn btn-icon" onclick="deleteHistoryRecord(' + l.id + ')" title="Delete Record"><i data-lucide="trash-2"></i></button></td>'
                        + '</tr>';
                });
                tbody.innerHTML = html;
                safeCreateIcons();
            } catch(e) {}
        }

        document.getElementById('load-history-btn').addEventListener('click', loadHistory);

        async function doExport(format) {
            const classId = document.getElementById('hist-class-select').value;
            if (!classId) return;

            const params = 'class_id=' + classId + '&date_from=' + dateFrom + '&date_to=' + dateTo + '&format=' + format;

            if (pywebviewReady && window.pywebview && window.pywebview.api && typeof window.pywebview.api.save_file === 'function') {
                try {
                    const data = await apiCall('/api/attendance/export-data?' + params);
                    const saved = await window.pywebview.api.save_file(data.filename, data.content, data.mime);
                    if (saved) showToast('File saved', 'success');
                    else showToast('Save cancelled', 'info');
                } catch (err) {
                    showToast('Export failed: ' + (err.message || err), 'error');
                }
                return;
            }
            window.location.href = apiBaseUrl + '/api/attendance/export?' + params;
        }

        document.getElementById('export-excel-btn').addEventListener('click', () => doExport('xlsx'));
        document.getElementById('export-csv-btn').addEventListener('click', () => doExport('csv'));

    } catch(e) { console.error('buildLecturerHistory error:', e); }
}

async function deleteHistoryRecord(recordId) {
    if (!confirm('Are you sure you want to delete this log entry?')) return;
    try {
        await apiCall(`/api/attendance/history/${recordId}`, { method: 'DELETE' });
        showToast('Record deleted', 'info');
        const container = document.getElementById('tab-content');
        if (container) buildLecturerHistory(container);
    } catch(e){}
}


// ==========================================
// STUDENT ATTENDANCE & ENROLLMENT WIZARD
// ==========================================

async function buildStudentDashboard(container) {
    try {
        const records = await apiCall(`/api/student/attendance/${currentUser.full_name}`);
        let rowsHtml = '';
        records.forEach(r => {
            rowsHtml += `
                <tr>
                    <td><code>${r.class_code}</code></td>
                    <td><strong>${r.class_name}</strong></td>
                    <td>${r.session_date}</td>
                    <td>${r.timestamp}</td>
                    <td><span class="status-badge" style="text-transform: uppercase;">${r.method}</span></td>
                </tr>
            `;
        });

        container.innerHTML = `
            <div class="dashboard-grid">
                <div class="col-12 dashboard-card glass">
                    <div class="card-header">
                        <h3>My Attendance Log</h3>
                    </div>
                    <div class="table-wrapper">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Class Code</th>
                                    <th>Class Name</th>
                                    <th>Date</th>
                                    <th>Logged Time</th>
                                    <th>Method</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${rowsHtml || '<tr><td colspan="5" style="text-align: center;">No attendance logs recorded yet.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
    } catch (e) {}
}

function renderEnrollmentSlots(containerEl, mode) {
    containerEl.innerHTML = '';
    for (let i = 0; i < 5; i++) {
        const slotEl = document.createElement('div');
        slotEl.className = 'photo-slot';
        slotEl.dataset.slot = i;

        if (enrollmentState.slots[i]) {
            const imgUrl = enrollmentState.slots[i].startsWith('http')
                ? enrollmentState.slots[i]
                : `${apiBaseUrl}${enrollmentState.slots[i]}?t=${Date.now()}`;
            slotEl.innerHTML = `<img src="${imgUrl}"><button class="slot-delete-btn" title="Remove photo">&times;</button>`;
        } else {
            slotEl.innerHTML = `<i data-lucide="image"></i>`;
        }

        containerEl.appendChild(slotEl);
    }
    safeCreateIcons();

    containerEl.querySelectorAll('.photo-slot').forEach(slotEl => {
        const idx = parseInt(slotEl.dataset.slot);

        const deleteBtn = slotEl.querySelector('.slot-delete-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                try {
                    await apiCall(`/api/enrollment/slot?user_id=${currentUser.id}&slot_idx=${idx}`, { method: 'DELETE' });
                } catch (err) {}
                enrollmentState.slots[idx] = null;
                renderEnrollmentSlots(containerEl, mode);
                updateWizardNextBtn(mode);
                showToast(`Photo ${idx + 1} removed`, "info");
            });
        }
    });
    updateWizardNextBtn(mode);
}

function updateWizardNextBtn(mode) {
    const btn = document.getElementById('wizard-next-btn');
    if (!btn) return;
    const filledCount = enrollmentState.slots.filter(s => s !== null).length;
    btn.disabled = filledCount < 5;
}

function buildStudentEnrollment(container) {
    enrollmentState.step = 1;
    enrollmentState.slots = Array(5).fill(null);
    enrollmentState.cameraActive = false;
    renderEnrollmentStep(container);
}

function renderEnrollmentStep(container) {
    const step = enrollmentState.step;
    let stepHtml = '';

    if (step === 1) {
        stepHtml = `
            <div class="dashboard-card glass" style="max-width: 600px; margin: 0 auto; animation: fadeIn 0.3s ease-out;">
                <h2 style="margin-bottom: 12px; font-weight: 700; display: flex; align-items: center; gap: 8px;">
                    <i data-lucide="scan-face" class="accent-color"></i> Face Registration Wizard
                </h2>
                <p style="color: var(--text-secondary); margin-bottom: 20px; line-height: 1.6;">
                    To enable facial recognition login and auto-attendance logging, you must enroll 5 reference photos.
                </p>
                <div style="background-color: var(--panel-color); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border-color); margin-bottom: 24px; font-size: 0.9rem;">
                    <strong style="display: block; margin-bottom: 6px;">Instructions for optimal accuracy:</strong>
                    • Find a well-lit room with light casting evenly on your face.<br>
                    • Keep a neutral facial expression.<br>
                    • Remove sunglasses, masks, or caps before starting.<br>
                    • Look straight into the camera.
                </div>
                <button class="btn primary-btn" id="start-wizard-btn">Start Enrollment Wizard</button>
            </div>
        `;
    } else if (step === 2) {
        // Reference Photos Collection Tab
        stepHtml = `
            <div class="dashboard-card glass" style="max-width: 700px; margin: 0 auto;">
                <div class="card-header" style="flex-direction: column; align-items: flex-start; gap: 8px; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin-bottom: 16px;">
                    <h3>📷 Step 2: Reference Photos Collection</h3>
                    <div class="tab-selectors" style="display: flex; gap: 10px; margin-top: 4px;">
                        <button class="tab-btn active" id="collection-mode-capture-btn">📷 Live Capture</button>
                        <button class="tab-btn" id="collection-mode-upload-btn">⬆ Upload Files</button>
                    </div>
                </div>
                
                <!-- Mode: Live Capture -->
                <div id="enroll-capture-section" style="display: flex; gap: 24px;">
                    <div style="flex: 1;">
                        <div class="camera-viewport" style="max-width: 100%; aspect-ratio: 4/3;">
                            <img id="enroll-feed" src="" style="width:100%; height:100%; object-fit:cover;" class="hidden">
                            <div id="enroll-cam-placeholder" style="text-align: center; color: var(--text-secondary)">
                                <i data-lucide="video" style="width: 40px; height: 40px; margin-bottom: 12px;"></i>
                                <p>Click Open Camera to start</p>
                            </div>
                        </div>
                        <div style="display: flex; gap: 10px; margin-top: 12px; align-items: center;">
                            <select id="enroll-cam-source-select" class="input-field" style="width: 140px; padding: 6px 10px; margin: 0; background: var(--panel-color); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: var(--radius-sm); font-size: 0.85rem;">
                                <option value="0">Default Cam (0)</option>
                                <option value="1">External Cam (1)</option>
                                <option value="2">External Cam (2)</option>
                                <option value="3">External Cam (3)</option>
                            </select>
                            <button class="btn ghost-btn" id="open-enroll-cam-btn" style="white-space: nowrap;">Open Camera</button>
                            <button class="btn success-btn" id="snap-btn" disabled style="white-space: nowrap;">📷 Snap</button>
                        </div>
                        <div id="enroll-slot-indicator" style="margin-top: 8px; font-size: 0.85rem; color: var(--text-secondary);">Capturing Slot 1 of 5</div>
                    </div>

                    <div style="width: 140px; display: flex; flex-direction: column; gap: 10px;">
                        <span style="font-weight:600; font-size:0.8rem; color:var(--text-secondary)">STAGED SLOTS</span>
                        <div id="enroll-slots-list" style="display:flex; flex-direction:column; gap:8px;"></div>
                    </div>
                </div>

                <!-- Mode: File Upload -->
                <div id="enroll-upload-section" class="hidden" style="display: flex; flex-direction: column; gap: 16px; align-items: center; padding: 24px 0; border: 1px dashed var(--border-color); border-radius: var(--radius-md);">
                    <i data-lucide="upload-cloud" style="width: 48px; height: 48px; color: var(--accent-color)"></i>
                    <p style="text-align: center; color: var(--text-secondary)">Select exactly 5 clear face photos for optimal recognition accuracy.</p>
                    <input type="file" id="enroll-file-input" multiple accept="image/*" class="hidden">
                    <button class="btn primary-btn" id="enroll-browse-btn">Browse & Upload Images</button>
                    <div id="enroll-upload-slots-list" style="display:flex; gap:8px; margin-top: 12px;"></div>
                </div>
                
                <div style="display: flex; justify-content: space-between; margin-top: 24px; border-top: 1px solid var(--border-color); padding-top: 16px;">
                    <button class="btn ghost-btn" id="wizard-back-btn">Back</button>
                    <button class="btn primary-btn" id="wizard-next-btn" disabled>Validate Photos →</button>
                </div>
            </div>
        `;
    } else if (step === 3) {
        // Validation Progress
        stepHtml = `
            <div class="dashboard-card glass" style="max-width: 600px; margin: 0 auto; text-align: center; padding: 40px;">
                <i data-lucide="shield-check" class="accent-color" style="width: 48px; height: 48px; margin-bottom: 16px;"></i>
                <h3>Validating Your reference Photos</h3>
                <p style="color: var(--text-secondary); margin-bottom: 24px;">The system is analyzing contrast, quality, and detecting landmarks to ensure high recognition accuracy.</p>
                <div id="validation-results-list" style="text-align: left; margin: 0 auto 24px auto; max-width: 400px; display: flex; flex-direction: column; gap: 8px;"></div>
                <div style="display: flex; justify-content: space-between; border-top: 1px solid var(--border-color); padding-top: 16px; width: 100%;">
                    <button class="btn ghost-btn" id="wizard-back-btn">Retake</button>
                    <button class="btn primary-btn" id="wizard-next-btn" disabled>Test Recognition →</button>
                </div>
            </div>
        `;
    } else if (step === 4) {
        // Live Test Recognition
        stepHtml = `
            <div class="dashboard-card glass" style="max-width: 700px; margin: 0 auto;">
                <div class="card-header">
                    <h3>🔍 Step 4: Test Recognition Rate</h3>
                    <span class="status-badge warning" id="test-conf-badge">Ready</span>
                </div>
                
                <div style="display: flex; gap: 24px;">
                    <div style="flex: 1;">
                        <div class="camera-viewport" style="max-width: 100%; aspect-ratio: 4/3;">
                            <img id="test-feed" src="" style="width:100%; height:100%; object-fit:cover;" class="hidden">
                            <div id="test-placeholder" style="text-align: center; color: var(--text-secondary)">
                                <i data-lucide="video" style="width: 40px; height: 40px; margin-bottom: 12px;"></i>
                                <p>Click Run Test to verify face match</p>
                            </div>
                        </div>
                    </div>
                    <div style="width: 240px; display: flex; flex-direction: column; gap: 14px;">
                        <button class="btn primary-btn" id="run-test-btn">▶ Run Recognition Test</button>
                        <p style="font-size:0.85rem; color:var(--text-secondary)">The model needs to correctly identify your face on video for at least 3 seconds before finalized enrollment.</p>
                        <div id="test-result-box" style="padding: 12px; border-radius: var(--radius-md); border:1px solid var(--border-color); display:flex; flex-direction:column; gap:4px;" class="hidden">
                            <strong id="test-result-title">Analyzing...</strong>
                            <span id="test-result-desc" style="font-size: 0.8rem; color: var(--text-secondary)">Wait for feed analysis</span>
                        </div>
                    </div>
                </div>
                
                <div style="display: flex; justify-content: space-between; margin-top: 24px; border-top: 1px solid var(--border-color); padding-top: 16px;">
                    <button class="btn ghost-btn" id="wizard-back-btn">Retake</button>
                    <button class="btn success-btn" id="wizard-confirm-btn" disabled>Confirm & Register Face ✓</button>
                </div>
            </div>
        `;
    } else if (step === 5) {
        // Success
        stepHtml = `
            <div class="dashboard-card glass" style="max-width: 500px; margin: 0 auto; text-align: center; padding: 40px; animation: fadeIn 0.4s ease-out;">
                <i data-lucide="party-popper" style="width: 64px; height: 64px; color: var(--success-color); margin-bottom: 20px;"></i>
                <h2>Face Model Registered!</h2>
                <p style="color: var(--text-secondary); margin-bottom: 24px;">Your biometric face template was successfully compiled and linked to your student ID. You can now use automated camera check-in.</p>
                <button class="btn primary-btn btn-full" id="finish-wizard-btn">Done</button>
            </div>
        `;
    }

    container.innerHTML = stepHtml;
    safeCreateIcons();

    // Hook step buttons
    if (step === 1) {
        document.getElementById('start-wizard-btn').addEventListener('click', () => {
            enrollmentState.step = 2;
            renderEnrollmentStep(container);
        });
    } else if (step === 2) {
        const slotsList = document.getElementById('enroll-slots-list');
        renderEnrollmentSlots(slotsList, 'capture');

        // Mode Switching
        document.getElementById('collection-mode-capture-btn').addEventListener('click', async () => {
            document.getElementById('collection-mode-capture-btn').classList.add('active');
            document.getElementById('collection-mode-upload-btn').classList.remove('active');
            document.getElementById('enroll-capture-section').classList.remove('hidden');
            document.getElementById('enroll-upload-section').classList.add('hidden');
        });
        document.getElementById('collection-mode-upload-btn').addEventListener('click', async () => {
            document.getElementById('collection-mode-upload-btn').classList.add('active');
            document.getElementById('collection-mode-capture-btn').classList.remove('active');
            document.getElementById('enroll-upload-section').classList.remove('hidden');
            document.getElementById('enroll-capture-section').classList.add('hidden');
            // Release camera if active
            if (enrollmentState.cameraActive) {
                await apiCall('/api/session/stop', { method: 'POST' });
                enrollmentState.cameraActive = false;
                document.getElementById('enroll-feed').src = '';
                document.getElementById('enroll-feed').classList.add('hidden');
                document.getElementById('enroll-cam-placeholder').classList.remove('hidden');
                document.getElementById('snap-btn').disabled = true;
            }
        });

        // Live Capture Events
        document.getElementById('open-enroll-cam-btn').addEventListener('click', async () => {
            try {
                const source = document.getElementById('enroll-cam-source-select').value;
                await apiCall(`/api/enrollment/start?user_id=${currentUser.id}&full_name=${currentUser.full_name}&camera_source=${source}`, { method: 'POST' });
                document.getElementById('enroll-cam-placeholder').classList.add('hidden');
                document.getElementById('enroll-feed').src = `${apiBaseUrl}/api/session/video_feed?t=${Date.now()}`;
                document.getElementById('enroll-feed').classList.remove('hidden');
                document.getElementById('snap-btn').disabled = false;
                enrollmentState.cameraActive = true;
            } catch(e){}
        });

        document.getElementById('snap-btn').addEventListener('click', async () => {
            const emptyIdx = enrollmentState.slots.findIndex(s => s === null);
            if (emptyIdx === -1) {
                showToast("All photo slots filled!", "warning");
                return;
            }

            try {
                const res = await apiCall(`/api/enrollment/capture?user_id=${currentUser.id}&full_name=${currentUser.full_name}&slot_idx=${emptyIdx}`, { method: 'POST' });
                enrollmentState.slots[emptyIdx] = res.filepath;
                
                // Refresh slots display
                renderEnrollmentSlots(slotsList, 'capture');

                const nextEmpty = enrollmentState.slots.findIndex(s => s === null);
                const indicator = document.getElementById('enroll-slot-indicator');
                if (nextEmpty !== -1) {
                    if (indicator) indicator.innerText = `Capturing Slot ${nextEmpty+1} of 5`;
                } else {
                    if (indicator) indicator.innerText = `All Slots Captured`;
                    document.getElementById('snap-btn').disabled = true;
                    document.getElementById('wizard-next-btn').disabled = false;
                    await apiCall('/api/session/stop', { method: 'POST' });
                }
            } catch(e){}
        });

        // File Upload Events
        document.getElementById('enroll-browse-btn').addEventListener('click', () => {
            document.getElementById('enroll-file-input').click();
        });

        document.getElementById('enroll-file-input').addEventListener('change', async (e) => {
            const files = e.target.files;
            if (files.length === 0) return;
            if (files.length < 5) {
                showToast("Please select exactly 5 images", "warning");
                return;
            }
            
            const formData = new FormData();
            for(let i=0; i<Math.min(files.length, 5); i++) {
                formData.append('files', files[i]);
            }
            
            try {
                showToast("Uploading images...", "info");
                const res = await fetch(`${apiBaseUrl}/api/enrollment/upload?user_id=${currentUser.id}`, {
                    method: 'POST',
                    body: formData
                });
                if (!res.ok) throw new Error("Upload failed");
                const data = await res.json();
                
                // Populate enrollmentState.slots
                for(let i=0; i<5; i++) {
                    enrollmentState.slots[i] = data.files[i];
                }
                
                // Render upload slots preview
                const uploadSlotsList = document.getElementById('enroll-upload-slots-list');
                renderEnrollmentSlots(uploadSlotsList, 'upload');
                
                showToast("Successfully uploaded 5 images!", "success");
                document.getElementById('wizard-next-btn').disabled = false;
            } catch(err) {
                showToast(err.message, "error");
            }
        });

        document.getElementById('wizard-back-btn').addEventListener('click', async () => {
            if (enrollmentState.cameraActive) {
                await apiCall('/api/session/stop', { method: 'POST' });
            }
            enrollmentState.step = 1;
            renderEnrollmentStep(container);
        });

        document.getElementById('wizard-next-btn').addEventListener('click', () => {
            enrollmentState.step = 3;
            renderEnrollmentStep(container);
        });
    } else if (step === 3) {
        // Run validation on load
        runValidation(container);
    } else if (step === 4) {
        document.getElementById('run-test-btn').addEventListener('click', async () => {
            try {
                await apiCall(`/api/enrollment/test/start?user_id=${currentUser.id}&full_name=${currentUser.full_name}`, { method: 'POST' });
                document.getElementById('test-placeholder').classList.add('hidden');
                document.getElementById('test-feed').src = `${apiBaseUrl}/api/session/video_feed?t=${Date.now()}`;
                document.getElementById('test-feed').classList.remove('hidden');
                
                const resBox = document.getElementById('test-result-box');
                resBox.classList.remove('hidden');
                
                let testCount = 0;
                let testInterval = setInterval(async () => {
                    testCount++;
                    const data = await apiCall('/api/session/live');
                    const match = data.marked.find(m => m.name === currentUser.full_name);
                    
                    if (match) {
                        clearInterval(testInterval);
                        document.getElementById('test-result-title').innerText = "✅ Recognized!";
                        document.getElementById('test-result-title').style.color = "var(--success-color)";
                        document.getElementById('test-result-desc').innerText = `Identified: ${currentUser.full_name}`;
                        document.getElementById('wizard-confirm-btn').disabled = false;
                        await apiCall('/api/session/stop', { method: 'POST' });
                        document.getElementById('test-feed').classList.add('hidden');
                        document.getElementById('test-placeholder').classList.remove('hidden');
                        document.getElementById('test-feed').src = '';
                    } else if (testCount >= 10) {
                        clearInterval(testInterval);
                        document.getElementById('test-result-title').innerText = "❌ Recognition Low";
                        document.getElementById('test-result-desc').innerText = "Face not recognized. Try retaking.";
                        await apiCall('/api/session/stop', { method: 'POST' });
                    }
                }, 1000);

            } catch(e){}
        });

        document.getElementById('wizard-back-btn').addEventListener('click', () => {
            enrollmentState.step = 2;
            renderEnrollmentStep(container);
        });

        document.getElementById('wizard-confirm-btn').addEventListener('click', async () => {
            try {
                await apiCall(`/api/enrollment/confirm?user_id=${currentUser.id}&full_name=${currentUser.full_name}`, { method: 'POST' });
                showToast("Biometrics enrolled!", "success");
                currentUser.face_enrolled = 1;
                localStorage.setItem('attendiq_user', JSON.stringify(currentUser));
                enrollmentState.step = 5;
                renderEnrollmentStep(container);
            } catch(e){}
        });
    } else if (step === 5) {
        document.getElementById('finish-wizard-btn').addEventListener('click', () => {
            switchTab('dashboard');
        });
    }
}

async function runValidation(container) {
    const listDiv = document.getElementById('validation-results-list');
    listDiv.innerHTML = '<p style="text-align:center;">Validating...</p>';
    
    try {
        const res = await apiCall(`/api/enrollment/validate?user_id=${currentUser.id}`, { method: 'POST' });
        
        let html = '';
        res.results.forEach(r => {
            let color = 'var(--text-secondary)';
            if (r.state === 'valid') color = 'var(--success-color)';
            if (r.state === 'invalid') color = 'var(--danger-color)';
            if (r.state === 'warn') color = 'var(--warning-color)';
            
            html += `
                <div style="display: flex; justify-content: space-between; padding: 10px; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: var(--panel-color);">
                    <span>Photo ${r.slot + 1}</span>
                    <span style="font-weight: 600; color: ${color}">${r.message}</span>
                </div>
            `;
        });
        listDiv.innerHTML = html;

        if (res.can_proceed) {
            document.getElementById('wizard-next-btn').disabled = false;
        } else {
            showToast("At least 3 valid photos required. Please go back and retake.", "warning");
        }
        
        document.getElementById('wizard-back-btn').addEventListener('click', () => {
            enrollmentState.step = 2;
            renderEnrollmentStep(container);
        });
        
        document.getElementById('wizard-next-btn').addEventListener('click', () => {
            enrollmentState.step = 4;
            renderEnrollmentStep(container);
        });
    } catch(e){}
}
