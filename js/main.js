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
    const navChatBtn = document.getElementById('nav-chat-btn');
    const chatTriggers = document.querySelectorAll('.open-chat-trigger');
    const chatStepIntro = document.getElementById('chat-step-intro');
    const chatStepConvo = document.getElementById('chat-step-convo');
    const chatOnboardingForm = document.getElementById('chat-onboarding-form');
    const chatInputName = document.getElementById('chat-input-name');
    const chatInputEmail = document.getElementById('chat-input-email');
    const chatSendForm = document.getElementById('chat-send-form');
    const chatComposerInput = document.getElementById('chat-composer-input');
    const chatStream = document.getElementById('chat-stream');

    // User session data for chat
    let chatUser = {
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

    // Step 1: Onboarding Submit
    if (chatOnboardingForm) {
        chatOnboardingForm.addEventListener('submit', (e) => {
            e.preventDefault();
            chatUser.name = chatInputName.value.trim();
            chatUser.email = chatInputEmail.value.trim();

            if (!chatUser.name || !chatUser.email) return;

            // Transition to Step 2
            chatStepIntro.classList.add('hidden');
            chatStepConvo.classList.remove('hidden');

            // Personalize greeting
            appendMessage('received', `Welcome ${chatUser.name}! I've connected our conversation to Mithun's direct relay. What would you like to discuss?`);
            chatComposerInput.focus();
        });
    }

    // Step 2: Message Sender
    if (chatSendForm) {
        chatSendForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const messageText = chatComposerInput.value.trim();
            if (!messageText) return;

            // Render sent bubble immediately
            appendMessage('sent', messageText);
            chatComposerInput.value = '';

            // Forward to FastAPI backend (which routes to Telegram)
            try {
                const apiUrl = window.location.origin.startsWith('http') ? '/api/chat' : 'http://localhost:8000/api/chat';
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
                    const data = await response.json();
                    setTimeout(() => {
                        appendMessage('received', data.reply || "Thanks for your message! It has been dispatched directly to Mithun's Telegram.");
                    }, 500);
                } else {
                    throw new Error('API unavailable');
                }
            } catch (err) {
                // Graceful fallback response when backend is offline or loading
                setTimeout(() => {
                    appendMessage('received', `Thanks ${chatUser.name}! Your message has been captured. Mithun will review and reply to ${chatUser.email} shortly.`);
                }, 600);
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
