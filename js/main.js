document.addEventListener('DOMContentLoaded', () => {
    // Initialize animators
    window.initAnimations();
    
    // --- 1. THEME TOGGLE ---
    const html = document.documentElement;
    const themeToggle = document.getElementById('theme-toggle');
    const themeJane = document.getElementById('theme-jane');
    
    themeToggle.addEventListener('click', () => {
        const isDark = html.getAttribute('data-theme') === 'dark';
        if (isDark) {
            html.setAttribute('data-theme', 'light');
            themeJane.src = 'res/chibi_jane/day.png';
        } else {
            html.setAttribute('data-theme', 'dark');
            themeJane.src = 'res/chibi_jane/night.png';
        }
    });

    // --- 2. LOADING SEQUENCE ---
    const loadingScreen = document.getElementById('loading-screen');
    const welcomeScreen = document.getElementById('welcome-screen');
    const mainContent = document.getElementById('main-content');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const welcomeText = document.getElementById('welcome-text');
    
    // Start walking animation
    window.animators.walking.start();
    
    let progress = 0;
    const MIN_LOADING_TIME = 5000; // 5 seconds minimum as requested
    const intervalTime = MIN_LOADING_TIME / 100;
    
    const loadingInterval = setInterval(() => {
        progress += 1;
        progressBar.style.width = `${progress}%`;
        progressText.innerText = `${progress}%`;
        
        if (progress >= 100) {
            clearInterval(loadingInterval);
            finishLoading();
        }
    }, intervalTime);
    
    function finishLoading() {
        window.animators.walking.stop();
        
        // Fade out loading screen
        loadingScreen.classList.add('fade-out');
        
        setTimeout(() => {
            loadingScreen.classList.add('hidden');
            
            // Show welcome screen
            welcomeScreen.classList.remove('hidden');
            window.animators.welcome.start();
            
            // Show welcome text slightly after start
            setTimeout(() => {
                welcomeText.classList.remove('hidden-text');
                welcomeText.classList.add('visible');
            }, 700);
            
        }, 500); // Wait for fade out
    }
    
    // Listen for welcome animation complete
    document.addEventListener('welcomeComplete', () => {
        setTimeout(() => {
            // Fade out welcome screen
            welcomeScreen.classList.add('fade-out');
            
            setTimeout(() => {
                welcomeScreen.classList.add('hidden');
                
                // Show main portfolio
                mainContent.classList.remove('hidden');
                
                // Start persistent background animations
                window.animators.clinging.start();
                // Bike animation started on scroll
                
                // Trigger initial scroll update
                handleScroll();
            }, 500);
        }, 1000); // Hold on bow for 1 second
    });
    
    // --- 3. SCROLL LOGIC ---
    let lastScrollY = window.scrollY;
    let bikeTimeout;
    const clingingJane = document.getElementById('jane-clinging');
    const bikeJane = document.getElementById('jane-bike');
    
    function handleScroll() {
        const currentScrollY = window.scrollY;
        const scrollHeight = document.documentElement.scrollHeight;
        const clientHeight = document.documentElement.clientHeight;
        const maxScroll = scrollHeight - clientHeight;
        
        if (maxScroll <= 0) return;
        
        const scrollPercentage = currentScrollY / maxScroll;
        
        // Update Hanging Jane Position
        // Hanging track is roughly clientHeight - some padding. 
        // We calculate max top based on window height and jane height (160px).
        const maxTop = clientHeight - 160; 
        const newTop = maxTop * scrollPercentage;
        clingingJane.style.top = `${newTop}px`;
        
        // Update Bike Jane Logic
        const isScrollingDown = currentScrollY > lastScrollY;
        
        if (Math.abs(currentScrollY - lastScrollY) > 5) {
            window.animators.bike.start();
            
            if (isScrollingDown) {
                window.animators.bike.setFrameUrl('res/chibi_jane/bike_back/');
            } else {
                window.animators.bike.setFrameUrl('res/chibi_jane/bike_front/');
            }
            
            // Stop bike animation after scrolling stops
            clearTimeout(bikeTimeout);
            bikeTimeout = setTimeout(() => {
                window.animators.bike.stop();
            }, 150); // Small buffer to detect scroll end
        }
        
        lastScrollY = currentScrollY;
        
        // Trigger Bye Jane if we reach the bottom
        if (scrollPercentage > 0.98 && !window.animators.bye.isPlaying) {
            // Only start if it's currently on frame 1 to avoid restarting constantly
            if (window.animators.bye.currentFrame === 1) {
                window.animators.bye.start();
            }
        } else if (scrollPercentage < 0.9 && window.animators.bye.currentFrame === window.animators.bye.frameCount) {
            // Reset bye animation if we scroll back up
            window.animators.bye.currentFrame = 1;
            window.animators.bye.updateImage();
        }
    }
    
    window.addEventListener('scroll', handleScroll);
});
