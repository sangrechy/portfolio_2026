/**
 * ============================================================================
 * MAIN CONTROLLER — MITHUN PORTFOLIO 2026
 * Orchestrates Loading -> Welcome -> Main Page, Smooth Scrolling,
 * Bike Travel Lane, Hanging Scrollbar, Theme Toggling, and Chat Relay
 * ============================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Animation Sequences
    window.initAnimations();

    // --- ELEMENTS REFS ---
    const htmlEl = document.documentElement;
    const loadingScreen = document.getElementById('loading-screen');
    const welcomeScreen = document.getElementById('welcome-screen');
    const mainContent = document.getElementById('main-content');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const welcomeText = document.getElementById('welcome-text');
    
    // Bike & Hanging Jane Elements
    const bikeLane = document.getElementById('bike-lane');
    const bikeRunner = document.getElementById('bike-runner');
    const hangingTrack = document.getElementById('hanging-track');
    const clingingCarriage = document.getElementById('clinging-carriage');
    
    // Theme Elements
    const themeBtn = document.getElementById('theme-toggle-btn');
    const themeJane = document.getElementById('theme-jane');

    // Chat Modal Elements
    const chatOverlay = document.getElementById('chat-modal-overlay');
    const chatCloseBtn = document.getElementById('chat-close-btn');
    const chatLogoutBtn = document.getElementById('chat-logout-btn');
    const navChatBtn = document.getElementById('nav-chat-btn');
    const chatTriggers = document.querySelectorAll('.open-chat-trigger');
    const chatStepIntro = document.getElementById('chat-step-intro');
    const chatStepConvo = document.getElementById('chat-step-convo');
    const chatOnboardingForm = document.getElementById('chat-onboarding-form');
    const chatInputName = document.getElementById('chat-input-name');
    const chatInputEmail = document.getElementById('chat-input-email');
    const startChatBtn = document.getElementById('start-chat-btn');
    const chatOtpForm = document.getElementById('chat-otp-form');
    const chatInputOtp = document.getElementById('chat-input-otp');
    const otpTargetEmailDisplay = document.getElementById('otp-target-email-display');
    const otpErrorMsg = document.getElementById('otp-error-msg');
    const verifyOtpBtn = document.getElementById('verify-otp-btn');
    const resendOtpBtn = document.getElementById('resend-otp-btn');
    const changeEmailBtn = document.getElementById('change-email-btn');
    const chatSendForm = document.getElementById('chat-send-form');
    const chatComposerInput = document.getElementById('chat-composer-input');
    const chatStream = document.getElementById('chat-stream');

    // User session data for chat & OTP
    let chatUser = {
        name: '',
        email: '',
        token: ''
    };
    let pendingOtpUser = {
        name: '',
        email: ''
    };

    // ========================================================================
    // 1. THEME ENGINE
    // ========================================================================
    function applyTheme(theme) {
        htmlEl.setAttribute('data-theme', theme);
        localStorage.setItem('portfolio_theme', theme);
        if (theme === 'dark') {
            themeJane.src = 'res/chibi_jane/night.png';
        } else {
            themeJane.src = 'res/chibi_jane/day.png';
        }
    }

    const savedTheme = localStorage.getItem('portfolio_theme') || 'dark';
    applyTheme(savedTheme);

    themeBtn.addEventListener('click', () => {
        const currentTheme = htmlEl.getAttribute('data-theme') || 'dark';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
    });

    // ========================================================================
    // 2. LOADING & WELCOME TRANSITION (Blueprint Sections 2 & 3)
    // ========================================================================
    window.animators.walking.start();
    
    // Smooth 60fps requestAnimationFrame Progress Bar
    const LOADING_DURATION = 1000; // 1000ms smooth progression
    const startTime = performance.now();

    function stepProgress(now) {
        const elapsed = now - startTime;
        const progressFraction = Math.min(elapsed / LOADING_DURATION, 1);
        const percent = Math.round(progressFraction * 100);

        progressBar.style.width = `${percent}%`;
        progressText.textContent = `${percent}%`;

        if (progressFraction < 1) {
            requestAnimationFrame(stepProgress);
        } else {
            // Explicitly lock to 100%
            progressBar.style.width = '100%';
            progressText.textContent = '100%';
            
            // Brief moment (120ms) so 100% is clearly seen before fading out
            setTimeout(() => {
                handleLoadingComplete();
            }, 120);
        }
    }

    requestAnimationFrame(stepProgress);

    function handleLoadingComplete() {
        window.animators.walking.stop();
        loadingScreen.classList.add('fade-out');

        // Immediate snap to welcome with no artificial lag
        setTimeout(() => {
            loadingScreen.classList.add('hidden');
            welcomeScreen.classList.remove('hidden');
            welcomeText.classList.remove('hidden-text');
            welcomeText.classList.add('visible');
            window.animators.welcome.start();
        }, 160);
    }

    // Welcome Complete Handler: 350ms frame sequence + 150ms hold = exactly 0.5s (500ms)
    document.addEventListener('welcomeComplete', () => {
        setTimeout(() => {
            welcomeScreen.classList.add('fade-out');
            
            setTimeout(() => {
                welcomeScreen.classList.add('hidden');
                mainContent.classList.remove('hidden');

                // Start Hanging Jane animation
                window.animators.clinging.start();

                // Initial scroll positioning
                updateScrollPositions();
            }, 160);
        }, 150);
    });

    // ========================================================================
    // 3. SCROLL SYSTEM: BIKE JANE (LEFT) & HANGING JANE (RIGHT)
    // ========================================================================
    let lastScrollY = window.scrollY;
    let bikePauseTimer = null;
    let isDraggingScrollbar = false;

    function updateScrollPositions() {
        const currentScrollY = window.scrollY;
        const scrollHeight = document.documentElement.scrollHeight;
        const clientHeight = document.documentElement.clientHeight;
        const maxScroll = scrollHeight - clientHeight;

        if (maxScroll <= 0) return;

        const scrollPercentage = Math.min(1, Math.max(0, currentScrollY / maxScroll));

        // --- A. BIKE JANE JOURNEY (LEFT SIDE) ---
        // Bike travels within its fixed lane from top to middle to bottom
        if (bikeLane && bikeRunner) {
            const laneHeight = bikeLane.clientHeight;
            const runnerHeight = bikeRunner.clientHeight || 84;
            const maxBikeTravel = Math.max(0, laneHeight - runnerHeight);
            const bikeTop = scrollPercentage * maxBikeTravel;
            bikeRunner.style.top = `${bikeTop}px`;

            // Detect scroll direction and animate bike
            const scrollDelta = currentScrollY - lastScrollY;
            if (Math.abs(scrollDelta) > 2) {
                window.animators.bike.start();

                if (scrollDelta > 0) {
                    // Scrolling DOWN: use bike_front/
                    window.animators.bike.setFrameUrl('res/chibi_jane/bike_front/');
                } else {
                    // Scrolling UP: use bike_back/
                    window.animators.bike.setFrameUrl('res/chibi_jane/bike_back/');
                }

                clearTimeout(bikePauseTimer);
                bikePauseTimer = setTimeout(() => {
                    window.animators.bike.stop();
                }, 160);
            }
        }

        // --- B. HANGING JANE SCROLLBAR (RIGHT SIDE) ---
        if (hangingTrack && clingingCarriage && !isDraggingScrollbar) {
            const trackHeight = hangingTrack.clientHeight;
            const carriageHeight = clingingCarriage.offsetHeight || 110;
            const maxTrackTravel = Math.max(0, trackHeight - carriageHeight);
            const clingTop = scrollPercentage * maxTrackTravel;
            clingingCarriage.style.top = `${clingTop}px`;
        }

        // --- C. FOOTER BYE JANE TRIGGER (Continuous Loop) ---
        if (scrollPercentage > 0.88) {
            if (!window.animators.bye.isPlaying) {
                window.animators.bye.start();
            }
        } else if (scrollPercentage < 0.80) {
            if (window.animators.bye.isPlaying) {
                window.animators.bye.stop();
            }
        }

        // --- D. NAV LINK ACTIVE HIGHLIGHT ---
        updateActiveNavLink();

        lastScrollY = currentScrollY;
    }

    // Passive scroll listener
    window.addEventListener('scroll', updateScrollPositions, { passive: true });
    window.addEventListener('resize', updateScrollPositions);

    // ========================================================================
    // 4. INTERACTIVE HANGING SCROLLBAR (True Native Scrollbar Behavior)
    // ========================================================================
    if (hangingTrack && clingingCarriage) {
        let dragGrabOffsetY = 0;

        function getScrollMetrics() {
            const trackRect = hangingTrack.getBoundingClientRect();
            const carriageHeight = clingingCarriage.offsetHeight || 110;
            const maxTravel = Math.max(1, trackRect.height - carriageHeight);
            const scrollHeight = document.documentElement.scrollHeight;
            const clientHeight = document.documentElement.clientHeight;
            const maxScroll = Math.max(1, scrollHeight - clientHeight);
            return { trackRect, carriageHeight, maxTravel, maxScroll };
        }

        function setScrollFromThumb(thumbTop, metrics) {
            const clampedTop = Math.max(0, Math.min(metrics.maxTravel, thumbTop));
            // Move Jane carriage directly with cursor
            clingingCarriage.style.top = `${clampedTop}px`;
            // Scroll document to matching position
            const scrollRatio = clampedTop / metrics.maxTravel;
            window.scrollTo(0, scrollRatio * metrics.maxScroll);
        }

        // Pointer down on Carriage: starts drag
        clingingCarriage.addEventListener('pointerdown', (e) => {
            isDraggingScrollbar = true;
            clingingCarriage.setPointerCapture(e.pointerId);
            clingingCarriage.classList.add('is-dragging');

            const carriageRect = clingingCarriage.getBoundingClientRect();
            dragGrabOffsetY = e.clientY - carriageRect.top;

            document.body.style.userSelect = 'none';
            e.preventDefault();
            e.stopPropagation();
        });

        // Pointer move: Jane follows cursor 1:1 in real time
        clingingCarriage.addEventListener('pointermove', (e) => {
            if (!isDraggingScrollbar) return;
            const metrics = getScrollMetrics();
            const thumbTop = e.clientY - metrics.trackRect.top - dragGrabOffsetY;
            setScrollFromThumb(thumbTop, metrics);
        });

        function endDrag(e) {
            if (isDraggingScrollbar) {
                isDraggingScrollbar = false;
                try { clingingCarriage.releasePointerCapture(e.pointerId); } catch (err) {}
                clingingCarriage.classList.remove('is-dragging');
                document.body.style.userSelect = '';
            }
        }

        clingingCarriage.addEventListener('pointerup', endDrag);
        clingingCarriage.addEventListener('pointercancel', endDrag);

        // Click track outside carriage: jump scrollbar directly to clicked location
        hangingTrack.addEventListener('pointerdown', (e) => {
            if (e.target.closest('#clinging-carriage')) return;
            const metrics = getScrollMetrics();
            const targetTop = e.clientY - metrics.trackRect.top - (metrics.carriageHeight / 2);
            setScrollFromThumb(targetTop, metrics);
        });
    }

    // ========================================================================
    // 5. NAV ACTIVE LINK HIGHLIGHTING
    // ========================================================================
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.main-nav .nav-link:not(.nav-btn)');

    function updateActiveNavLink() {
        const scrollPosition = window.scrollY + 180;
        sections.forEach((section) => {
            const top = section.offsetTop;
            const height = section.offsetHeight;
            const id = section.getAttribute('id');
            if (scrollPosition >= top && scrollPosition < top + height) {
                navLinks.forEach((link) => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === `#${id}`) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }

    // ========================================================================
    // 6. PROJECT GALLERY THUMBNAIL SWITCHER
    // ========================================================================
    const galleryButtons = document.querySelectorAll('.gallery-thumb-btn');
    
    // Sample views data for each project
    const projectViews = {
        '1': {
            '1': {
                code: `// AI Automation & Telegram Bot Orchestrator
class AutonomousAgentDispatcher:
    def __init__(self, api_key: str):
        self.router = APIRouter(prefix="/api/agent")
        self.event_bus = EventBus()
        
    async def dispatch(self, payload: AgentPayload) -> TaskResult:
        telegram_worker.notify(f"Dispatched task: {payload.name}")
        return await engine.execute(payload)`,
                bg: 'linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%)'
            },
            '2': {
                code: `// Telegram Instant Bot Webhook Handler
async def handle_telegram_webhook(update: TelegramUpdate):
    chat_id = update.message.chat.id
    user_text = update.message.text
    
    analysis = await ai_engine.analyze(user_text)
    await bot.send_message(chat_id, text=analysis.summary)`,
                bg: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)'
            },
            '3': {
                code: `// High-Performance Task Metrics
{
    "uptime": "99.98%",
    "avg_latency_ms": 14.2,
    "telegram_dispatch_latency": "120ms",
    "active_agents": 8
}`,
                bg: 'linear-gradient(135deg, #172554 0%, #0f172a 100%)'
            }
        },
        '2': {
            '1': {
                code: `// Realtime Cloud Telemetry Dashboard
const DashboardStream = () => {
    const [metrics, setMetrics] = useState<MetricData[]>([]);
    useWebSocket("wss://telemetry.mithun.dev", {
        onMessage: (evt) => updateHeatmap(JSON.parse(evt.data))
    });
    return <InteractiveHeatmap data={metrics} />;
};`,
                bg: 'linear-gradient(135deg, #022c22 0%, #064e3b 100%)'
            },
            '2': {
                code: `// Distributed Cloud Trace Exporter
func ExportTraceSpan(ctx context.Context, span *TraceSpan) error {
    payload := serialize(span)
    return kafkaProducer.Send("traces.telemetry", payload)
}`,
                bg: 'linear-gradient(135deg, #042f2e 0%, #134e4a 100%)'
            },
            '3': {
                code: `// Benchmark Throughput
BenchmarkTelemetryIngest-8   5000000   240 ns/op
Heap allocations: 0 allocs/op
GC Pause time: < 0.2ms`,
                bg: 'linear-gradient(135deg, #064e3b 0%, #022c22 100%)'
            }
        },
        '3': {
            '1': {
                code: `// High-Concurrency Distributed Chat Server
class ChatHub:
    def __init__(self):
        self.active_conns: list[WebSocket] = []
        self.redis_client = aioredis.from_url("redis://localhost:6379")
        
    async def broadcast(self, channel: str, msg: dict):
        await self.redis_client.publish(channel, json.dumps(msg))`,
                bg: 'linear-gradient(135deg, #311042 0%, #1e1b4b 100%)'
            },
            '2': {
                code: `// Redis Pub/Sub Stream Consumer
async def listen_redis_stream(hub: ChatHub):
    async for message in hub.redis_client.channel_reader("chat"):
        await hub.dispatch_to_clients(message.data)`,
                bg: 'linear-gradient(135deg, #2e1065 0%, #1e1b4b 100%)'
            },
            '3': {
                code: `// WebSocket Stress Benchmark (50,000 Concurrent Users)
Success Rate: 100%
p99 Delivery: 8ms
Memory Footprint: 210MB`,
                bg: 'linear-gradient(135deg, #1e1b4b 0%, #3b0764 100%)'
            }
        }
    };

    galleryButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
            const projId = btn.getAttribute('data-proj');
            const viewId = btn.getAttribute('data-view');
            const container = document.getElementById(`project-${projId}`);
            if (!container) return;

            // Toggle active button state
            container.querySelectorAll('.gallery-thumb-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update visual preview
            const canvasLayer = container.querySelector('.canvas-image-layer');
            const codeBlock = container.querySelector('.canvas-code-preview code');
            
            if (projectViews[projId] && projectViews[projId][viewId]) {
                const viewData = projectViews[projId][viewId];
                if (canvasLayer) canvasLayer.style.background = viewData.bg;
                if (codeBlock) codeBlock.textContent = viewData.code;
            }
        });
    });

    // ========================================================================
    // 7. CHAT UI MODAL & FASTAPI / TELEGRAM BRIDGE
    // ========================================================================
    function openChatModal() {
        chatOverlay.classList.remove('hidden');
    }

    function closeChatModal() {
        chatOverlay.classList.add('hidden');
    }

    // Triggers
    if (navChatBtn) navChatBtn.addEventListener('click', openChatModal);
    chatTriggers.forEach(t => t.addEventListener('click', openChatModal));
    if (chatCloseBtn) chatCloseBtn.addEventListener('click', closeChatModal);

    chatOverlay.addEventListener('click', (e) => {
        if (e.target === chatOverlay) closeChatModal();
    });

    function getBackendUrl(path) {
        const origin = window.location.origin || '';
        if (origin.startsWith('http') && (origin.includes(':8000') || (!origin.includes(':5500') && !origin.includes(':3000')))) {
            return path;
        }
        return `http://127.0.0.1:8000${path}`;
    }

    // --- COOKIE & SESSION STORAGE HELPERS (10-Day Session Lifetime) ---
    function setCookie(name, value, days = 10) {
        const expires = new Date(Date.now() + days * 864e5).toUTCString();
        document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
    }

    function getCookie(name) {
        return document.cookie.split('; ').reduce((r, v) => {
            const parts = v.split('=');
            return parts[0] === name ? decodeURIComponent(parts[1]) : r;
        }, '');
    }

    function deleteCookie(name) {
        document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
    }

    function persistChatSession(name, email, token = '') {
        const data = JSON.stringify({ name, email, token, timestamp: Date.now() });
        setCookie('portfolio_chat_user', data, 10);
        try { localStorage.setItem('portfolio_chat_user', data); } catch (e) {}
    }

    function getStoredChatSession() {
        try {
            const raw = getCookie('portfolio_chat_user') || localStorage.getItem('portfolio_chat_user');
            if (raw) return JSON.parse(raw);
        } catch (e) {}
        return null;
    }

    function clearChatSession() {
        deleteCookie('portfolio_chat_user');
        try { localStorage.removeItem('portfolio_chat_user'); } catch (e) {}
    }

    // --- TELEMETRY: VISITOR TRACKING (On Load) ---
    try {
        fetch(getBackendUrl('/api/telemetry/visit'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ page: window.location.pathname })
        }).catch(() => {});
    } catch (e) {}

    // 2-Way Chat Live Poller (Fetches Mithun's replies from Telegram)
    let chatPollTimer = null;
    const seenReplyIds = new Set();

    async function fetchReplies(email) {
        if (!email) return;
        try {
            const pollUrl = getBackendUrl(`/api/chat/poll?email=${encodeURIComponent(email)}`);
            const res = await fetch(pollUrl);
            if (res.ok) {
                const data = await res.json();
                if (data.messages && Array.isArray(data.messages)) {
                    data.messages.forEach(msg => {
                        if (!seenReplyIds.has(msg.id)) {
                            seenReplyIds.add(msg.id);
                            appendMessage('received', msg.message);
                        }
                    });
                }
            }
        } catch (err) {
            // Ignore background polling glitches silently
        }
    }

    function startChatPolling(email) {
        if (!email) return;
        if (chatPollTimer) clearInterval(chatPollTimer);
        
        // Immediate fetch upon entering chat
        fetchReplies(email);

        chatPollTimer = setInterval(() => {
            if (!email || chatStepConvo.classList.contains('hidden')) return;
            fetchReplies(email);
        }, 1200);
    }

    async function enterConversationView(isReturning = false) {
        chatStepIntro.classList.add('hidden');
        chatStepConvo.classList.remove('hidden');
        if (chatLogoutBtn) chatLogoutBtn.classList.remove('hidden');

        if (isReturning) {
            // Load conversation history
            try {
                const historyUrl = getBackendUrl(`/api/chat/history?email=${encodeURIComponent(chatUser.email)}`);
                const res = await fetch(historyUrl);
                if (res.ok) {
                    const data = await res.json();
                    if (data.history && data.history.length > 0) {
                        chatStream.innerHTML = '';
                        data.history.forEach(item => {
                            seenReplyIds.add(item.id);
                            appendMessage(item.type, item.message);
                        });
                    } else {
                        chatStream.innerHTML = '';
                        appendMessage('received', `Welcome back ${chatUser.name}! Your verified 10-day session is active. What's on your mind?`);
                    }
                }
            } catch (e) {
                appendMessage('received', `Welcome back ${chatUser.name}! Reconnected to direct relay.`);
            }
        } else {
            chatStream.innerHTML = '';
            appendMessage('received', `Welcome ${chatUser.name}! Your email has been verified and connected to Mithun's direct relay. What would you like to discuss?`);
        }

        chatComposerInput.focus();
        startChatPolling(chatUser.email);
    }

    // Restore existing verified session from Cookie / LocalStorage on boot
    const storedSession = getStoredChatSession();
    if (storedSession && storedSession.name && storedSession.email && storedSession.token) {
        chatUser.name = storedSession.name;
        chatUser.email = storedSession.email;
        chatUser.token = storedSession.token;
        enterConversationView(true);
    }

    // Step 1A: Onboarding Form Submit -> Send OTP
    if (chatOnboardingForm) {
        chatOnboardingForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = chatInputName.value.trim();
            const email = chatInputEmail.value.trim();

            if (!name || !email) return;

            pendingOtpUser = { name, email };
            if (startChatBtn) {
                startChatBtn.disabled = true;
                startChatBtn.textContent = '[ SENDING CODE... ]';
            }

            try {
                const resp = await fetch(getBackendUrl('/api/otp/send'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, email })
                });

                const data = await resp.json();
                if (resp.ok && data.status === 'success') {
                    // Transition to OTP verification step
                    chatOnboardingForm.classList.add('hidden');
                    chatOtpForm.classList.remove('hidden');
                    if (otpTargetEmailDisplay) otpTargetEmailDisplay.textContent = email;
                    if (chatInputOtp) {
                        chatInputOtp.value = '';
                        chatInputOtp.focus();
                    }
                    if (otpErrorMsg) otpErrorMsg.classList.add('hidden');
                } else {
                    alert(data.detail || 'Could not send verification code. Please try again.');
                }
            } catch (err) {
                alert('Failed to connect to verification server. Please ensure the backend is active.');
            } finally {
                if (startChatBtn) {
                    startChatBtn.disabled = false;
                    startChatBtn.textContent = '[ SEND VERIFICATION CODE ]';
                }
            }
        });
    }

    // Step 1B: OTP Form Submit -> Verify Code & Establish 10-Day Session
    if (chatOtpForm) {
        chatOtpForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const otpCode = chatInputOtp ? chatInputOtp.value.trim() : '';
            if (!otpCode || otpCode.length !== 6) {
                if (otpErrorMsg) {
                    otpErrorMsg.textContent = 'Please enter a valid 6-digit code.';
                    otpErrorMsg.classList.remove('hidden');
                }
                return;
            }

            if (verifyOtpBtn) {
                verifyOtpBtn.disabled = true;
                verifyOtpBtn.textContent = '[ VERIFYING... ]';
            }

            try {
                const resp = await fetch(getBackendUrl('/api/otp/verify'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: pendingOtpUser.name,
                        email: pendingOtpUser.email,
                        otp: otpCode
                    })
                });

                const data = await resp.json();
                if (resp.ok && data.verified) {
                    // Success! Establish 10-day verified session
                    chatUser.name = pendingOtpUser.name;
                    chatUser.email = pendingOtpUser.email;
                    chatUser.token = data.token || 'verified_token';
                    persistChatSession(chatUser.name, chatUser.email, chatUser.token);

                    // Reset forms
                    chatOtpForm.classList.add('hidden');
                    chatOnboardingForm.classList.remove('hidden');
                    if (otpErrorMsg) otpErrorMsg.classList.add('hidden');

                    // Enter live chat
                    enterConversationView(false);
                } else {
                    if (otpErrorMsg) {
                        otpErrorMsg.textContent = data.detail || 'Invalid verification code. Please try again.';
                        otpErrorMsg.classList.remove('hidden');
                    }
                    if (chatInputOtp) {
                        chatInputOtp.focus();
                        chatInputOtp.select();
                    }
                }
            } catch (err) {
                if (otpErrorMsg) {
                    otpErrorMsg.textContent = 'Connection error. Please try again.';
                    otpErrorMsg.classList.remove('hidden');
                }
            } finally {
                if (verifyOtpBtn) {
                    verifyOtpBtn.disabled = false;
                    verifyOtpBtn.textContent = '[ VERIFY & START CHAT ]';
                }
            }
        });
    }

    // Resend OTP handler
    if (resendOtpBtn) {
        resendOtpBtn.addEventListener('click', async () => {
            if (!pendingOtpUser.email) return;
            resendOtpBtn.textContent = 'Sending...';
            resendOtpBtn.disabled = true;
            try {
                await fetch(getBackendUrl('/api/otp/send'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(pendingOtpUser)
                });
                resendOtpBtn.textContent = 'Code Sent!';
                setTimeout(() => {
                    resendOtpBtn.textContent = 'Resend Code';
                    resendOtpBtn.disabled = false;
                }, 3000);
            } catch (e) {
                resendOtpBtn.textContent = 'Failed';
                setTimeout(() => {
                    resendOtpBtn.textContent = 'Resend Code';
                    resendOtpBtn.disabled = false;
                }, 2000);
            }
        });
    }

    // Change Email handler
    if (changeEmailBtn) {
        changeEmailBtn.addEventListener('click', () => {
            chatOtpForm.classList.add('hidden');
            chatOnboardingForm.classList.remove('hidden');
            if (otpErrorMsg) otpErrorMsg.classList.add('hidden');
            if (chatInputEmail) chatInputEmail.focus();
        });
    }

    // Logout Button Handler
    if (chatLogoutBtn) {
        chatLogoutBtn.addEventListener('click', async () => {
            const oldName = chatUser.name;
            const oldEmail = chatUser.email;

            // Send logout notification to Telegram
            try {
                fetch(getBackendUrl('/api/chat/status'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: oldName,
                        email: oldEmail,
                        action: 'logout'
                    }),
                    keepalive: true
                });
            } catch (err) {}

            // Clear session & reset UI
            clearChatSession();
            chatUser = { name: '', email: '', token: '' };
            pendingOtpUser = { name: '', email: '' };

            if (chatPollTimer) clearInterval(chatPollTimer);
            chatStepConvo.classList.add('hidden');
            chatStepIntro.classList.remove('hidden');
            chatLogoutBtn.classList.add('hidden');
            chatOnboardingForm.classList.remove('hidden');
            chatOtpForm.classList.add('hidden');
            if (chatInputName) chatInputName.value = '';
            if (chatInputEmail) chatInputEmail.value = '';
            if (chatInputOtp) chatInputOtp.value = '';
            chatStream.innerHTML = '';
        });
    }

    // Page Reload / Unload Event Listener (Beacon to Telegram for Visit Exit & Chat Exit)
    window.addEventListener('beforeunload', () => {
        // 1. General visitor exit beacon
        try {
            navigator.sendBeacon(
                getBackendUrl('/api/telemetry/exit'),
                JSON.stringify({ page: window.location.pathname })
            );
        } catch (e) {}

        // 2. Chat user session status beacon if logged in
        if (chatUser.email && chatUser.name) {
            try {
                navigator.sendBeacon(
                    getBackendUrl('/api/chat/status'),
                    JSON.stringify({
                        name: chatUser.name,
                        email: chatUser.email,
                        action: 'reload_or_exit'
                    })
                );
            } catch (e) {}
        }
    });

    // Step 2: Message Sender
    if (chatSendForm) {
        chatSendForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const messageText = chatComposerInput.value.trim();
            if (!messageText) return;

            // Render sent bubble immediately
            appendMessage('sent', messageText);
            chatComposerInput.value = '';

            // Ensure polling is active
            startChatPolling(chatUser.email);

            // Forward to FastAPI backend (which routes to Telegram with IP & Geo)
            try {
                const apiUrl = getBackendUrl('/api/chat');
                const response = await fetch(apiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: chatUser.name,
                        email: chatUser.email,
                        message: messageText
                    })
                });

                if (response.ok) {
                    // Check for replies immediately
                    setTimeout(() => fetchReplies(chatUser.email), 600);
                }
            } catch (err) {
                console.log('[Chat Dispatch Error]:', err);
            }
        });
    }

    function appendMessage(type, text) {
        const row = document.createElement('div');
        row.className = `chat-bubble-row ${type}`;

        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        if (type === 'received') {
            row.innerHTML = `
                <img src="res/chibi_jane/dp.png" alt="Mithun Avatar" class="chat-bubble-dp">
                <div class="chat-bubble">
                    <span class="sender-name">Mithun</span>
                    <p>${escapeHtml(text)}</p>
                    <span class="bubble-time">${timeStr}</span>
                </div>
            `;
        } else {
            row.innerHTML = `
                <div class="chat-bubble">
                    <p>${escapeHtml(text)}</p>
                    <span class="bubble-time">${timeStr}</span>
                </div>
            `;
        }

        chatStream.appendChild(row);
        chatStream.scrollTop = chatStream.scrollHeight;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
});
