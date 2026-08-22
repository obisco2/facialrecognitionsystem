/* ================================================================
   AttendIQ — Mock API Layer
   Intercepts fetch() and returns fake data for static deployments.
   Load this BEFORE app.js via: <script src="mock-api.js"></script>
   ================================================================ */
(function () {
    'use strict';

    // --- In-memory mock database ---
    const DB = {
        users: [
            { id: 1, username: 'admin',    full_name: 'Admin User',     role: 'admin',    student_id: null,   email: 'admin@unilag.edu.ng',   face_enrolled: 0, created_at: '2026-08-10 09:00:00' },
            { id: 2, username: 'dr.adesina', full_name: 'Dr. Adesina',  role: 'lecturer', student_id: null,   email: 'adesina@unilag.edu.ng',  face_enrolled: 0, created_at: '2026-08-10 09:05:00' },
            { id: 3, username: 'sudotads', full_name: 'Michael Obitade', role: 'student',  student_id: '210408502', email: 'obitade@unilag.edu.ng', face_enrolled: 1, created_at: '2026-08-12 10:00:00' },
            { id: 4, username: 'james',    full_name: 'James Nwankwo',   role: 'student',  student_id: '210408115', email: 'james@unilag.edu.ng',   face_enrolled: 1, created_at: '2026-08-12 10:05:00' },
            { id: 5, username: 'fatima',   full_name: 'Fatima Bello',    role: 'student',  student_id: '210408230', email: 'fatima@unilag.edu.ng',  face_enrolled: 0, created_at: '2026-08-13 08:30:00' },
            { id: 6, username: 'chidi',    full_name: 'Chidi Eze',       role: 'student',  student_id: '210408301', email: 'chidi@unilag.edu.ng',   face_enrolled: 1, created_at: '2026-08-13 09:00:00' },
            { id: 7, username: 'aisha',    full_name: 'Aisha Mohammed',  role: 'student',  student_id: '210408418', email: 'aisha@unilag.edu.ng',   face_enrolled: 0, created_at: '2026-08-14 11:00:00' },
            { id: 8, username: 'dr.okafor', full_name: 'Dr. Okafor',     role: 'lecturer', student_id: null,   email: 'okafor@unilag.edu.ng',  face_enrolled: 0, created_at: '2026-08-10 09:10:00' },
        ],
        classes: [
            { id: 1, name: 'Engineering Mathematics II', code: 'MTH202', lecturer_id: 2, schedule: 'Mon/Wed 9-11', room: 'LT009', created_at: '2026-08-10 09:20:00' },
            { id: 2, name: 'Digital Logic Design',       code: 'CPE201', lecturer_id: 2, schedule: 'Tue/Thu 10-12', room: 'Lab 3', created_at: '2026-08-10 09:25:00' },
            { id: 3, name: 'Data Structures',            code: 'CSC201', lecturer_id: 8, schedule: 'Mon/Wed 2-4',  room: 'LT005', created_at: '2026-08-10 09:30:00' },
        ],
        enrollments: [
            { id: 1, student_id: 3, class_id: 1, enrolled_at: '2026-08-12 10:10:00' },
            { id: 2, student_id: 4, class_id: 1, enrolled_at: '2026-08-12 10:12:00' },
            { id: 3, student_id: 5, class_id: 1, enrolled_at: '2026-08-13 08:35:00' },
            { id: 4, student_id: 3, class_id: 2, enrolled_at: '2026-08-12 10:15:00' },
            { id: 5, student_id: 6, class_id: 2, enrolled_at: '2026-08-13 09:05:00' },
            { id: 6, student_id: 4, class_id: 3, enrolled_at: '2026-08-14 08:00:00' },
            { id: 7, student_id: 7, class_id: 3, enrolled_at: '2026-08-14 11:05:00' },
        ],
        attendance_log: [
            { id: 1, student_id: 3, class_id: 1, session_date: '2026-08-18', timestamp: '09:02:14', method: 'face',     confidence: 0.92, marked_by: null },
            { id: 2, student_id: 4, class_id: 1, session_date: '2026-08-18', timestamp: '09:03:01', method: 'face',     confidence: 0.87, marked_by: null },
            { id: 3, student_id: 5, class_id: 1, session_date: '2026-08-18', timestamp: '09:15:00', method: 'manual',   confidence: null, marked_by: 2 },
            { id: 4, student_id: 3, class_id: 2, session_date: '2026-08-18', timestamp: '10:01:45', method: 'face',     confidence: 0.95, marked_by: null },
            { id: 5, student_id: 6, class_id: 2, session_date: '2026-08-18', timestamp: '10:02:10', method: 'face',     confidence: 0.88, marked_by: null },
            { id: 6, student_id: 3, class_id: 1, session_date: '2026-08-19', timestamp: '09:01:30', method: 'face',     confidence: 0.94, marked_by: null },
            { id: 7, student_id: 4, class_id: 1, session_date: '2026-08-19', timestamp: '09:02:55', method: 'face',     confidence: 0.91, marked_by: null },
        ],
        config: {
            recognition_engine: 'lbph',
            camera_index: 0,
            stream_url: '',
            frame_scale: 0.25,
            tolerance: 0.6,
        },
        nextId: 100,
        _next(table) { return ++this.nextId; },
    };

    // --- Helpers ---
    const today = () => new Date().toISOString().slice(0, 10);
    const nowTime = () => { const d = new Date(); return d.toTimeString().slice(0, 8); };
    const respond = (data, status = 200) => new Response(JSON.stringify(data), {
        status,
        headers: { 'Content-Type': 'application/json' },
    });
    const error = (msg, status = 400) => new Response(JSON.stringify({ detail: msg }), {
        status,
        headers: { 'Content-Type': 'application/json' },
    });

    // --- Route handler map ---
    // Each entry: { pattern: RegExp, handler: (match, method, url, body) => Response|Promise }
    const routes = [];

    function route(method, pattern, handler) {
        routes.push({ method, pattern, handler });
    }

    // ── Auth ──
    route('POST', /^\/api\/auth\/login$/, (_m, _p, _u, body) => {
        const { username, password } = body;
        const user = DB.users.find(u => u.username === username);
        if (!user || !password) return error('Invalid username or password', 401);
        return respond({ ...user });
    });

    // ── Users ──
    route('GET', /^\/api\/users$/, (_m, _p, url) => {
        const u = new URL(url, 'http://x');
        const role = u.searchParams.get('role');
        let list = DB.users;
        if (role) list = list.filter(u => u.role === role);
        return respond(list);
    });

    route('POST', /^\/api\/users$/, (_m, _p, _u, body) => {
        const u = { id: DB._next(), ...body, face_enrolled: 0, created_at: new Date().toISOString() };
        DB.users.push(u);
        return respond(u, 201);
    });

    route('DELETE', /^\/api\/users\/(\d+)$/, (m) => {
        const id = +m[1];
        DB.users = DB.users.filter(u => u.id !== id);
        DB.enrollments = DB.enrollments.filter(e => e.student_id !== id);
        return respond({ status: 'ok' });
    });

    // ── Classes ──
    route('GET', /^\/api\/classes$/, (_m, _p, url) => {
        const u = new URL(url, 'http://x');
        const lecturerId = u.searchParams.get('lecturer_id');
        let list = DB.classes.map(c => {
            const lecturer = DB.users.find(u => u.id === c.lecturer_id);
            const enrolled_count = DB.enrollments.filter(e => e.class_id === c.id).length;
            return { ...c, lecturer_name: lecturer?.full_name || 'N/A', enrolled_count };
        });
        if (lecturerId) list = list.filter(c => c.lecturer_id === +lecturerId);
        return respond(list);
    });

    route('POST', /^\/api\/classes$/, (_m, _p, url, body) => {
        const u = new URL(url, 'http://x');
        const lecturerId = +u.searchParams.get('lecturer_id');
        const c = { id: DB._next(), ...body, lecturer_id: lecturerId, created_at: new Date().toISOString() };
        DB.classes.push(c);
        return respond(c, 201);
    });

    route('DELETE', /^\/api\/classes\/(\d+)$/, (m) => {
        const id = +m[1];
        DB.classes = DB.classes.filter(c => c.id !== id);
        DB.enrollments = DB.enrollments.filter(e => e.class_id !== id);
        return respond({ status: 'ok' });
    });

    // ── Enrollments ──
    route('GET', /^\/api\/classes\/(\d+)\/enrollments$/, (m) => {
        const classId = +m[1];
        const enrolled = DB.enrollments
            .filter(e => e.class_id === classId)
            .map(e => DB.users.find(u => u.id === e.student_id))
            .filter(Boolean);
        const enrolledIds = new Set(enrolled.map(u => u.id));
        const unenrolled = DB.users.filter(u => u.role === 'student' && !enrolledIds.has(u.id));
        return respond({ enrolled, unenrolled });
    });

    route('POST', /^\/api\/classes\/(\d+)\/enrollments$/, (m, _p, url) => {
        const classId = +m[1];
        const u = new URL(url, 'http://x');
        const studentId = +u.searchParams.get('student_id');
        const exists = DB.enrollments.find(e => e.student_id === studentId && e.class_id === classId);
        if (!exists) DB.enrollments.push({ id: DB._next(), student_id: studentId, class_id: classId, enrolled_at: new Date().toISOString() });
        return respond({ status: 'ok' });
    });

    route('DELETE', /^\/api\/classes\/(\d+)\/enrollments\/(\d+)$/, (m) => {
        const classId = +m[1], studentId = +m[2];
        DB.enrollments = DB.enrollments.filter(e => !(e.student_id === studentId && e.class_id === classId));
        return respond({ status: 'ok' });
    });

    // ── Config ──
    route('GET', /^\/api\/config$/, () => respond(DB.config));

    route('POST', /^\/api\/config$/, (_m, _p, _u, body) => {
        Object.assign(DB.config, body);
        return respond({ status: 'ok' });
    });

    // ── Bias ──
    route('GET', /^\/api\/bias\/results$/, () => respond({
        status: 'ok',
        overall: { detection_rate: 0.94, recognition_accuracy: 0.89, disparity_gap: 0.03 },
        by_skin_type: { '1': { accuracy: 0.91 }, '2': { accuracy: 0.93 }, '3': { accuracy: 0.90 }, '4': { accuracy: 0.88 }, '5': { accuracy: 0.86 }, '6': { accuracy: 0.84 } },
        by_gender: { male: { accuracy: 0.90 }, female: { accuracy: 0.88 } },
    }));

    route('POST', /^\/api\/bias\/evaluate$/, () => respond({ status: 'ok', message: 'Evaluation complete' }));

    // ── Session ──
    let sessionActive = false;

    route('POST', /^\/api\/session\/start$/, () => { sessionActive = true; return respond({ status: 'ok' }); });
    route('POST', /^\/api\/session\/stop$/, () => { sessionActive = false; return respond({ status: 'ok' }); });

    route('GET', /^\/api\/session\/live$/, () => {
        const todayStr = today();
        const marked = DB.attendance_log
            .filter(a => a.session_date === todayStr)
            .map(a => {
                const user = DB.users.find(u => u.id === a.student_id);
                return { name: user?.full_name || 'Unknown', time: a.timestamp, conf: a.confidence, method: a.method };
            });
        return respond({ marked });
    });

    // ── Manual Attendance ──
    route('POST', /^\/api\/attendance\/manual$/, (_m, _p, _u, body) => {
        const { student_id, class_id, marked_by } = body;
        const todayStr = today();
        const exists = DB.attendance_log.find(a => a.student_id === student_id && a.class_id === class_id && a.session_date === todayStr);
        if (exists) return error('Student already logged today', 400);
        const entry = {
            id: DB._next(), student_id, class_id, session_date: todayStr,
            timestamp: nowTime(), method: 'manual', confidence: null, marked_by,
        };
        DB.attendance_log.push(entry);
        return respond({ status: 'ok' });
    });

    // ── Attendance History ──
    route('GET', /^\/api\/attendance\/history$/, (_m, _p, url) => {
        const u = new URL(url, 'http://x');
        const classId = +u.searchParams.get('class_id');
        const date = u.searchParams.get('date') || today();
        const records = DB.attendance_log
            .filter(a => a.class_id === classId && a.session_date === date)
            .map(a => {
                const user = DB.users.find(u => u.id === a.student_id);
                return { id: a.id, student_id_string: user?.student_id || '', full_name: user?.full_name || 'Unknown', timestamp: a.timestamp, method: a.method, confidence: a.confidence };
            });
        return respond(records);
    });

    route('DELETE', /^\/api\/attendance\/history\/(\d+)$/, (m) => {
        const id = +m[1];
        DB.attendance_log = DB.attendance_log.filter(a => a.id !== id);
        return respond({ status: 'ok' });
    });

    // ── Student Attendance ──
    route('GET', /^\/api\/student\/attendance\/(.+)$/, (m) => {
        const name = decodeURIComponent(m[1]);
        const user = DB.users.find(u => u.full_name === name);
        if (!user) return respond([]);
        const records = DB.attendance_log
            .filter(a => a.student_id === user.id)
            .map(a => {
                const cls = DB.classes.find(c => c.id === a.class_id);
                return { class_code: cls?.code || '?', class_name: cls?.name || '?', session_date: a.session_date, timestamp: a.timestamp, method: a.method };
            });
        return respond(records);
    });

    // ── Enrollment (student face enrollment) ──
    const enrollmentSlots = {}; // userId -> [filepath|null x5]

    route('POST', /^\/api\/enrollment\/start$/, () => respond({ status: 'ok' }));

    route('POST', /^\/api\/enrollment\/capture$/, (_m, _p, url, body) => {
        const u = new URL(url, 'http://x');
        const userId = +u.searchParams.get('user_id');
        const slotIdx = +u.searchParams.get('slot_idx');
        if (!enrollmentSlots[userId]) enrollmentSlots[userId] = [null, null, null, null, null];
        const path = `/data/known_faces/__temp_${userId}__/capture_${slotIdx}.jpg`;
        enrollmentSlots[userId][slotIdx] = path;
        return respond({ status: 'ok', filepath: path });
    });

    route('DELETE', /^\/api\/enrollment\/slot$/, (m, _p, url) => {
        const u = new URL(url, 'http://x');
        const userId = +u.searchParams.get('user_id');
        const slotIdx = +u.searchParams.get('slot_idx');
        if (enrollmentSlots[userId]) enrollmentSlots[userId][slotIdx] = null;
        return respond({ status: 'ok' });
    });

    route('POST', /^\/api\/enrollment\/upload$/, (_m, _p, url) => {
        const u = new URL(url, 'http://x');
        const userId = +u.searchParams.get('user_id');
        if (!enrollmentSlots[userId]) enrollmentSlots[userId] = [null, null, null, null, null];
        const files = [];
        for (let i = 0; i < 5; i++) {
            const path = `/data/known_faces/__temp_${userId}__/upload_${i}.jpg`;
            enrollmentSlots[userId][i] = path;
            files.push(path);
        }
        return respond({ files });
    });

    route('POST', /^\/api\/enrollment\/validate$/, (_m, _p, url) => {
        const u = new URL(url, 'http://x');
        const userId = +u.searchParams.get('user_id');
        const slots = enrollmentSlots[userId] || [null, null, null, null, null];
        const results = slots.map((s, i) => ({
            slot: i,
            state: s ? 'valid' : 'missing',
            message: s ? 'Face detected — OK' : 'No image in slot',
        }));
        const validCount = results.filter(r => r.state === 'valid').length;
        return respond({ results, can_proceed: validCount >= 3 });
    });

    route('POST', /^\/api\/enrollment\/test\/start$/, () => respond({ status: 'ok' }));

    route('POST', /^\/api\/enrollment\/confirm$/, (_m, _p, url) => {
        const u = new URL(url, 'http://x');
        const userId = +u.searchParams.get('user_id');
        const user = DB.users.find(u => u.id === userId);
        if (user) user.face_enrolled = 1;
        delete enrollmentSlots[userId];
        return respond({ status: 'ok' });
    });

    // ── Video Feed (placeholder) ──
    // Return a small animated SVG as a fake "camera feed"
    const PLACEHOLDER_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">
        <rect fill="#1a1a2e" width="640" height="480"/>
        <rect fill="#16213e" x="20" y="20" width="600" height="440" rx="12"/>
        <circle cx="320" cy="200" r="60" fill="none" stroke="#e94560" stroke-width="3" opacity="0.6"/>
        <circle cx="320" cy="200" r="20" fill="#e94560" opacity="0.4"/>
        <text x="320" y="310" text-anchor="middle" fill="#e94560" font-family="monospace" font-size="18" opacity="0.7">MOCK CAMERA FEED</text>
        <text x="320" y="340" text-anchor="middle" fill="#888" font-family="monospace" font-size="12">Demo mode — no backend connected</text>
    </svg>`;

    // ── Intercept fetch ──
    const originalFetch = window.fetch;
    window.fetch = async function (input, init) {
        const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input);

        // Only intercept /api/ and /data/ paths
        if (!url.includes('/api/') && !url.includes('/data/')) {
            return originalFetch.call(window, input, init);
        }

        // Video feed — return placeholder SVG
        if (url.includes('/api/session/video_feed')) {
            return new Response(PLACEHOLDER_SVG, {
                status: 200,
                headers: { 'Content-Type': 'image/svg+xml' },
            });
        }

        // Export — return a mock CSV
        if (url.includes('/api/attendance/export')) {
            const csv = 'Student ID,Full Name,Date,Time,Method\n210408502,Michael Obitade,2026-08-19,09:01:30,face\n210408115,James Nwankwo,2026-08-19,09:02:55,face';
            return new Response(csv, {
                status: 200,
                headers: { 'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=attendance_export.csv' },
            });
        }

        // Parse request info
        const method = (init?.method || 'GET').toUpperCase();
        let body = null;
        if (init?.body) {
            try { body = JSON.parse(init.body); } catch { body = init.body; }
        }

        // Find matching route
        const path = new URL(url, 'http://x').pathname;
        for (const r of routes) {
            if (r.method !== method) continue;
            const match = path.match(r.pattern);
            if (match) {
                try {
                    return await r.handler(match, method, url, body);
                } catch (e) {
                    console.error('[MockAPI] Route error:', e);
                    return error('Internal mock error', 500);
                }
            }
        }

        // No route matched — log and return 404
        console.warn('[MockAPI] Unmatched:', method, url);
        return error('Not found (mock)', 404);
    };

    console.log('%c[AttendIQ Mock API] Loaded — all API calls are intercepted.', 'color: #e94560; font-weight: bold;');
})();
