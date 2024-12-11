// Configuration - these should match your .env values
const BUCKET_NAME = 'radio-files';
const VULTR_HOSTNAME = 'sjc1.vultrobjects.com'; // Update this to match your config

const ITEMS_PER_PAGE = 10;
let currentPage = 1;

async function fetchArchiveFiles() {
    try {
        // Try to get cached metadata first
        const cache = await caches.open('episodes-cache');
        const cachedResponse = await cache.match('episodes-metadata');
        
        if (cachedResponse) {
            const cachedData = await cachedResponse.json();
            const cacheAge = Date.now() - cachedData.timestamp;
            
            // Use cache if it's less than 5 minutes old and has valid data
            if (cacheAge < 300000 && Array.isArray(cachedData.episodes) && cachedData.episodes.length > 0) {
                // Validate cached data structure
                if (cachedData.episodes[0].key && cachedData.episodes[0].lastModified) {
                    displayEpisodes(cachedData.episodes);
                    return;
                }
            }
        }

        // Get the container element
        const episodesContainer = document.getElementById('episodes-container');
        if (!episodesContainer) {
            console.error('Episodes container element not found');
            return;
        }

        // Show loader
        episodesContainer.innerHTML = `
            <div class="col-12 d-flex justify-content-center align-items-center" style="min-height: 200px;">
                <span class="loader"></span>
            </div>
        `;

        // Fetch the files from the bucket
        const response = await fetch(`https://${BUCKET_NAME}.${VULTR_HOSTNAME}/`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Parse the XML response
        const data = await response.text();
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(data, 'text/xml');
        
        // Convert XML to JSON structure
        const contents = Array.from(xmlDoc.getElementsByTagName('Contents')).map(content => ({
            key: content.getElementsByTagName('Key')[0].textContent,
            lastModified: content.getElementsByTagName('LastModified')[0].textContent
        }));

        // Sort and filter the contents
        const sortedContents = contents
            .filter(item => item.key.startsWith('archive/') && item.key.endsWith('.mp3'))
            .sort((a, b) => new Date(b.lastModified) - new Date(a.lastModified));

        // Clear loader
        episodesContainer.innerHTML = '';

        // Display initial batch
        const totalItems = sortedContents.length;
        const start = 0;
        const end = Math.min(ITEMS_PER_PAGE, totalItems);
        displayEpisodes(sortedContents.slice(start, end));

        // Add "Load More" button if needed
        if (totalItems > ITEMS_PER_PAGE) {
            episodesContainer.insertAdjacentHTML('beforeend', `
                <div class="col-12 text-center mt-4">
                    <button class="btn btn-outline-primary" id="loadMoreBtn">
                        Load More Episodes
                    </button>
                </div>
            `);
            
            document.getElementById('loadMoreBtn').addEventListener('click', () => {
                currentPage++;
                const newStart = (currentPage - 1) * ITEMS_PER_PAGE;
                const newEnd = Math.min(newStart + ITEMS_PER_PAGE, totalItems);
                displayEpisodes(sortedContents.slice(newStart, newEnd));
                
                if (newEnd >= totalItems) {
                    document.getElementById('loadMoreBtn').remove();
                }
            });
        }

        // Cache the new data
        const episodesData = {
            timestamp: Date.now(),
            episodes: sortedContents.map(item => ({
                key: item.key,
                lastModified: item.lastModified
            }))
        };
        await cache.put('episodes-metadata', new Response(JSON.stringify(episodesData)));

    } catch (error) {
        console.error('Failed to fetch archive files:', error);
        showError('Failed to load episodes. Please try again later.');
    }
}

function displayEpisodes(episodes) {
    const fragment = document.createDocumentFragment();
    
    episodes.forEach(item => {
        // Validate item has required properties
        if (!item || !item.key || !item.lastModified) {
            console.warn('Invalid episode data:', item);
            return;
        }

        // Only process MP3 files from the archive folder
        const fileUrl = `https://${BUCKET_NAME}.${VULTR_HOSTNAME}/${item.key}`;
        
        // Format the date
        const date = new Date(item.lastModified);
        const formattedDate = date.toLocaleDateString('en-AU', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });

        // Format the title (remove 'archive/' and '.mp3')
        const title = item.key.replace('archive/', '').replace('.mp3', '');
        
        // Create card element
        const cardCol = document.createElement('div');
        cardCol.className = 'col-12 mb-4 d-flex justify-content-center';
        
        // Set the card content
        cardCol.innerHTML = `
            <div class="card" style="border: 0px; width: 100%;">
                <div class="card-body d-flex flex-column" style="border-radius: 35px; border: 3px solid var(--bs-primary);">
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <h4 class="card-title mb-0" style="font-family: 'Helvetica Now Display'; font-weight: 900;">
                            ${title}
                        </h4>
                        <span class="text-muted" style="font-family: 'Helvetica Now Display';">
                            ${formattedDate}
                        </span>
                    </div>
                    <div class="audio-container loading">
                        <audio controls preload="metadata">
                            <source src="${fileUrl}" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                    </div>
                </div>
            </div>
        `;
        
        const audioElement = cardCol.querySelector('audio');
        const container = cardCol.querySelector('.audio-container');

        // Add buffer management
        audioElement.addEventListener('play', () => {
            audioElement.preload = 'auto';
        }, { once: true });

        audioElement.addEventListener('pause', () => {
            if (audioElement.duration - audioElement.currentTime > 10) {
                audioElement.preload = 'metadata';
            }
        });

        // Remove initial loading class
        container.classList.remove('loading');

        // Only show loading spinner when actually buffering
        audioElement.addEventListener('waiting', () => {
            container.classList.add('loading');
        });

        audioElement.addEventListener('playing', () => {
            container.classList.remove('loading');
        });

        audioElement.addEventListener('canplay', () => {
            container.classList.remove('loading');
        });

        // Also remove loading state when paused
        audioElement.addEventListener('pause', () => {
            container.classList.remove('loading');
        });

        // Handle seeking
        audioElement.addEventListener('seeking', () => {
            container.classList.add('loading');
        });

        audioElement.addEventListener('seeked', () => {
            container.classList.remove('loading');
        });

        fragment.appendChild(cardCol);
    });
    
    document.getElementById('episodes-container').appendChild(fragment);
}

function showError(message) {
    const episodesContainer = document.getElementById('episodes-container');
    if (episodesContainer) {
        episodesContainer.innerHTML = `
            <div class="col-12">
                <div class="alert alert-danger" role="alert">
                    <h4 class="alert-heading">Error Loading Episodes</h4>
                    <p>${message}</p>
                    <hr>
                    <button class="btn btn-outline-danger" onclick="location.reload()">
                        Retry
                    </button>
                </div>
            </div>
        `;
    }
}

// Call the function when the page loads
document.addEventListener('DOMContentLoaded', () => {
    fetchArchiveFiles();  // This will handle the episode listings
    setupModalAudio();    // This will handle the modal audio setup
});

// Add fallback for browsers without audio support
function createFallbackPlayer(audioUrl, title) {
    return `
        <div class="fallback-player">
            <p>Your browser doesn't support HTML5 audio. Here are alternative ways to listen:</p>
            <ul>
                <li><a href="${audioUrl}" download>Download the episode</a></li>
                <li><a href="${audioUrl}" target="_blank">Open in new tab</a></li>
            </ul>
        </div>
    `;
}

function createAudioElement(fileUrl, title) {
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.preload = 'metadata';  // Only load metadata initially
    
    // Set a small buffer size (in seconds)
    const BUFFER_SIZE = 10;
    
    audio.addEventListener('loadedmetadata', () => {
        // Set initial playback buffer
        if ('mediaSession' in navigator) {
            // Modern browsers: use Media Session API
            navigator.mediaSession.setPositionState({
                duration: audio.duration,
                playbackRate: audio.playbackRate,
                position: audio.currentTime
            });
        }
    });

    // Manage buffering based on play state
    audio.addEventListener('play', () => {
        audio.preload = 'auto';  // Allow full preload when playing
    });

    audio.addEventListener('pause', () => {
        // If we're not near the end, limit preload
        if (audio.duration - audio.currentTime > BUFFER_SIZE) {
            audio.preload = 'metadata';
        }
    });

    // Cleanup when audio is removed from DOM
    audio.addEventListener('remove', () => {
        audio.src = '';
        audio.load();
    });
    
    return audio;
}

function attachAudioEvents(audio) {
    const container = audio.closest('.audio-container');
    
    const events = ['waiting', 'playing', 'canplay', 'pause', 'seeking', 'seeked'];
    events.forEach(event => {
        audio.addEventListener(event, () => {
            container.classList.toggle('loading', ['waiting', 'seeking'].includes(event));
        });
    });
}

function cleanupAudioElements() {
    const audioElements = document.querySelectorAll('audio');
    const viewportHeight = window.innerHeight;
    const buffer = viewportHeight * 2; // Keep loaded 2 viewport heights away

    audioElements.forEach(audio => {
        const rect = audio.getBoundingClientRect();
        const isFarFromViewport = rect.top < -buffer || rect.bottom > viewportHeight + buffer;
        
        if (audio.paused && isFarFromViewport) {
            audio.src = '';
            audio.load();
        } else if (!isFarFromViewport && !audio.src && audio.querySelector('source')) {
            // Reload the source if it was unloaded but now near viewport
            audio.src = audio.querySelector('source').src;
            audio.load();
        }
    });
}

// Reduce cleanup frequency
let scrollTimeout;
window.addEventListener('scroll', () => {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(cleanupAudioElements, 2000); // Increased to 2 seconds
});

// Add this function to handle the modal audio
function setupModalAudio() {
    const modal = document.getElementById('modal-1');
    const modalAudio = modal.querySelector('audio');
    const modalContainer = modal.querySelector('.audio-container');
    const BUFFER_SIZE = 10;

    modal.addEventListener('show.bs.modal', async () => {
        try {
            const response = await fetch(`https://${BUCKET_NAME}.${VULTR_HOSTNAME}/`);
            const data = await response.text();
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(data, 'text/xml');
            
            const contents = Array.from(xmlDoc.getElementsByTagName('Contents'))
                .filter(item => {
                    const key = item.getElementsByTagName('Key')[0].textContent;
                    return key.startsWith('archive/') && key.endsWith('.mp3');
                })
                .sort((a, b) => {
                    const dateA = new Date(a.getElementsByTagName('LastModified')[0].textContent);
                    const dateB = new Date(b.getElementsByTagName('LastModified')[0].textContent);
                    return dateB - dateA;
                });

            if (contents.length > 0) {
                const latestKey = contents[0].getElementsByTagName('Key')[0].textContent;
                const fileUrl = `https://${BUCKET_NAME}.${VULTR_HOSTNAME}/${latestKey}`;
                
                // Update the audio source
                const source = modalAudio.querySelector('source');
                if (source.src !== fileUrl) {
                    source.src = fileUrl;
                    modalAudio.load();
                }
                
                // Keep metadata loaded but don't buffer
                modalAudio.preload = 'metadata';
                
                // Update the aria label with the title
                const title = latestKey.replace('archive/', '').replace('.mp3', '');
                modalAudio.setAttribute('aria-label', `Audio player for ${title}`);
            }
        } catch (error) {
            console.error('Error loading latest episode:', error);
        }
    });

    // Clean up when modal closes but keep source
    modal.addEventListener('hidden.bs.modal', () => {
        modalAudio.pause();
        modalAudio.currentTime = 0;
        modalContainer.classList.remove('loading');
        // Don't clear the source or reload
    });

    // Buffer management
    modalAudio.addEventListener('play', () => {
        modalAudio.preload = 'auto';  // Allow buffering when playing
    });

    modalAudio.addEventListener('pause', () => {
        modalAudio.preload = 'metadata';  // Stop buffering when paused
    });

    // Loading state handlers
    modalAudio.addEventListener('waiting', () => {
        modalContainer.classList.add('loading');
    });

    modalAudio.addEventListener('playing', () => {
        modalContainer.classList.remove('loading');
    });

    modalAudio.addEventListener('canplay', () => {
        modalContainer.classList.remove('loading');
    });
}
