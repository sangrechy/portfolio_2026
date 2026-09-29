/**
 * projects.js
 * Interactive logic for Project Gallery & Engineering Vault
 * Handles Theme Sync, Deep Linking, Smooth Hash Scroll, and Lightbox Modal
 */

(function () {
    'use strict';

    // =========================================================================
    // 1. THEME SYNCHRONIZATION
    // =========================================================================
    const htmlEl = document.documentElement;
    const themeBtn = document.getElementById('gallery-theme-toggle');
    const themeIcon = document.getElementById('theme-toggle-icon');
    const themeLabel = document.getElementById('theme-toggle-label');

    function applyTheme(theme) {
        htmlEl.setAttribute('data-theme', theme);
        localStorage.setItem('portfolio_theme', theme);
        if (theme === 'dark') {
            if (themeIcon) themeIcon.textContent = '☀️';
            if (themeLabel) themeLabel.textContent = 'Light';
        } else {
            if (themeIcon) themeIcon.textContent = '🌙';
            if (themeLabel) themeLabel.textContent = 'Dark';
        }
    }

    const savedTheme = localStorage.getItem('portfolio_theme') || 'dark';
    applyTheme(savedTheme);

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const current = htmlEl.getAttribute('data-theme') || 'dark';
            applyTheme(current === 'dark' ? 'light' : 'dark');
        });
    }

    // =========================================================================
    // 2. QUICK JUMP PILLS & SMOOTH HASH SCROLL
    // =========================================================================
    const jumpPills = document.querySelectorAll('.jump-pill');
    const projectSections = document.querySelectorAll('.project-section-wrapper');

    // Handle initial hash on page load
    function handleInitialHash() {
        const hash = window.location.hash;
        if (!hash) return;

        const targetId = hash.replace('#', '');
        const targetSection = document.getElementById(targetId);
        if (targetSection) {
            setTimeout(() => {
                targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                targetSection.classList.add('pulse-highlight');
                setTimeout(() => targetSection.classList.remove('pulse-highlight'), 2200);

                // Update active pill
                jumpPills.forEach(pill => {
                    if (pill.getAttribute('href') === hash) {
                        pill.classList.add('active');
                    } else {
                        pill.classList.remove('active');
                    }
                });
            }, 250);
        }
    }

    // Click handler for jump pills
    jumpPills.forEach(pill => {
        pill.addEventListener('click', (e) => {
            const href = pill.getAttribute('href');
            if (href === '#all') {
                e.preventDefault();
                window.scrollTo({ top: 0, behavior: 'smooth' });
                jumpPills.forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                history.replaceState(null, '', window.location.pathname);
                return;
            }

            const targetSection = document.querySelector(href);
            if (targetSection) {
                e.preventDefault();
                targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                targetSection.classList.add('pulse-highlight');
                setTimeout(() => targetSection.classList.remove('pulse-highlight'), 2200);
                jumpPills.forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                history.replaceState(null, '', href);
            }
        });
    });

    // Scroll spy via IntersectionObserver
    if ('IntersectionObserver' in window && projectSections.length > 0) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.id;
                    jumpPills.forEach(pill => {
                        if (pill.getAttribute('href') === `#${id}`) {
                            pill.classList.add('active');
                        } else {
                            pill.classList.remove('active');
                        }
                    });
                }
            });
        }, {
            rootMargin: '-20% 0px -60% 0px',
            threshold: 0.1
        });

        projectSections.forEach(sec => observer.observe(sec));
    }

    // =========================================================================
    // 3. CYBERPUNK LIGHTBOX MODAL
    // =========================================================================
    const lightbox = document.getElementById('gallery-lightbox');
    const lightboxBox = document.getElementById('lightbox-box');
    const lightboxCounter = document.getElementById('lightbox-counter');
    const lightboxTitle = document.getElementById('lightbox-title');
    const lightboxDesc = document.getElementById('lightbox-desc');
    const closeBtn = document.getElementById('lightbox-close');
    const prevBtn = document.getElementById('lightbox-prev');
    const nextBtn = document.getElementById('lightbox-next');

    // Collect all media cards
    const mediaCards = Array.from(document.querySelectorAll('.media-card'));
    let currentIdx = 0;

    function openLightbox(index) {
        if (!lightbox || index < 0 || index >= mediaCards.length) return;
        currentIdx = index;
        const card = mediaCards[currentIdx];
        const mediaType = card.getAttribute('data-media-type') || 'image';
        const src = card.getAttribute('data-src');
        const title = card.getAttribute('data-title') || '';
        const desc = card.getAttribute('data-desc') || '';

        // Clear existing media
        lightboxBox.innerHTML = '';

        if (mediaType === 'video') {
            const video = document.createElement('video');
            video.src = src;
            video.controls = true;
            video.autoplay = true;
            video.playsInline = true;
            video.className = 'lightbox-video';
            lightboxBox.appendChild(video);
        } else {
            const img = document.createElement('img');
            img.src = src;
            img.alt = title;
            img.className = 'lightbox-img';
            lightboxBox.appendChild(img);
        }

        if (lightboxCounter) {
            lightboxCounter.textContent = `Media ${currentIdx + 1} of ${mediaCards.length}`;
        }
        if (lightboxTitle) lightboxTitle.textContent = title;
        if (lightboxDesc) lightboxDesc.textContent = desc;

        lightbox.classList.add('active');
        lightbox.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeLightbox() {
        if (!lightbox) return;
        // Pause any running video
        const video = lightboxBox.querySelector('video');
        if (video) video.pause();

        lightbox.classList.remove('active');
        lightbox.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    function showNext() {
        const next = (currentIdx + 1) % mediaCards.length;
        openLightbox(next);
    }

    function showPrev() {
        const prev = (currentIdx - 1 + mediaCards.length) % mediaCards.length;
        openLightbox(prev);
    }

    // Attach click handlers to media cards
    mediaCards.forEach((card, idx) => {
        // If card contains a video player with controls, avoid hijacking the play button directly
        const videoEl = card.querySelector('video');
        if (videoEl) {
            // Let the video controls work natively on the card, but card banner can open lightbox
            const infoBar = card.querySelector('.media-info-bar');
            if (infoBar) {
                infoBar.addEventListener('click', () => openLightbox(idx));
            }
        } else {
            card.addEventListener('click', () => openLightbox(idx));
        }
    });

    if (closeBtn) closeBtn.addEventListener('click', closeLightbox);
    if (nextBtn) nextBtn.addEventListener('click', showNext);
    if (prevBtn) prevBtn.addEventListener('click', showPrev);

    // Click outside to close
    if (lightbox) {
        lightbox.addEventListener('click', (e) => {
            if (e.target === lightbox || e.target.classList.contains('lightbox-stage')) {
                closeLightbox();
            }
        });
    }

    // Keyboard support
    window.addEventListener('keydown', (e) => {
        if (!lightbox || !lightbox.classList.contains('active')) return;
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowRight') showNext();
        if (e.key === 'ArrowLeft') showPrev();
    });

    // Touch Swipe Support for Mobile
    let touchStartX = 0;
    let touchEndX = 0;

    if (lightbox) {
        lightbox.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });

        lightbox.addEventListener('touchend', (e) => {
            touchEndX = e.changedTouches[0].screenX;
            handleSwipe();
        }, { passive: true });
    }

    function handleSwipe() {
        const swipeThreshold = 50;
        if (touchEndX < touchStartX - swipeThreshold) {
            // Swiped Left -> Next
            showNext();
        } else if (touchEndX > touchStartX + swipeThreshold) {
            // Swiped Right -> Prev
            showPrev();
        }
    }

    // Run on ready
    window.addEventListener('DOMContentLoaded', handleInitialHash);

})();
