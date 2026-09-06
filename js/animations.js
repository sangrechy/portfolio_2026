/**
 * ============================================================================
 * JANE ANIMATION CONTROLLER (v2.0)
 * Handles precise frame-by-frame sequences with instant cache lookups
 * ============================================================================
 */

class JaneAnimator {
    constructor(elementId, frameBaseUrl, frameCount, frameDelay, loop = true, onComplete = null) {
        this.element = document.getElementById(elementId);
        this.frameBaseUrl = frameBaseUrl;
        this.frameCount = frameCount;
        this.frameDelay = frameDelay;
        this.loop = loop;
        this.onComplete = onComplete;
        
        this.currentFrame = 1;
        this.timer = null;
        this.isPlaying = false;
        
        // Image cache dictionary: baseUrl -> Array<Image>
        this.cache = {};
        this.preloadFrames(frameBaseUrl, frameCount);
    }

    preloadFrames(baseUrl, count) {
        if (this.cache[baseUrl]) return;
        this.cache[baseUrl] = [];
        for (let i = 1; i <= count; i++) {
            const img = new Image();
            img.src = `${baseUrl}${i}.png`;
            this.cache[baseUrl].push(img);
        }
    }

    start() {
        if (this.isPlaying) return;
        this.isPlaying = true;
        this.timer = setInterval(() => this.nextFrame(), this.frameDelay);
    }

    stop() {
        if (!this.isPlaying) return;
        this.isPlaying = false;
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    nextFrame() {
        this.currentFrame++;
        
        if (this.currentFrame > this.frameCount) {
            if (this.loop) {
                this.currentFrame = 1;
            } else {
                this.currentFrame = this.frameCount; // Hold on final frame
                this.stop();
                if (this.onComplete) this.onComplete();
                return;
            }
        }
        
        this.updateImage();
    }
    
    updateImage() {
        if (this.element && this.cache[this.frameBaseUrl]) {
            const cachedImg = this.cache[this.frameBaseUrl][this.currentFrame - 1];
            if (cachedImg && cachedImg.src) {
                this.element.src = cachedImg.src;
            }
        }
    }
    
    setFrameUrl(frameBaseUrl) {
        if (this.frameBaseUrl === frameBaseUrl) return;
        this.frameBaseUrl = frameBaseUrl;
        this.preloadFrames(frameBaseUrl, this.frameCount);
        this.updateImage();
    }
}

// Global Animators Map
const animators = {};

function initAnimations() {
    // 1. Walking (Loading Screen) - 8 frames, 120ms
    animators.walking = new JaneAnimator('jane-walking', 'res/chibi_jane/walking/', 8, 120, true);
    
    // 2. Welcome (Intro Bow) - 5 frames, 70ms, plays 1->5 once, total ~350ms + 150ms hold (0.5s total)
    animators.welcome = new JaneAnimator('jane-welcome', 'res/chibi_jane/welcome/', 5, 70, false, () => {
        document.dispatchEvent(new Event('welcomeComplete'));
    });
    
    // 3. Bike (Scroll journey) - Preload BOTH bike_front (downward) and bike_back (upward)
    animators.bike = new JaneAnimator('jane-bike', 'res/chibi_jane/bike_front/', 8, 110, true);
    animators.bike.preloadFrames('res/chibi_jane/bike_back/', 8);
    
    // 4. Clinging (Right Scrollbar Jane) - 4 frames, 200ms
    animators.clinging = new JaneAnimator('jane-clinging', 'res/chibi_jane/clinging/', 4, 200, true);
    
    // 5. Bye (Footer ending in continuous loop) - 4 frames, 130ms, loop = true
    animators.bye = new JaneAnimator('jane-bye', 'res/chibi_jane/bye/', 4, 130, true);
}

// Expose globally
window.initAnimations = initAnimations;
window.animators = animators;
