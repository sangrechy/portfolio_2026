/**
 * Jane Animation Controller
 * Handles frame-by-frame sequences for various Jane states.
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
        
        // Preload images
        this.images = [];
        for (let i = 1; i <= frameCount; i++) {
            const img = new Image();
            img.src = `${this.frameBaseUrl}${i}.png`;
            this.images.push(img);
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
        clearInterval(this.timer);
        this.timer = null;
    }

    nextFrame() {
        this.currentFrame++;
        
        if (this.currentFrame > this.frameCount) {
            if (this.loop) {
                this.currentFrame = 1;
            } else {
                this.currentFrame = this.frameCount; // Hold on last frame
                this.stop();
                if (this.onComplete) this.onComplete();
                return;
            }
        }
        
        this.updateImage();
    }
    
    updateImage() {
        if (this.element) {
            // Use preloaded image source
            this.element.src = this.images[this.currentFrame - 1].src;
        }
    }
    
    setFrameUrl(frameBaseUrl) {
        if (this.frameBaseUrl === frameBaseUrl) return;
        this.frameBaseUrl = frameBaseUrl;
        
        // Preload new images
        this.images = [];
        for (let i = 1; i <= this.frameCount; i++) {
            const img = new Image();
            img.src = `${this.frameBaseUrl}${i}.png`;
            this.images.push(img);
        }
        
        this.updateImage();
    }
}

// Global Animators
const animators = {};

function initAnimations() {
    // 1. Walking (Loading) - 8 frames, 120ms
    animators.walking = new JaneAnimator('jane-walking', 'res/chibi_jane/walking/', 8, 120, true);
    
    // 2. Welcome - 5 frames, 500ms, plays once
    animators.welcome = new JaneAnimator('jane-welcome', 'res/chibi_jane/welcome/', 5, 500, false, () => {
        // Expose a global event when welcome finishes
        document.dispatchEvent(new Event('welcomeComplete'));
    });
    
    // 3. Bike (Scroll) - 8 frames, 120ms, loops
    animators.bike = new JaneAnimator('jane-bike', 'res/chibi_jane/bike_back/', 8, 120, true);
    
    // 4. Clinging (Scrollbar) - 4 frames, 200ms
    animators.clinging = new JaneAnimator('jane-clinging', 'res/chibi_jane/clinging/', 4, 200, true);
    
    // 5. Bye (Footer) - 4 frames, 120ms, plays once and holds (or loops based on preference, instructions say 1->4 hold if intended, but also HTML said loop. We'll play once and hold).
    animators.bye = new JaneAnimator('jane-bye', 'res/chibi_jane/bye/', 4, 120, false);
}

// Export to window
window.initAnimations = initAnimations;
window.animators = animators;
